from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coc_star_api.models import RoomChatTabModel
from coc_star_api.room_chat import RoomChatTab


DEFAULT_TABS = (
    ("main", "主频道", "main", True, True, 0),
    ("info", "信息", "info", False, True, 1),
    ("chat", "聊天", "chat", True, True, 2),
)


class RoomChatTabRepository:
    async def list_by_room(self, session: AsyncSession, room_id: str) -> list[RoomChatTab]:
        result = await session.scalars(
            select(RoomChatTabModel).where(RoomChatTabModel.room_id == room_id).order_by(RoomChatTabModel.sort_order, RoomChatTabModel.tab_id)
        )
        return [self._to_domain(model) for model in result]

    async def ensure_defaults(self, session: AsyncSession, room_id: str) -> list[RoomChatTab]:
        existing = await self.list_by_room(session, room_id)
        existing_types = {tab.tab_type for tab in existing if tab.is_default}
        for suffix, name, tab_type, show_dialogue, is_default, sort_order in DEFAULT_TABS:
            if tab_type in existing_types:
                continue
            session.add(RoomChatTabModel(tab_id=f"{room_id}:{suffix}", room_id=room_id, name=name, tab_type=tab_type, show_dialogue=show_dialogue, is_default=is_default, sort_order=sort_order))
        await session.commit()
        return await self.list_by_room(session, room_id)

    async def create(self, session: AsyncSession, tab: RoomChatTab) -> None:
        session.add(RoomChatTabModel(tab_id=tab.tab_id, room_id=tab.room_id, name=tab.name, tab_type=tab.tab_type, show_dialogue=tab.show_dialogue, is_default=tab.is_default, sort_order=tab.sort_order))
        await session.commit()

    @staticmethod
    def _to_domain(model: RoomChatTabModel) -> RoomChatTab:
        return RoomChatTab(model.tab_id, model.room_id, model.name, model.tab_type, model.show_dialogue, model.is_default, model.sort_order)
