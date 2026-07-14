import logging
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from coc_star_api.room_manager import BoardToken, RoomConnection, RoomManager, RoomMember, RoomScene
from coc_star_api.board_repository import BoardTokenRepository
from coc_star_api.account_auth import AccountClaims, AccountTokenService, InvalidAccountToken
from coc_star_api.database import engine, initialize_database, session_factory
from coc_star_api.dice_roller import InvalidDiceExpression, roll_dice
from coc_star_api.face_matcher import match_face
from coc_star_api.room_repository import RoomRepository
from coc_star_api.scene_repository import SceneRepository
from coc_star_api.scene_layer import SceneLayer
from coc_star_api.scene_layer_repository import SceneLayerRepository
from coc_star_api.token_presentation import TokenFace, TokenPresentation
from coc_star_api.token_presentation_repository import TokenPresentationRepository
from coc_star_api.room_bgm import BgmPlayback, RoomBgm
from coc_star_api.room_bgm_repository import RoomBgmRepository
from coc_star_api.room_chat import RoomChatTab
from coc_star_api.room_chat_repository import RoomChatTabRepository
from coc_star_api.user_repository import UserRepository
from coc_star_api.passwords import PasswordHasher
from coc_star_api.session_auth import InvalidSessionToken, SessionClaims, SessionTokenService
from coc_star_api.settings import settings

app = FastAPI(title="coc-star API", version="0.1.0")
asset_root = Path("uploads")
asset_root.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=asset_root), name="uploads")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https://[a-z0-9-]+\.trycloudflare\.com",
    allow_credentials=False,
    allow_methods=["DELETE", "GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
room_manager = RoomManager()
board_repository = BoardTokenRepository()
room_repository = RoomRepository()
scene_repository = SceneRepository()
scene_layer_repository = SceneLayerRepository()
token_presentation_repository = TokenPresentationRepository()
room_bgm_repository = RoomBgmRepository()
room_chat_tab_repository = RoomChatTabRepository()
user_repository = UserRepository()
logger = logging.getLogger("coc-star.room")
session_tokens = SessionTokenService(settings.session_secret)
account_tokens = AccountTokenService(settings.session_secret)
password_hasher = PasswordHasher()


class ChatMessage(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)
    token_id: str | None = Field(default=None, max_length=64)
    tab_id: str | None = Field(default=None, max_length=128)
    character_name: str | None = Field(default=None, max_length=40)
    character_color: str = Field(default="#d7b56d", pattern=r"^#[0-9a-fA-F]{6}$")


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


class SceneRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    background_url: str = Field(default="", max_length=2_048, pattern=r"^$|^https?://")


class SceneActivationRequest(BaseModel):
    scene_id: str = Field(min_length=1, max_length=128)


class TokenPresentationRequest(BaseModel):
    token_id: str = Field(min_length=1, max_length=64)
    token_type: Literal["npc", "character"] = "npc"
    image_url: str | None = Field(default=None, max_length=2_048)
    scale: float = Field(default=1.0, ge=0.25, le=4.0)
    active_face_id: str | None = Field(default=None, max_length=64)


class TokenFaceRequest(BaseModel):
    token_id: str = Field(min_length=1, max_length=64)
    face_id: str | None = Field(default=None, max_length=64)
    label: str = Field(min_length=1, max_length=80)
    trigger: str | None = Field(default=None, max_length=80)
    image_url: str = Field(min_length=1, max_length=2_048)


class SceneLayerRequest(BaseModel):
    layer_id: str | None = Field(default=None, max_length=128)
    scene_id: str = Field(min_length=1, max_length=128)
    layer_type: Literal["background", "foreground", "panel", "marker"]
    name: str = Field(min_length=1, max_length=120)
    image_url: str | None = Field(default=None, max_length=2_048)
    text: str = Field(default="", max_length=500)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=2)
    height: float = Field(gt=0, le=2)
    z_index: int = Field(ge=-100, le=100)
    visible: bool = True


class BgmTrackRequest(BaseModel):
    bgm_id: str | None = Field(default=None, max_length=128)
    slot: Literal["bgm01", "bgm02"]
    name: str = Field(min_length=1, max_length=120)
    audio_url: str = Field(min_length=1, max_length=2_048)
    loop: bool = True


class BgmControlRequest(BaseModel):
    slot: Literal["bgm01", "bgm02"]
    action: Literal["play", "pause", "stop"]
    position: float = Field(default=0.0, ge=0)


class ChatTabRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    show_dialogue: bool = False


@app.on_event("startup")
async def startup() -> None:
    await initialize_database()
    async with session_factory() as session:
        if not await room_repository.exists(session, "demo-room"):
            await room_repository.create_room(session, "demo-room", "演示房间")
        for room_id in await room_repository.list_room_ids(session):
            room_manager.create_room(room_id)
            scenes = await scene_repository.list_by_room(session, room_id)
            if not scenes:
                await scene_repository.create(session, f"{room_id}-default", room_id, "默认场景", "")
                scenes = await scene_repository.list_by_room(session, room_id)
            active_scene = next((scene for scene in scenes if scene.is_active), scenes[0])
            room_manager.set_scenes(room_id, [scene_from_model(scene) for scene in scenes], active_scene.scene_id)
            layers = await scene_layer_repository.list_by_scenes(session, [scene.scene_id for scene in scenes])
            room_manager.set_scene_layers(layers)
            chat_tabs = await room_chat_tab_repository.ensure_defaults(session, room_id)
            room_manager.set_chat_tabs(room_id, chat_tabs)
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
            chat_tabs = await room_chat_tab_repository.ensure_defaults(session, room_id)
            default_scene = await scene_repository.create(session, f"{room_id}-default", room_id, "默认场景", "")
    except SQLAlchemyError:
        logger.exception("room_creation_failed room_id=%s", room_id)
        raise HTTPException(status_code=503, detail="room_persistence_failed") from None
    room_manager.create_room(room_id)
    room_manager.set_scenes(room_id, [scene_from_model(default_scene)], default_scene.scene_id)
    room_manager.set_chat_tabs(room_id, chat_tabs)
    logger.info("room_created room_id=%s user_id=%s", room_id, member.user_id)
    return {"room_id": room_id, "access_token": session_tokens.issue(member), "member": member_payload(member)}


@app.post("/api/rooms/{room_id}/join")
async def join_room(room_id: str, request: RoomMemberRequest, authorization: str | None = Header(default=None)) -> dict[str, object]:
    account = require_account(authorization)
    try:
        async with session_factory() as session:
            if not await room_repository.exists(session, room_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room_not_found")
            existing_member = await room_repository.get_member(session, room_id, account.user_id)
            member = SessionClaims(account.user_id, room_id, request.display_name, existing_member.role if existing_member else "player")
            await room_repository.add_member(session, room_id, member.user_id, member.display_name, member.role)
    except SQLAlchemyError:
        logger.exception("room_join_persistence_failed room_id=%s", room_id)
        raise HTTPException(status_code=503, detail="room_persistence_failed") from None
    if not room_manager.has_room(room_id):
        room_manager.create_room(room_id)
    logger.info("room_join_token_issued room_id=%s user_id=%s", room_id, member.user_id)
    return {"room_id": room_id, "access_token": session_tokens.issue(member), "member": member_payload(member)}


@app.get("/api/rooms")
async def list_my_rooms(authorization: str | None = Header(default=None)) -> dict[str, list[dict[str, object]]]:
    account = require_account(authorization)
    async with session_factory() as session:
        room_rows = await room_repository.list_for_user(session, account.user_id)
    rooms = [
        {
            "room_id": room.room_id,
            "name": room.name,
            "role": member.role,
            "is_owner": room.owner_user_id == account.user_id,
            "display_name": member.display_name,
            "created_at": room.created_at.isoformat() if room.created_at else None,
        }
        for room, member in room_rows
    ]
    logger.info("room_listed user_id=%s count=%s", account.user_id, len(rooms))
    return {"rooms": rooms}


@app.delete("/api/rooms/{room_id}")
async def remove_my_room(room_id: str, authorization: str | None = Header(default=None)) -> dict[str, str]:
    account = require_account(authorization)
    async with session_factory() as session:
        action = await room_repository.remove_for_user(session, room_id, account.user_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room_membership_not_found")
    if action == "deleted":
        room_manager.remove_room(room_id)
    logger.info("room_removed room_id=%s user_id=%s action=%s", room_id, account.user_id, action)
    return {"action": action, "room_id": room_id}


@app.post("/api/rooms/{room_id}/assets")
async def upload_room_asset(room_id: str, request: Request, authorization: str | None = Header(default=None)) -> dict[str, str]:
    account = require_account(authorization)
    async with session_factory() as session:
        if await room_repository.get_member(session, room_id, account.user_id) is None:
            raise HTTPException(status_code=403, detail="room_membership_required")
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    extensions = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "audio/mpeg": ".mp3",
        "audio/ogg": ".ogg",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mp4": ".m4a",
    }
    extension = extensions.get(content_type)
    if extension is None:
        raise HTTPException(status_code=415, detail="unsupported_asset_type")
    content = await request.body()
    max_size = 32 * 1024 * 1024 if content_type.startswith("audio/") else 8 * 1024 * 1024
    if not content or len(content) > max_size:
        raise HTTPException(status_code=413, detail="asset_too_large")
    filename = f"{uuid4().hex}{extension}"
    (asset_root / filename).write_bytes(content)
    logger.info("room_asset_uploaded room_id=%s user_id=%s filename=%s", room_id, account.user_id, filename)
    return {"url": f"/uploads/{filename}", "content_type": content_type}


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
            tokens = room_manager.board_tokens(room_id)
            token_ids = [token.token_id for token in tokens]
            presentations = await token_presentation_repository.list_presentations(session, token_ids)
            faces = await token_presentation_repository.list_faces(session, token_ids)
            room_manager.set_token_presentations(room_id, presentations, faces)
    async with session_factory() as session:
        bgm_tracks = await room_bgm_repository.list_by_room(session, room_id)
        chat_tabs = await room_chat_tab_repository.ensure_defaults(session, room_id)
    room_manager.set_chat_tabs(room_id, chat_tabs)
    members = await room_manager.join(room_id, connection)
    active_scene = room_manager.active_scene(room_id)
    await websocket.send_json(
        {
            "type": "room.connected",
            "room_id": room_id,
            "self": member.to_payload(),
            "members": [room_member.to_payload() for room_member in members],
            "board": {"tokens": [board_token_payload(room_id, token) for token in room_manager.board_tokens(room_id)]},
            "scenes": [scene.to_payload() for scene in room_manager.scenes(room_id)],
            "active_scene": active_scene.to_payload() if active_scene else None,
            "scene_layers": [layer.to_payload() for layer in room_manager.scene_layers(active_scene.scene_id)] if active_scene else [],
            "bgm_tracks": [track.to_payload() for track in bgm_tracks],
            "bgm_playback": [playback.to_payload() for playback in room_manager.bgm_playback(room_id)],
            "chat_tabs": [tab.to_payload() for tab in room_manager.chat_tabs(room_id)],
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
            if payload.get("type") == "board.token.presentation.update":
                await handle_token_presentation_update(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "board.token.face.upsert":
                await handle_token_face_upsert(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "board.token.face.remove":
                await handle_token_face_remove(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "room.member.role.update":
                await handle_member_role_update(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "room.member.remove":
                await handle_member_remove(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "scene.create":
                await handle_scene_create(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "scene.activate":
                await handle_scene_activate(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "scene.layer.upsert":
                await handle_scene_layer_upsert(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "scene.layer.remove":
                await handle_scene_layer_remove(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "bgm.track.upsert":
                await handle_bgm_track_upsert(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "bgm.track.remove":
                await handle_bgm_track_remove(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "bgm.control":
                await handle_bgm_control(websocket, room_id, member, payload)
                continue
            if payload.get("type") == "chat.tab.create":
                await handle_chat_tab_create(websocket, room_id, member, payload)
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
            chat_tab = room_manager.chat_tab(room_id, message.tab_id)
            dice_expression = parse_dice_command(message.text)
            if dice_expression is not None:
                try:
                    result = roll_dice(dice_expression)
                except InvalidDiceExpression:
                    await websocket.send_json({"type": "error", "code": "invalid_dice_expression"})
                    logger.info("dice_roll_rejected room_id=%s user_id=%s expression=%s", room_id, user_id, dice_expression)
                    continue
                await room_manager.broadcast(
                    room_id,
                    {
                        "type": "dice.result",
                        "result": {
                            "roll_id": str(uuid4()),
                            "user_id": member.user_id,
                            "display_name": member.display_name,
                            "tab_id": chat_tab.tab_id if chat_tab else None,
                            "expression": result.expression,
                            "rolls": list(result.rolls),
                            "modifier": result.modifier,
                            "total": result.total,
                        },
                    },
                )
                logger.info("dice_roll_broadcast room_id=%s user_id=%s expression=%s total=%s", room_id, user_id, result.expression, result.total)
                continue
            visible_text = message.text
            owned_token = next((token for token in room_manager.board_tokens(room_id) if token.owner_user_id == member.user_id and token.token_id == message.token_id), None)
            face_match = None
            if owned_token is not None:
                face_match = match_face(message.text, room_manager.faces(room_id, owned_token.token_id))
                visible_text = face_match.visible_text
                if face_match.face is not None:
                    current_presentation = room_manager.presentation(room_id, owned_token.token_id)
                    updated_presentation = TokenPresentation(
                        token_id=owned_token.token_id,
                        token_type="character" if current_presentation.image_url else "npc",
                        image_url=current_presentation.image_url,
                        scale=current_presentation.scale,
                        active_face_id=face_match.face.face_id,
                    )
                    async with session_factory() as session:
                        await token_presentation_repository.upsert_presentation(session, updated_presentation)
                    room_manager.upsert_presentation(room_id, updated_presentation)
                    await room_manager.broadcast(room_id, {"type": "board.token.presentation.updated", "presentation": updated_presentation.to_payload()})
            await room_manager.broadcast(
                room_id,
                {
                    "type": "chat.message",
                    "message": {
                        "message_id": str(uuid4()),
                        "user_id": member.user_id,
                        "display_name": member.display_name,
                        "character_name": (message.character_name or member.display_name).strip() or member.display_name,
                        "character_color": message.character_color,
                        "tab_id": chat_tab.tab_id if chat_tab else None,
                        "show_dialogue": chat_tab.show_dialogue if chat_tab else False,
                        "text": visible_text,
                        "token_id": owned_token.token_id if owned_token else None,
                        "face_id": face_match.face.face_id if face_match and face_match.face else None,
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


def board_token_payload(room_id: str, token: BoardToken) -> dict[str, object]:
    return {
        **token.to_payload(),
        "presentation": room_manager.presentation(room_id, token.token_id).to_payload(),
        "faces": [face.to_payload() for face in room_manager.faces(room_id, token.token_id)],
    }


def scene_from_model(scene: object) -> RoomScene:
    return RoomScene(
        scene_id=scene.scene_id,
        name=scene.name,
        background_url=scene.background_url,
        is_active=scene.is_active,
    )


def parse_dice_command(text: str) -> str | None:
    command, separator, expression = text.strip().partition(" ")
    if command.lower() not in {"/r", "/roll"}:
        return None
    return expression.strip() if separator else ""


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
    await room_manager.broadcast(room_id, {"type": "board.token.upserted", "token": board_token_payload(room_id, token)})
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


async def can_edit_token(room_id: str, actor: RoomMember, token_id: str) -> bool:
    token = room_manager.get_token(room_id, token_id)
    return token is not None and (actor.role == "gm" or token.owner_user_id == actor.user_id)


async def handle_token_presentation_update(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    try:
        request = TokenPresentationRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json({"type": "error", "code": "invalid_token_presentation"})
        return
    if not await can_edit_token(room_id, actor, request.token_id):
        await websocket.send_json({"type": "error", "code": "token_edit_forbidden"})
        return
    presentation = TokenPresentation(
        token_id=request.token_id,
        token_type=request.token_type if request.image_url else "npc",
        image_url=request.image_url,
        scale=request.scale,
        active_face_id=request.active_face_id,
    )
    try:
        async with session_factory() as session:
            await token_presentation_repository.upsert_presentation(session, presentation)
    except SQLAlchemyError:
        logger.exception("token_presentation_update_failed room_id=%s token_id=%s", room_id, request.token_id)
        await websocket.send_json({"type": "error", "code": "token_persistence_failed"})
        return
    room_manager.upsert_presentation(room_id, presentation)
    await room_manager.broadcast(room_id, {"type": "board.token.presentation.updated", "presentation": presentation.to_payload()})
    logger.info("token_presentation_updated room_id=%s token_id=%s user_id=%s", room_id, request.token_id, actor.user_id)


async def handle_token_face_upsert(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    try:
        request = TokenFaceRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json({"type": "error", "code": "invalid_token_face"})
        return
    if not await can_edit_token(room_id, actor, request.token_id):
        await websocket.send_json({"type": "error", "code": "token_edit_forbidden"})
        return
    label = request.label.strip()
    trigger = (request.trigger or label).strip()
    if not trigger:
        await websocket.send_json({"type": "error", "code": "invalid_token_face_trigger"})
        return
    face = TokenFace(request.face_id or str(uuid4()), request.token_id, label, request.image_url, trigger)
    try:
        async with session_factory() as session:
            await token_presentation_repository.upsert_face(session, face)
    except SQLAlchemyError:
        logger.exception("token_face_upsert_failed room_id=%s token_id=%s", room_id, request.token_id)
        await websocket.send_json({"type": "error", "code": "token_persistence_failed"})
        return
    room_manager.upsert_face(room_id, face)
    await room_manager.broadcast(room_id, {"type": "board.token.face.upserted", "face": face.to_payload()})
    logger.info("token_face_upserted room_id=%s token_id=%s face_id=%s user_id=%s", room_id, request.token_id, face.face_id, actor.user_id)


async def handle_token_face_remove(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    token_id = payload.get("token_id")
    face_id = payload.get("face_id")
    if not isinstance(token_id, str) or not isinstance(face_id, str) or not await can_edit_token(room_id, actor, token_id):
        await websocket.send_json({"type": "error", "code": "token_edit_forbidden"})
        return
    try:
        async with session_factory() as session:
            await token_presentation_repository.delete_face(session, token_id, face_id)
    except SQLAlchemyError:
        logger.exception("token_face_remove_failed room_id=%s token_id=%s", room_id, token_id)
        await websocket.send_json({"type": "error", "code": "token_persistence_failed"})
        return
    room_manager.remove_face(room_id, face_id)
    await room_manager.broadcast(room_id, {"type": "board.token.face.removed", "token_id": token_id, "face_id": face_id})
    logger.info("token_face_removed room_id=%s token_id=%s face_id=%s user_id=%s", room_id, token_id, face_id, actor.user_id)


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


async def handle_scene_create(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    if actor.role != "gm":
        await websocket.send_json({"type": "error", "code": "scene_management_forbidden"})
        return
    try:
        request = SceneRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json({"type": "error", "code": "invalid_scene"})
        return
    try:
        async with session_factory() as session:
            scene_model = await scene_repository.create(
                session,
                str(uuid4()),
                room_id,
                request.name.strip(),
                request.background_url,
            )
    except SQLAlchemyError:
        logger.exception("scene_creation_failed room_id=%s user_id=%s", room_id, actor.user_id)
        await websocket.send_json({"type": "error", "code": "scene_persistence_failed"})
        return
    scene = room_manager.activate_scene(room_id, scene_model.scene_id)
    if scene is None:
        scene = RoomScene(scene_model.scene_id, scene_model.name, scene_model.background_url, True)
        room_manager.upsert_scene(room_id, scene)
    await room_manager.broadcast(room_id, {"type": "scene.updated", "scene": scene.to_payload()})
    logger.info("scene_created room_id=%s user_id=%s scene_id=%s", room_id, actor.user_id, scene.scene_id)


async def handle_scene_activate(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    if actor.role != "gm":
        await websocket.send_json({"type": "error", "code": "scene_management_forbidden"})
        return
    try:
        request = SceneActivationRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json({"type": "error", "code": "invalid_scene"})
        return
    try:
        async with session_factory() as session:
            scene_model = await scene_repository.activate(session, room_id, request.scene_id)
    except SQLAlchemyError:
        logger.exception("scene_activation_failed room_id=%s user_id=%s scene_id=%s", room_id, actor.user_id, request.scene_id)
        await websocket.send_json({"type": "error", "code": "scene_persistence_failed"})
        return
    if scene_model is None:
        await websocket.send_json({"type": "error", "code": "scene_not_found"})
        return
    scene = room_manager.activate_scene(room_id, scene_model.scene_id)
    if scene is None:
        scene = scene_from_model(scene_model)
        room_manager.upsert_scene(room_id, scene)
    await room_manager.broadcast(room_id, {"type": "scene.activated", "scene": scene.to_payload(), "layers": [layer.to_payload() for layer in room_manager.scene_layers(scene.scene_id)]})
    logger.info("scene_activated room_id=%s user_id=%s scene_id=%s", room_id, actor.user_id, scene.scene_id)


async def handle_scene_layer_upsert(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    if actor.role != "gm":
        await websocket.send_json({"type": "error", "code": "scene_management_forbidden"})
        return
    try:
        request = SceneLayerRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json({"type": "error", "code": "invalid_scene_layer"})
        return
    if not any(scene.scene_id == request.scene_id for scene in room_manager.scenes(room_id)):
        await websocket.send_json({"type": "error", "code": "scene_not_found"})
        return
    if request.layer_type != "marker" and not request.image_url:
        await websocket.send_json({"type": "error", "code": "scene_layer_image_required"})
        return
    layer = SceneLayer(
        layer_id=request.layer_id or str(uuid4()),
        scene_id=request.scene_id,
        layer_type=request.layer_type,
        name=request.name.strip(),
        image_url=request.image_url,
        text=request.text.strip(),
        x=request.x,
        y=request.y,
        width=request.width,
        height=request.height,
        z_index=request.z_index,
        visible=request.visible,
    )
    try:
        async with session_factory() as session:
            await scene_layer_repository.upsert(session, layer)
    except SQLAlchemyError:
        logger.exception("scene_layer_upsert_failed room_id=%s layer_id=%s", room_id, layer.layer_id)
        await websocket.send_json({"type": "error", "code": "scene_layer_persistence_failed"})
        return
    room_manager.upsert_scene_layer(layer)
    await room_manager.broadcast(room_id, {"type": "scene.layer.upserted", "layer": layer.to_payload()})
    logger.info("scene_layer_upserted room_id=%s layer_id=%s layer_type=%s user_id=%s", room_id, layer.layer_id, layer.layer_type, actor.user_id)


async def handle_scene_layer_remove(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    if actor.role != "gm":
        await websocket.send_json({"type": "error", "code": "scene_management_forbidden"})
        return
    scene_id = payload.get("scene_id")
    layer_id = payload.get("layer_id")
    if not isinstance(scene_id, str) or not isinstance(layer_id, str):
        await websocket.send_json({"type": "error", "code": "invalid_scene_layer"})
        return
    if not any(layer.layer_id == layer_id and layer.scene_id == scene_id for layer in room_manager.scene_layers(scene_id)):
        await websocket.send_json({"type": "error", "code": "scene_layer_not_found"})
        return
    try:
        async with session_factory() as session:
            await scene_layer_repository.delete(session, scene_id, layer_id)
    except SQLAlchemyError:
        logger.exception("scene_layer_remove_failed room_id=%s layer_id=%s", room_id, layer_id)
        await websocket.send_json({"type": "error", "code": "scene_layer_persistence_failed"})
        return
    room_manager.remove_scene_layer(scene_id, layer_id)
    await room_manager.broadcast(room_id, {"type": "scene.layer.removed", "scene_id": scene_id, "layer_id": layer_id})
    logger.info("scene_layer_removed room_id=%s layer_id=%s user_id=%s", room_id, layer_id, actor.user_id)


async def handle_bgm_track_upsert(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    if actor.role != "gm":
        await websocket.send_json({"type": "error", "code": "bgm_management_forbidden"})
        return
    try:
        request = BgmTrackRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json({"type": "error", "code": "invalid_bgm_track"})
        return
    track = RoomBgm(
        bgm_id=request.bgm_id or str(uuid4()),
        room_id=room_id,
        slot=request.slot,
        name=request.name.strip(),
        audio_url=request.audio_url,
        loop=request.loop,
    )
    try:
        async with session_factory() as session:
            existing_tracks = await room_bgm_repository.list_by_room(session, room_id)
            for existing in existing_tracks:
                if existing.slot == track.slot and existing.bgm_id != track.bgm_id:
                    await room_bgm_repository.delete(session, room_id, existing.bgm_id)
            await room_bgm_repository.upsert(session, track)
    except SQLAlchemyError:
        logger.exception("bgm_track_upsert_failed room_id=%s bgm_id=%s", room_id, track.bgm_id)
        await websocket.send_json({"type": "error", "code": "bgm_persistence_failed"})
        return
    await room_manager.broadcast(room_id, {"type": "bgm.track.upserted", "track": track.to_payload()})
    logger.info("bgm_track_upserted room_id=%s bgm_id=%s slot=%s user_id=%s", room_id, track.bgm_id, track.slot, actor.user_id)


async def handle_bgm_track_remove(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    if actor.role != "gm":
        await websocket.send_json({"type": "error", "code": "bgm_management_forbidden"})
        return
    bgm_id = payload.get("bgm_id")
    if not isinstance(bgm_id, str) or not bgm_id:
        await websocket.send_json({"type": "error", "code": "invalid_bgm_track"})
        return
    try:
        async with session_factory() as session:
            tracks = await room_bgm_repository.list_by_room(session, room_id)
            if not any(track.bgm_id == bgm_id for track in tracks):
                await websocket.send_json({"type": "error", "code": "bgm_track_not_found"})
                return
            await room_bgm_repository.delete(session, room_id, bgm_id)
    except SQLAlchemyError:
        logger.exception("bgm_track_remove_failed room_id=%s bgm_id=%s", room_id, bgm_id)
        await websocket.send_json({"type": "error", "code": "bgm_persistence_failed"})
        return
    await room_manager.broadcast(room_id, {"type": "bgm.track.removed", "bgm_id": bgm_id})
    logger.info("bgm_track_removed room_id=%s bgm_id=%s user_id=%s", room_id, bgm_id, actor.user_id)


async def handle_bgm_control(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    if actor.role != "gm":
        await websocket.send_json({"type": "error", "code": "bgm_management_forbidden"})
        return
    try:
        request = BgmControlRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json({"type": "error", "code": "invalid_bgm_control"})
        return
    async with session_factory() as session:
        tracks = await room_bgm_repository.list_by_room(session, room_id)
    if not any(track.slot == request.slot for track in tracks):
        await websocket.send_json({"type": "error", "code": "bgm_track_not_found"})
        return
    position = 0.0 if request.action == "stop" else request.position
    playback = BgmPlayback(request.slot, request.action, request.action == "play", position)
    room_manager.set_bgm_playback(room_id, playback)
    await room_manager.broadcast(room_id, {"type": "bgm.control", "playback": playback.to_payload()})
    logger.info("bgm_control room_id=%s slot=%s action=%s position=%s user_id=%s", room_id, request.slot, request.action, position, actor.user_id)


async def handle_chat_tab_create(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> None:
    try:
        request = ChatTabRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json({"type": "error", "code": "invalid_chat_tab"})
        return
    tab = RoomChatTab(
        tab_id=str(uuid4()),
        room_id=room_id,
        name=request.name.strip(),
        tab_type="custom",
        show_dialogue=request.show_dialogue,
        is_default=False,
        sort_order=100,
    )
    try:
        async with session_factory() as session:
            await room_chat_tab_repository.create(session, tab)
    except SQLAlchemyError:
        logger.exception("chat_tab_create_failed room_id=%s user_id=%s", room_id, actor.user_id)
        await websocket.send_json({"type": "error", "code": "chat_tab_persistence_failed"})
        return
    room_manager.upsert_chat_tab(tab)
    await room_manager.broadcast(room_id, {"type": "chat.tab.created", "tab": tab.to_payload()})
    logger.info("chat_tab_created room_id=%s tab_id=%s user_id=%s", room_id, tab.tab_id, actor.user_id)
