from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

VOCABULARIES = (
    "organization_family",
    "organization_type",
    "area_of_impact",
    "category",
    "technology",
    "sport_focus",
    "market",
    "stage",
    "funding_stage",
    "investor_type",
    "investor_subtype",
    "investment_stage",
    "research_evidence",
    "relevance",
    "event_type",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True)
    description: Mapped[str] = mapped_column(default="")
    published: Mapped[bool] = mapped_column(default=False)


class Term(Base):
    __tablename__ = "terms"
    __table_args__ = (
        UniqueConstraint("vocabulary", "name"),
        CheckConstraint(f"vocabulary IN ({_quoted(VOCABULARIES)})", name="vocabulary_known"),
        Index(
            "ix_terms_vocabulary_code",
            "vocabulary",
            "code",
            unique=True,
            postgresql_where=text("code IS NOT NULL"),
            sqlite_where=text("code IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vocabulary: Mapped[str]
    name: Mapped[str]
    code: Mapped[str | None]
    description: Mapped[str | None]
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("terms.id"))
    sort_order: Mapped[int] = mapped_column(default=0)

    parent: Mapped["Term | None"] = relationship(remote_side=[id])
