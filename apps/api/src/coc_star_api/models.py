from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
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
