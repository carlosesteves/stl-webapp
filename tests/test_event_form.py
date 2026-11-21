from datetime import date
from decimal import Decimal

import pytest

from app.event_form import parse_amount_input, parse_date_parts, split_investors


@pytest.mark.parametrize(
    "year, month, day, expected",
    [
        ("", "", "", (None, "unknown")),
        ("2024", "", "", (date(2024, 1, 1), "year")),
        (" 2024 ", "5", "", (date(2024, 5, 1), "month")),
        ("2024", "05", "13", (date(2024, 5, 13), "day")),
    ],
)
def test_date_precision_follows_what_was_filled_in(year, month, day, expected):
    assert parse_date_parts(year, month, day) == expected


@pytest.mark.parametrize(
    "year, month, day",
    [
        ("", "5", ""),
        ("", "", "13"),
        ("2024", "", "13"),
        ("2024", "13", ""),
        ("2024", "0", ""),
        ("2024", "2", "30"),
        ("abcd", "", ""),
        ("1500", "", ""),
        ("2024", "x", ""),
    ],
)
def test_invalid_dates_are_rejected_with_a_message(year, month, day):
    with pytest.raises(ValueError) as error:
        parse_date_parts(year, month, day)

    assert str(error.value)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("", None),
        ("  ", None),
        ("1400000", Decimal("1400000")),
        ("€1.4M", Decimal("1400000")),
        ("1.4m", Decimal("1400000")),
        ("250k", Decimal("250000")),
        ("1,400,000", Decimal("1400000")),
        ("€ 12.5", Decimal("12.5")),
    ],
)
def test_parse_amount_input(text, expected):
    assert parse_amount_input(text) == expected


@pytest.mark.parametrize("text", ["lots", "-5", "1.4 billion", "€€"])
def test_unparseable_amounts_are_rejected(text):
    with pytest.raises(ValueError):
        parse_amount_input(text)


def test_split_investors_by_line_or_semicolon_and_drops_blanks():
    assert split_investors("Lince\n José Pinto ;Portugal Ventures\n\n") == [
        "Lince",
        "José Pinto",
        "Portugal Ventures",
    ]
    assert split_investors("") == []
