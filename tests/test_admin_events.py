from datetime import date
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import select

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


@pytest.fixture
def types(session):
    terms = {
        code: Term(vocabulary="event_type", name=name, code=code)
        for code, name in [("pivot", "Pivot"), ("funding_round", "Funding round"), ("other", "Other")]
    }
    session.add_all(terms.values())
    session.add(Term(vocabulary="funding_stage", name="Seed"))
    session.commit()
    return terms


@pytest.fixture
def org(session, types):
    organization = Organization(name="ZWIM")
    session.add(organization)
    session.commit()
    return organization


def soup(response):
    return BeautifulSoup(response.text, "html.parser")


def events_of(session):
    return session.scalars(select(OrganizationEvent).order_by(OrganizationEvent.id)).all()


def post_new(client, org, types, **fields):
    data = {"event_type_id": str(types["pivot"].id), "title": "Something"}
    data.update(fields)
    return client.post(f"/admin/organizations/{org.id}/events", data=data)


# --- new form -------------------------------------------------------------

def test_new_event_form_lists_event_types_and_fields(admin_client, org, types):
    page = soup(admin_client.get(f"/admin/organizations/{org.id}/events/new"))

    options = {o.text.strip() for o in page.select("select[name=event_type_id] option")}
    assert {"Pivot", "Funding round", "Other"} <= options
    for name in ("year", "month", "day", "title", "description", "old_value", "new_value",
                 "related_name", "source_url", "is_published", "funding_stage_id", "amount", "investors"):
        assert page.select_one(f"[name={name}]") is not None, name
    assert page.select_one("input[name=is_published]").has_attr("checked") is False
    assert page.select_one(f"main form[action='/admin/organizations/{org.id}/events']") is not None


def test_new_form_for_missing_organization_is_404(admin_client):
    assert admin_client.get("/admin/organizations/999/events/new").status_code == 404


# --- create ---------------------------------------------------------------

def test_create_event_with_date_and_defaults(admin_client, session, org, types):
    response = post_new(admin_client, org, types, year="2024", month="5", description="d",
                        old_value="a", new_value="b", source_url="https://x.test")

    assert response.status_code == 303
    assert response.headers["location"] == f"/admin/organizations/{org.id}"
    (event,) = events_of(session)
    assert (event.organization_id, event.event_type.code, event.title) == (org.id, "pivot", "Something")
    assert (event.event_date, event.date_precision) == (date(2024, 5, 1), "month")
    assert (event.description, event.old_value, event.new_value, event.source_url) == (
        "d", "a", "b", "https://x.test",
    )
    assert event.is_published is False


def test_create_public_event_without_date(admin_client, session, org, types):
    post_new(admin_client, org, types, is_published="on")

    (event,) = events_of(session)
    assert event.is_published is True
    assert (event.event_date, event.date_precision) == (None, "unknown")


def test_related_name_links_an_existing_organization(admin_client, session, org, types):
    session.add(Organization(name="Playtomic"))
    session.commit()

    post_new(admin_client, org, types, related_name="playtomic")
    post_new(admin_client, org, types, related_name="Unknown Co")

    linked, unlinked = events_of(session)
    assert linked.related_org.name == "Playtomic"
    assert (unlinked.related_org, unlinked.related_name) == (None, "Unknown Co")


@pytest.mark.parametrize(
    "fields, message",
    [
        ({"month": "5"}, "year"),
        ({"year": "2024", "month": "13"}, "Month"),
        ({"title": "  "}, "title"),
        ({"event_type_id": "99999"}, "type"),
        ({"event_type_id": ""}, "type"),
    ],
)
def test_invalid_input_rerenders_with_error_and_saves_nothing(admin_client, session, org, types, fields, message):
    response = post_new(admin_client, org, types, description="keep me", **fields)

    assert response.status_code == 422
    page = soup(response)
    assert message.lower() in page.select_one("[role=alert]").text.lower()
    assert page.select_one("textarea[name=description]").text.strip() == "keep me"
    assert events_of(session) == []


def test_funding_round_is_created_with_stage_amount_and_linked_investors(admin_client, session, org, types):
    session.add(Organization(name="Lince"))
    stage = session.scalars(select(Term).where(Term.vocabulary == "funding_stage")).one()
    session.commit()

    response = post_new(
        admin_client, org, types, event_type_id=str(types["funding_round"].id), year="2026",
        funding_stage_id=str(stage.id), amount="€1.4M", investors="Lince\nJosé Pinto",
    )

    assert response.status_code == 303
    (event,) = events_of(session)
    round_ = event.funding_round
    assert (round_.stage.name, round_.amount_eur) == ("Seed", Decimal("1400000"))
    assert [(i.display_name, i.investor_org is not None) for i in round_.investors] == [
        ("Lince", True), ("José Pinto", False),
    ]


def test_bad_amount_is_reported(admin_client, session, org, types):
    response = post_new(admin_client, org, types, event_type_id=str(types["funding_round"].id), amount="lots")

    assert response.status_code == 422
    assert "amount" in soup(response).select_one("[role=alert]").text.lower()
    assert events_of(session) == []


def test_funding_fields_are_ignored_for_other_types(admin_client, session, org, types):
    post_new(admin_client, org, types, amount="€1M", investors="Lince")

    (event,) = events_of(session)
    assert event.funding_round is None


def test_create_for_missing_organization_is_404(admin_client, types):
    response = admin_client.post("/admin/organizations/999/events",
                                 data={"event_type_id": str(types["pivot"].id), "title": "x"})

    assert response.status_code == 404


# --- edit / update ----------------------------------------------------------

@pytest.fixture
def event(session, org, types):
    event = OrganizationEvent(
        organization=org, event_type=types["pivot"], title="Original",
        event_date=date(2024, 5, 13), date_precision="day", description="desc",
        related_name="Acme", is_published=True,
    )
    session.add(event)
    session.commit()
    return event


def test_edit_form_is_prefilled(admin_client, event, types):
    page = soup(admin_client.get(f"/admin/events/{event.id}/edit"))

    assert page.select_one("input[name=title]")["value"] == "Original"
    assert [page.select_one(f"input[name={n}]")["value"] for n in ("year", "month", "day")] == ["2024", "5", "13"]
    assert page.select_one("select[name=event_type_id] option[selected]")["value"] == str(types["pivot"].id)
    assert page.select_one("input[name=is_published]").has_attr("checked")
    assert page.select_one("input[name=related_name]")["value"] == "Acme"
    assert page.select_one(f"main form[action='/admin/events/{event.id}']") is not None


def test_update_changes_fields_and_precision(admin_client, session, event, types):
    response = admin_client.post(f"/admin/events/{event.id}", data={
        "event_type_id": str(types["other"].id), "title": "Changed", "year": "2025",
    })

    assert response.status_code == 303
    assert response.headers["location"] == f"/admin/organizations/{event.organization_id}"
    session.refresh(event)
    assert (event.title, event.event_type.code) == ("Changed", "other")
    assert (event.event_date, event.date_precision) == (date(2025, 1, 1), "year")
    assert (event.description, event.related_name, event.is_published) == (None, None, False)


def test_update_with_errors_keeps_the_event_unchanged(admin_client, session, event, types):
    response = admin_client.post(f"/admin/events/{event.id}", data={
        "event_type_id": str(types["pivot"].id), "title": "", "year": "2025",
    })

    assert response.status_code == 422
    session.refresh(event)
    assert event.title == "Original"


def test_switching_to_funding_adds_a_round_and_away_removes_it(admin_client, session, event, types):
    admin_client.post(f"/admin/events/{event.id}", data={
        "event_type_id": str(types["funding_round"].id), "title": "Round",
        "amount": "250k", "investors": "A\nB",
    })
    session.refresh(event)
    assert event.funding_round.amount_eur == Decimal("250000")
    assert len(event.funding_round.investors) == 2

    admin_client.post(f"/admin/events/{event.id}", data={
        "event_type_id": str(types["funding_round"].id), "title": "Round", "investors": "C",
    })
    session.refresh(event)
    assert [i.display_name for i in event.funding_round.investors] == ["C"]
    assert event.funding_round.amount_eur is None

    admin_client.post(f"/admin/events/{event.id}", data={
        "event_type_id": str(types["other"].id), "title": "Round",
    })
    session.expire_all()
    assert session.scalars(select(FundingRound)).all() == []
    assert session.scalars(select(FundingRoundInvestor)).all() == []


def test_edit_form_shows_existing_funding_details(admin_client, session, event, types):
    admin_client.post(f"/admin/events/{event.id}", data={
        "event_type_id": str(types["funding_round"].id), "title": "Round",
        "amount": "1400000", "investors": "A\nB",
    })

    page = soup(admin_client.get(f"/admin/events/{event.id}/edit"))

    assert page.select_one("input[name=amount]")["value"] == "1400000"
    assert page.select_one("textarea[name=investors]").text.strip().splitlines() == ["A", "B"]


def test_edit_and_update_missing_event_are_404(admin_client, types):
    assert admin_client.get("/admin/events/999/edit").status_code == 404
    assert admin_client.post("/admin/events/999", data={"event_type_id": "1", "title": "x"}).status_code == 404


# --- delete ----------------------------------------------------------------

def test_delete_event(admin_client, session, event):
    response = admin_client.post(f"/admin/events/{event.id}/delete")

    assert response.status_code == 303
    assert response.headers["location"] == f"/admin/organizations/{event.organization_id}"
    assert events_of(session) == []


def test_delete_missing_event_is_404(admin_client):
    assert admin_client.post("/admin/events/999/delete").status_code == 404


# --- detail page links and access --------------------------------------------

def test_detail_page_links_to_add_edit_and_delete(admin_client, org, event):
    page = soup(admin_client.get(f"/admin/organizations/{org.id}"))

    assert page.select_one(f"main a[href='/admin/organizations/{org.id}/events/new']") is not None
    item = page.select_one("[data-testid=event]")
    assert item.select_one(f"a[href='/admin/events/{event.id}/edit']") is not None
    assert item.select_one(f"form[action='/admin/events/{event.id}/delete'][method=post]") is not None


def test_all_event_routes_require_admin(client, org, event):
    client.follow_redirects = False
    requests = [
        ("get", f"/admin/organizations/{org.id}/events/new"),
        ("post", f"/admin/organizations/{org.id}/events"),
        ("get", f"/admin/events/{event.id}/edit"),
        ("post", f"/admin/events/{event.id}"),
        ("post", f"/admin/events/{event.id}/delete"),
    ]
    for method, url in requests:
        response = getattr(client, method)(url)
        assert (response.status_code, response.headers["location"]) == (303, "/admin/login"), url
