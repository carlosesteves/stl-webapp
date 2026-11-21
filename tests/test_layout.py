import pytest
from bs4 import BeautifulSoup

from app.auth import require_admin
from app.models import Organization


def soup(response):
    return BeautifulSoup(response.text, "html.parser")


@pytest.fixture
def admin_client(client):
    client.follow_redirects = False
    client.app.dependency_overrides[require_admin] = lambda: {"sub": "admin"}
    return client


def test_bootstrap_is_served_locally(client):
    assert client.get("/static/vendor/bootstrap/bootstrap.min.css").status_code == 200
    assert client.get("/static/vendor/bootstrap/bootstrap.bundle.min.js").status_code == 200


def test_public_page_has_header_menu_main_and_footer(client):
    page = soup(client.get("/"))

    assert page.select_one("header nav a[href='/']") is not None
    assert page.select_one("header nav a[href='/admin']") is not None
    assert page.select_one("main") is not None
    assert page.select_one("footer") is not None
    assert page.select_one("link[href='/static/vendor/bootstrap/bootstrap.min.css']") is not None
    assert page.select_one("script[src='/static/vendor/bootstrap/bootstrap.bundle.min.js']") is not None
    assert page.select_one("meta[name=viewport]") is not None
    assert page.select_one("aside") is None


def test_public_menu_marks_the_current_page(client):
    page = soup(client.get("/"))

    assert "active" in page.select_one("header nav a.nav-link[href='/']")["class"]


def test_admin_page_has_header_sidebar_main_and_footer(admin_client, session):
    session.add(Organization(name="Acme"))
    session.commit()

    page = soup(admin_client.get("/admin"))

    assert page.select_one("header") is not None
    assert page.select_one("aside nav a[href='/admin']") is not None
    assert "active" in page.select_one("aside nav a[href='/admin']")["class"]
    assert page.select_one("main") is not None
    assert "Acme" in page.select_one("main").text
    assert page.select_one("footer") is not None


def test_admin_has_logout_in_the_header(admin_client):
    page = soup(admin_client.get("/admin"))

    form = page.select_one("header form[action='/admin/logout']")
    assert form is not None and form["method"] == "post"


def test_admin_form_page_uses_the_admin_layout(admin_client):
    page = soup(admin_client.get("/admin/organizations/new"))

    assert page.select_one("aside nav") is not None
    assert page.select_one("main form[action='/admin/organizations']") is not None


def test_login_page_has_no_sidebar_or_logout(client):
    page = soup(client.get("/admin/login"))

    assert page.select_one("aside") is None
    assert page.select_one("form[action='/admin/logout']") is None
    assert page.select_one("main form[action='/admin/login']") is not None
