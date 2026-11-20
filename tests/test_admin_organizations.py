import pytest
from sqlalchemy import select

from app.auth import require_admin
from app.models import Organization


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
    session.add_all([Organization(name="Visible", is_published=True), Organization(name="Hidden")])
    session.commit()

    response = admin_client.get("/admin")

    assert response.status_code == 200
    assert "Visible" in response.text
    assert "Hidden" in response.text


def test_create_organization(admin_client, session):
    response = admin_client.post(
        "/admin/organizations",
        data={"name": "New", "description": "Desc", "is_published": "on"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    organization = session.scalars(select(Organization)).one()
    assert (organization.name, organization.description, organization.is_published) == ("New", "Desc", True)


def test_create_organization_unchecked_box_is_unpublished(admin_client, session):
    admin_client.post("/admin/organizations", data={"name": "New"})

    assert session.scalars(select(Organization)).one().is_published is False


def test_new_organization_form_renders(admin_client):
    response = admin_client.get("/admin/organizations/new")

    assert response.status_code == 200
    assert 'name="name"' in response.text


def test_edit_form_prefilled(admin_client, session):
    organization = Organization(name="Old")
    session.add(organization)
    session.commit()

    response = admin_client.get(f"/admin/organizations/{organization.id}/edit")

    assert response.status_code == 200
    assert 'value="Old"' in response.text


def test_update_organization(admin_client, session):
    organization = Organization(name="Old", is_published=True)
    session.add(organization)
    session.commit()

    response = admin_client.post(
        f"/admin/organizations/{organization.id}", data={"name": "Renamed", "description": "D"}
    )

    assert response.status_code == 303
    session.refresh(organization)
    assert (organization.name, organization.description, organization.is_published) == ("Renamed", "D", False)


def test_edit_missing_organization_is_404(admin_client):
    assert admin_client.get("/admin/organizations/999/edit").status_code == 404
    assert admin_client.post("/admin/organizations/999", data={"name": "x"}).status_code == 404


def test_delete_organization(admin_client, session):
    organization = Organization(name="Doomed")
    session.add(organization)
    session.commit()

    response = admin_client.post(f"/admin/organizations/{organization.id}/delete")

    assert response.status_code == 303
    assert session.scalars(select(Organization)).all() == []


def test_delete_missing_organization_is_404(admin_client):
    assert admin_client.post("/admin/organizations/999/delete").status_code == 404


def test_organization_routes_require_admin(client):
    client.follow_redirects = False

    assert client.post("/admin/organizations", data={"name": "x"}).status_code == 303
    assert client.post("/admin/organizations/1/delete").status_code == 303
