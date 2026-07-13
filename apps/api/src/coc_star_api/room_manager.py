from dataclasses import dataclass

from fastapi import WebSocket


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

    def to_payload(self) -> dict[str, str | float]:
        return {
            "token_id": self.token_id,
            "owner_user_id": self.owner_user_id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "color": self.color,
        }


class RoomManager:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[str, RoomConnection]] = {}
        self._boards: dict[str, dict[str, BoardToken]] = {}
        self._known_rooms: set[str] = set()

    def create_room(self, room_id: str) -> None:
        self._known_rooms.add(room_id)

    def has_room(self, room_id: str) -> bool:
        return room_id in self._known_rooms

    def members(self, room_id: str) -> list[RoomMember]:
        room = self._rooms.get(room_id, {})
        return [connection.member for connection in room.values()]

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
