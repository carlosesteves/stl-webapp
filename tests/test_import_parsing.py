from datetime import date, datetime
from decimal import Decimal

import pytest

from app.importer.parsing import (
    clean,
    parse_amount_eur,
    parse_bool,
    parse_date,
    parse_investors,
    parse_year,
    split_names,
    split_multi,
)


@pytest.mark.parametrize("raw", [None, float("nan"), "", "  ", "N.A.", "N.A", "n.a.", "Unknown"])
def test_clean_treats_placeholders_as_missing(raw):
    assert clean(raw) is None


def test_clean_trims_and_collapses_whitespace():
    assert clean("  Blockchain  & Digital   Authentication ") == "Blockchain & Digital Authentication"


@pytest.mark.parametrize(
    "raw, expected",
    [("Yes", True), ("YES", True), ("No", False), ("no", False), ("N.A.", None), (None, None), ("maybe", None)],
)
def test_parse_bool(raw, expected):
    assert parse_bool(raw) is expected


@pytest.mark.parametrize(
    "raw, expected",
    [(2024, 2024), (2024.0, 2024), ("2022", 2022), ("N.A.", None), ("Unknown", None), (None, None), ("3.09.2026", 2026), ("€100k", None)],
)
def test_parse_year(raw, expected):
    assert parse_year(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("€250k", Decimal("250000")),
        ("€1.4M", Decimal("1400000")),
        ("€12.2M ", Decimal("12200000")),
        ("€50K", Decimal("50000")),
        ("30k", Decimal("30000")),
        ("€2.59M", Decimal("2590000")),
        ("€1M", Decimal("1000000")),
        ("Pitchbook", None),
        ("C16-i02", None),
        (None, None),
    ],
)
def test_parse_amount_eur(raw, expected):
    assert parse_amount_eur(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        (datetime(2026, 10, 24), (date(2026, 10, 24), "day")),
        ("2026-04-13", (date(2026, 4, 13), "day")),
        ("3.09.2026", (date(2026, 9, 3), "day")),
        (2025, (date(2025, 1, 1), "year")),
        ("2025", (date(2025, 1, 1), "year")),
        ("N.A.", (None, "unknown")),
        (None, (None, "unknown")),
        ("€100k", (None, "unknown")),
    ],
)
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


def test_split_multi_on_semicolons_and_drops_placeholders():
    assert split_multi("Motion Sensors;  IoT/Connected Devices; Smart Equipment; N.A.") == [
        "Motion Sensors",
        "IoT/Connected Devices",
        "Smart Equipment",
    ]
    assert split_multi(None) == []


def test_split_names_handles_mixed_separators():
    assert split_names("Vasco Correia, Ricardo Pinto, Ricardo Pereira e Tiago Ribeiro") == [
        "Vasco Correia",
        "Ricardo Pinto",
        "Ricardo Pereira",
        "Tiago Ribeiro",
    ]
    assert split_names("Joana Serra & João Vasconcelos") == ["Joana Serra", "João Vasconcelos"]
    assert split_names("A; B;  C") == ["A", "B", "C"]


@pytest.mark.parametrize(
    "raw, names, year",
    [
        ("Angels Way", ["Angels Way"], None),
        ("Lince capital + Portugal Ventures", ["Lince capital", "Portugal Ventures"], None),
        (
            "GED Ventures, José Pinto, Pedro Aguiar, Tiago Monteiro",
            ["GED Ventures", "José Pinto", "Pedro Aguiar", "Tiago Monteiro"],
            None,
        ),
        (
            "Riva Group, Albuquerque & Associados, and António Félix da Costa;€9M",
            ["Riva Group", "Albuquerque & Associados", "António Félix da Costa"],
            None,
        ),
        (
            "from Faber Ventures, Kibo Ventures, White Star Capital and Caixa Capital",
            ["Faber Ventures", "Kibo Ventures", "White Star Capital", "Caixa Capital"],
            None,
        ),
        ("ADvantage(2022)", ["ADvantage"], 2022),
        ("€50K", [], None),
        (None, [], None),
    ],
)
def test_parse_investors(raw, names, year):
    assert parse_investors(raw) == (names, year)
