from datetime import date
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup

from app.auth import require_admin
from app.models import (
    FundingRound,
    FundingRoundInvestor,
    Organization,
    OrganizationEvent,
    Term,
)


@pytest.fixture
def admin_client(client):
    client.follow_redirects = False
    client.app.dependency_overrides[require_admin] = lambda: {"sub": "admin"}
    return client


def page(response):
    return BeautifulSoup(response.text, "html.parser")


def event_type(session, code, name):
    term = Term(vocabulary="event_type", name=name, code=code)
    session.add(term)
    return term


def add_event(session, org, term, title, event_date=None, precision="unknown", **fields):
    event = OrganizationEvent(
        organization=org, event_type=term, title=title,
        event_date=event_date, date_precision=precision, **fields,
    )
    session.add(event)
    return event


@pytest.fixture
def org(session):
    organization = Organization(
        name="ZWIM", description="Swim trainer", country="Portugal", founding_year=2020,
        website="https://zwim.test", is_published=True, is_active=True,
        organization_type=Term(vocabulary="organization_type", name="Startup"),
        stage=Term(vocabulary="stage", name="Early"),
    )
    session.add(organization)
    session.commit()
    return organization


def timeline(response):
    return page(response).select("[data-testid=event]")


def test_detail_shows_organization_facts(admin_client, org):
    html = page(admin_client.get(f"/admin/organizations/{org.id}"))
    text = html.select_one("main").text

    for expected in ("ZWIM", "Swim trainer", "Startup", "Early", "Portugal", "2020"):
        assert expected in text
    assert html.select_one("main a[href='https://zwim.test']") is not None
    assert html.select_one(f"main a[href='/admin/organizations/{org.id}/edit']") is not None


def test_events_are_listed_chronologically_with_undated_last(admin_client, session, org):
    pivot = event_type(session, "pivot", "Pivot")
    add_event(session, org, pivot, "undated one")
    add_event(session, org, pivot, "later", date(2025, 1, 1), "year")
    add_event(session, org, pivot, "earlier", date(2020, 3, 1), "month")
    session.commit()

    items = timeline(admin_client.get(f"/admin/organizations/{org.id}"))

    assert [i.select_one("[data-testid=title]").text.strip() for i in items] == [
        "earlier", "later", "undated one",
    ]
    assert "Mar 2020" in items[0].select_one("[data-testid=date]").text
    assert "2025" in items[1].select_one("[data-testid=date]").text
    assert "Date unknown" in items[2].select_one("[data-testid=date]").text


def test_event_shows_type_and_public_flag(admin_client, session, org):
    pivot = event_type(session, "pivot", "Pivot")
    add_event(session, org, pivot, "public one", is_published=True)
    add_event(session, org, pivot, "private one", is_published=False)
    session.commit()

    items = {
        i.select_one("[data-testid=title]").text.strip(): i
        for i in timeline(admin_client.get(f"/admin/organizations/{org.id}"))
    }

    assert "Pivot" in items["public one"].select_one("[data-testid=type]").text
    assert "Public" in items["public one"].select_one("[data-testid=visibility]").text
    assert "Private" in items["private one"].select_one("[data-testid=visibility]").text


def test_rebranding_and_related_party_details(admin_client, session, org):
    rebrand = event_type(session, "rebranding", "Rebranding")
    acquisition = event_type(session, "acquisition", "Acquisition")
    add_event(session, org, rebrand, "Renamed", old_value="Splink", new_value="ZWIM")
    add_event(session, org, acquisition, "Acquired", date(2026, 1, 1), "year",
              related_name="webook.com", description="All cash deal")
    session.commit()

    text = page(admin_client.get(f"/admin/organizations/{org.id}")).select_one("main").text

    assert "Splink" in text and "ZWIM" in text
    assert "webook.com" in text
    assert "All cash deal" in text


def test_funding_round_details(admin_client, session, org):
    funding = event_type(session, "funding_round", "Funding round")
    event = add_event(session, org, funding, "Seed funding round", date(2026, 1, 1), "year")
    event.funding_round = FundingRound(
        stage=Term(vocabulary="funding_stage", name="Seed"),
        amount_eur=Decimal("1400000"),
        investors=[
            FundingRoundInvestor(investor_org=Organization(name="Lince")),
            FundingRoundInvestor(investor_name="José Pinto"),
        ],
    )
    session.commit()

    (item,) = timeline(admin_client.get(f"/admin/organizations/{org.id}"))

    assert "Seed" in item.text
    assert "€1,400,000" in item.text
    assert "Lince" in item.text and "José Pinto" in item.text


def test_organization_without_events_says_so(admin_client, org):
    html = page(admin_client.get(f"/admin/organizations/{org.id}"))

    assert timeline(admin_client.get(f"/admin/organizations/{org.id}")) == []
    assert "No events yet" in html.select_one("main").text


def test_events_of_other_organizations_are_not_shown(admin_client, session, org):
    pivot = event_type(session, "pivot", "Pivot")
    other = Organization(name="Other")
    add_event(session, other, pivot, "someone else's event")
    session.add(other)
    session.commit()

    assert "someone else's event" not in admin_client.get(f"/admin/organizations/{org.id}").text


def test_missing_organization_is_404(admin_client):
    assert admin_client.get("/admin/organizations/999").status_code == 404


def test_detail_requires_admin(client, org):
    client.follow_redirects = False

    response = client.get(f"/admin/organizations/{org.id}")

    assert (response.status_code, response.headers["location"]) == (303, "/admin/login")


def test_list_links_each_name_to_its_detail_page(admin_client, org):
    html = page(admin_client.get("/admin"))

    assert html.select_one(f"main a[href='/admin/organizations/{org.id}']").text.strip() == "ZWIM"
