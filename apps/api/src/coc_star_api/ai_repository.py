import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coc_star_api.models import AiProviderConfigModel, AiRunLogModel, RoomAiConfigModel


class AiRepository:
    async def list_providers(self, session: AsyncSession, user_id: str) -> list[AiProviderConfigModel]:
        result = await session.scalars(select(AiProviderConfigModel).where(AiProviderConfigModel.user_id == user_id).order_by(AiProviderConfigModel.created_at))
        return list(result)

    async def get_provider(self, session: AsyncSession, provider_id: str, user_id: str) -> AiProviderConfigModel | None:
        provider = await session.get(AiProviderConfigModel, provider_id)
        return provider if provider and provider.user_id == user_id else None

    async def upsert_provider(self, session: AsyncSession, provider: AiProviderConfigModel) -> None:
        current = await session.get(AiProviderConfigModel, provider.provider_id)
        if current is None:
            session.add(provider)
        else:
            for field in ("name", "provider_type", "base_url", "model", "api_key", "enabled"):
                setattr(current, field, getattr(provider, field))
        await session.commit()

    async def delete_provider(self, session: AsyncSession, provider_id: str, user_id: str) -> bool:
        provider = await self.get_provider(session, provider_id, user_id)
        if provider is None:
            return False
        await session.delete(provider)
        await session.commit()
        return True

    async def get_room_config(self, session: AsyncSession, room_id: str) -> RoomAiConfigModel | None:
        return await session.get(RoomAiConfigModel, room_id)

    async def upsert_room_config(self, session: AsyncSession, config: RoomAiConfigModel) -> None:
        current = await session.get(RoomAiConfigModel, config.room_id)
        if current is None:
            session.add(config)
        else:
            for field in ("provider_id", "enabled", "assistant_name", "system_prompt", "avatar_url", "trigger_mode", "scene_context_enabled", "knowledge_base_ids"):
                setattr(current, field, getattr(config, field))
        await session.commit()

    async def add_log(self, session: AsyncSession, log: AiRunLogModel) -> None:
        session.add(log)
        await session.commit()

    async def list_logs(self, session: AsyncSession, room_id: str, limit: int = 100) -> list[AiRunLogModel]:
        result = await session.scalars(select(AiRunLogModel).where(AiRunLogModel.room_id == room_id).order_by(AiRunLogModel.created_at.desc()).limit(limit))
        return list(result)


def encode_knowledge_base_ids(ids: list[str]) -> str:
    return json.dumps(ids, ensure_ascii=False)


def decode_knowledge_base_ids(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []
