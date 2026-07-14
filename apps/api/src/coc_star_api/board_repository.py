from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from coc_star_api.models import BoardTokenModel
from coc_star_api.room_manager import BoardToken


class BoardTokenRepository:
    async def list_by_room(self, session: AsyncSession, room_id: str) -> list[BoardToken]:
        result = await session.scalars(select(BoardTokenModel).where(BoardTokenModel.room_id == room_id))
        return [self._to_domain(model) for model in result]

    async def upsert(self, session: AsyncSession, room_id: str, token: BoardToken) -> None:
        model = await session.get(BoardTokenModel, token.token_id)
        if model is None:
            model = BoardTokenModel(token_id=token.token_id, room_id=room_id)
            session.add(model)
        model.owner_user_id = token.owner_user_id
        model.name = token.name
        model.x = token.x
        model.y = token.y
        model.color = token.color
        model.shape = token.shape
        await session.commit()

    async def delete(self, session: AsyncSession, room_id: str, token_id: str) -> None:
        await session.execute(delete(BoardTokenModel).where(BoardTokenModel.room_id == room_id, BoardTokenModel.token_id == token_id))
        await session.commit()

    @staticmethod
    def _to_domain(model: BoardTokenModel) -> BoardToken:
        return BoardToken(
            token_id=model.token_id,
            owner_user_id=model.owner_user_id,
            name=model.name,
            x=model.x,
            y=model.y,
            color=model.color,
            shape=model.shape,
        )
