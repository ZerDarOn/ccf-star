import base64
import hashlib
import hmac
import os


class PasswordHasher:
    _algorithm = "scrypt"
    _n = 16_384
    _r = 8
    _p = 1

    def hash(self, password: str) -> str:
        salt = os.urandom(16)
        digest = self._derive(password, salt, self._n, self._r, self._p)
        return "$".join(
            [self._algorithm, str(self._n), str(self._r), str(self._p), self._encode(salt), self._encode(digest)]
        )

    def verify(self, password: str, encoded: str) -> bool:
        try:
            algorithm, n, r, p, salt, expected = encoded.split("$", maxsplit=5)
            if algorithm != self._algorithm:
                return False
            actual = self._derive(password, self._decode(salt), int(n), int(r), int(p))
            return hmac.compare_digest(self._decode(expected), actual)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
