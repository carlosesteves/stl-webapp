import pytest
from sqlalchemy import select

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


def test_create_item(admin_client, session):
    response = admin_client.post(
        "/admin/items",
        data={"name": "New", "description": "Desc", "published": "on"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    item = session.scalars(select(Item)).one()
    assert (item.name, item.description, item.published) == ("New", "Desc", True)


def test_create_item_unchecked_box_is_unpublished(admin_client, session):
    admin_client.post("/admin/items", data={"name": "New"})

    assert session.scalars(select(Item)).one().published is False


def test_new_item_form_renders(admin_client):
    response = admin_client.get("/admin/items/new")

    assert response.status_code == 200
    assert 'name="name"' in response.text
