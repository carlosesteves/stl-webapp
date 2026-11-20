import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Organization, Term


def test_new_organization_is_not_published_by_default(session):
    org = Organization(name="CourtMaster")
    session.add(org)
    session.commit()

    assert org.is_published is False
    assert org.created_at is not None
    assert org.updated_at is not None


def test_organization_name_is_unique(session):
    session.add_all([Organization(name="Dup"), Organization(name="Dup")])

    with pytest.raises(IntegrityError):
        session.commit()


def test_legacy_index_is_unique_when_set(session):
    session.add_all(
        [Organization(name="A", legacy_index=1), Organization(name="B", legacy_index=1)]
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_single_valued_classifications(session):
    startup = Term(vocabulary="organization_type", name="Startup")
    early = Term(vocabulary="stage", name="Early")
    core = Term(vocabulary="relevance", name="Core")
    org = Organization(name="X", organization_type=startup, stage=early, relevance=core)
    session.add(org)
    session.commit()

    assert (org.organization_type.name, org.stage.name, org.relevance.name) == (
        "Startup",
        "Early",
        "Core",
    )


def test_optional_attributes_default_to_none(session):
    org = Organization(name="Bare")
    session.add(org)
    session.commit()

    assert org.founding_year is None
    assert org.is_active is None
    assert org.website is None
