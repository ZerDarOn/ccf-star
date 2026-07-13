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


class RoomModel(Base):
    __tablename__ = "rooms"

    room_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RoomMemberModel(Base):
    __tablename__ = "room_members"

    room_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(20))
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RoomSceneModel(Base):
    __tablename__ = "room_scenes"

    scene_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    room_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(120))
    background_url: Mapped[str] = mapped_column(String(2_048), default="")
    is_active: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
