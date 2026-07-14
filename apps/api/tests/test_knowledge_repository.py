import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from coc_star_api.database import Base
from coc_star_api.knowledge_repository import KnowledgeRepository
from coc_star_api.models import KnowledgeBaseModel, KnowledgeDocumentModel, RoomKnowledgeConfigModel


@pytest.mark.asyncio
async def test_deleting_a_parent_knowledge_base_removes_descendants_documents_and_mounts(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'knowledge.db').as_posix()}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = KnowledgeRepository()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add_all([
            KnowledgeBaseModel(knowledge_base_id="root", user_id="gm", parent_id=None, name="Root", kind="knowledge"),
            KnowledgeBaseModel(knowledge_base_id="child", user_id="gm", parent_id="root", name="Child", kind="knowledge"),
            KnowledgeDocumentModel(document_id="document", knowledge_base_id="child", title="Note", content="content", category="rule"),
            RoomKnowledgeConfigModel(room_id="room", knowledge_base_ids=json.dumps(["root", "child", "other"])),
        ])
        await session.commit()

        assert await repository.delete_base(session, "root", "gm") == ["root", "child"]
        assert await session.get(KnowledgeBaseModel, "root") is None
        assert await session.get(KnowledgeBaseModel, "child") is None
        assert await session.get(KnowledgeDocumentModel, "document") is None
        config = await session.get(RoomKnowledgeConfigModel, "room")
        assert config is not None
        assert json.loads(config.knowledge_base_ids) == ["other"]
    await engine.dispose()
