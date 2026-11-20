from sqlalchemy import select
from sqlalchemy.orm import Session

from app import seed_data
from app.db import get_engine
from app.models import Term


def seed_vocabularies(session: Session) -> None:
    """Insert missing terms; existing terms (and admin edits to them) are left alone."""
    existing = {
        (term.vocabulary, term.name): term for term in session.scalars(select(Term))
    }

    def ensure(vocabulary, name, *, code=None, description=None, parent=None, sort_order=0):
        term = existing.get((vocabulary, name))
        if term is None:
            term = Term(
                vocabulary=vocabulary,
                name=name,
                code=code,
                description=description,
                parent=parent,
                sort_order=sort_order,
            )
            session.add(term)
            existing[(vocabulary, name)] = term
        return term

    for order, (name, code, description) in enumerate(seed_data.EVENT_TYPES):
        ensure("event_type", name, code=code, description=description, sort_order=order)

    order = 0
    for family_name, type_names in seed_data.ORGANIZATION_TYPES.items():
        family = ensure("organization_family", family_name, sort_order=order)
        for type_name in type_names:
            order += 1
            ensure("organization_type", type_name, parent=family, sort_order=order)

    for order, (name, description) in enumerate(seed_data.STAGES):
        ensure("stage", name, description=description, sort_order=order)

    for order, (name, description) in enumerate(seed_data.INVESTMENT_STAGES):
        ensure("investment_stage", name, description=description, sort_order=order)

    for vocabulary, names in seed_data.SIMPLE_VOCABULARIES.items():
        for order, name in enumerate(names):
            ensure(vocabulary, name, sort_order=order)

    session.commit()


if __name__ == "__main__":
    with Session(get_engine()) as session:
        seed_vocabularies(session)
