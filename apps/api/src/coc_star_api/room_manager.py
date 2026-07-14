from dataclasses import dataclass, replace

from fastapi import WebSocket

from coc_star_api.token_presentation import TokenFace, TokenPresentation
from coc_star_api.scene_layer import SceneLayer
from coc_star_api.room_bgm import BgmPlayback
from coc_star_api.room_chat import RoomChatTab


@dataclass(slots=True, frozen=True)
class RoomMember:
    user_id: str
    display_name: str
    role: str

    def to_payload(self) -> dict[str, str]:
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "role": self.role,
        }


@dataclass(slots=True)
class RoomConnection:
    member: RoomMember
    websocket: WebSocket


@dataclass(slots=True, frozen=True)
class BoardToken:
    token_id: str
    owner_user_id: str
    name: str
    x: float
    y: float
    color: str
    shape: str = "circle"

    def to_payload(self) -> dict[str, str | float]:
        return {
            "token_id": self.token_id,
            "owner_user_id": self.owner_user_id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "color": self.color,
            "shape": self.shape,
        }


@dataclass(slots=True, frozen=True)
class RoomScene:
    scene_id: str
    name: str
    background_url: str
    is_active: bool = False

    def to_payload(self) -> dict[str, str | bool]:
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "background_url": self.background_url,
            "is_active": self.is_active,
        }


class RoomManager:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[str, RoomConnection]] = {}
        self._boards: dict[str, dict[str, BoardToken]] = {}
        self._presentations: dict[str, dict[str, TokenPresentation]] = {}
        self._faces: dict[str, dict[str, TokenFace]] = {}
        self._scenes: dict[str, dict[str, RoomScene]] = {}
        self._active_scenes: dict[str, str] = {}
        self._scene_layers: dict[str, dict[str, SceneLayer]] = {}
        self._bgm_playback: dict[str, dict[str, BgmPlayback]] = {}
        self._chat_tabs: dict[str, dict[str, RoomChatTab]] = {}
        self._known_rooms: set[str] = set()

    def create_room(self, room_id: str) -> None:
        self._known_rooms.add(room_id)

    def has_room(self, room_id: str) -> bool:
        return room_id in self._known_rooms

    def remove_room(self, room_id: str) -> None:
        self._known_rooms.discard(room_id)
        self._rooms.pop(room_id, None)
        self._boards.pop(room_id, None)
        self._presentations.pop(room_id, None)
        self._faces.pop(room_id, None)
        self._scenes.pop(room_id, None)
        self._active_scenes.pop(room_id, None)
        self._scene_layers.pop(room_id, None)
        self._bgm_playback.pop(room_id, None)
        self._chat_tabs.pop(room_id, None)

    def members(self, room_id: str) -> list[RoomMember]:
        room = self._rooms.get(room_id, {})
        return [connection.member for connection in room.values()]

    def connection(self, room_id: str, user_id: str) -> RoomConnection | None:
        return self._rooms.get(room_id, {}).get(user_id)

    def update_member_role(self, room_id: str, user_id: str, role: str) -> RoomMember | None:
        connection = self.connection(room_id, user_id)
        if connection is None:
            return None
        connection.member = replace(connection.member, role=role)
        return connection.member

    def detach(self, room_id: str, user_id: str) -> RoomConnection | None:
        room = self._rooms.get(room_id)
        if room is None:
            return None
        connection = room.pop(user_id, None)
        if not room:
            self._rooms.pop(room_id, None)
        return connection

    def board_tokens(self, room_id: str) -> list[BoardToken]:
        return list(self._boards.get(room_id, {}).values())

    def get_token(self, room_id: str, token_id: str) -> BoardToken | None:
        return self._boards.get(room_id, {}).get(token_id)

    def upsert_token(self, room_id: str, token: BoardToken) -> None:
        self._boards.setdefault(room_id, {})[token.token_id] = token

    def remove_token(self, room_id: str, token_id: str) -> BoardToken | None:
        board = self._boards.get(room_id)
        if board is None:
            return None
        token = board.pop(token_id, None)
        if not board:
            self._boards.pop(room_id, None)
        return token

    def set_token_presentations(self, room_id: str, presentations: list[TokenPresentation], faces: list[TokenFace]) -> None:
        self._presentations[room_id] = {item.token_id: item for item in presentations}
        self._faces[room_id] = {item.face_id: item for item in faces}

    def presentation(self, room_id: str, token_id: str) -> TokenPresentation:
        return self._presentations.get(room_id, {}).get(token_id, TokenPresentation(token_id))

    def faces(self, room_id: str, token_id: str) -> list[TokenFace]:
        return [face for face in self._faces.get(room_id, {}).values() if face.token_id == token_id]

    def upsert_presentation(self, room_id: str, presentation: TokenPresentation) -> None:
        self._presentations.setdefault(room_id, {})[presentation.token_id] = presentation

    def upsert_face(self, room_id: str, face: TokenFace) -> None:
        self._faces.setdefault(room_id, {})[face.face_id] = face

    def remove_face(self, room_id: str, face_id: str) -> TokenFace | None:
        return self._faces.get(room_id, {}).pop(face_id, None)

    def set_scenes(self, room_id: str, scenes: list[RoomScene], active_scene_id: str | None) -> None:
        self._scenes[room_id] = {scene.scene_id: scene for scene in scenes}
        if active_scene_id is not None:
            self._active_scenes[room_id] = active_scene_id

    def scenes(self, room_id: str) -> list[RoomScene]:
        return list(self._scenes.get(room_id, {}).values())

    def active_scene(self, room_id: str) -> RoomScene | None:
        active_scene_id = self._active_scenes.get(room_id)
        return self._scenes.get(room_id, {}).get(active_scene_id) if active_scene_id else None

    def upsert_scene(self, room_id: str, scene: RoomScene) -> None:
        self._scenes.setdefault(room_id, {})[scene.scene_id] = scene
        if scene.is_active:
            self._active_scenes[room_id] = scene.scene_id

    def activate_scene(self, room_id: str, scene_id: str) -> RoomScene | None:
        scene = self._scenes.get(room_id, {}).get(scene_id)
        if scene is None:
            return None
        scenes = self._scenes[room_id]
        for current_id, current in list(scenes.items()):
            scenes[current_id] = replace(current, is_active=current_id == scene_id)
        self._active_scenes[room_id] = scene_id
        return scenes[scene_id]

    def set_scene_layers(self, layers: list[SceneLayer]) -> None:
        for layer in layers:
            self._scene_layers.setdefault(layer.scene_id, {})[layer.layer_id] = layer

    def scene_layers(self, scene_id: str) -> list[SceneLayer]:
        return sorted(self._scene_layers.get(scene_id, {}).values(), key=lambda layer: (layer.z_index, layer.layer_id))

    def upsert_scene_layer(self, layer: SceneLayer) -> None:
        self._scene_layers.setdefault(layer.scene_id, {})[layer.layer_id] = layer

    def remove_scene_layer(self, scene_id: str, layer_id: str) -> SceneLayer | None:
        return self._scene_layers.get(scene_id, {}).pop(layer_id, None)

    def bgm_playback(self, room_id: str) -> list[BgmPlayback]:
        return list(self._bgm_playback.get(room_id, {}).values())

    def set_bgm_playback(self, room_id: str, playback: BgmPlayback) -> None:
        self._bgm_playback.setdefault(room_id, {})[playback.slot] = playback

    def set_chat_tabs(self, room_id: str, tabs: list[RoomChatTab]) -> None:
        self._chat_tabs[room_id] = {tab.tab_id: tab for tab in tabs}

    def chat_tabs(self, room_id: str) -> list[RoomChatTab]:
        return sorted(self._chat_tabs.get(room_id, {}).values(), key=lambda tab: (tab.sort_order, tab.tab_id))

    def chat_tab(self, room_id: str, tab_id: str | None) -> RoomChatTab | None:
        tabs = self._chat_tabs.get(room_id, {})
        if tab_id and tab_id in tabs:
            return tabs[tab_id]
        return next((tab for tab in tabs.values() if tab.tab_type == "main"), None)

    def upsert_chat_tab(self, tab: RoomChatTab) -> None:
        self._chat_tabs.setdefault(tab.room_id, {})[tab.tab_id] = tab

    async def join(self, room_id: str, connection: RoomConnection) -> list[RoomMember]:
        room = self._rooms.setdefault(room_id, {})
        room[connection.member.user_id] = connection
        await self.broadcast(
            room_id,
            {
                "type": "member.joined",
                "member": connection.member.to_payload(),
            },
            exclude_user_id=connection.member.user_id,
        )
        return self.members(room_id)

    async def leave(self, room_id: str, user_id: str) -> None:
        room = self._rooms.get(room_id)
        if room is None:
            return
        connection = room.pop(user_id, None)
        if connection is None:
            return
        await self.broadcast(
            room_id,
            {"type": "member.left", "user_id": user_id},
            exclude_user_id=user_id,
        )
        if not room:
            self._rooms.pop(room_id, None)

    async def broadcast(
        self,
        room_id: str,
        payload: dict[str, object],
        *,
        exclude_user_id: str | None = None,
    ) -> None:
        room = self._rooms.get(room_id, {})
        for user_id, connection in list(room.items()):
            if user_id == exclude_user_id:
                continue
            try:
                await connection.websocket.send_json(payload)
            except Exception:
                room.pop(user_id, None)
