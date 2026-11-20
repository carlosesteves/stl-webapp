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


def org(session, name):
    return session.scalars(select(Organization).where(Organization.name == name)).one()


def test_prr_funding_with_project_and_amount(session):
    run(session, {
        "Name": "A", "PRR Funding,": "Yes",
        "PRR Innovation Projects,": "C16-i02", "Public Funding": "€30k",
    })

    (funding,) = org(session, "A").public_funding
    assert (funding.programme, funding.project_ref, funding.amount_eur) == (
        "PRR", "C16-i02", Decimal("30000"),
    )


def test_amount_formats_in_public_funding(session):
    run(session,
        {"Name": "A", "PRR Funding,": "Yes", "Public Funding": "30k"},
        {"Name": "B", "PRR Funding,": "Yes", "Public Funding": "€11.9M "})

    assert org(session, "A").public_funding[0].amount_eur == Decimal("30000")
    assert org(session, "B").public_funding[0].amount_eur == Decimal("11900000")


def test_prr_yes_without_details_is_still_recorded(session):
    run(session, {"Name": "A", "PRR Funding,": "Yes"})

    (funding,) = org(session, "A").public_funding
    assert (funding.programme, funding.project_ref, funding.amount_eur) == ("PRR", None, None)


def test_public_funding_outside_prr_and_none_at_all(session):
    run(session,
        {"Name": "A", "PRR Funding,": "No", "Public Funding": "€92k"},
        {"Name": "B", "PRR Funding,": "No"})

    assert org(session, "A").public_funding[0].programme == "Other public"
    assert org(session, "B").public_funding == []


def test_relationships_from_list_columns(session):
    run(session,
        {"Name": "Lince"},
        {
            "Name": "A",
            "Ecossystem Connections": "Lince ; SPRINT",
            "Past Investments": "Bhout; Zwim",
            "Use cases": "ABIMOTA; AM2R",
            "Partnership actors": "SPRINT R&D center",
        })

    links = {(r.kind, r.related_name, r.related_org.name if r.related_org else None)
             for r in org(session, "A").relationships}
    assert links == {
        ("ecosystem_connection", None, "Lince"),
        ("ecosystem_connection", "SPRINT", None),
        ("past_investment", "Bhout", None),
        ("past_investment", "Zwim", None),
        ("use_case", "ABIMOTA", None),
        ("use_case", "AM2R", None),
        ("research_link", "SPRINT R&D center", None),
    }


def test_columns_without_a_home_are_reported_not_dropped_silently(session):
    report = run(session, {"Name": "A", "Customers": "FC Porto", "Pilot Deployments": "Lisbon"})

    assert {(i.column, i.value) for i in report.issues} == {
        ("Customers", "FC Porto"),
        ("Pilot Deployments", "Lisbon"),
    }
