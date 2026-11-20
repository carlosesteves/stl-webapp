from collections.abc import Callable

import jwt
from jwt import PyJWKClient

SYMMETRIC_ALGORITHMS = ["HS256"]
ASYMMETRIC_ALGORITHMS = ["ES256", "RS256"]
AUDIENCE = "authenticated"


class InvalidToken(Exception):
    pass


class TokenVerifier:
    """Verifies Supabase access tokens (HS256 shared secret or JWKS-signed)."""

    def __init__(
        self,
        jwt_secret: str,
        jwks_url: str,
        key_resolver: Callable[[str], object] | None = None,
    ):
        self._jwt_secret = jwt_secret
        self._jwks_url = jwks_url
        if key_resolver is None and jwks_url:
            client = PyJWKClient(jwks_url, cache_keys=True)
            key_resolver = lambda token: client.get_signing_key_from_jwt(token).key  # noqa: E731
        self._key_resolver = key_resolver

    def verify(self, token: str) -> dict:
        try:
            algorithm = jwt.get_unverified_header(token).get("alg")
            key, algorithms = self._key_for(algorithm, token)
            return jwt.decode(token, key, algorithms=algorithms, audience=AUDIENCE)
        except jwt.PyJWTError as error:
            raise InvalidToken(str(error)) from error

    def _key_for(self, algorithm: str | None, token: str):
        if algorithm in SYMMETRIC_ALGORITHMS and self._jwt_secret:
            return self._jwt_secret, SYMMETRIC_ALGORITHMS
        if algorithm in ASYMMETRIC_ALGORITHMS and self._key_resolver:
            return self._key_resolver(token), ASYMMETRIC_ALGORITHMS
        raise InvalidToken(f"Unsupported or unconfigured algorithm: {algorithm}")
