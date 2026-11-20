from sqlalchemy import func, select

from app.models import Term
from app.seed import seed_vocabularies


def names(session, vocabulary):
    return {
        t.name for t in session.scalars(select(Term).where(Term.vocabulary == vocabulary))
    }


def test_seeds_event_types_with_stable_codes(session):
    seed_vocabularies(session)

    codes = {
        t.code for t in session.scalars(select(Term).where(Term.vocabulary == "event_type"))
    }
    assert {"funding_round", "rebranding", "pivot", "acquisition", "dissolution"} <= codes


def test_organization_types_belong_to_families(session):
    seed_vocabularies(session)

    startup = session.scalars(
        select(Term).where(Term.vocabulary == "organization_type", Term.name == "Startup")
    ).one()
    assert startup.parent.name == "Empresas"
    assert names(session, "organization_family") == {
        "Empresas",
        "Desporto",
        "Conhecimento",
        "Ecossistema",
    }
    assert len(names(session, "organization_type")) == 17


def test_seeds_workbook_vocabularies_without_junk(session):
    seed_vocabularies(session)

    assert "Athlete Performance" in names(session, "area_of_impact")
    assert "Core" in names(session, "relevance")
    assert "Series C+" in names(session, "funding_stage")
    assert "criteria??" not in names(session, "stage")
    assert "N.A." not in names(session, "technology")
    assert "No" not in names(session, "research_evidence")
    assert "Blockchain & Digital Authentication" in names(session, "technology")


def test_stage_has_definitions(session):
    seed_vocabularies(session)

    idea = session.scalars(
        select(Term).where(Term.vocabulary == "stage", Term.name == "Idea")
    ).one()
    assert "Pre-product" in idea.description


def test_seeding_is_idempotent_and_keeps_admin_edits(session):
    seed_vocabularies(session)
    count = session.scalar(select(func.count()).select_from(Term))
    pivot = session.scalars(select(Term).where(Term.code == "pivot")).one()
    pivot.description = "edited by admin"
    session.commit()

    seed_vocabularies(session)

    assert session.scalar(select(func.count()).select_from(Term)) == count
    assert session.scalars(select(Term).where(Term.code == "pivot")).one().description == (
        "edited by admin"
    )
