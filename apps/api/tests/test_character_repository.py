import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from coc_star_api.character_repository import CharacterRepository
from coc_star_api.database import Base
from coc_star_api.models import RoomCharacterModel


@pytest.mark.asyncio
async def test_activate_room_character_switches_only_the_users_loaded_character(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'characters.db').as_posix()}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = CharacterRepository()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with factory() as session:
        session.add_all([
            RoomCharacterModel(room_character_id="old", room_id="room", character_id="character-old", user_id="player", active=True),
            RoomCharacterModel(room_character_id="new", room_id="room", character_id="character-new", user_id="player", active=False),
            RoomCharacterModel(room_character_id="other", room_id="room", character_id="character-other", user_id="other-player", active=True),
        ])
        await session.commit()

        assert await repository.activate_room_character(session, "room", "player", "character-new") is True
        await session.commit()

    async with factory() as session:
        assert (await session.get(RoomCharacterModel, "old")).active is False
        assert (await session.get(RoomCharacterModel, "new")).active is True
        assert (await session.get(RoomCharacterModel, "other")).active is True
        assert await repository.activate_room_character(session, "room", "player", "not-loaded") is False

    await engine.dispose()
