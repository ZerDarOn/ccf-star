from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class SceneLayer:
    layer_id: str
    scene_id: str
    layer_type: str
    name: str
    image_url: str | None
    text: str
    x: float
    y: float
    width: float
    height: float
    z_index: int
    visible: bool

    def to_payload(self) -> dict[str, str | float | int | bool | None]:
        return {
            "layer_id": self.layer_id,
            "scene_id": self.scene_id,
            "layer_type": self.layer_type,
            "name": self.name,
            "image_url": self.image_url,
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "z_index": self.z_index,
            "visible": self.visible,
        }
