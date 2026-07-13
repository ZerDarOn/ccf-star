import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


class InvalidSessionToken(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SessionClaims:
    user_id: str
    room_id: str
    display_name: str
    role: str


class SessionTokenService:
    def __init__(self, secret: str, lifetime_seconds: int = 86_400) -> None:
        self._secret = secret.encode("utf-8")
        self._lifetime_seconds = lifetime_seconds

    def issue(self, claims: SessionClaims) -> str:
        payload = {
            "sub": claims.user_id,
            "room_id": claims.room_id,
            "display_name": claims.display_name,
            "role": claims.role,
            "exp": int(time.time()) + self._lifetime_seconds,
        }
        encoded_payload = self._encode(payload)
        signature = self._sign(encoded_payload)
        return f"{encoded_payload}.{signature}"

    def verify(self, token: str) -> SessionClaims:
        try:
            encoded_payload, encoded_signature = token.split(".", maxsplit=1)
            expected_signature = self._sign(encoded_payload)
            if not hmac.compare_digest(encoded_signature, expected_signature):
                raise InvalidSessionToken("invalid signature")
            payload = json.loads(self._decode(encoded_payload))
            if int(payload["exp"]) <= int(time.time()):
                raise InvalidSessionToken("expired token")
            return SessionClaims(
                user_id=str(payload["sub"]),
                room_id=str(payload["room_id"]),
                display_name=str(payload["display_name"]),
                role=str(payload["role"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise InvalidSessionToken("malformed token") from error

    def _sign(self, encoded_payload: str) -> str:
        digest = hmac.new(self._secret, encoded_payload.encode("ascii"), hashlib.sha256).digest()
        return self._encode_bytes(digest)

    @staticmethod
    def _encode(payload: dict[str, object]) -> str:
        return SessionTokenService._encode_bytes(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    @staticmethod
    def _encode_bytes(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
