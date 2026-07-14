from dataclasses import dataclass, field

import pytest

from coc_star_api.room_manager import BoardToken, RoomConnection, RoomManager, RoomMember


@dataclass
class FakeWebSocket:
    sent: list[dict[str, object]] = field(default_factory=list)

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_join_broadcasts_to_existing_members() -> None:
    manager = RoomManager()
    first_socket = FakeWebSocket()
    second_socket = FakeWebSocket()
    first = RoomConnection(RoomMember("u1", "林风眠", "gm"), first_socket)
    second = RoomConnection(RoomMember("u2", "苏鸣澈", "player"), second_socket)

    await manager.join("room-1", first)
    members = await manager.join("room-1", second)

    assert [member.user_id for member in members] == ["u1", "u2"]
    assert first_socket.sent == [{"type": "member.joined", "member": second.member.to_payload()}]
    assert second_socket.sent == []


@pytest.mark.asyncio
async def test_leave_broadcasts_and_removes_empty_room() -> None:
    manager = RoomManager()
    socket = FakeWebSocket()
    connection = RoomConnection(RoomMember("u1", "林风眠", "gm"), socket)

    await manager.join("room-1", connection)
    await manager.leave("room-1", "u1")

    assert manager.members("room-1") == []


def test_board_tokens_are_scoped_to_room() -> None:
    manager = RoomManager()
    token = BoardToken("token-1", "u1", "调查员", 0.25, 0.5, "#d7b56d", "square", "character-1")

    manager.upsert_token("room-1", token)

    assert manager.board_tokens("room-1") == [token]
    assert manager.board_tokens("room-2") == []
    assert token.to_payload()["character_id"] == "character-1"
    assert token.to_payload()["shape"] == "square"
    assert manager.remove_token("room-1", "token-1") == token
    assert manager.get_token("room-1", "token-1") is None
