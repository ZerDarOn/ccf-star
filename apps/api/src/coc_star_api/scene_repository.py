from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from coc_star_api.models import RoomSceneModel


class SceneRepository:
    async def list_by_room(self, session: AsyncSession, room_id: str) -> list[RoomSceneModel]:
        result = await session.scalars(
            select(RoomSceneModel).where(RoomSceneModel.room_id == room_id).order_by(RoomSceneModel.created_at)
        )
        return list(result)

    async def get_active(self, session: AsyncSession, room_id: str) -> RoomSceneModel | None:
        return await session.scalar(
            select(RoomSceneModel).where(RoomSceneModel.room_id == room_id, RoomSceneModel.is_active.is_(True))
        )

    async def create(
        self,
        session: AsyncSession,
        scene_id: str,
        room_id: str,
        name: str,
        background_url: str,
    ) -> RoomSceneModel:
        await session.execute(update(RoomSceneModel).where(RoomSceneModel.room_id == room_id).values(is_active=False))
        scene = RoomSceneModel(
            scene_id=scene_id,
            room_id=room_id,
            name=name,
            background_url=background_url,
            is_active=True,
        )
        session.add(scene)
        await session.commit()
        return scene

    async def activate(self, session: AsyncSession, room_id: str, scene_id: str) -> RoomSceneModel | None:
        scene = await session.get(RoomSceneModel, scene_id)
        if scene is None or scene.room_id != room_id:
            return None
        await session.execute(update(RoomSceneModel).where(RoomSceneModel.room_id == room_id).values(is_active=False))
        scene.is_active = True
        await session.commit()
        return scene
