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


def test_edit_form_prefilled(admin_client, session):
    item = Item(name="Old")
    session.add(item)
    session.commit()

    response = admin_client.get(f"/admin/items/{item.id}/edit")

    assert response.status_code == 200
    assert 'value="Old"' in response.text


def test_update_item(admin_client, session):
    item = Item(name="Old", published=True)
    session.add(item)
    session.commit()

    response = admin_client.post(
        f"/admin/items/{item.id}", data={"name": "Renamed", "description": "D"}
    )

    assert response.status_code == 303
    session.refresh(item)
    assert (item.name, item.description, item.published) == ("Renamed", "D", False)


def test_edit_missing_item_is_404(admin_client):
    assert admin_client.get("/admin/items/999/edit").status_code == 404
    assert admin_client.post("/admin/items/999", data={"name": "x"}).status_code == 404


def test_delete_item(admin_client, session):
    item = Item(name="Doomed")
    session.add(item)
    session.commit()

    response = admin_client.post(f"/admin/items/{item.id}/delete")

    assert response.status_code == 303
    assert session.scalars(select(Item)).all() == []


def test_delete_missing_item_is_404(admin_client):
    assert admin_client.post("/admin/items/999/delete").status_code == 404


def test_item_routes_require_admin(client):
    client.follow_redirects = False

    assert client.post("/admin/items", data={"name": "x"}).status_code == 303
    assert client.post("/admin/items/1/delete").status_code == 303
