from coc_star_api.room_manager import RoomManager, RoomScene


def test_room_manager_tracks_active_scene() -> None:
    manager = RoomManager()
    first = RoomScene("scene-1", "车站", "https://example.com/station.jpg", True)
    second = RoomScene("scene-2", "地下室", "https://example.com/basement.jpg")

    manager.set_scenes("room-1", [first, second], first.scene_id)
    activated = manager.activate_scene("room-1", second.scene_id)

    assert activated == RoomScene("scene-2", "地下室", "https://example.com/basement.jpg", True)
    assert manager.active_scene("room-1") == activated
