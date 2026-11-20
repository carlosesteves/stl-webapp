from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    CheckConstraint,
    Table,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
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


organization_terms = Table(
    "organization_terms",
    Base.metadata,
    Column(
        "organization_id",
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("term_id", ForeignKey("terms.id"), primary_key=True),
    Index("ix_organization_terms_term_id", "term_id"),
)


class Founder(Base):
    __tablename__ = "founders"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    name: Mapped[str]


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

    tags: Mapped[list[Term]] = relationship(secondary=organization_terms)
    founders: Mapped[list[Founder]] = relationship(
        cascade="all, delete-orphan", order_by=Founder.id
    )

    events: Mapped[list["OrganizationEvent"]] = relationship(
        back_populates="organization",
        foreign_keys="OrganizationEvent.organization_id",
        cascade="all, delete-orphan",
        order_by=(
            "[OrganizationEvent.event_date.is_(None),"
            " OrganizationEvent.event_date, OrganizationEvent.id]"
        ),
    )

    public_funding: Mapped[list["PublicFunding"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    relationships: Mapped[list["Relationship"]] = relationship(
        back_populates="organization",
        foreign_keys="Relationship.organization_id",
        cascade="all, delete-orphan",
    )

    def tags_in(self, vocabulary: str) -> list[Term]:
        return [tag for tag in self.tags if tag.vocabulary == vocabulary]


DATE_PRECISIONS = ("day", "month", "year", "unknown")


class OrganizationEvent(Base):
    __tablename__ = "organization_events"
    __table_args__ = (
        CheckConstraint(
            f"date_precision IN ({_quoted(DATE_PRECISIONS)})", name="date_precision_known"
        ),
        CheckConstraint(
            "(event_date IS NULL) = (date_precision = 'unknown')",
            name="unknown_precision_iff_no_date",
        ),
        Index("ix_organization_events_org_date", "organization_id", "event_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    event_type_id: Mapped[int] = mapped_column(ForeignKey("terms.id"))
    event_date: Mapped[date | None]
    date_precision: Mapped[str] = mapped_column(default="year")
    title: Mapped[str]
    description: Mapped[str | None]
    old_value: Mapped[str | None]
    new_value: Mapped[str | None]
    related_org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    related_name: Mapped[str | None]
    source_url: Mapped[str | None]
    is_published: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped[Organization] = relationship(
        back_populates="events", foreign_keys=[organization_id]
    )
    event_type: Mapped[Term] = relationship()
    related_org: Mapped[Organization | None] = relationship(foreign_keys=[related_org_id])
    funding_round: Mapped["FundingRound | None"] = relationship(
        back_populates="event", cascade="all, delete-orphan", uselist=False
    )


class FundingRound(Base):
    __tablename__ = "funding_rounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("organization_events.id", ondelete="CASCADE"), unique=True
    )
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("terms.id"))
    amount_eur: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None]

    event: Mapped[OrganizationEvent] = relationship(back_populates="funding_round")
    stage: Mapped[Term | None] = relationship()
    investors: Mapped[list["FundingRoundInvestor"]] = relationship(
        cascade="all, delete-orphan", order_by="FundingRoundInvestor.id"
    )


class FundingRoundInvestor(Base):
    __tablename__ = "funding_round_investors"
    __table_args__ = (
        CheckConstraint(
            "investor_org_id IS NOT NULL OR investor_name IS NOT NULL",
            name="investor_org_or_name",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    funding_round_id: Mapped[int] = mapped_column(
        ForeignKey("funding_rounds.id", ondelete="CASCADE")
    )
    investor_org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    investor_name: Mapped[str | None]

    investor_org: Mapped[Organization | None] = relationship()

    @property
    def display_name(self) -> str:
        return self.investor_org.name if self.investor_org else self.investor_name


class PublicFunding(Base):
    __tablename__ = "public_funding"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    programme: Mapped[str] = mapped_column(default="PRR")
    project_ref: Mapped[str | None]
    amount_eur: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None]

    organization: Mapped[Organization] = relationship(back_populates="public_funding")


RELATIONSHIP_KINDS = (
    "customer",
    "ecosystem_connection",
    "past_investment",
    "use_case",
    "research_link",
)


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_quoted(RELATIONSHIP_KINDS)})", name="kind_known"),
        CheckConstraint(
            "related_org_id IS NOT NULL OR related_name IS NOT NULL",
            name="related_org_or_name",
        ),
        Index("ix_relationships_org_kind", "organization_id", "kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    kind: Mapped[str]
    related_org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    related_name: Mapped[str | None]
    url: Mapped[str | None]
    notes: Mapped[str | None]

    organization: Mapped[Organization] = relationship(
        back_populates="relationships", foreign_keys=[organization_id]
    )
    related_org: Mapped[Organization | None] = relationship(foreign_keys=[related_org_id])
