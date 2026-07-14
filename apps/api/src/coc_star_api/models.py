from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from coc_star_api.database import Base


class BoardTokenModel(Base):
    __tablename__ = "board_tokens"

    token_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    room_id: Mapped[str] = mapped_column(String(128), index=True)
    owner_user_id: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(40))
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    color: Mapped[str] = mapped_column(String(7))
    shape: Mapped[str] = mapped_column(String(20), default="circle")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class TokenPresentationModel(Base):
    __tablename__ = "token_presentations"

    token_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_type: Mapped[str] = mapped_column(String(20), default="npc")
    image_url: Mapped[str | None] = mapped_column(String(2_048), nullable=True)
    scale: Mapped[float] = mapped_column(Float, default=1.0)
    active_face_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class TokenFaceModel(Base):
    __tablename__ = "token_faces"

    face_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_id: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(80))
    trigger: Mapped[str | None] = mapped_column(String(80), nullable=True)
    image_url: Mapped[str] = mapped_column(String(2_048))


class RoomModel(Base):
    __tablename__ = "rooms"

    room_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    owner_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RoomMemberModel(Base):
    __tablename__ = "room_members"

    room_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(20))
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RoomChatTabModel(Base):
    __tablename__ = "room_chat_tabs"

    tab_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    room_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(40))
    tab_type: Mapped[str] = mapped_column(String(20))
    show_dialogue: Mapped[bool] = mapped_column(default=False)
    is_default: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=100)


class RoomSceneModel(Base):
    __tablename__ = "room_scenes"

    scene_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    room_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(120))
    background_url: Mapped[str] = mapped_column(String(2_048), default="")
    is_active: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SceneLayerModel(Base):
    __tablename__ = "scene_layers"

    layer_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    scene_id: Mapped[str] = mapped_column(String(128), index=True)
    layer_type: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    image_url: Mapped[str | None] = mapped_column(String(2_048), nullable=True)
    text: Mapped[str] = mapped_column(String(500), default="")
    x: Mapped[float] = mapped_column(Float, default=0.5)
    y: Mapped[float] = mapped_column(Float, default=0.5)
    width: Mapped[float] = mapped_column(Float, default=0.4)
    height: Mapped[float] = mapped_column(Float, default=0.3)
    z_index: Mapped[int] = mapped_column(default=0)
    visible: Mapped[bool] = mapped_column(default=True)
    shape: Mapped[str] = mapped_column(String(20), default="rectangle")
    image_fit: Mapped[str] = mapped_column(String(20), default="cover")
    blur: Mapped[float] = mapped_column(Float, default=0.0)
    opacity: Mapped[float] = mapped_column(Float, default=1.0)


class RoomBgmModel(Base):
    __tablename__ = "room_bgm_tracks"

    bgm_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    room_id: Mapped[str] = mapped_column(String(128), index=True)
    slot: Mapped[str] = mapped_column(String(8), index=True)
    name: Mapped[str] = mapped_column(String(120))
    audio_url: Mapped[str] = mapped_column(String(2_048))
    loop: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AiProviderConfigModel(Base):
    __tablename__ = "ai_provider_configs"

    provider_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(80))
    provider_type: Mapped[str] = mapped_column(String(40), default="openai-compatible")
    base_url: Mapped[str] = mapped_column(String(2_048))
    model: Mapped[str] = mapped_column(String(160))
    api_key: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class KnowledgeBaseModel(Base):
    __tablename__ = "knowledge_bases"

    knowledge_base_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    kind: Mapped[str] = mapped_column(String(20), default="knowledge")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"

    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), default="未分类")
    source_type: Mapped[str] = mapped_column(String(20), default="manual")
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class RoomKnowledgeConfigModel(Base):
    __tablename__ = "room_knowledge_configs"

    room_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    knowledge_base_ids: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class RoomAiConfigModel(Base):
    __tablename__ = "room_ai_configs"

    room_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    assistant_name: Mapped[str] = mapped_column(String(80), default="星语")
    system_prompt: Mapped[str] = mapped_column(Text, default="你是一个温和、有人情味的跑团助手。")
    avatar_url: Mapped[str | None] = mapped_column(String(2_048), nullable=True)
    trigger_mode: Mapped[str] = mapped_column(String(20), default="mention")
    scene_context_enabled: Mapped[bool] = mapped_column(default=True)
    knowledge_base_ids: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AiRunLogModel(Base):
    __tablename__ = "ai_run_logs"

    log_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    room_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    request_summary: Mapped[str] = mapped_column(String(500), default="")
    response_summary: Mapped[str] = mapped_column(String(500), default="")
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
