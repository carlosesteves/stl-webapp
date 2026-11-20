import pytest

from app.auth import ACCESS_COOKIE, TokenVerifier, get_verifier
from app.supabase import InvalidCredentials, SignInResult, get_auth_client
from tests.test_auth import SECRET, hs256, make_claims


class FakeAuthClient:
    def __init__(self, token=None):
        self._token = token

    def sign_in(self, email, password):
        if self._token is None:
            raise InvalidCredentials()
        return SignInResult(access_token=self._token, expires_in=3600)


@pytest.fixture
def login_client(client):
    client.follow_redirects = False
    client.app.dependency_overrides[get_verifier] = lambda: TokenVerifier(SECRET, "")
    return client


def use_auth(client, token):
    client.app.dependency_overrides[get_auth_client] = lambda: FakeAuthClient(token)


def post_login(client):
    return client.post("/admin/login", data={"email": "a@b.c", "password": "pw"})


def test_login_page_renders_form(login_client):
    response = login_client.get("/admin/login")

    assert response.status_code == 200
    assert 'name="email"' in response.text
    assert 'name="password"' in response.text


def test_admin_login_sets_cookie_and_redirects(login_client):
    use_auth(login_client, hs256(make_claims()))

    response = post_login(login_client)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    set_cookie = response.headers["set-cookie"]
    assert f"{ACCESS_COOKIE}=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_bad_credentials_show_error_without_cookie(login_client):
    use_auth(login_client, None)

    response = post_login(login_client)

    assert response.status_code == 401
    assert "Invalid email or password" in response.text
    assert "set-cookie" not in response.headers


def test_non_admin_login_is_forbidden_without_cookie(login_client):
    use_auth(login_client, hs256(make_claims(app_metadata={"role": "user"})))

    response = post_login(login_client)

    assert response.status_code == 403
    assert "set-cookie" not in response.headers


def test_logout_clears_cookie_and_redirects(login_client):
    response = login_client.post("/admin/logout")

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"
    assert f'{ACCESS_COOKIE}=""' in response.headers["set-cookie"]
