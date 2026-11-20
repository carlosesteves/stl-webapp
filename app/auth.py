from collections.abc import Callable

from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient

from app.config import get_settings

SYMMETRIC_ALGORITHMS = ["HS256"]
ASYMMETRIC_ALGORITHMS = ["ES256", "RS256"]
AUDIENCE = "authenticated"
ACCESS_COOKIE = "access_token"
ADMIN_ROLE = "admin"


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


@lru_cache
def get_verifier() -> TokenVerifier:
    settings = get_settings()
    jwks_url = (
        f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        if settings.supabase_url
        else ""
    )
    return TokenVerifier(jwt_secret=settings.supabase_jwt_secret, jwks_url=jwks_url)


def require_admin(
    request: Request, verifier: TokenVerifier = Depends(get_verifier)
) -> dict:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        claims = verifier.verify(token)
    except InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token")
    if claims.get("app_metadata", {}).get("role") != ADMIN_ROLE:
        raise HTTPException(status_code=403, detail="Admin only")
    return claims
