from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from coc_star_api.models import SceneLayerModel
from coc_star_api.scene_layer import SceneLayer


class SceneLayerRepository:
    async def list_by_scenes(self, session: AsyncSession, scene_ids: list[str]) -> list[SceneLayer]:
        if not scene_ids:
            return []
        result = await session.scalars(select(SceneLayerModel).where(SceneLayerModel.scene_id.in_(scene_ids)))
        return [self._to_domain(model) for model in result]

    async def upsert(self, session: AsyncSession, layer: SceneLayer) -> None:
        model = await session.get(SceneLayerModel, layer.layer_id)
        if model is None:
            model = SceneLayerModel(layer_id=layer.layer_id)
            session.add(model)
        model.scene_id = layer.scene_id
        model.layer_type = layer.layer_type
        model.name = layer.name
        model.image_url = layer.image_url
        model.text = layer.text
        model.x = layer.x
        model.y = layer.y
        model.width = layer.width
        model.height = layer.height
        model.z_index = layer.z_index
        model.visible = layer.visible
        await session.commit()

    async def delete(self, session: AsyncSession, scene_id: str, layer_id: str) -> None:
        await session.execute(delete(SceneLayerModel).where(SceneLayerModel.scene_id == scene_id, SceneLayerModel.layer_id == layer_id))
        await session.commit()

    @staticmethod
    def _to_domain(model: SceneLayerModel) -> SceneLayer:
        return SceneLayer(model.layer_id, model.scene_id, model.layer_type, model.name, model.image_url, model.text, model.x, model.y, model.width, model.height, model.z_index, model.visible)
