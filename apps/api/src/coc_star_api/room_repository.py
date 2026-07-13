from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coc_star_api.models import RoomMemberModel, RoomModel


class RoomRepository:
    async def list_room_ids(self, session: AsyncSession) -> list[str]:
        result = await session.scalars(select(RoomModel.room_id))
        return list(result)

    async def exists(self, session: AsyncSession, room_id: str) -> bool:
        return await session.get(RoomModel, room_id) is not None

    async def get_member(self, session: AsyncSession, room_id: str, user_id: str) -> RoomMemberModel | None:
        return await session.get(RoomMemberModel, (room_id, user_id))

    async def create_room(self, session: AsyncSession, room_id: str, name: str) -> None:
        session.add(RoomModel(room_id=room_id, name=name))
        await session.commit()

    async def create_room_with_owner(
        self,
        session: AsyncSession,
        room_id: str,
        name: str,
        user_id: str,
        display_name: str,
    ) -> None:
        session.add(RoomModel(room_id=room_id, name=name))
        session.add(RoomMemberModel(room_id=room_id, user_id=user_id, display_name=display_name, role="gm"))
        await session.commit()

    async def add_member(
        self,
        session: AsyncSession,
        room_id: str,
        user_id: str,
        display_name: str,
        role: str,
    ) -> None:
        member = await session.get(RoomMemberModel, (room_id, user_id))
        if member is None:
            session.add(RoomMemberModel(room_id=room_id, user_id=user_id, display_name=display_name, role=role))
        else:
            member.display_name = display_name
            member.role = role
        await session.commit()

    async def update_member_role(self, session: AsyncSession, room_id: str, user_id: str, role: str) -> bool:
        member = await session.get(RoomMemberModel, (room_id, user_id))
        if member is None:
            return False
        member.role = role
        await session.commit()
        return True

    async def remove_member(self, session: AsyncSession, room_id: str, user_id: str) -> bool:
        member = await session.get(RoomMemberModel, (room_id, user_id))
        if member is None:
            return False
        await session.delete(member)
        await session.commit()
        return True
