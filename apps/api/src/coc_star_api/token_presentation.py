from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class TokenPresentation:
    token_id: str
    token_type: str = "npc"
    image_url: str | None = None
    scale: float = 1.0
    active_face_id: str | None = None

    def to_payload(self) -> dict[str, str | float | None]:
        return {
            "token_id": self.token_id,
            "token_type": self.token_type,
            "image_url": self.image_url,
            "scale": self.scale,
            "active_face_id": self.active_face_id,
        }


@dataclass(slots=True, frozen=True)
class TokenFace:
    face_id: str
    token_id: str
    label: str
    image_url: str
    trigger: str | None = None

    def to_payload(self) -> dict[str, str]:
        return {
            "face_id": self.face_id,
            "token_id": self.token_id,
            "label": self.label,
            "image_url": self.image_url,
            "trigger": self.trigger or self.label,
        }
