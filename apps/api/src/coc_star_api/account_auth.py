import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


class InvalidAccountToken(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AccountClaims:
    user_id: str
    username: str
    token_type: str


class AccountTokenService:
    def __init__(self, secret: str, access_lifetime_seconds: int = 900, refresh_lifetime_seconds: int = 2_592_000) -> None:
        self._secret = secret.encode("utf-8")
        self._access_lifetime_seconds = access_lifetime_seconds
        self._refresh_lifetime_seconds = refresh_lifetime_seconds

    def issue_pair(self, claims: AccountClaims) -> dict[str, str]:
        return {
            "access_token": self.issue(claims, "access", self._access_lifetime_seconds),
            "refresh_token": self.issue(claims, "refresh", self._refresh_lifetime_seconds),
        }

    def issue(self, claims: AccountClaims, token_type: str, lifetime_seconds: int) -> str:
        payload = {"sub": claims.user_id, "username": claims.username, "type": token_type, "exp": int(time.time()) + lifetime_seconds}
        encoded = self._encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = self._sign(encoded)
        return f"{encoded}.{signature}"

    def verify(self, token: str, expected_type: str) -> AccountClaims:
        try:
            encoded, signature = token.split(".", maxsplit=1)
            if not hmac.compare_digest(signature, self._sign(encoded)):
                raise InvalidAccountToken("invalid signature")
            payload = json.loads(self._decode(encoded))
            if payload["type"] != expected_type or int(payload["exp"]) <= int(time.time()):
                raise InvalidAccountToken("invalid account token")
            return AccountClaims(str(payload["sub"]), str(payload["username"]), str(payload["type"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise InvalidAccountToken("malformed account token") from error

    def _sign(self, encoded: str) -> str:
        return self._encode(hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest())

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
