from dataclasses import dataclass

from coc_star_api.token_presentation import TokenFace


@dataclass(frozen=True)
class FaceMatch:
    face: TokenFace | None
    visible_text: str


def match_face(text: str, faces: list[TokenFace]) -> FaceMatch:
    candidates: list[tuple[str, TokenFace]] = []
    for face in faces:
        for prefix in ("#", "@"):
            marker = f"{prefix}{face.label}"
            if text.endswith(marker):
                candidates.append((marker, face))
    if not candidates:
        return FaceMatch(None, text)
    marker, face = max(candidates, key=lambda item: len(item[0]))
    return FaceMatch(face, text[: -len(marker)].rstrip())
