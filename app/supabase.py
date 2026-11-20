from dataclasses import dataclass

import httpx
from fastapi import Depends

from app.config import Settings, get_settings


class InvalidCredentials(Exception):
    pass


@dataclass
class SignInResult:
    access_token: str
    expires_in: int


class SupabaseAuthClient:
    def __init__(self, base_url: str, anon_key: str):
        self._base_url = base_url.rstrip("/")
        self._anon_key = anon_key

    def sign_in(self, email: str, password: str) -> SignInResult:
        response = httpx.post(
            f"{self._base_url}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": self._anon_key},
            json={"email": email, "password": password},
            timeout=10,
        )
        if response.status_code in (400, 401, 422):
            raise InvalidCredentials()
        response.raise_for_status()
        body = response.json()
        return SignInResult(body["access_token"], body["expires_in"])


def get_auth_client(settings: Settings = Depends(get_settings)) -> SupabaseAuthClient:
    return SupabaseAuthClient(settings.supabase_url, settings.supabase_anon_key)
