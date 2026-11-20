from datetime import date, datetime

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


def test_scalar_fields_are_imported_and_cleaned(session):
    run(session, {
        "Index": 1, "Name": "CourtMaster", "MVP": "Yes", "Active": "Yes", "AI": "No",
        "Scaling potential": "YES", "Website": "https://www.court-master.com/",
        "Email": "info@court-master.com", "Email alt": "form: https://x.test",
        "Linkedin": "https://www.linkedin.com/company/courtmaster/",
        "Description": "AI-powered padel", "Origin": "Portugal", "Founding year": 2024,
        "Spin-of origin": "UPTEC", "Looking for": "SPRINT R&D consultancy", "Comment": "hi",
    })

    o = org(session, "CourtMaster")
    assert (o.legacy_index, o.is_mvp, o.is_active, o.ai_enabled, o.scaling_potential) == (
        1, True, True, False, True,
    )
    assert (o.website, o.email, o.email_alt) == (
        "https://www.court-master.com/", "info@court-master.com", "form: https://x.test",
    )
    assert (o.country, o.founding_year, o.spin_off_origin) == ("Portugal", 2024, "UPTEC")
    assert (o.seeking, o.comment, o.description) == ("SPRINT R&D consultancy", "hi", "AI-powered padel")


def test_placeholders_become_null(session):
    run(session, {"Name": "X", "Founding year": "N.A.", "Active": "N.A.", "AI": None})

    o = org(session, "X")
    assert (o.founding_year, o.is_active, o.ai_enabled, o.scaling_potential) == (None, None, None, None)


def test_only_mvp_organizations_are_published(session):
    run(session, {"Name": "A", "MVP": "Yes"}, {"Name": "B", "MVP": "No"}, {"Name": "C"})

    assert [org(session, n).is_published for n in "ABC"] == [True, False, False]


def test_created_and_updated_come_from_the_sheet(session):
    run(session,
        {"Name": "A", "Date added": "2026-04-13", "Last checked": datetime(2026, 10, 24)},
        {"Name": "B", "Date added": "2026-04-13"})

    assert org(session, "A").created_at.date() == date(2026, 4, 13)
    assert org(session, "A").updated_at.date() == date(2026, 10, 24)
    assert org(session, "B").updated_at.date() == date(2026, 4, 13)


@pytest.mark.parametrize(
    "old, new",
    [
        ("Startup", "Startup"),
        ("Spin-off", "Startup"),
        ("Consulting Firm", "Consulting & Services"),
        ("Incubator", "Incubator & Accelerator"),
        ("Technology & Innovation Centers", "Interface Centre (CTI/CoLAB)"),
        ("Research & Innovation Cluster", "Cluster & Association"),
        ("Investment fund", "Investor"),
        ("National Governing Body", "Public Agency"),
    ],
)
def test_old_organization_types_map_to_new_taxonomy(session, old, new):
    run(session, {"Name": "X", "Organization": old})

    assert org(session, "X").organization_type.name == new


@pytest.mark.parametrize("old", ["Sport Assessment Centers", "Sport Innovation Hub", "Mystery"])
def test_unmappable_types_are_left_empty_and_reported(session, old):
    report = run(session, {"Name": "X", "Organization": old})

    assert org(session, "X").organization_type is None
    assert any(i.name == "X" and i.column == "Organization" and i.value == old for i in report.issues)


def test_stage_is_a_single_term(session):
    run(session, {"Name": "A", "Stage": "Early"}, {"Name": "B", "Stage": "N.A."})

    assert org(session, "A").stage.name == "Early"
    assert org(session, "B").stage is None


def test_multi_value_tags_across_vocabularies(session):
    run(session, {
        "Name": "X",
        "Area of Impact": "Athlete Performance; Health & Wellness",
        "Technology": "Motion Sensors;  IoT/Connected Devices; N.A.",
        "Sport Focus": "Padel", "Market": "Clubs; Athletes",
        "Category": "Video Analysis Platforms; Content Creation & Distribution tools",
        "Evidence-Based Research": "Patent",
    })

    o = org(session, "X")
    assert {t.name for t in o.tags_in("area_of_impact")} == {"Athlete Performance", "Health & Wellness"}
    assert {t.name for t in o.tags_in("technology")} == {"Motion Sensors", "IoT/Connected Devices"}
    assert {t.name for t in o.tags_in("market")} == {"Clubs", "Athletes"}
    assert len(o.tags_in("category")) == 2
    assert [t.name for t in o.tags_in("research_evidence")] == ["Patent"]


def test_known_typo_is_corrected_and_unknown_values_are_reported(session):
    report = run(session, {"Name": "X", "Area of Impact": "Athelete Performance", "Market": "Combination; Clubs"})

    o = org(session, "X")
    assert [t.name for t in o.tags_in("area_of_impact")] == ["Athlete Performance"]
    assert [t.name for t in o.tags_in("market")] == ["Clubs"]
    assert [(i.column, i.value) for i in report.issues] == [("Market", "Combination")]


def test_founders_are_split(session):
    run(session, {"Name": "X", "Founders/CEO": "Joana Serra & João Vasconcelos"})

    assert [f.name for f in org(session, "X").founders] == ["Joana Serra", "João Vasconcelos"]


def test_existing_organizations_are_skipped_not_overwritten(session):
    run(session, {"Name": "X", "Description": "original"})

    report = run(session, {"Name": "X", "Description": "changed"})

    assert org(session, "X").description == "original"
    assert report.created == 0
    assert report.skipped == ["X"]


def test_rows_without_a_name_are_reported(session):
    report = run(session, {"Index": 9, "Name": None})

    assert report.created == 0
    assert any(i.column == "Name" for i in report.issues)
