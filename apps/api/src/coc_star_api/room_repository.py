from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from coc_star_api.models import BoardTokenModel, RoomBgmModel, RoomChatTabModel, RoomMemberModel, RoomModel, RoomSceneModel, SceneLayerModel, TokenFaceModel, TokenPresentationModel


class RoomRepository:
    async def list_room_ids(self, session: AsyncSession) -> list[str]:
        result = await session.scalars(select(RoomModel.room_id))
        return list(result)

    async def exists(self, session: AsyncSession, room_id: str) -> bool:
        return await session.get(RoomModel, room_id) is not None

    async def list_for_user(self, session: AsyncSession, user_id: str) -> list[tuple[RoomModel, RoomMemberModel]]:
        result = await session.execute(
            select(RoomModel, RoomMemberModel)
            .join(RoomMemberModel, RoomMemberModel.room_id == RoomModel.room_id)
            .where(RoomMemberModel.user_id == user_id)
            .order_by(RoomModel.created_at.desc(), RoomModel.room_id)
        )
        return list(result.all())

    async def remove_for_user(self, session: AsyncSession, room_id: str, user_id: str) -> str | None:
        room = await session.get(RoomModel, room_id)
        member = await session.get(RoomMemberModel, (room_id, user_id))
        if room is None or member is None:
            return None
        if room.owner_user_id != user_id:
            await session.delete(member)
            await session.commit()
            return "left"
        scene_ids = list(await session.scalars(select(RoomSceneModel.scene_id).where(RoomSceneModel.room_id == room_id)))
        token_ids = list(await session.scalars(select(BoardTokenModel.token_id).where(BoardTokenModel.room_id == room_id)))
        if scene_ids:
            await session.execute(delete(SceneLayerModel).where(SceneLayerModel.scene_id.in_(scene_ids)))
        if token_ids:
            await session.execute(delete(TokenFaceModel).where(TokenFaceModel.token_id.in_(token_ids)))
            await session.execute(delete(TokenPresentationModel).where(TokenPresentationModel.token_id.in_(token_ids)))
        await session.execute(delete(RoomSceneModel).where(RoomSceneModel.room_id == room_id))
        await session.execute(delete(RoomChatTabModel).where(RoomChatTabModel.room_id == room_id))
        await session.execute(delete(RoomBgmModel).where(RoomBgmModel.room_id == room_id))
        await session.execute(delete(BoardTokenModel).where(BoardTokenModel.room_id == room_id))
        await session.execute(delete(RoomMemberModel).where(RoomMemberModel.room_id == room_id))
        await session.delete(room)
        await session.commit()
        return "deleted"

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
        session.add(RoomModel(room_id=room_id, name=name, owner_user_id=user_id))
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
