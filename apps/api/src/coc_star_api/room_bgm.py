from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class RoomBgm:
    bgm_id: str
    room_id: str
    slot: str
    name: str
    audio_url: str
    loop: bool = True

    def to_payload(self) -> dict[str, str | bool]:
        return {
            "bgm_id": self.bgm_id,
            "room_id": self.room_id,
            "slot": self.slot,
            "name": self.name,
            "audio_url": self.audio_url,
            "loop": self.loop,
        }


@dataclass(slots=True, frozen=True)
class BgmPlayback:
    slot: str
    action: str
    is_playing: bool
    position: float = 0.0

    def to_payload(self) -> dict[str, str | bool | float]:
        return {
            "slot": self.slot,
            "action": self.action,
            "is_playing": self.is_playing,
            "position": self.position,
        }
