import json

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from coc_star_api.models import KnowledgeBaseModel, KnowledgeDocumentModel, RoomKnowledgeConfigModel


class KnowledgeRepository:
    async def list_bases(self, session: AsyncSession, user_id: str) -> list[KnowledgeBaseModel]:
        result = await session.scalars(select(KnowledgeBaseModel).where(KnowledgeBaseModel.user_id == user_id).order_by(KnowledgeBaseModel.created_at.desc()))
        return list(result)

    async def get_base(self, session: AsyncSession, base_id: str, user_id: str) -> KnowledgeBaseModel | None:
        base = await session.get(KnowledgeBaseModel, base_id)
        return base if base and base.user_id == user_id else None

    async def document_counts(self, session: AsyncSession, base_ids: list[str]) -> dict[str, int]:
        if not base_ids:
            return {}
        rows = await session.execute(
            select(KnowledgeDocumentModel.knowledge_base_id, func.count(KnowledgeDocumentModel.document_id))
            .where(KnowledgeDocumentModel.knowledge_base_id.in_(base_ids))
            .group_by(KnowledgeDocumentModel.knowledge_base_id)
        )
        return {base_id: count for base_id, count in rows}

    async def upsert_base(self, session: AsyncSession, base: KnowledgeBaseModel) -> None:
        current = await session.get(KnowledgeBaseModel, base.knowledge_base_id)
        if current is None:
            session.add(base)
        else:
            current.name = base.name
            current.description = base.description
            current.kind = base.kind
            current.parent_id = base.parent_id
        await session.commit()

    async def delete_base(self, session: AsyncSession, base_id: str, user_id: str) -> list[str] | None:
        bases = await self.list_bases(session, user_id)
        if base_id not in {base.knowledge_base_id for base in bases}:
            return None
        children: dict[str, list[str]] = {}
        for base in bases:
            if base.parent_id:
                children.setdefault(base.parent_id, []).append(base.knowledge_base_id)
        deleted_ids: list[str] = []
        pending = [base_id]
        while pending:
            current_id = pending.pop()
            deleted_ids.append(current_id)
            pending.extend(children.get(current_id, []))
        await session.execute(delete(KnowledgeDocumentModel).where(KnowledgeDocumentModel.knowledge_base_id.in_(deleted_ids)))
        configs = await session.scalars(select(RoomKnowledgeConfigModel))
        for config in configs:
            try:
                mounted_ids = json.loads(config.knowledge_base_ids)
            except json.JSONDecodeError:
                mounted_ids = []
            if isinstance(mounted_ids, list):
                kept_ids = [item for item in mounted_ids if isinstance(item, str) and item not in deleted_ids]
                if kept_ids != mounted_ids:
                    config.knowledge_base_ids = json.dumps(kept_ids, ensure_ascii=False)
        await session.execute(delete(KnowledgeBaseModel).where(KnowledgeBaseModel.knowledge_base_id.in_(deleted_ids)))
        await session.commit()
        return deleted_ids

    async def list_documents(self, session: AsyncSession, base_id: str) -> list[KnowledgeDocumentModel]:
        result = await session.scalars(select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.knowledge_base_id == base_id).order_by(KnowledgeDocumentModel.updated_at.desc()))
        return list(result)

    async def get_document(self, session: AsyncSession, document_id: str) -> KnowledgeDocumentModel | None:
        return await session.get(KnowledgeDocumentModel, document_id)

    async def upsert_document(self, session: AsyncSession, document: KnowledgeDocumentModel) -> None:
        current = await session.get(KnowledgeDocumentModel, document.document_id)
        if current is None:
            session.add(document)
        else:
            for field in ("knowledge_base_id", "title", "content", "category", "source_type", "source_name", "mime_type", "ai_enabled"):
                setattr(current, field, getattr(document, field))
        await session.commit()

    async def delete_document(self, session: AsyncSession, document_id: str) -> bool:
        document = await session.get(KnowledgeDocumentModel, document_id)
        if document is None:
            return False
        await session.delete(document)
        await session.commit()
        return True

    async def get_room_config(self, session: AsyncSession, room_id: str) -> RoomKnowledgeConfigModel | None:
        return await session.get(RoomKnowledgeConfigModel, room_id)

    async def upsert_room_config(self, session: AsyncSession, config: RoomKnowledgeConfigModel) -> None:
        current = await session.get(RoomKnowledgeConfigModel, config.room_id)
        if current is None:
            session.add(config)
        else:
            current.knowledge_base_ids = config.knowledge_base_ids
        await session.commit()
