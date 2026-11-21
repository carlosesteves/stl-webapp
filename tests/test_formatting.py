from datetime import date
from decimal import Decimal

import pytest

from app.formatting import format_eur, format_event_date


@pytest.mark.parametrize(
    "day, precision, expected",
    [
        (date(2026, 4, 13), "day", "13 Apr 2026"),
        (date(2024, 5, 1), "month", "May 2024"),
        (date(2026, 1, 1), "year", "2026"),
        (None, "unknown", "Date unknown"),
    ],
)
def test_format_event_date_follows_precision(day, precision, expected):
    assert format_event_date(day, precision) == expected


@pytest.mark.parametrize(
    "amount, expected",
    [
        (Decimal("1400000.00"), "€1,400,000"),
        (Decimal("250000"), "€250,000"),
        (Decimal("1234.50"), "€1,234.50"),
        (None, ""),
    ],
)
def test_format_eur(amount, expected):
    assert format_eur(amount) == expected


from app.formatting import display_domain, is_http_url  # noqa: E402


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.court-master.com/", "court-master.com"),
        ("http://emjogo.pt", "emjogo.pt"),
        ("https://eu.zen8swimtrainer.com/products/zen8swimtrainer", "eu.zen8swimtrainer.com"),
        ("https://wisifytech.com/pt", "wisifytech.com"),
        ("www.example.org/x", "example.org"),
        ("", ""),
        (None, ""),
    ],
)
def test_display_domain(url, expected):
    assert display_domain(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://a.test", True),
        ("http://a.test", True),
        ("HTTPS://A.TEST", True),
        ("javascript:alert(1)", False),
        ("data:text/html,x", False),
        ("a.test", False),
        ("", False),
        (None, False),
    ],
)
def test_is_http_url(url, expected):
    assert is_http_url(url) is expected
