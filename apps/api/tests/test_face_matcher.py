from coc_star_api.face_matcher import match_face
from coc_star_api.token_presentation import TokenFace


def test_face_match_hides_hash_command_and_prefers_longest_label() -> None:
    faces = [
        TokenFace("f1", "t1", "哭", "/uploads/cry.png"),
        TokenFace("f2", "t1", "哭泣", "/uploads/crying.png"),
    ]

    result = match_face("我真的很难过 #哭泣", faces)

    assert result.face == faces[1]
    assert result.visible_text == "我真的很难过"


def test_face_match_supports_ccfolia_style_at_command() -> None:
    face = TokenFace("f1", "t1", "愤怒", "/uploads/angry.png")

    result = match_face("@愤怒", [face])

    assert result.face == face
    assert result.visible_text == ""
