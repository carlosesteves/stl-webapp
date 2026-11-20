from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
    text,
)
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


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    legacy_index: Mapped[int | None] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None]

    organization_type_id: Mapped[int | None] = mapped_column(ForeignKey("terms.id"))
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("terms.id"))
    relevance_id: Mapped[int | None] = mapped_column(ForeignKey("terms.id"))

    is_mvp: Mapped[bool | None]
    is_active: Mapped[bool | None]
    is_published: Mapped[bool] = mapped_column(default=False)
    ai_enabled: Mapped[bool | None]
    scaling_potential: Mapped[bool | None]

    country: Mapped[str | None]
    founding_year: Mapped[int | None]
    spin_off_origin: Mapped[str | None]
    website: Mapped[str | None]
    linkedin_url: Mapped[str | None]
    email: Mapped[str | None]
    email_alt: Mapped[str | None]
    seeking: Mapped[str | None]
    comment: Mapped[str | None]

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization_type: Mapped[Term | None] = relationship(foreign_keys=[organization_type_id])
    stage: Mapped[Term | None] = relationship(foreign_keys=[stage_id])
    relevance: Mapped[Term | None] = relationship(foreign_keys=[relevance_id])
