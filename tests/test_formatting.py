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
