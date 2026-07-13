import pytest

from coc_star_api.session_auth import InvalidSessionToken, SessionClaims, SessionTokenService


def test_session_token_round_trip() -> None:
    service = SessionTokenService("test-secret")
    claims = SessionClaims("user-1", "room-1", "林风眠", "gm")

    assert service.verify(service.issue(claims)) == claims


def test_tampered_session_token_is_rejected() -> None:
    service = SessionTokenService("test-secret")
    token = service.issue(SessionClaims("user-1", "room-1", "林风眠", "player"))

    with pytest.raises(InvalidSessionToken):
        service.verify(f"{token}tampered")
