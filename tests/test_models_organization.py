import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Founder, Organization, Term, organization_terms


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


def test_multi_value_tags_and_founders(session):
    ai = Term(vocabulary="technology", name="Artificial Intelligence")
    cv = Term(vocabulary="technology", name="Computer Vision")
    padel = Term(vocabulary="sport_focus", name="Padel")
    org = Organization(name="Tagged", tags=[ai, cv, padel])
    org.founders.append(Founder(name="Ana"))
    session.add(org)
    session.commit()

    assert {t.name for t in org.tags_in("technology")} == {
        "Artificial Intelligence",
        "Computer Vision",
    }
    assert [t.name for t in org.tags_in("sport_focus")] == ["Padel"]
    assert [f.name for f in org.founders] == ["Ana"]


def test_deleting_organization_removes_tag_links_and_founders(session):
    ai = Term(vocabulary="technology", name="AI")
    org = Organization(name="Gone", tags=[ai], founders=[Founder(name="Ana")])
    session.add(org)
    session.commit()

    session.delete(org)
    session.commit()

    assert session.scalars(select(Founder)).all() == []
    assert session.execute(select(organization_terms)).all() == []
    assert session.get(Term, ai.id) is not None
