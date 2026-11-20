from dataclasses import dataclass, field
from datetime import datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importer.parsing import (
    clean,
    parse_amount_eur,
    parse_bool,
    parse_date,
    parse_investors,
    parse_year,
    split_multi,
    split_names,
)
from app.models import (
    Founder,
    FundingRound,
    FundingRoundInvestor,
    Organization,
    OrganizationEvent,
    Term,
)

ORGANIZATION_TYPE_MAP = {
    "Startup": "Startup",
    "Spin-off": "Startup",
    "Scaleup": "Scaleup",
    "SME": "SME",
    "Corporation": "Corporation",
    "Consulting Firm": "Consulting & Services",
    "Consulting & Services": "Consulting & Services",
    "Sport Federation": "Sport Federation & League",
    "Sport Club": "Sport Club",
    "Health & Fitness Operator": "Health & Fitness Operator",
    "University": "University",
    "Research Center": "Research Center",
    "Sport Lab": "Sport Lab & Performance Centre",
    "Sport Lab & Performance Centre": "Sport Lab & Performance Centre",
    "Technology & Innovation Centers": "Interface Centre (CTI/CoLAB)",
    "Colab": "Interface Centre (CTI/CoLAB)",
    "Test Bed": "Test Bed",
    "Incubator": "Incubator & Accelerator",
    "Accellerator": "Incubator & Accelerator",
    "Incubator & Accelerator": "Incubator & Accelerator",
    "Research & Innovation Cluster": "Cluster & Association",
    "Cluster & Association": "Cluster & Association",
    "Investment": "Investor",
    "Investment fund": "Investor",
    "Investment firm": "Investor",
    "Investor": "Investor",
    "National Governing Body": "Public Agency",
}

TAG_COLUMNS = {
    "Area of Impact": "area_of_impact",
    "Category": "category",
    "Technology": "technology",
    "Sport Focus": "sport_focus",
    "Market": "market",
    "Evidence-Based Research": "research_evidence",
    "Investor type": "investor_type",
    "Investor Subtype": "investor_subtype",
    "Investment Stage": "investment_stage",
}

VALUE_CORRECTIONS = {"Athelete Performance": "Athlete Performance"}


@dataclass
class Issue:
    name: str
    column: str
    value: str
    message: str


@dataclass
class Report:
    created: int = 0
    skipped: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


class Vocabulary:
    def __init__(self, session: Session):
        self._terms = {
            (t.vocabulary, t.name.lower()): t for t in session.scalars(select(Term))
        }

    def event_type(self, code: str) -> Term:
        return next(
            t for (v, _), t in self._terms.items() if v == "event_type" and t.code == code
        )

    def find(self, vocabulary: str, name: str) -> Term | None:
        return self._terms.get((vocabulary, name.lower()))


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_datetime(value) -> datetime | None:
    day, precision = parse_date(value)
    if day is None:
        return None
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def import_rows(session: Session, rows: list[dict]) -> Report:
    report = Report()
    vocabulary = Vocabulary(session)
    known = {o.name.lower(): o for o in session.scalars(select(Organization))}
    existing = {o.name for o in known.values()}
    created: list[tuple[dict, Organization]] = []

    for row in rows:
        name = clean(row.get("Name"))
        if name is None:
            report.issues.append(Issue(str(row.get("Index")), "Name", "", "Row has no name"))
            continue
        if name in existing:
            report.skipped.append(name)
            continue
        organization = _build_organization(name, row, vocabulary, report)
        session.add(organization)
        known[name.lower()] = organization
        existing.add(name)
        created.append((row, organization))
        report.created += 1

    for row, organization in created:
        organization.events.extend(_build_events(organization, row, vocabulary, known, report))
    return report


def _build_organization(name: str, row: dict, vocabulary: Vocabulary, report: Report) -> Organization:
    is_mvp = parse_bool(row.get("MVP"))
    created_at = _as_datetime(row.get("Date added"))
    updated_at = _as_datetime(row.get("Last checked")) or created_at

    organization = Organization(
        name=name,
        legacy_index=_as_int(row.get("Index")),
        description=clean(row.get("Description")),
        is_mvp=is_mvp,
        is_active=parse_bool(row.get("Active")),
        is_published=is_mvp is True,
        ai_enabled=parse_bool(row.get("AI")),
        scaling_potential=True if parse_bool(row.get("Scaling potential")) else None,
        country=clean(row.get("Origin")),
        founding_year=parse_year(row.get("Founding year")),
        spin_off_origin=clean(row.get("Spin-of origin")),
        website=clean(row.get("Website")),
        linkedin_url=clean(row.get("Linkedin")),
        email=clean(row.get("Email")),
        email_alt=clean(row.get("Email alt")),
        seeking=clean(row.get("Looking for")),
        comment=clean(row.get("Comment")),
    )
    if created_at:
        organization.created_at = created_at
        organization.updated_at = updated_at

    organization.organization_type = _organization_type(name, row, vocabulary, report)
    stage = clean(row.get("Stage"))
    if stage:
        organization.stage = _find(vocabulary, "stage", stage, name, "Stage", report)

    for column, vocab_name in TAG_COLUMNS.items():
        for value in split_multi(row.get(column)):
            term = _find(vocabulary, vocab_name, VALUE_CORRECTIONS.get(value, value), name, column, report, shown=value)
            if term and term not in organization.tags:
                organization.tags.append(term)

    organization.founders = [Founder(name=n) for n in split_names(row.get("Founders/CEO"))]
    return organization


def _organization_type(name, row, vocabulary, report):
    old = clean(row.get("Organization"))
    if old is None:
        return None
    new = ORGANIZATION_TYPE_MAP.get(old)
    if new is None:
        report.issues.append(Issue(name, "Organization", old, "No equivalent in the new taxonomy"))
        return None
    return vocabulary.find("organization_type", new)


def _find(vocabulary, vocab_name, value, org_name, column, report, shown=None):
    term = vocabulary.find(vocab_name, value)
    if term is None:
        report.issues.append(Issue(org_name, column, shown or value, f"Not in the {vocab_name} vocabulary"))
    return term


def _present(value) -> bool:
    return value is not None and str(value).strip() not in ("", "nan")


def _event(vocabulary, code, title, date_value=None, precision="unknown", **fields) -> OrganizationEvent:
    return OrganizationEvent(
        event_type=vocabulary.event_type(code),
        title=title,
        event_date=date_value,
        date_precision=precision,
        **fields,
    )


def _build_events(organization, row, vocabulary, known, report) -> list[OrganizationEvent]:
    name = organization.name
    events = []

    if old_name := clean(row.get("Rebranding")):
        events.append(_event(
            vocabulary, "rebranding", f"Renamed from {old_name} to {name}",
            old_value=old_name, new_value=name,
        ))

    if parse_bool(row.get("Pivot")):
        sector = clean(row.get("Sector pivoting to"))
        events.append(_event(
            vocabulary, "pivot", f"Pivot to {sector}" if sector else "Pivot", new_value=sector,
        ))

    if parse_bool(row.get("M&A")):
        events.append(_acquisition_event(vocabulary, row, known))

    if _present(row.get("Date of dissolution")):
        day, precision = parse_date(row.get("Date of dissolution"))
        events.append(_event(vocabulary, "dissolution", "Dissolved", day, precision))

    if funding := _funding_event(name, row, vocabulary, known, report):
        events.append(funding)
    return events


def _acquisition_event(vocabulary, row, known) -> OrganizationEvent:
    parts = split_multi(row.get("Buyer"))
    year_part = next((p for p in parts if p.isdigit() and len(p) == 4), None)
    buyer = next((p for p in parts if p != year_part), None)
    day, precision = parse_date(year_part)
    return _event(
        vocabulary, "acquisition", f"Acquired by {buyer}" if buyer else "Acquired", day, precision,
        related_name=buyer, related_org=known.get(buyer.lower()) if buyer else None,
    )


def _funding_event(name, row, vocabulary, known, report) -> OrganizationEvent | None:
    stage_name = clean(row.get("Funding stage2"))
    investors, investor_year = parse_investors(row.get("Investors"))
    amount = parse_amount_eur(row.get("Funding"))
    date_cell = row.get("Funding date")
    if amount is None:
        amount = parse_amount_eur(date_cell, strict=True) or parse_amount_eur(
            row.get("Investors"), strict=True
        )
    day, precision = (None, "unknown")
    if parse_amount_eur(date_cell, strict=True) is None:
        day, precision = parse_date(date_cell)
    if day is None and investor_year:
        day, precision = parse_date(investor_year)

    has_detail = investors or amount is not None or day is not None
    if not has_detail and stage_name in (None, "Bootstrapped"):
        return None

    stage = None
    if stage_name:
        stage = _find(vocabulary, "funding_stage", stage_name, name, "Funding stage2", report)
    title = f"{stage.name} funding round" if stage else "Funding round"
    event = _event(vocabulary, "funding_round", title, day, precision)
    event.funding_round = FundingRound(
        stage=stage,
        amount_eur=amount,
        investors=[
            FundingRoundInvestor(
                investor_org=known.get(investor.lower()),
                investor_name=None if investor.lower() in known else investor,
            )
            for investor in investors
        ],
    )
    return event
