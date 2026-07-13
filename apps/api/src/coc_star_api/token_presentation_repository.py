from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from coc_star_api.models import TokenFaceModel, TokenPresentationModel
from coc_star_api.token_presentation import TokenFace, TokenPresentation


class TokenPresentationRepository:
    async def list_presentations(self, session: AsyncSession, token_ids: list[str]) -> list[TokenPresentation]:
        if not token_ids:
            return []
        result = await session.scalars(select(TokenPresentationModel).where(TokenPresentationModel.token_id.in_(token_ids)))
        return [self._to_presentation(model) for model in result]

    async def list_faces(self, session: AsyncSession, token_ids: list[str]) -> list[TokenFace]:
        if not token_ids:
            return []
        result = await session.scalars(select(TokenFaceModel).where(TokenFaceModel.token_id.in_(token_ids)))
        return [self._to_face(model) for model in result]

    async def upsert_presentation(self, session: AsyncSession, presentation: TokenPresentation) -> None:
        model = await session.get(TokenPresentationModel, presentation.token_id)
        if model is None:
            model = TokenPresentationModel(token_id=presentation.token_id)
            session.add(model)
        model.token_type = presentation.token_type
        model.image_url = presentation.image_url
        model.scale = presentation.scale
        model.active_face_id = presentation.active_face_id
        await session.commit()

    async def upsert_face(self, session: AsyncSession, face: TokenFace) -> None:
        model = await session.get(TokenFaceModel, face.face_id)
        if model is None:
            model = TokenFaceModel(face_id=face.face_id, token_id=face.token_id)
            session.add(model)
        model.token_id = face.token_id
        model.label = face.label
        model.image_url = face.image_url
        await session.commit()

    async def delete_face(self, session: AsyncSession, token_id: str, face_id: str) -> None:
        await session.execute(delete(TokenFaceModel).where(TokenFaceModel.token_id == token_id, TokenFaceModel.face_id == face_id))
        await session.commit()

    @staticmethod
    def _to_presentation(model: TokenPresentationModel) -> TokenPresentation:
        return TokenPresentation(model.token_id, model.token_type, model.image_url, model.scale, model.active_face_id)

    @staticmethod
    def _to_face(model: TokenFaceModel) -> TokenFace:
        return TokenFace(model.face_id, model.token_id, model.label, model.image_url)
