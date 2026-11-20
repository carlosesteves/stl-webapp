import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Term


def test_term_name_unique_within_vocabulary(session):
    session.add(Term(vocabulary="stage", name="Idea"))
    session.add(Term(vocabulary="stage", name="Idea"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_same_name_allowed_in_different_vocabularies(session):
    session.add(Term(vocabulary="stage", name="Seed"))
    session.add(Term(vocabulary="funding_stage", name="Seed"))

    session.commit()


def test_code_unique_within_vocabulary_when_set(session):
    session.add(Term(vocabulary="event_type", name="A", code="pivot"))
    session.add(Term(vocabulary="event_type", name="B", code="pivot"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_null_codes_do_not_collide(session):
    session.add(Term(vocabulary="stage", name="Idea"))
    session.add(Term(vocabulary="stage", name="Early"))

    session.commit()


def test_unknown_vocabulary_is_rejected(session):
    session.add(Term(vocabulary="bogus", name="X"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_organization_type_can_have_family_parent(session):
    family = Term(vocabulary="organization_family", name="Empresas")
    startup = Term(vocabulary="organization_type", name="Startup", parent=family)
    session.add(startup)
    session.commit()

    assert startup.parent.name == "Empresas"
