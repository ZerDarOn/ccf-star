from coc_star_api.room_bgm import BgmPlayback, RoomBgm
from coc_star_api.room_manager import RoomManager


def test_bgm_payload_and_playback_are_room_scoped() -> None:
    track = RoomBgm("track-1", "room-1", "bgm01", "夜雨", "/uploads/rain.mp3")
    manager = RoomManager()
    manager.set_bgm_playback("room-1", BgmPlayback("bgm01", "play", True, 12.5))

    assert track.to_payload()["slot"] == "bgm01"
    assert manager.bgm_playback("room-1")[0].position == 12.5
    assert manager.bgm_playback("room-2") == []
