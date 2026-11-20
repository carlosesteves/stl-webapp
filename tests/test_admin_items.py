import pytest

from app.auth import require_admin
from app.models import Item


@pytest.fixture
def admin_client(client):
    client.follow_redirects = False
    client.app.dependency_overrides[require_admin] = lambda: {"sub": "admin"}
    return client


def test_unauthenticated_admin_redirects_to_login(client):
    client.follow_redirects = False

    response = client.get("/admin")

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_admin_list_shows_published_and_unpublished(admin_client, session):
    session.add_all([Item(name="Visible", published=True), Item(name="Hidden")])
    session.commit()

    response = admin_client.get("/admin")

    assert response.status_code == 200
    assert "Visible" in response.text
    assert "Hidden" in response.text
