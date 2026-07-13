import logging
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from coc_star_api.room_manager import BoardToken, RoomConnection, RoomManager, RoomMember
from coc_star_api.board_repository import BoardTokenRepository
from coc_star_api.account_auth import AccountClaims, AccountTokenService, InvalidAccountToken
from coc_star_api.database import engine, initialize_database, session_factory
from coc_star_api.room_repository import RoomRepository
from coc_star_api.user_repository import UserRepository
from coc_star_api.passwords import PasswordHasher
from coc_star_api.session_auth import InvalidSessionToken, SessionClaims, SessionTokenService
from coc_star_api.settings import settings

app = FastAPI(title="coc-star API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
room_manager = RoomManager()
board_repository = BoardTokenRepository()
room_repository = RoomRepository()
user_repository = UserRepository()
logger = logging.getLogger("coc-star.room")
session_tokens = SessionTokenService(settings.session_secret)
account_tokens = AccountTokenService(settings.session_secret)
password_hasher = PasswordHasher()


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
    room_name: str = Field(default="", max_length=120)


class MemberRoleRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    role: Literal["gm", "player"]


class AccountCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[\w\-\u4e00-\u9fff]+$")
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


@app.on_event("startup")
async def startup() -> None:
    await initialize_database()
    async with session_factory() as session:
        if not await room_repository.exists(session, "demo-room"):
            await room_repository.create_room(session, "demo-room", "演示房间")
        for room_id in await room_repository.list_room_ids(session):
            room_manager.create_room(room_id)
    logger.info("database_initialized")


@app.on_event("shutdown")
async def shutdown() -> None:
    await engine.dispose()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "coc-star-api"}


@app.post("/api/auth/register", status_code=201)
async def register_account(request: AccountCredentials) -> dict[str, object]:
    username = request.username.strip().casefold()
    try:
        async with session_factory() as session:
            if await user_repository.get_by_username(session, username) is not None:
                raise HTTPException(status_code=409, detail="username_taken")
            user = await user_repository.create(session, str(uuid4()), username, password_hasher.hash(request.password))
    except SQLAlchemyError:
        logger.exception("account_registration_failed username=%s", username)
        raise HTTPException(status_code=503, detail="account_persistence_failed") from None
    claims = AccountClaims(user.user_id, user.username, "access")
    logger.info("account_registered user_id=%s", user.user_id)
    return {"user": {"user_id": user.user_id, "username": user.username}, **account_tokens.issue_pair(claims)}


@app.post("/api/auth/login")
async def login_account(request: AccountCredentials) -> dict[str, object]:
    username = request.username.strip().casefold()
    async with session_factory() as session:
        user = await user_repository.get_by_username(session, username)
    if user is None or not password_hasher.verify(request.password, user.password_hash):
        logger.info("account_login_rejected username=%s", username)
        raise HTTPException(status_code=401, detail="invalid_credentials")
    claims = AccountClaims(user.user_id, user.username, "access")
    logger.info("account_login_succeeded user_id=%s", user.user_id)
    return {"user": {"user_id": user.user_id, "username": user.username}, **account_tokens.issue_pair(claims)}


@app.post("/api/auth/refresh")
async def refresh_account(request: RefreshRequest) -> dict[str, str]:
    try:
        claims = account_tokens.verify(request.refresh_token, "refresh")
    except InvalidAccountToken:
        raise HTTPException(status_code=401, detail="invalid_refresh_token") from None
    return account_tokens.issue_pair(AccountClaims(claims.user_id, claims.username, "access"))


@app.post("/api/rooms")
async def create_room(request: RoomMemberRequest, authorization: str | None = Header(default=None)) -> dict[str, object]:
    account = require_account(authorization)
    room_id = f"room-{uuid4().hex[:8]}"
    member = SessionClaims(account.user_id, room_id, request.display_name, "gm")
    room_name = request.room_name.strip() or f"{request.display_name}的房间"
    try:
        async with session_factory() as session:
            await room_repository.create_room_with_owner(session, room_id, room_name, member.user_id, member.display_name)
    except SQLAlchemyError:
        logger.exception("room_creation_failed room_id=%s", room_id)
        raise HTTPException(status_code=503, detail="room_persistence_failed") from None
    room_manager.create_room(room_id)
    logger.info("room_created room_id=%s user_id=%s", room_id, member.user_id)
    return {"room_id": room_id, "access_token": session_tokens.issue(member), "member": member_payload(member)}


@app.post("/api/rooms/{room_id}/join")
async def join_room(room_id: str, request: RoomMemberRequest, authorization: str | None = Header(default=None)) -> dict[str, object]:
    account = require_account(authorization)
    try:
        async with session_factory() as session:
            if not await room_repository.exists(session, room_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room_not_found")
            member = SessionClaims(account.user_id, room_id, request.display_name, "player")
            await room_repository.add_member(session, room_id, member.user_id, member.display_name, member.role)
    except SQLAlchemyError:
        logger.exception("room_join_persistence_failed room_id=%s", room_id)
        raise HTTPException(status_code=503, detail="room_persistence_failed") from None
    if not room_manager.has_room(room_id):
        room_manager.create_room(room_id)
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
    async with session_factory() as session:
        persisted_member = await room_repository.get_member(session, room_id, user_id)
    if persisted_member is None:
        logger.info("room_connection_rejected room_id=%s user_id=%s reason=member_not_found", room_id, user_id)
        await websocket.close(code=1008)
        return
    member = RoomMember(user_id=user_id, display_name=persisted_member.display_name, role=persisted_member.role)
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
            if payload.get("type") == "room.member.role.update":
                await handle_member_role_update(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "room.member.remove":
                await handle_member_remove(websocket, room_id, member, payload)
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


def require_account(authorization: str | None) -> AccountClaims:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="account_auth_required")
    try:
        return account_tokens.verify(authorization[7:], "access")
    except InvalidAccountToken:
        raise HTTPException(status_code=401, detail="invalid_account_token") from None


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


async def handle_member_role_update(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    if actor.role != "gm":
        await websocket.send_json({"type": "error", "code": "member_management_forbidden"})
        return
    try:
        request = MemberRoleRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json({"type": "error", "code": "invalid_member_role"})
        return
    if request.user_id == actor.user_id:
        await websocket.send_json({"type": "error", "code": "cannot_change_own_role"})
        return
    target = room_manager.connection(room_id, request.user_id)
    if target is None:
        await websocket.send_json({"type": "error", "code": "member_not_online"})
        return
    try:
        async with session_factory() as session:
            if not await room_repository.update_member_role(session, room_id, request.user_id, request.role):
                await websocket.send_json({"type": "error", "code": "member_not_found"})
                return
    except SQLAlchemyError:
        logger.exception("member_role_update_failed room_id=%s user_id=%s", room_id, request.user_id)
        await websocket.send_json({"type": "error", "code": "member_persistence_failed"})
        return
    updated_member = room_manager.update_member_role(room_id, request.user_id, request.role)
    if updated_member is None:
        return
    await room_manager.broadcast(room_id, {"type": "member.role.updated", "member": updated_member.to_payload()})
    logger.info("member_role_updated room_id=%s user_id=%s role=%s", room_id, request.user_id, request.role)


async def handle_member_remove(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    if actor.role != "gm":
        await websocket.send_json({"type": "error", "code": "member_management_forbidden"})
        return
    user_id = payload.get("user_id")
    if not isinstance(user_id, str) or not user_id:
        await websocket.send_json({"type": "error", "code": "invalid_member"})
        return
    if user_id == actor.user_id:
        await websocket.send_json({"type": "error", "code": "cannot_remove_self"})
        return
    target = room_manager.connection(room_id, user_id)
    if target is None:
        await websocket.send_json({"type": "error", "code": "member_not_online"})
        return
    try:
        async with session_factory() as session:
            if not await room_repository.remove_member(session, room_id, user_id):
                await websocket.send_json({"type": "error", "code": "member_not_found"})
                return
    except SQLAlchemyError:
        logger.exception("member_remove_failed room_id=%s user_id=%s", room_id, user_id)
        await websocket.send_json({"type": "error", "code": "member_persistence_failed"})
        return
    room_manager.detach(room_id, user_id)
    await target.websocket.send_json({"type": "member.removed", "user_id": user_id})
    await target.websocket.close(code=1008)
    await room_manager.broadcast(room_id, {"type": "member.removed", "user_id": user_id})
    logger.info("member_removed room_id=%s user_id=%s actor_user_id=%s", room_id, user_id, actor.user_id)
