from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coc_star_api.models import UserModel


class UserRepository:
    async def get_by_username(self, session: AsyncSession, username: str) -> UserModel | None:
        return await session.scalar(select(UserModel).where(UserModel.username == username))

    async def create(self, session: AsyncSession, user_id: str, username: str, password_hash: str) -> UserModel:
        user = UserModel(user_id=user_id, username=username, password_hash=password_hash)
        session.add(user)
        await session.commit()
        return user
