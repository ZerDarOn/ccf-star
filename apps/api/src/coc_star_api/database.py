from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase

from coc_star_api.settings import settings


class Base(DeclarativeBase):
    pass


engine: AsyncEngine = create_async_engine(settings.database_url, echo=False)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def initialize_database() -> None:
    from coc_star_api.models import BoardTokenModel

    del BoardTokenModel
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        if connection.dialect.name == "sqlite":
            columns = await connection.execute(text("PRAGMA table_info(rooms)"))
            column_names = {row[1] for row in columns}
            if "owner_user_id" not in column_names:
                await connection.execute(text("ALTER TABLE rooms ADD COLUMN owner_user_id VARCHAR(128)"))
            await connection.execute(text("""
                UPDATE rooms
                SET owner_user_id = (
                    SELECT user_id FROM room_members
                    WHERE room_members.room_id = rooms.room_id AND room_members.role = 'gm'
                    ORDER BY joined_at ASC LIMIT 1
                )
                WHERE owner_user_id IS NULL
            """))
            face_columns = await connection.execute(text("PRAGMA table_info(token_faces)"))
            face_column_names = {row[1] for row in face_columns}
            if "trigger" not in face_column_names:
                await connection.execute(text('ALTER TABLE token_faces ADD COLUMN "trigger" VARCHAR(80)'))
