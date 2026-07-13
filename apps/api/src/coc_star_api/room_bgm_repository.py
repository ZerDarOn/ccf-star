from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from coc_star_api.models import RoomBgmModel
from coc_star_api.room_bgm import RoomBgm


class RoomBgmRepository:
    async def list_by_room(self, session: AsyncSession, room_id: str) -> list[RoomBgm]:
        result = await session.scalars(
            select(RoomBgmModel).where(RoomBgmModel.room_id == room_id).order_by(RoomBgmModel.slot, RoomBgmModel.bgm_id)
        )
        return [self._to_domain(model) for model in result]

    async def upsert(self, session: AsyncSession, track: RoomBgm) -> None:
        model = await session.get(RoomBgmModel, track.bgm_id)
        if model is None:
            model = RoomBgmModel(bgm_id=track.bgm_id)
            session.add(model)
        model.room_id = track.room_id
        model.slot = track.slot
        model.name = track.name
        model.audio_url = track.audio_url
        model.loop = track.loop
        await session.commit()

    async def delete(self, session: AsyncSession, room_id: str, bgm_id: str) -> None:
        await session.execute(delete(RoomBgmModel).where(RoomBgmModel.room_id == room_id, RoomBgmModel.bgm_id == bgm_id))
        await session.commit()

    @staticmethod
    def _to_domain(model: RoomBgmModel) -> RoomBgm:
        return RoomBgm(model.bgm_id, model.room_id, model.slot, model.name, model.audio_url, model.loop)
