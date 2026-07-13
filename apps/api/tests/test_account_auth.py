import pytest

from coc_star_api.account_auth import AccountClaims, AccountTokenService, InvalidAccountToken
from coc_star_api.passwords import PasswordHasher


def test_password_hash_round_trip() -> None:
    hasher = PasswordHasher()
    encoded = hasher.hash("correct horse battery staple")

    assert hasher.verify("correct horse battery staple", encoded)
    assert not hasher.verify("wrong password", encoded)


def test_refresh_token_has_expected_type() -> None:
    service = AccountTokenService("test-secret")
    claims = AccountClaims("user-1", "player", "access")
    pair = service.issue_pair(claims)

    assert service.verify(pair["access_token"], "access") == claims
    assert service.verify(pair["refresh_token"], "refresh").user_id == "user-1"
    with pytest.raises(InvalidAccountToken):
        service.verify(pair["refresh_token"], "access")
