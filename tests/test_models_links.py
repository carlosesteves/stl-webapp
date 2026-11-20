import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Organization, PublicFunding, Relationship


@pytest.fixture
def org(session):
    org = Organization(name="Acme")
    session.add(org)
    session.commit()
    return org


def test_public_funding_defaults_to_prr(session, org):
    funding = PublicFunding(organization=org, project_ref="C16-i02", amount_eur=30000)
    session.add(funding)
    session.commit()

    assert funding.programme == "PRR"
    assert org.public_funding == [funding]


def test_relationship_with_free_text_party(session, org):
    link = Relationship(organization=org, kind="customer", related_name="FC Porto")
    session.add(link)
    session.commit()

    assert org.relationships == [link]


def test_relationship_can_point_to_organization(session, org):
    other = Organization(name="Other")
    link = Relationship(organization=org, kind="ecosystem_connection", related_org=other)
    session.add(link)
    session.commit()

    assert link.related_org.name == "Other"


def test_relationship_needs_a_party(session, org):
    session.add(Relationship(organization=org, kind="customer"))

    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize("kind", ["partner", "pilot", "incubation", "bogus"])
def test_dated_or_unknown_kinds_are_not_relationships(session, org, kind):
    session.add(Relationship(organization=org, kind=kind, related_name="X"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_organization_removes_links(session, org):
    session.add_all([
        PublicFunding(organization=org, amount_eur=1),
        Relationship(organization=org, kind="use_case", related_name="ABIMOTA"),
    ])
    session.commit()

    session.delete(org)
    session.commit()

    assert session.query(PublicFunding).count() == 0
    assert session.query(Relationship).count() == 0
