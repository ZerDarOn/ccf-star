from coc_star_api.room_chat import RoomChatTab
from coc_star_api.room_manager import RoomManager


def test_chat_tabs_keep_main_as_fallback_and_preserve_dialogue_setting() -> None:
    manager = RoomManager()
    main = RoomChatTab("room:main", "room", "主频道", "main", True, True, 0)
    info = RoomChatTab("room:info", "room", "信息", "info", False, True, 1)
    manager.set_chat_tabs("room", [main, info])

    assert manager.chat_tab("room", "room:info") == info
    assert manager.chat_tab("room", "missing") == main
    assert manager.chat_tabs("room") == [main, info]
