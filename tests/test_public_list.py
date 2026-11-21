import pytest
from bs4 import BeautifulSoup

from app.models import Organization, Term


def rows(client):
    html = BeautifulSoup(client.get("/").text, "html.parser")
    return html, html.select("main table tbody tr")


def cells(row):
    return [c.get_text(" ", strip=True) for c in row.select("td")]


@pytest.fixture
def full_org(session):
    organization = Organization(
        name="CourtMaster", description="AI padel video", country="Portugal",
        founding_year=2024, website="https://www.court-master.com/", is_published=True,
        organization_type=Term(vocabulary="organization_type", name="Startup"),
        stage=Term(vocabulary="stage", name="Growth"),
    )
    session.add(organization)
    session.commit()
    return organization


def test_list_has_the_expected_columns(client, full_org):
    html, _ = rows(client)

    assert [th.text.strip() for th in html.select("main table thead th")] == [
        "Name", "Type", "Stage", "Country", "Founded", "Website",
    ]


def test_row_shows_type_stage_country_founded_and_website(client, full_org):
    _, (row,) = rows(client)

    name, kind, stage, country, founded, website = cells(row)
    assert name.startswith("CourtMaster") and "AI padel video" in name
    assert (kind, stage, country, founded, website) == (
        "Startup", "Growth", "Portugal", "2024", "court-master.com",
    )
    assert row.select_one(f"a[href='/organizations/{full_org.id}']").text.strip() == "CourtMaster"
    link = row.select_one("a[href='https://www.court-master.com/']")
    assert link.text.strip() == "court-master.com"
    assert link["rel"] == ["noopener", "noreferrer"] and link["target"] == "_blank"


def test_missing_values_show_a_dash(client, session):
    session.add(Organization(name="Bare", is_published=True))
    session.commit()

    _, (row,) = rows(client)

    assert cells(row)[1:] == ["–", "–", "–", "–", "–"]


@pytest.mark.parametrize("website", ["javascript:alert(1)", "not a url", "ftp://x.test"])
def test_non_http_websites_are_not_linked(client, session, website):
    session.add(Organization(name="Odd", is_published=True, website=website))
    session.commit()

    _, (row,) = rows(client)

    assert row.select("td")[5].select_one("a") is None


def test_organization_page_also_refuses_non_http_links(client, session):
    organization = Organization(
        name="Odd", is_published=True, website="javascript:alert(1)",
        linkedin_url="javascript:alert(2)",
    )
    session.add(organization)
    session.commit()

    html = BeautifulSoup(client.get(f"/organizations/{organization.id}").text, "html.parser")

    assert html.select_one("main a[href^='javascript:']") is None


def test_unpublished_organizations_stay_out_and_empty_state_remains(client, session):
    session.add(Organization(name="Hidden", is_published=False))
    session.commit()

    html, found = rows(client)

    assert found == []
    assert "Nothing here yet" in html.select_one("main").text
