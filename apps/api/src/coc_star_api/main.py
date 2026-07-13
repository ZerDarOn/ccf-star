import logging
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from coc_star_api.room_manager import BoardToken, RoomConnection, RoomManager, RoomMember
from coc_star_api.board_repository import BoardTokenRepository
from coc_star_api.database import engine, initialize_database, session_factory
from coc_star_api.session_auth import InvalidSessionToken, SessionClaims, SessionTokenService
from coc_star_api.settings import settings

app = FastAPI(title="coc-star API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
room_manager = RoomManager()
board_repository = BoardTokenRepository()
logger = logging.getLogger("coc-star.room")
session_tokens = SessionTokenService(settings.session_secret)


class ChatMessage(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)


class BoardTokenInput(BaseModel):
    token_id: str | None = Field(default=None, min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=40)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class RoomMemberRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)


@app.on_event("startup")
async def startup() -> None:
    await initialize_database()
    room_manager.create_room("demo-room")
    logger.info("database_initialized")


@app.on_event("shutdown")
async def shutdown() -> None:
    await engine.dispose()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "coc-star-api"}


@app.post("/api/rooms")
async def create_room(request: RoomMemberRequest) -> dict[str, object]:
    room_id = f"room-{uuid4().hex[:8]}"
    member = SessionClaims(str(uuid4()), room_id, request.display_name, "gm")
    room_manager.create_room(room_id)
    logger.info("room_created room_id=%s user_id=%s", room_id, member.user_id)
    return {"room_id": room_id, "access_token": session_tokens.issue(member), "member": member_payload(member)}


@app.post("/api/rooms/{room_id}/join")
async def join_room(room_id: str, request: RoomMemberRequest) -> dict[str, object]:
    if not room_manager.has_room(room_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room_not_found")
    member = SessionClaims(str(uuid4()), room_id, request.display_name, "player")
    logger.info("room_join_token_issued room_id=%s user_id=%s", room_id, member.user_id)
    return {"room_id": room_id, "access_token": session_tokens.issue(member), "member": member_payload(member)}


@app.websocket("/ws/rooms/{room_id}")
async def room_socket(websocket: WebSocket, room_id: str) -> None:
    await websocket.accept()
    try:
        auth_payload = await websocket.receive_json()
        access_token = auth_payload.get("access_token") if isinstance(auth_payload, dict) else None
        if not isinstance(auth_payload, dict) or auth_payload.get("type") != "auth":
            raise InvalidSessionToken("missing auth event")
        claims = session_tokens.verify(access_token if isinstance(access_token, str) else "")
    except InvalidSessionToken:
        logger.info("room_connection_rejected room_id=%s reason=invalid_session", room_id)
        await websocket.close(code=1008)
        return
    except WebSocketDisconnect:
        logger.info("room_connection_closed_before_auth room_id=%s", room_id)
        return
    if claims.room_id != room_id:
        logger.info("room_connection_rejected room_id=%s user_id=%s reason=room_mismatch", room_id, claims.user_id)
        await websocket.close(code=1008)
        return
    user_id = claims.user_id
    member = RoomMember(user_id=user_id, display_name=claims.display_name, role=claims.role)
    connection = RoomConnection(member=member, websocket=websocket)

    logger.info("room_connection_opened room_id=%s user_id=%s", room_id, user_id)
    if not room_manager.board_tokens(room_id):
        async with session_factory() as session:
            for token in await board_repository.list_by_room(session, room_id):
                room_manager.upsert_token(room_id, token)
    members = await room_manager.join(room_id, connection)
    await websocket.send_json(
        {
            "type": "room.connected",
            "room_id": room_id,
            "self": member.to_payload(),
            "members": [room_member.to_payload() for room_member in members],
            "board": {"tokens": [token.to_payload() for token in room_manager.board_tokens(room_id)]},
        }
    )

    try:
        while True:
            payload = await websocket.receive_json()
            if not isinstance(payload, dict):
                await websocket.send_json({"type": "error", "code": "invalid_event"})
                continue
            if payload.get("type") == "board.token.upsert":
                await handle_token_upsert(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "board.token.remove":
                await handle_token_remove(websocket, room_id, member, payload)
                continue
            if payload.get("type") != "chat.message":
                await websocket.send_json({"type": "error", "code": "unsupported_event"})
                continue
            try:
                message = ChatMessage.model_validate(payload)
            except ValidationError:
                await websocket.send_json({"type": "error", "code": "invalid_chat_message"})
                logger.info("chat_message_rejected room_id=%s user_id=%s", room_id, user_id)
                continue
            await room_manager.broadcast(
                room_id,
                {
                    "type": "chat.message",
                    "message": {
                        "message_id": str(uuid4()),
                        "user_id": member.user_id,
                        "display_name": member.display_name,
                        "text": message.text,
                    },
                },
            )
            logger.info("chat_message_broadcast room_id=%s user_id=%s", room_id, user_id)
    except WebSocketDisconnect:
        logger.info("room_connection_closed room_id=%s user_id=%s", room_id, user_id)
    except Exception:
        logger.exception("room_connection_failed room_id=%s user_id=%s", room_id, user_id)
    finally:
        await room_manager.leave(room_id, user_id)


def member_payload(member: SessionClaims) -> dict[str, str]:
    return {
        "user_id": member.user_id,
        "display_name": member.display_name,
        "role": member.role,
    }


async def handle_token_upsert(
    websocket: WebSocket,
    room_id: str,
    member: RoomMember,
    payload: dict[str, object],
) -> None:
    try:
        token_input = BoardTokenInput.model_validate(payload)
    except ValidationError:
        await websocket.send_json({"type": "error", "code": "invalid_board_token"})
        return

    token_id = token_input.token_id or str(uuid4())
    current_token = room_manager.get_token(room_id, token_id)
    if current_token is not None and current_token.owner_user_id != member.user_id and member.role != "gm":
        await websocket.send_json({"type": "error", "code": "board_token_forbidden"})
        return
    token = BoardToken(
        token_id=token_id,
        owner_user_id=current_token.owner_user_id if current_token else member.user_id,
        name=token_input.name,
        x=token_input.x,
        y=token_input.y,
        color=token_input.color,
    )
    try:
        async with session_factory() as session:
            await board_repository.upsert(session, room_id, token)
    except SQLAlchemyError:
        await websocket.send_json({"type": "error", "code": "board_persistence_failed"})
        logger.exception("board_token_persistence_failed room_id=%s token_id=%s", room_id, token_id)
        return
    room_manager.upsert_token(room_id, token)
    await room_manager.broadcast(room_id, {"type": "board.token.upserted", "token": token.to_payload()})
    logger.info("board_token_upserted room_id=%s token_id=%s user_id=%s", room_id, token_id, member.user_id)


async def handle_token_remove(
    websocket: WebSocket,
    room_id: str,
    member: RoomMember,
    payload: dict[str, object],
) -> None:
    token_id = payload.get("token_id")
    if not isinstance(token_id, str):
        await websocket.send_json({"type": "error", "code": "invalid_board_token"})
        return
    token = room_manager.get_token(room_id, token_id)
    if token is None:
        return
    if token.owner_user_id != member.user_id and member.role != "gm":
        await websocket.send_json({"type": "error", "code": "board_token_forbidden"})
        return
    try:
        async with session_factory() as session:
            await board_repository.delete(session, room_id, token_id)
    except SQLAlchemyError:
        await websocket.send_json({"type": "error", "code": "board_persistence_failed"})
        logger.exception("board_token_persistence_failed room_id=%s token_id=%s", room_id, token_id)
        return
    room_manager.remove_token(room_id, token_id)
    await room_manager.broadcast(room_id, {"type": "board.token.removed", "token_id": token_id})
    logger.info("board_token_removed room_id=%s token_id=%s user_id=%s", room_id, token_id, member.user_id)
