import logging
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Literal
from uuid import uuid4
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import ClientDisconnect

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
from coc_star_api.ai_provider import AiProviderError, complete
from coc_star_api.ai_repository import AiRepository, decode_knowledge_base_ids, encode_knowledge_base_ids
from coc_star_api.coc7_rules import canonical_check_target, derive_stats, parse_st, resolve_check
from coc_star_api.character_repository import CharacterRepository, decode_sheet, encode_sheet
from coc_star_api.knowledge_repository import KnowledgeRepository
from coc_star_api.models import AiProviderConfigModel, AiRunLogModel, CharacterLibraryModel, KnowledgeBaseModel, KnowledgeDocumentModel, RoomAiConfigModel, RoomCharacterModel, RoomKnowledgeConfigModel

app = FastAPI(title="coc-star API", version="0.1.0")
asset_root = Path(settings.uploads_root).resolve()
asset_root.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=asset_root), name="uploads")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https://[a-z0-9-]+\.trycloudflare\.com",
    allow_credentials=False,
    allow_methods=["DELETE", "GET", "POST", "PUT"],
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
ai_repository = AiRepository()
knowledge_repository = KnowledgeRepository()
character_repository = CharacterRepository()
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
    shape: Literal["circle", "square"] = "circle"
    character_id: str | None = Field(default=None, max_length=64)


class RoomMemberRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)
    room_name: str = Field(default="", max_length=120)


class MemberRoleRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    role: Literal["gm", "player"]


class MemberNameRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)


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
    shape: Literal["rectangle", "square", "circle"] = "rectangle"
    image_fit: Literal["cover", "contain", "fill"] = "cover"
    blur: float = Field(default=0.0, ge=0, le=24)
    opacity: float = Field(default=1.0, ge=0.05, le=1)


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


class AiProviderRequest(BaseModel):
    provider_id: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    provider_type: str = Field(default="openai-compatible", max_length=40)
    base_url: str = Field(min_length=1, max_length=2_048, pattern=r"^https?://")
    model: str = Field(min_length=1, max_length=160)
    api_key: str | None = Field(default=None, max_length=8_000)
    enabled: bool = True


class KnowledgeBaseRequest(BaseModel):
    parent_id: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    kind: Literal["knowledge", "documents"] = "knowledge"


class KnowledgeDocumentRequest(BaseModel):
    document_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=100_000)
    category: str = Field(default="未分类", min_length=1, max_length=80)
    ai_enabled: bool = True


class RoomKnowledgeRequest(BaseModel):
    knowledge_base_ids: list[str] = Field(default_factory=list, max_length=50)


class CharacterLibraryRequest(BaseModel):
    character_id: str | None = Field(default=None, max_length=64)
    system: str = Field(default="coc7", max_length=40)
    name: str = Field(min_length=1, max_length=160)
    sheet_data: dict[str, object] = Field(default_factory=dict)
    source_type: str = Field(default="manual", max_length=30)


class StCharacterImportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=20_000)


class RoomAiConfigRequest(BaseModel):
    provider_id: str | None = Field(default=None, max_length=64)
    enabled: bool = False
    assistant_name: str = Field(default="星语", min_length=1, max_length=80)
    system_prompt: str = Field(default="你是一个温和、有人情味的跑团助手。", max_length=8_000)
    avatar_url: str | None = Field(default=None, max_length=2_048)
    trigger_mode: Literal["mention", "main_channel", "all"] = "mention"
    scene_context_enabled: bool = True
    knowledge_base_ids: list[str] = Field(default_factory=list, max_length=20)


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
    logger.info("persistent_storage_ready database=%s uploads=%s", settings.database_url, asset_root)


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


@app.get("/api/ai/providers")
async def list_ai_providers(authorization: str | None = Header(default=None)) -> dict[str, list[dict[str, object]]]:
    account = require_account(authorization)
    async with session_factory() as session:
        providers = await ai_repository.list_providers(session, account.user_id)
    return {"providers": [ai_provider_payload(provider) for provider in providers]}


@app.get("/api/characters")
async def list_characters(authorization: str | None = Header(default=None)) -> dict[str, list[dict[str, object]]]:
    account = require_account(authorization)
    async with session_factory() as session:
        characters = await character_repository.list_library(session, account.user_id)
    return {"characters": [character_payload(character) for character in characters]}


@app.post("/api/characters")
async def save_character(request: CharacterLibraryRequest, authorization: str | None = Header(default=None)) -> dict[str, object]:
    account = require_account(authorization)
    character_id = request.character_id or str(uuid4())
    async with session_factory() as session:
        current = await character_repository.get_library(session, character_id, account.user_id)
        if request.character_id and current is None:
            raise HTTPException(status_code=404, detail="character_not_found")
        character = CharacterLibraryModel(character_id=character_id, user_id=account.user_id, system=request.system, name=request.name.strip(), sheet_data=encode_sheet(request.sheet_data), source_type=request.source_type)
        await character_repository.upsert_library(session, character)
    logger.info("character_library_saved user_id=%s character_id=%s source=%s", account.user_id, character_id, request.source_type)
    return {"character": character_payload(character)}


@app.post("/api/characters/import-st")
async def import_st_character(request: StCharacterImportRequest, authorization: str | None = Header(default=None)) -> dict[str, object]:
    account = require_account(authorization)
    imported = parse_st(request.text)
    attributes = dict(imported.attributes)
    resources = dict(imported.resources)
    derived = derive_stats(attributes)
    sheet_data = {
        "attributes": attributes,
        "resources": {
            "hp": {"current": resources.get("hp", derived.hp_max), "max": derived.hp_max},
            "mp": {"current": resources.get("mp", derived.mp_max), "max": derived.mp_max},
            "san": {"current": resources.get("san", derived.san_max), "max": derived.san_max},
        },
        "skills": imported.skills,
        "derived": {"build": derived.build, "damage_bonus": derived.damage_bonus},
        "import_warnings": imported.warnings,
    }
    character = CharacterLibraryModel(character_id=str(uuid4()), user_id=account.user_id, system="coc7", name=request.name.strip(), sheet_data=encode_sheet(sheet_data), source_type="st")
    async with session_factory() as session:
        await character_repository.upsert_library(session, character)
    logger.info("character_st_imported user_id=%s character_id=%s warnings=%s", account.user_id, character.character_id, len(imported.warnings))
    return {"character": character_payload(character), "warnings": imported.warnings, "unknown_text": imported.unknown_text}


@app.delete("/api/characters/{character_id}")
async def delete_character(character_id: str, authorization: str | None = Header(default=None)) -> dict[str, str]:
    account = require_account(authorization)
    async with session_factory() as session:
        if not await character_repository.delete_library(session, character_id, account.user_id):
            raise HTTPException(status_code=404, detail="character_not_found")
    logger.info("character_library_deleted user_id=%s character_id=%s", account.user_id, character_id)
    return {"character_id": character_id}


@app.get("/api/rooms/{room_id}/characters")
async def list_room_characters(room_id: str, authorization: str | None = Header(default=None)) -> dict[str, list[dict[str, object]]]:
    account = require_account(authorization)
    await require_room_member(room_id, account.user_id)
    async with session_factory() as session:
        characters = await character_repository.list_room_characters(session, room_id, account.user_id)
    return {"characters": [room_character_payload(character) for character in characters]}


@app.post("/api/rooms/{room_id}/characters/{character_id}")
async def load_room_character(room_id: str, character_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    account = require_account(authorization)
    await require_room_member(room_id, account.user_id)
    async with session_factory() as session:
        character = await character_repository.get_library(session, character_id, account.user_id)
        if character is None:
            raise HTTPException(status_code=404, detail="character_not_found")
        room_character = RoomCharacterModel(room_character_id=str(uuid4()), room_id=room_id, character_id=character.character_id, user_id=account.user_id, sheet_data=character.sheet_data)
        await character_repository.add_room_character(session, room_character)
    logger.info("room_character_loaded room_id=%s user_id=%s character_id=%s", room_id, account.user_id, character_id)
    return {"character": room_character_payload(room_character)}


@app.post("/api/ai/providers")
async def save_ai_provider(request: AiProviderRequest, authorization: str | None = Header(default=None)) -> dict[str, object]:
    account = require_account(authorization)
    provider_id = request.provider_id or str(uuid4())
    async with session_factory() as session:
        current = await ai_repository.get_provider(session, provider_id, account.user_id)
        api_key = request.api_key.strip() if request.api_key else (current.api_key if current else "")
        if not api_key:
            raise HTTPException(status_code=422, detail="api_key_required")
        provider = AiProviderConfigModel(provider_id=provider_id, user_id=account.user_id, name=request.name.strip(), provider_type=request.provider_type, base_url=request.base_url.rstrip("/"), model=request.model.strip(), api_key=api_key, enabled=request.enabled)
        await ai_repository.upsert_provider(session, provider)
    logger.info("ai_provider_saved user_id=%s provider_id=%s", account.user_id, provider_id)
    return {"provider": ai_provider_payload(provider)}


@app.delete("/api/ai/providers/{provider_id}")
async def delete_ai_provider(provider_id: str, authorization: str | None = Header(default=None)) -> dict[str, str]:
    account = require_account(authorization)
    async with session_factory() as session:
        if not await ai_repository.delete_provider(session, provider_id, account.user_id):
            raise HTTPException(status_code=404, detail="provider_not_found")
    logger.info("ai_provider_deleted user_id=%s provider_id=%s", account.user_id, provider_id)
    return {"provider_id": provider_id}


@app.get("/api/knowledge-bases")
async def list_knowledge_bases(authorization: str | None = Header(default=None)) -> dict[str, list[dict[str, object]]]:
    account = require_account(authorization)
    async with session_factory() as session:
        bases = await knowledge_repository.list_bases(session, account.user_id)
        document_counts = await knowledge_repository.document_counts(session, [base.knowledge_base_id for base in bases])
        payload = [knowledge_base_payload(base, document_counts.get(base.knowledge_base_id, 0)) for base in bases]
    return {"knowledge_bases": payload}


@app.post("/api/knowledge-bases")
async def save_knowledge_base(request: KnowledgeBaseRequest, authorization: str | None = Header(default=None)) -> dict[str, object]:
    account = require_account(authorization)
    if request.parent_id:
        async with session_factory() as session:
            parent = await knowledge_repository.get_base(session, request.parent_id, account.user_id)
            if parent is None:
                raise HTTPException(status_code=404, detail="parent_knowledge_base_not_found")
            if parent.kind != request.kind:
                raise HTTPException(status_code=422, detail="parent_knowledge_base_kind_mismatch")
    base = KnowledgeBaseModel(knowledge_base_id=str(uuid4()), user_id=account.user_id, parent_id=request.parent_id, name=request.name.strip(), description=request.description.strip(), kind=request.kind)
    async with session_factory() as session:
        await knowledge_repository.upsert_base(session, base)
    logger.info("knowledge_base_created user_id=%s knowledge_base_id=%s kind=%s", account.user_id, base.knowledge_base_id, base.kind)
    return {"knowledge_base": knowledge_base_payload(base, 0)}


@app.get("/api/knowledge-bases/{base_id}/documents")
async def list_knowledge_documents(base_id: str, authorization: str | None = Header(default=None)) -> dict[str, list[dict[str, object]]]:
    account = require_account(authorization)
    async with session_factory() as session:
        if await knowledge_repository.get_base(session, base_id, account.user_id) is None:
            raise HTTPException(status_code=404, detail="knowledge_base_not_found")
        documents = await knowledge_repository.list_documents(session, base_id)
    return {"documents": [knowledge_document_payload(document) for document in documents]}


@app.post("/api/knowledge-bases/{base_id}/documents")
async def save_knowledge_document(base_id: str, request: KnowledgeDocumentRequest, authorization: str | None = Header(default=None)) -> dict[str, object]:
    account = require_account(authorization)
    async with session_factory() as session:
        if await knowledge_repository.get_base(session, base_id, account.user_id) is None:
            raise HTTPException(status_code=404, detail="knowledge_base_not_found")
        existing = await knowledge_repository.get_document(session, request.document_id) if request.document_id else None
        if existing is not None and existing.knowledge_base_id != base_id:
            raise HTTPException(status_code=403, detail="document_forbidden")
        document = KnowledgeDocumentModel(document_id=request.document_id or str(uuid4()), knowledge_base_id=base_id, title=request.title.strip(), content=request.content.strip(), category=request.category.strip(), ai_enabled=request.ai_enabled)
        await knowledge_repository.upsert_document(session, document)
    logger.info("knowledge_document_saved user_id=%s document_id=%s knowledge_base_id=%s action=%s", account.user_id, document.document_id, base_id, "updated" if request.document_id else "created")
    return {"document": knowledge_document_payload(document)}


@app.post("/api/knowledge-bases/{base_id}/files")
async def import_knowledge_file(base_id: str, request: Request, authorization: str | None = Header(default=None)) -> dict[str, object]:
    account = require_account(authorization)
    async with session_factory() as session:
        if await knowledge_repository.get_base(session, base_id, account.user_id) is None:
            raise HTTPException(status_code=404, detail="knowledge_base_not_found")
    try:
        content = await request.body()
    except ClientDisconnect:
        logger.warning("room_asset_upload_disconnected room_id=%s user_id=%s content_type=%s", room_id, account.user_id, content_type)
        raise HTTPException(status_code=499, detail="asset_upload_disconnected") from None
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="knowledge_file_too_large")
    source_name = request.headers.get("x-file-name", "imported.txt")
    extension = Path(source_name).suffix.lower()
    supported_extensions = {".txt", ".md", ".markdown", ".json", ".csv", ".yaml", ".yml", ".xml", ".docx"}
    if extension not in supported_extensions:
        raise HTTPException(status_code=415, detail="unsupported_knowledge_file")
    try:
        if extension == ".docx":
            with ZipFile(BytesIO(content)) as archive:
                document_xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(document_xml)
            paragraphs = []
            for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                text = "".join(node.text or "" for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
                if text.strip():
                    paragraphs.append(text)
            text_content = "\n".join(paragraphs)
        else:
            text_content = content.decode("utf-8-sig")
    except (BadZipFile, KeyError, ElementTree.ParseError, UnicodeDecodeError):
        raise HTTPException(status_code=415, detail="knowledge_file_cannot_be_read") from None
    if not text_content.strip():
        raise HTTPException(status_code=422, detail="knowledge_file_is_empty")
    if len(text_content) > 100_000:
        raise HTTPException(status_code=413, detail="knowledge_file_text_too_large")
    document = KnowledgeDocumentModel(document_id=str(uuid4()), knowledge_base_id=base_id, title=Path(source_name).stem[:160] or "导入文档", content=text_content, category=extension.lstrip(".") or "file", source_type="file", source_name=source_name[:255], mime_type=request.headers.get("content-type"), ai_enabled=True)
    async with session_factory() as session:
        await knowledge_repository.upsert_document(session, document)
    logger.info("knowledge_file_imported user_id=%s knowledge_base_id=%s document_id=%s filename=%s", account.user_id, base_id, document.document_id, source_name)
    return {"document": knowledge_document_payload(document)}


@app.delete("/api/knowledge-bases/{base_id}/documents/{document_id}")
async def delete_knowledge_document(base_id: str, document_id: str, authorization: str | None = Header(default=None)) -> dict[str, str]:
    account = require_account(authorization)
    async with session_factory() as session:
        if await knowledge_repository.get_base(session, base_id, account.user_id) is None:
            raise HTTPException(status_code=404, detail="knowledge_base_not_found")
        document = await knowledge_repository.get_document(session, document_id)
        if document is None or document.knowledge_base_id != base_id:
            raise HTTPException(status_code=404, detail="document_not_found")
        await knowledge_repository.delete_document(session, document_id)
    logger.info("knowledge_document_deleted user_id=%s document_id=%s knowledge_base_id=%s", account.user_id, document_id, base_id)
    return {"document_id": document_id}


@app.delete("/api/knowledge-bases/{base_id}")
async def delete_knowledge_base(base_id: str, authorization: str | None = Header(default=None)) -> dict[str, str]:
    account = require_account(authorization)
    async with session_factory() as session:
        deleted_ids = await knowledge_repository.delete_base(session, base_id, account.user_id)
        if deleted_ids is None:
            raise HTTPException(status_code=404, detail="knowledge_base_not_found")
    logger.info("knowledge_base_deleted user_id=%s knowledge_base_id=%s descendants=%s", account.user_id, base_id, len(deleted_ids) - 1)
    return {"knowledge_base_id": base_id}


@app.get("/api/rooms/{room_id}/knowledge")
async def get_room_knowledge(room_id: str, authorization: str | None = Header(default=None)) -> dict[str, list[str]]:
    account = require_account(authorization)
    await require_room_member(room_id, account.user_id)
    async with session_factory() as session:
        config = await knowledge_repository.get_room_config(session, room_id)
    return {"knowledge_base_ids": decode_knowledge_base_ids(config.knowledge_base_ids) if config else []}


@app.put("/api/rooms/{room_id}/knowledge")
async def save_room_knowledge(room_id: str, request: RoomKnowledgeRequest, authorization: str | None = Header(default=None)) -> dict[str, list[str]]:
    account = require_account(authorization)
    await require_room_gm(room_id, account.user_id)
    async with session_factory() as session:
        bases = await knowledge_repository.list_bases(session, account.user_id)
        allowed_ids = {base.knowledge_base_id for base in bases}
        if not set(request.knowledge_base_ids).issubset(allowed_ids):
            raise HTTPException(status_code=403, detail="knowledge_base_forbidden")
        config = RoomKnowledgeConfigModel(room_id=room_id, knowledge_base_ids=encode_knowledge_base_ids(request.knowledge_base_ids))
        await knowledge_repository.upsert_room_config(session, config)
    logger.info("room_knowledge_mounted room_id=%s user_id=%s count=%s", room_id, account.user_id, len(request.knowledge_base_ids))
    return {"knowledge_base_ids": request.knowledge_base_ids}


@app.get("/api/rooms/{room_id}/ai")
async def get_room_ai_config(room_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    account = require_account(authorization)
    await require_room_member(room_id, account.user_id)
    async with session_factory() as session:
        config = await ai_repository.get_room_config(session, room_id)
    return {"config": ai_room_config_payload(config)}


@app.put("/api/rooms/{room_id}/ai")
async def save_room_ai_config(room_id: str, request: RoomAiConfigRequest, authorization: str | None = Header(default=None)) -> dict[str, object]:
    account = require_account(authorization)
    await require_room_gm(room_id, account.user_id)
    async with session_factory() as session:
        if request.provider_id and await ai_repository.get_provider(session, request.provider_id, account.user_id) is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        config = RoomAiConfigModel(room_id=room_id, provider_id=request.provider_id, enabled=request.enabled, assistant_name=request.assistant_name.strip(), system_prompt=request.system_prompt.strip(), avatar_url=request.avatar_url, trigger_mode=request.trigger_mode, scene_context_enabled=request.scene_context_enabled, knowledge_base_ids=encode_knowledge_base_ids(request.knowledge_base_ids))
        await ai_repository.upsert_room_config(session, config)
    logger.info("room_ai_config_saved room_id=%s user_id=%s enabled=%s", room_id, account.user_id, request.enabled)
    return {"config": ai_room_config_payload(config)}


@app.get("/api/rooms/{room_id}/ai/logs")
async def list_room_ai_logs(room_id: str, authorization: str | None = Header(default=None)) -> dict[str, list[dict[str, object]]]:
    account = require_account(authorization)
    await require_room_gm(room_id, account.user_id)
    async with session_factory() as session:
        logs = await ai_repository.list_logs(session, room_id)
    return {"logs": [ai_log_payload(log) for log in logs]}


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
        "audio/mp3": ".mp3",
        "audio/ogg": ".ogg",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
        "audio/flac": ".flac",
        "audio/x-flac": ".flac",
        "audio/webm": ".webm",
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
            if payload.get("type") == "room.member.name.update":
                updated_member = await handle_member_name_update(websocket, room_id, member, payload)
                if updated_member is not None:
                    member = updated_member
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
            coc_target = parse_coc_check_command(message.text)
            if coc_target is not None:
                target, target_name = coc_target
                if target is None:
                    async with session_factory() as session:
                        active_character = await character_repository.get_active_room_character(session, room_id, user_id)
                    if active_character is not None:
                        sheet = decode_sheet(active_character.sheet_data)
                        resolved = canonical_check_target(target_name)
                        if resolved is not None:
                            category, field_id = resolved
                            values = sheet.get("attributes" if category == "attribute" else "skills", {})
                            if isinstance(values, dict) and isinstance(values.get(field_id), int):
                                target = values[field_id]
                if target is None:
                    await websocket.send_json({"type": "error", "code": "character_check_target_missing"})
                    continue
                result = roll_dice("1d100")
                check = resolve_check(target, result.total)
                await room_manager.broadcast(room_id, {"type": "dice.result", "result": {"roll_id": str(uuid4()), "user_id": member.user_id, "display_name": member.display_name, "tab_id": chat_tab.tab_id if chat_tab else None, "expression": f"cc<={target} {target_name}", "rolls": list(result.rolls), "modifier": 0, "total": result.total, "target": target, "level": check.level}})
                logger.info("coc_check_broadcast room_id=%s user_id=%s target_name=%s target=%s roll=%s level=%s", room_id, user_id, target_name, target, result.total, check.level)
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
            await maybe_run_room_ai(room_id, member, chat_tab, visible_text)
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


def parse_coc_check_command(text: str) -> tuple[int | None, str] | None:
    normalized = text.strip()
    if normalized.startswith("{") and "}" in normalized:
        target_name, _, suffix = normalized[1:].partition("}")
        if not target_name.strip() or suffix.strip():
            return None
        return None, target_name.strip()
    match = re.fullmatch(r"cc\s*<=\s*(\d{1,3})(?:\s+(.+))?", normalized, re.IGNORECASE)
    if match is None:
        return None
    return min(int(match.group(1)), 100), (match.group(2) or "检定").strip()


def require_account(authorization: str | None) -> AccountClaims:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="account_auth_required")
    try:
        return account_tokens.verify(authorization[7:], "access")
    except InvalidAccountToken:
        raise HTTPException(status_code=401, detail="invalid_account_token") from None


async def require_room_member(room_id: str, user_id: str) -> object:
    async with session_factory() as session:
        member = await room_repository.get_member(session, room_id, user_id)
    if member is None:
        raise HTTPException(status_code=403, detail="room_membership_required")
    return member


async def require_room_gm(room_id: str, user_id: str) -> object:
    member = await require_room_member(room_id, user_id)
    if member.role != "gm":
        raise HTTPException(status_code=403, detail="gm_required")
    return member


def ai_provider_payload(provider: AiProviderConfigModel) -> dict[str, object]:
    masked = f"{provider.api_key[:4]}••••{provider.api_key[-4:]}" if len(provider.api_key) >= 8 else "••••"
    return {"provider_id": provider.provider_id, "name": provider.name, "provider_type": provider.provider_type, "base_url": provider.base_url, "model": provider.model, "api_key_masked": masked, "enabled": provider.enabled}


def knowledge_base_payload(base: KnowledgeBaseModel, document_count: int) -> dict[str, object]:
    return {"knowledge_base_id": base.knowledge_base_id, "parent_id": base.parent_id, "name": base.name, "description": base.description, "kind": base.kind, "document_count": document_count, "created_at": base.created_at.isoformat() if base.created_at else None}


def knowledge_document_payload(document: KnowledgeDocumentModel) -> dict[str, object]:
    return {"document_id": document.document_id, "knowledge_base_id": document.knowledge_base_id, "title": document.title, "content": document.content, "category": document.category, "source_type": document.source_type, "source_name": document.source_name, "mime_type": document.mime_type, "ai_enabled": document.ai_enabled, "created_at": document.created_at.isoformat() if document.created_at else None, "updated_at": document.updated_at.isoformat() if document.updated_at else None}


def character_payload(character: CharacterLibraryModel) -> dict[str, object]:
    return {"character_id": character.character_id, "system": character.system, "name": character.name, "source_type": character.source_type, "sheet_data": decode_sheet(character.sheet_data), "created_at": character.created_at.isoformat() if character.created_at else None, "updated_at": character.updated_at.isoformat() if character.updated_at else None}


def room_character_payload(character: RoomCharacterModel) -> dict[str, object]:
    return {"room_character_id": character.room_character_id, "room_id": character.room_id, "character_id": character.character_id, "sheet_data": decode_sheet(character.sheet_data), "active": character.active, "created_at": character.created_at.isoformat() if character.created_at else None}


def ai_room_config_payload(config: RoomAiConfigModel | None) -> dict[str, object]:
    if config is None:
        return {"room_id": None, "provider_id": None, "enabled": False, "assistant_name": "星语", "system_prompt": "你是一个温和、有人情味的跑团助手。", "avatar_url": None, "trigger_mode": "mention", "scene_context_enabled": True, "knowledge_base_ids": []}
    return {"room_id": config.room_id, "provider_id": config.provider_id, "enabled": config.enabled, "assistant_name": config.assistant_name, "system_prompt": config.system_prompt, "avatar_url": config.avatar_url, "trigger_mode": config.trigger_mode, "scene_context_enabled": config.scene_context_enabled, "knowledge_base_ids": decode_knowledge_base_ids(config.knowledge_base_ids)}


def ai_log_payload(log: AiRunLogModel) -> dict[str, object]:
    return {"log_id": log.log_id, "room_id": log.room_id, "user_id": log.user_id, "event_type": log.event_type, "status": log.status, "request_summary": log.request_summary, "response_summary": log.response_summary, "latency_ms": log.latency_ms, "created_at": log.created_at.isoformat() if log.created_at else None}


async def maybe_run_room_ai(room_id: str, member: RoomMember, chat_tab: RoomChatTab | None, text: str) -> None:
    async with session_factory() as session:
        config = await ai_repository.get_room_config(session, room_id)
        if config is None or not config.enabled:
            return
        should_run = config.trigger_mode == "all" or (config.trigger_mode == "main_channel" and chat_tab and chat_tab.tab_type == "main") or (config.trigger_mode == "mention" and (text.startswith("@") or text.startswith("#")))
        if not should_run:
            return
        provider = await session.get(AiProviderConfigModel, config.provider_id) if config.provider_id else None
        if provider is None or not provider.enabled:
            await ai_repository.add_log(session, AiRunLogModel(log_id=str(uuid4()), room_id=room_id, user_id=member.user_id, event_type="chat_completion", status="skipped", request_summary="未配置可用的 AI 厂商", response_summary="", latency_ms=0))
            return
        room_knowledge = await knowledge_repository.get_room_config(session, room_id)
        documents = []
        mounted_ids = decode_knowledge_base_ids(room_knowledge.knowledge_base_ids) if room_knowledge else []
        for base_id in mounted_ids:
            documents.extend(await knowledge_repository.list_documents(session, base_id))
        scene = room_manager.active_scene(room_id)
    prompt_text = text.lstrip("@#").strip() if config.trigger_mode == "mention" else text
    knowledge_context = "\n".join(f"[{document.category}] {document.title}: {document.content[:2_000]}" for document in documents if document.ai_enabled)[:16_000]
    scene_context = f"当前场景：{scene.name}" if config.scene_context_enabled and scene else ""
    messages = [{"role": "system", "content": config.system_prompt}, {"role": "system", "content": f"{scene_context}\n参考资料：\n{knowledge_context}"}, {"role": "user", "content": prompt_text}]
    started = time.perf_counter()
    try:
        reply = await complete(provider.base_url, provider.api_key, provider.model, messages)
    except AiProviderError as error:
        async with session_factory() as session:
            await ai_repository.add_log(session, AiRunLogModel(log_id=str(uuid4()), room_id=room_id, user_id=member.user_id, event_type="chat_completion", status="failed", request_summary=prompt_text[:500], response_summary=str(error), latency_ms=int((time.perf_counter() - started) * 1000)))
        logger.exception("ai_completion_failed room_id=%s user_id=%s", room_id, member.user_id)
        return
    async with session_factory() as session:
        await ai_repository.add_log(session, AiRunLogModel(log_id=str(uuid4()), room_id=room_id, user_id=member.user_id, event_type="chat_completion", status="succeeded", request_summary=prompt_text[:500], response_summary=reply.text[:500], latency_ms=int((time.perf_counter() - started) * 1000)))
    await room_manager.broadcast(room_id, {"type": "chat.message", "message": {"message_id": str(uuid4()), "user_id": "ai", "display_name": config.assistant_name, "character_name": config.assistant_name, "character_color": "#9ec5ff", "tab_id": chat_tab.tab_id if chat_tab else None, "show_dialogue": True, "text": reply.text, "token_id": None, "face_id": None, "ai_avatar_url": config.avatar_url}})
    logger.info("ai_completion_succeeded room_id=%s model=%s latency_ms=%s", room_id, reply.model, int((time.perf_counter() - started) * 1000))


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
    token_owner_id = current_token.owner_user_id if current_token else member.user_id
    current_character_id = current_token.character_id if current_token else None
    character_binding_changed = token_input.character_id != current_character_id
    if character_binding_changed and token_owner_id != member.user_id:
        await websocket.send_json({"type": "error", "code": "character_binding_forbidden"})
        return
    token = BoardToken(
        token_id=token_id,
        owner_user_id=token_owner_id,
        name=token_input.name,
        x=token_input.x,
        y=token_input.y,
        color=token_input.color,
        shape=token_input.shape,
        character_id=token_input.character_id,
    )
    try:
        async with session_factory() as session:
            if token_input.character_id and token_owner_id == member.user_id:
                if await character_repository.get_library(session, token_input.character_id, member.user_id) is None:
                    await websocket.send_json({"type": "error", "code": "character_not_found"})
                    return
                if not await character_repository.activate_room_character(session, room_id, member.user_id, token_input.character_id):
                    await websocket.send_json({"type": "error", "code": "character_not_loaded_in_room"})
                    return
            await board_repository.upsert(session, room_id, token)
    except SQLAlchemyError:
        await websocket.send_json({"type": "error", "code": "board_persistence_failed"})
        logger.exception("board_token_persistence_failed room_id=%s token_id=%s", room_id, token_id)
        return
    room_manager.upsert_token(room_id, token)
    await room_manager.broadcast(room_id, {"type": "board.token.upserted", "token": board_token_payload(room_id, token)})
    logger.info("board_token_upserted room_id=%s token_id=%s user_id=%s shape=%s", room_id, token_id, member.user_id, token.shape)


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


async def handle_member_name_update(
    websocket: WebSocket,
    room_id: str,
    actor: RoomMember,
    payload: dict[str, object],
) -> RoomMember | None:
    try:
        request = MemberNameRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json({"type": "error", "code": "invalid_member_name"})
        return None
    display_name = request.display_name.strip()
    if not display_name:
        await websocket.send_json({"type": "error", "code": "invalid_member_name"})
        return None
    try:
        async with session_factory() as session:
            if not await room_repository.update_member_name(session, room_id, actor.user_id, display_name):
                await websocket.send_json({"type": "error", "code": "member_not_found"})
                return None
    except SQLAlchemyError:
        logger.exception("member_name_update_failed room_id=%s user_id=%s", room_id, actor.user_id)
        await websocket.send_json({"type": "error", "code": "member_persistence_failed"})
        return None
    updated_member = room_manager.update_member_name(room_id, actor.user_id, display_name)
    if updated_member is None:
        return None
    await room_manager.broadcast(room_id, {"type": "member.name.updated", "member": updated_member.to_payload()})
    logger.info("member_name_updated room_id=%s user_id=%s", room_id, actor.user_id)
    return updated_member


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
        shape=request.shape,
        image_fit=request.image_fit,
        blur=request.blur,
        opacity=request.opacity,
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
