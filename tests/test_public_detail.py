from datetime import date
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup

from app.models import (
    FundingRound,
    FundingRoundInvestor,
    Organization,
    OrganizationEvent,
    PublicFunding,
    Relationship,
    Term,
)


def soup(response):
    return BeautifulSoup(response.text, "html.parser")


def term(vocabulary, name, code=None):
    return Term(vocabulary=vocabulary, name=name, code=code)


@pytest.fixture
def pivot():
    return term("event_type", "Pivot", "pivot")


@pytest.fixture
def org(session):
    organization = Organization(
        name="ZWIM", description="Swim trainer", country="Portugal", founding_year=2020,
        website="https://zwim.test", linkedin_url="https://linkedin.test/zwim",
        is_published=True, email="secret@zwim.test", email_alt="alt@zwim.test",
        comment="internal note", seeking="internal wish",
        organization_type=term("organization_type", "Startup"),
        stage=term("stage", "Early"),
        tags=[term("technology", "Computer Vision"), term("sport_focus", "Swimming"),
              term("area_of_impact", "Athlete Performance")],
    )
    organization.public_funding.append(PublicFunding(project_ref="PRR-SECRET", amount_eur=1))
    organization.relationships.append(Relationship(kind="customer", related_name="Hidden Customer"))
    session.add(organization)
    session.commit()
    return organization


def add_event(session, org, pivot, title, public=True, event_date=None, precision="unknown", **fields):
    event = OrganizationEvent(
        organization=org, event_type=pivot, title=title, is_published=public,
        event_date=event_date, date_precision=precision, **fields,
    )
    session.add(event)
    return event


def events(response):
    return soup(response).select("[data-testid=event]")


def test_published_organization_page_shows_public_facts(client, org):
    response = client.get(f"/organizations/{org.id}")

    assert response.status_code == 200
    html = soup(response)
    text = html.select_one("main").text
    for expected in ("ZWIM", "Swim trainer", "Startup", "Early", "Portugal", "2020",
                     "Computer Vision", "Swimming", "Athlete Performance"):
        assert expected in text
    assert html.select_one("main a[href='https://zwim.test']") is not None
    assert html.select_one("main a[href='https://linkedin.test/zwim']") is not None
    assert html.select_one("header nav") is not None and html.select_one("footer") is not None


def test_internal_information_is_not_exposed(client, org):
    page = client.get(f"/organizations/{org.id}").text

    for secret in ("secret@zwim.test", "alt@zwim.test", "internal note", "internal wish",
                   "PRR-SECRET", "Hidden Customer"):
        assert secret not in page


def test_no_admin_controls_on_the_public_page(client, session, org, pivot):
    add_event(session, org, pivot, "Public one")
    session.commit()

    html = soup(client.get(f"/organizations/{org.id}"))

    assert html.select_one("main form") is None
    assert html.select_one("main a[href*='/edit']") is None
    assert html.select_one("main a[href^='/admin']") is None


def test_unpublished_or_missing_organization_is_404(client, session, org, pivot):
    hidden = Organization(name="Hidden", is_published=False)
    add_event(session, hidden, pivot, "A public event on a hidden org")
    session.add(hidden)
    session.commit()

    assert client.get(f"/organizations/{hidden.id}").status_code == 404
    assert client.get("/organizations/99999").status_code == 404


def test_only_public_events_are_shown_in_chronological_order(client, session, org, pivot):
    add_event(session, org, pivot, "private one", public=False, event_date=date(2021, 1, 1), precision="year")
    add_event(session, org, pivot, "undated public", event_date=None)
    add_event(session, org, pivot, "later", event_date=date(2025, 6, 1), precision="month")
    add_event(session, org, pivot, "earlier", event_date=date(2022, 1, 1), precision="year")
    session.commit()

    response = client.get(f"/organizations/{org.id}")
    items = events(response)

    assert [i.select_one("[data-testid=title]").text.strip() for i in items] == [
        "earlier", "later", "undated public",
    ]
    assert "private one" not in response.text
    assert "2022" in items[0].select_one("[data-testid=date]").text
    assert "Jun 2025" in items[1].select_one("[data-testid=date]").text
    assert items[2].select_one("[data-testid=date]") is None
    assert "Date unknown" not in response.text


def test_event_type_and_details_are_shown(client, session, org, pivot):
    add_event(session, org, pivot, "Renamed", old_value="Splink", new_value="ZWIM",
              related_name="webook.com", description="Public blurb")
    session.commit()

    (item,) = events(client.get(f"/organizations/{org.id}"))

    assert "Pivot" in item.select_one("[data-testid=type]").text
    for expected in ("Splink", "ZWIM", "webook.com", "Public blurb"):
        assert expected in item.text


def test_related_organization_is_linked_only_when_published(client, session, org, pivot):
    visible = Organization(name="Visible Co", is_published=True)
    invisible = Organization(name="Invisible Co", is_published=False)
    add_event(session, org, pivot, "with visible", related_org=visible)
    add_event(session, org, pivot, "with invisible", related_org=invisible)
    session.commit()

    items = {i.select_one("[data-testid=title]").text.strip(): i
             for i in events(client.get(f"/organizations/{org.id}"))}

    assert items["with visible"].select_one(f"a[href='/organizations/{visible.id}']") is not None
    assert "Invisible Co" in items["with invisible"].text
    assert items["with invisible"].select_one("a") is None


def test_public_funding_event_shows_stage_amount_and_investors(client, session, org):
    funding = term("event_type", "Funding round", "funding_round")
    event = add_event(session, org, funding, "Seed funding round", event_date=date(2026, 1, 1), precision="year")
    event.funding_round = FundingRound(
        stage=term("funding_stage", "Seed"), amount_eur=Decimal("1400000"),
        investors=[FundingRoundInvestor(investor_org=Organization(name="Lince")),
                   FundingRoundInvestor(investor_name="José Pinto")],
    )
    session.commit()

    (item,) = events(client.get(f"/organizations/{org.id}"))

    for expected in ("Seed", "€1,400,000", "Lince", "José Pinto"):
        assert expected in item.text


def test_organization_without_public_events_says_so(client, session, org, pivot):
    add_event(session, org, pivot, "private", public=False)
    session.commit()

    response = client.get(f"/organizations/{org.id}")

    assert events(response) == []
    assert "No public events yet" in soup(response).select_one("main").text


def test_home_links_to_the_organization_page(client, org):
    html = soup(client.get("/"))

    assert html.select_one(f"main a[href='/organizations/{org.id}']").text.strip() == "ZWIM"
