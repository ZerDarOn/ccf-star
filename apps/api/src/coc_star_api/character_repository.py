import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coc_star_api.models import CharacterLibraryModel, RoomCharacterModel


class CharacterRepository:
    async def list_library(self, session: AsyncSession, user_id: str) -> list[CharacterLibraryModel]:
        result = await session.scalars(select(CharacterLibraryModel).where(CharacterLibraryModel.user_id == user_id).order_by(CharacterLibraryModel.updated_at.desc()))
        return list(result)

    async def get_library(self, session: AsyncSession, character_id: str, user_id: str) -> CharacterLibraryModel | None:
        character = await session.get(CharacterLibraryModel, character_id)
        return character if character and character.user_id == user_id else None

    async def upsert_library(self, session: AsyncSession, character: CharacterLibraryModel) -> None:
        current = await session.get(CharacterLibraryModel, character.character_id)
        if current is None:
            session.add(character)
        else:
            for field in ("system", "name", "sheet_data", "source_type"):
                setattr(current, field, getattr(character, field))
        await session.commit()

    async def delete_library(self, session: AsyncSession, character_id: str, user_id: str) -> bool:
        character = await self.get_library(session, character_id, user_id)
        if character is None:
            return False
        await session.delete(character)
        await session.commit()
        return True

    async def list_room_characters(self, session: AsyncSession, room_id: str, user_id: str) -> list[RoomCharacterModel]:
        result = await session.scalars(select(RoomCharacterModel).where(RoomCharacterModel.room_id == room_id, RoomCharacterModel.user_id == user_id).order_by(RoomCharacterModel.created_at))
        return list(result)

    async def get_active_room_character(self, session: AsyncSession, room_id: str, user_id: str) -> RoomCharacterModel | None:
        return await session.scalar(select(RoomCharacterModel).where(RoomCharacterModel.room_id == room_id, RoomCharacterModel.user_id == user_id, RoomCharacterModel.active.is_(True)).limit(1))

    async def activate_room_character(self, session: AsyncSession, room_id: str, user_id: str, character_id: str) -> bool:
        characters = await self.list_room_characters(session, room_id, user_id)
        target = next((item for item in characters if item.character_id == character_id), None)
        if target is None:
            return False
        for item in characters:
            item.active = item.room_character_id == target.room_character_id
        return True

    async def add_room_character(self, session: AsyncSession, room_character: RoomCharacterModel) -> None:
        current = await session.scalars(select(RoomCharacterModel).where(RoomCharacterModel.room_id == room_character.room_id, RoomCharacterModel.user_id == room_character.user_id))
        for item in current:
            item.active = False
        session.add(room_character)
        await session.commit()

    async def remove_room_character(self, session: AsyncSession, room_character_id: str, user_id: str) -> bool:
        character = await session.get(RoomCharacterModel, room_character_id)
        if character is None or character.user_id != user_id:
            return False
        await session.delete(character)
        await session.commit()
        return True


def decode_sheet(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def encode_sheet(value: dict[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False)
