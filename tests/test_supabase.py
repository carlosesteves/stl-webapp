import httpx
import pytest

from app.supabase import AuthServiceError, InvalidCredentials, SupabaseAuthClient


def client_returning(monkeypatch, status, json=None):
    def fake_post(url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(status, json=json or {}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    return SupabaseAuthClient("https://x.supabase.co", "anon")


def test_success_returns_token(monkeypatch):
    client = client_returning(monkeypatch, 200, {"access_token": "tok", "expires_in": 3600})

    result = client.sign_in("a@b.c", "pw")

    assert (result.access_token, result.expires_in) == ("tok", 3600)


@pytest.mark.parametrize("status", [400, 422])
def test_bad_credentials_statuses(monkeypatch, status):
    client = client_returning(monkeypatch, status, {"error_code": "invalid_credentials"})

    with pytest.raises(InvalidCredentials):
        client.sign_in("a@b.c", "pw")


@pytest.mark.parametrize("status", [401, 403, 404, 500, 502])
def test_other_statuses_are_service_errors_with_detail(monkeypatch, status):
    client = client_returning(monkeypatch, status, {"message": "Invalid API key"})

    with pytest.raises(AuthServiceError) as error:
        client.sign_in("a@b.c", "pw")

    assert str(status) in str(error.value)
    assert "Invalid API key" in str(error.value)


def test_network_failure_is_a_service_error(monkeypatch):
    def failing_post(url, **kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "post", failing_post)
    client = SupabaseAuthClient("https://x.supabase.co", "anon")

    with pytest.raises(AuthServiceError):
        client.sign_in("a@b.c", "pw")
