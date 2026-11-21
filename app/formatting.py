from datetime import date
from decimal import Decimal
from urllib.parse import urlparse

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def format_event_date(day: date | None, precision: str) -> str:
    if day is None or precision == "unknown":
        return "Date unknown"
    if precision == "year":
        return str(day.year)
    if precision == "month":
        return f"{MONTHS[day.month - 1]} {day.year}"
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def format_eur(amount: Decimal | None) -> str:
    if amount is None:
        return ""
    if amount == amount.to_integral_value():
        return f"€{amount:,.0f}"
    return f"€{amount:,.2f}"


def is_http_url(url: str | None) -> bool:
    return bool(url) and url.lower().startswith(("http://", "https://"))


def display_domain(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "//" in url else f"//{url}")
    host = parsed.netloc or parsed.path.split("/")[0]
    return host.removeprefix("www.")
