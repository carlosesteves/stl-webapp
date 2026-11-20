from dataclasses import dataclass

import httpx
from fastapi import Depends

from app.config import Settings, get_settings


class InvalidCredentials(Exception):
    pass


class AuthServiceError(Exception):
    """Supabase could not be reached, or rejected our request for a reason other than the user's credentials."""


@dataclass
class SignInResult:
    access_token: str
    expires_in: int


class SupabaseAuthClient:
    def __init__(self, base_url: str, anon_key: str):
        self._base_url = base_url.rstrip("/")
        self._anon_key = anon_key

    def sign_in(self, email: str, password: str) -> SignInResult:
        try:
            response = httpx.post(
                f"{self._base_url}/auth/v1/token",
                params={"grant_type": "password"},
                headers={"apikey": self._anon_key},
                json={"email": email, "password": password},
                timeout=10,
            )
        except httpx.HTTPError as error:
            raise AuthServiceError(f"Could not reach Supabase: {error!r}") from error
        if response.status_code in (400, 422):
            raise InvalidCredentials()
        if response.status_code != 200:
            raise AuthServiceError(f"Supabase answered {response.status_code}: {response.text[:300]}")
        body = response.json()
        return SignInResult(body["access_token"], body["expires_in"])


def get_auth_client(settings: Settings = Depends(get_settings)) -> SupabaseAuthClient:
    return SupabaseAuthClient(settings.supabase_url, settings.supabase_anon_key)
