from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class RoomChatTab:
    tab_id: str
    room_id: str
    name: str
    tab_type: str
    show_dialogue: bool
    is_default: bool
    sort_order: int

    def to_payload(self) -> dict[str, str | bool | int]:
        return {
            "tab_id": self.tab_id,
            "room_id": self.room_id,
            "name": self.name,
            "tab_type": self.tab_type,
            "show_dialogue": self.show_dialogue,
            "is_default": self.is_default,
            "sort_order": self.sort_order,
        }
