from coc_star_api.room_manager import RoomManager
from coc_star_api.scene_layer import SceneLayer


def test_scene_layers_are_sorted_by_z_index_and_can_be_removed() -> None:
    manager = RoomManager()
    foreground = SceneLayer("f", "s", "foreground", "雾", "/fog.png", "", 0.5, 0.5, 1, 1, 2, True)
    background = SceneLayer("b", "s", "background", "街道", "/street.png", "", 0.5, 0.5, 1, 1, 0, True)

    manager.set_scene_layers([foreground, background])

    assert manager.scene_layers("s") == [background, foreground]
    assert manager.remove_scene_layer("s", "f") == foreground
