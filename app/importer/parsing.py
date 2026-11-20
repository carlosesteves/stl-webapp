import math
import re
from datetime import date, datetime
from decimal import Decimal

PLACEHOLDERS = {"", "n.a.", "n.a", "na", "unknown"}
AMOUNT = re.compile(r"^€?\s*(\d+(?:[.,]\d+)?)\s*([kKmM])?$")
YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
DAY_FIRST = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
ISO_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
MULTIPLIERS = {"k": Decimal(1_000), "m": Decimal(1_000_000)}


def clean(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return None if text.lower() in PLACEHOLDERS else text


def parse_bool(value) -> bool | None:
    text = (clean(value) or "").lower()
    return {"yes": True, "no": False}.get(text)


def parse_year(value) -> int | None:
    if isinstance(value, (int, float)) and not (isinstance(value, float) and math.isnan(value)):
        return int(value)
    text = clean(value)
    if text is None or re.search(r"[€kKmM]\s*$|^€", text):
        return None
    match = YEAR.search(text)
    return int(match.group(1)) if match else None


def parse_amount_eur(value) -> Decimal | None:
    text = clean(value)
    match = AMOUNT.match(text) if text else None
    if not match:
        return None
    number = Decimal(match.group(1).replace(",", "."))
    suffix = (match.group(2) or "").lower()
    return number * MULTIPLIERS.get(suffix, Decimal(1))


def parse_date(value) -> tuple[date | None, str]:
    if isinstance(value, datetime):
        return value.date(), "day"
    if isinstance(value, (int, float)) and not (isinstance(value, float) and math.isnan(value)):
        return date(int(value), 1, 1), "year"
    text = clean(value)
    if text is None:
        return None, "unknown"
    if match := ISO_DAY.match(text):
        year, month, day = map(int, match.groups())
        return date(year, month, day), "day"
    if match := DAY_FIRST.match(text):
        day, month, year = map(int, match.groups())
        return date(year, month, day), "day"
    if re.fullmatch(r"\d{4}", text):
        return date(int(text), 1, 1), "year"
    return None, "unknown"


def split_multi(value) -> list[str]:
    text = clean(value)
    if text is None:
        return []
    return [part for part in (clean(p) for p in text.split(";")) if part]


def split_names(value) -> list[str]:
    text = clean(value)
    if text is None:
        return []
    parts = re.split(r"[;,&]|\s+e\s+", text)
    return [part for part in (clean(p) for p in parts) if part]


def parse_investors(value) -> tuple[list[str], int | None]:
    text = clean(value)
    if text is None:
        return [], None
    text = re.sub(r"^from\s+", "", text, flags=re.I)
    year = None
    names = []
    for part in re.split(r"[;,+]|\s+and\s+", text):
        part = re.sub(r"^and\s+", "", part.strip(), flags=re.I)
        if year_match := re.search(r"\((\d{4})\)\s*$", part):
            year = int(year_match.group(1))
            part = part[: year_match.start()]
        name = clean(part)
        if name and parse_amount_eur(name) is None:
            names.append(name)
    return names, year
