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
