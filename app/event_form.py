import calendar
import re
from datetime import date
from decimal import Decimal

from app.importer.parsing import parse_amount_eur

MIN_YEAR, MAX_YEAR = 1800, 2100


def _int(text: str, label: str) -> int:
    try:
        return int(text.strip())
    except ValueError:
        raise ValueError(f"{label} must be a number") from None


def parse_date_parts(year: str, month: str, day: str) -> tuple[date | None, str]:
    year, month, day = year.strip(), month.strip(), day.strip()
    if not (year or month or day):
        return None, "unknown"
    if not year:
        raise ValueError("Enter a year when a month or day is given")
    y = _int(year, "Year")
    if not MIN_YEAR <= y <= MAX_YEAR:
        raise ValueError(f"Year must be between {MIN_YEAR} and {MAX_YEAR}")
    if not month:
        if day:
            raise ValueError("Enter a month when a day is given")
        return date(y, 1, 1), "year"
    m = _int(month, "Month")
    if not 1 <= m <= 12:
        raise ValueError("Month must be between 1 and 12")
    if not day:
        return date(y, m, 1), "month"
    d = _int(day, "Day")
    if not 1 <= d <= calendar.monthrange(y, m)[1]:
        raise ValueError("That day does not exist in the chosen month")
    return date(y, m, d), "day"


def parse_amount_input(text: str) -> Decimal | None:
    text = text.strip()
    if not text:
        return None
    if re.fullmatch(r"€?\s*\d{1,3}(,\d{3})+", text):
        text = text.replace(",", "")
    amount = parse_amount_eur(text.replace(" ", ""))
    if amount is None:
        raise ValueError("Amount not understood (try 1400000 or €1.4M)")
    return amount


def split_investors(text: str) -> list[str]:
    return [name.strip() for name in re.split(r"[\n;]", text) if name.strip()]


from dataclasses import dataclass  # noqa: E402

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models import (  # noqa: E402
    FundingRound,
    FundingRoundInvestor,
    Organization,
    OrganizationEvent,
    Term,
)

FUNDING_ROUND_CODE = "funding_round"


@dataclass
class EventFormData:
    event_type_id: str = ""
    year: str = ""
    month: str = ""
    day: str = ""
    title: str = ""
    description: str = ""
    old_value: str = ""
    new_value: str = ""
    related_name: str = ""
    source_url: str = ""
    is_published: bool = False
    funding_stage_id: str = ""
    amount: str = ""
    investors: str = ""

    @classmethod
    def from_event(cls, event: OrganizationEvent) -> "EventFormData":
        day = event.event_date
        precision = event.date_precision
        data = cls(
            event_type_id=str(event.event_type_id),
            year=str(day.year) if day and precision != "unknown" else "",
            month=str(day.month) if day and precision in ("month", "day") else "",
            day=str(day.day) if day and precision == "day" else "",
            title=event.title,
            description=event.description or "",
            old_value=event.old_value or "",
            new_value=event.new_value or "",
            related_name=(event.related_org.name if event.related_org else event.related_name) or "",
            source_url=event.source_url or "",
            is_published=event.is_published,
        )
        if event.funding_round:
            round_ = event.funding_round
            data.funding_stage_id = str(round_.stage_id or "")
            data.amount = format(round_.amount_eur.normalize(), "f") if round_.amount_eur is not None else ""
            data.investors = "\n".join(i.display_name for i in round_.investors)
        return data


def _optional(text: str) -> str | None:
    return text.strip() or None


def _term_or_none(session: Session, raw_id: str, vocabulary: str) -> Term | None:
    try:
        term = session.get(Term, int(raw_id))
    except ValueError:
        return None
    return term if term is not None and term.vocabulary == vocabulary else None


def _find_organization(session: Session, name: str) -> Organization | None:
    return session.scalars(
        select(Organization).where(func.lower(Organization.name) == name.lower())
    ).first()


def apply_event_form(session: Session, event: OrganizationEvent, data: EventFormData) -> list[str]:
    """Validate the form and, only if it is valid, copy it onto the event. Returns error messages."""
    errors: list[str] = []

    event_type = _term_or_none(session, data.event_type_id, "event_type")
    if event_type is None:
        errors.append("Choose an event type.")
    if not data.title.strip():
        errors.append("Enter a title.")
    try:
        event_date, precision = parse_date_parts(data.year, data.month, data.day)
    except ValueError as error:
        errors.append(str(error))

    is_funding = event_type is not None and event_type.code == FUNDING_ROUND_CODE
    stage = amount = None
    if is_funding:
        if data.funding_stage_id.strip():
            stage = _term_or_none(session, data.funding_stage_id, "funding_stage")
            if stage is None:
                errors.append("Choose a valid funding stage.")
        try:
            amount = parse_amount_input(data.amount)
        except ValueError as error:
            errors.append(str(error))
    if errors:
        return errors

    event.event_type = event_type
    event.title = data.title.strip()
    event.event_date, event.date_precision = event_date, precision
    event.description = _optional(data.description)
    event.old_value = _optional(data.old_value)
    event.new_value = _optional(data.new_value)
    event.source_url = _optional(data.source_url)
    event.is_published = data.is_published

    related_name = _optional(data.related_name)
    event.related_org = _find_organization(session, related_name) if related_name else None
    event.related_name = None if event.related_org else related_name

    if is_funding:
        round_ = event.funding_round or FundingRound()
        round_.stage, round_.amount_eur = stage, amount
        round_.investors = [
            FundingRoundInvestor(
                investor_org=(org := _find_organization(session, name)),
                investor_name=None if org else name,
            )
            for name in split_investors(data.investors)
        ]
        event.funding_round = round_
    else:
        event.funding_round = None
    return []
