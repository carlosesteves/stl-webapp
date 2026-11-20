from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.importer.workbook import import_rows
from app.models import Organization
from app.seed import seed_vocabularies


@pytest.fixture(autouse=True)
def seeded(session):
    seed_vocabularies(session)


def run(session, *rows):
    report = import_rows(session, list(rows))
    session.commit()
    return report


def events(session, name, code=None):
    o = session.scalars(select(Organization).where(Organization.name == name)).one()
    return [e for e in o.events if code is None or e.event_type.code == code]


def test_rebranding_cell_is_the_old_name(session):
    run(session, {"Name": "Fan Collex", "Rebranding": "Splink"})

    (event,) = events(session, "Fan Collex", "rebranding")
    assert (event.old_value, event.new_value) == ("Splink", "Fan Collex")
    assert event.title == "Renamed from Splink to Fan Collex"
    assert (event.event_date, event.date_precision) == (None, "unknown")
    assert event.is_published is False


def test_pivot_event_records_target_sector(session):
    run(session,
        {"Name": "A", "Pivot": "Yes", "Sector pivoting to": "E-commerce; Retail"},
        {"Name": "B", "Pivot": "Yes"},
        {"Name": "C", "Pivot": "No", "Sector pivoting to": "Ignored"},
        {"Name": "D", "Pivot": "N.A."})

    (a,) = events(session, "A", "pivot")
    assert (a.new_value, a.title) == ("E-commerce; Retail", "Pivot to E-commerce; Retail")
    assert events(session, "B", "pivot")[0].title == "Pivot"
    assert events(session, "C") == [] and events(session, "D") == []


def test_acquisition_with_buyer_and_year(session):
    run(session, {"Name": "SmartMove", "M&A": "Yes", "Buyer": "webook.com; 2026"})

    (event,) = events(session, "SmartMove", "acquisition")
    assert event.related_name == "webook.com"
    assert (event.event_date, event.date_precision) == (date(2026, 1, 1), "year")
    assert event.title == "Acquired by webook.com"


def test_acquisition_links_buyer_when_it_is_in_the_database(session):
    run(session, {"Name": "Playtomic"}, {"Name": "Air Courts", "M&A": "Yes", "Buyer": "Playtomic"})

    (event,) = events(session, "Air Courts", "acquisition")
    assert event.related_org.name == "Playtomic"
    assert (event.event_date, event.date_precision) == (None, "unknown")


def test_acquisition_without_buyer_and_no_acquisition_when_no(session):
    run(session, {"Name": "Field", "M&A": "Yes"}, {"Name": "Other", "M&A": "No", "Buyer": "X"})

    assert events(session, "Field", "acquisition")[0].title == "Acquired"
    assert events(session, "Other") == []


def test_dissolution_year_and_unknown(session):
    run(session,
        {"Name": "A", "Date of dissolution": 2025},
        {"Name": "B", "Date of dissolution": "N.A."})

    assert events(session, "A", "dissolution")[0].event_date == date(2025, 1, 1)
    (b,) = events(session, "B", "dissolution")
    assert (b.event_date, b.date_precision) == (None, "unknown")


def test_funding_round_with_investors_amount_and_year(session):
    run(session, {"Name": "Fund"}, {
        "Name": "ZWIM", "Funding stage2": "Seed", "Investors": "Fund + Lince capital",
        "Funding date": 2026, "Funding": "€1.4M",
    })

    (event,) = events(session, "ZWIM", "funding_round")
    round_ = event.funding_round
    assert event.title == "Seed funding round"
    assert (event.event_date, event.date_precision) == (date(2026, 1, 1), "year")
    assert round_.stage.name == "Seed"
    assert round_.amount_eur == Decimal("1400000")
    assert [i.display_name for i in round_.investors] == ["Fund", "Lince capital"]
    assert round_.investors[0].investor_org.name == "Fund"
    assert round_.investors[1].investor_org is None


def test_funding_with_only_amount_or_only_stage(session):
    run(session,
        {"Name": "A", "Funding": "€2M"},
        {"Name": "B", "Funding stage2": "Pre-Seed"})

    assert events(session, "A", "funding_round")[0].title == "Funding round"
    assert events(session, "A", "funding_round")[0].funding_round.amount_eur == Decimal("2000000")
    assert events(session, "B", "funding_round")[0].funding_round.stage.name == "Pre-Seed"


def test_bootstrapped_alone_is_not_a_round(session):
    run(session, {"Name": "A", "Funding stage2": "Bootstrapped"})

    assert events(session, "A") == []


def test_amount_written_in_the_wrong_columns_is_recovered(session):
    run(session,
        {"Name": "Vibo", "Funding stage2": "Seed", "Investors": "Pitchbook", "Funding date": "€100k"},
        {"Name": "Smash", "Investors": "€50K", "Funding date": "3.09.2026", "Funding": "€50K "})

    vibo = events(session, "Vibo", "funding_round")[0]
    assert vibo.funding_round.amount_eur == Decimal("100000")
    assert (vibo.event_date, vibo.date_precision) == (None, "unknown")
    smash = events(session, "Smash", "funding_round")[0]
    assert smash.funding_round.investors == []
    assert (smash.event_date, smash.date_precision) == (date(2026, 9, 3), "day")


def test_year_in_investor_text_is_used_when_no_funding_date(session):
    run(session, {"Name": "RealFevr", "Funding stage2": "Series A", "Investors": "ADvantage(2022)"})

    (event,) = events(session, "RealFevr", "funding_round")
    assert (event.event_date, event.date_precision) == (date(2022, 1, 1), "year")


def test_unknown_funding_stage_is_reported_but_round_kept(session):
    report = run(session, {"Name": "A", "Funding stage2": "Series Z", "Funding": "€1M"})

    assert events(session, "A", "funding_round")[0].funding_round.stage is None
    assert any(i.column == "Funding stage2" for i in report.issues)
