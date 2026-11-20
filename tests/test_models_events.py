from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    FundingRound,
    FundingRoundInvestor,
    Organization,
    OrganizationEvent,
    Term,
)


@pytest.fixture
def org(session):
    org = Organization(name="Acme")
    session.add(org)
    session.commit()
    return org


@pytest.fixture
def pivot_type(session):
    term = Term(vocabulary="event_type", name="Pivot", code="pivot")
    session.add(term)
    session.commit()
    return term


def make_event(org, event_type, **overrides):
    values = dict(
        organization=org,
        event_type=event_type,
        title="Something happened",
        event_date=date(2024, 5, 1),
        date_precision="month",
    )
    values.update(overrides)
    return OrganizationEvent(**values)


def test_event_is_not_public_by_default(session, org, pivot_type):
    event = make_event(org, pivot_type)
    session.add(event)
    session.commit()

    assert event.is_published is False


def test_events_are_listed_chronologically_with_undated_last(session, org, pivot_type):
    session.add_all([
        make_event(org, pivot_type, title="undated", event_date=None, date_precision="unknown"),
        make_event(org, pivot_type, title="later", event_date=date(2025, 1, 1)),
        make_event(org, pivot_type, title="earlier", event_date=date(2020, 1, 1)),
    ])
    session.commit()
    session.refresh(org)

    assert [e.title for e in org.events] == ["earlier", "later", "undated"]


def test_unknown_precision_requires_no_date_and_vice_versa(session, org, pivot_type):
    session.add(make_event(org, pivot_type, event_date=None, date_precision="year"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_invalid_precision_is_rejected(session, org, pivot_type):
    session.add(make_event(org, pivot_type, date_precision="decade"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_event_can_reference_related_organization(session, org, pivot_type):
    buyer = Organization(name="Buyer")
    event = make_event(org, pivot_type, related_org=buyer)
    session.add(event)
    session.commit()

    assert event.related_org.name == "Buyer"


def test_funding_round_with_investors(session, org):
    funding_type = Term(vocabulary="event_type", name="Funding round", code="funding_round")
    seed = Term(vocabulary="funding_stage", name="Seed")
    fund = Organization(name="Portugal Ventures")
    event = make_event(org, funding_type, title="Seed round")
    event.funding_round = FundingRound(
        stage=seed,
        amount_eur=2_000_000,
        investors=[
            FundingRoundInvestor(investor_org=fund),
            FundingRoundInvestor(investor_name="José Pinto"),
        ],
    )
    session.add(event)
    session.commit()

    saved = session.scalars(select(FundingRound)).one()
    assert saved.event.organization.name == "Acme"
    assert saved.stage.name == "Seed"
    assert [i.display_name for i in saved.investors] == ["Portugal Ventures", "José Pinto"]


def test_investor_needs_org_or_name(session, org):
    funding_type = Term(vocabulary="event_type", name="Funding round", code="funding_round")
    event = make_event(org, funding_type)
    event.funding_round = FundingRound(investors=[FundingRoundInvestor()])
    session.add(event)

    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_organization_deletes_events_and_rounds(session, org):
    funding_type = Term(vocabulary="event_type", name="Funding round", code="funding_round")
    event = make_event(org, funding_type)
    event.funding_round = FundingRound(investors=[FundingRoundInvestor(investor_name="X")])
    session.add(event)
    session.commit()

    session.delete(org)
    session.commit()

    assert session.scalars(select(OrganizationEvent)).all() == []
    assert session.scalars(select(FundingRound)).all() == []
    assert session.scalars(select(FundingRoundInvestor)).all() == []
