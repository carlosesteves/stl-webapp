from datetime import datetime

import openpyxl
from sqlalchemy import select

from app.importer.__main__ import import_workbook, read_rows
from app.models import Organization
from app.seed import seed_vocabularies


def make_workbook(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sports Tech PT"
    ws.append([None, "Index", "Name", "MVP", "Last checked", None])
    ws.append([None, 1, "Alpha", "Yes", datetime(2026, 10, 24), None])
    ws.append([None, None, None, None, None, None])
    ws.append([None, 2, "Beta", "No", None, None])
    wb.create_sheet("taxonomy")
    wb.save(path)


def test_read_rows_uses_headers_and_skips_blank_rows(tmp_path):
    path = tmp_path / "w.xlsx"
    make_workbook(path)

    rows = read_rows(path)

    assert [r["Name"] for r in rows] == ["Alpha", "Beta"]
    assert rows[0]["Last checked"] == datetime(2026, 10, 24)
    assert None not in rows[0]


def test_import_workbook_seeds_imports_and_commits(session, tmp_path):
    path = tmp_path / "w.xlsx"
    make_workbook(path)

    report = import_workbook(session, path)

    assert report.created == 2
    assert {o.name for o in session.scalars(select(Organization))} == {"Alpha", "Beta"}


def test_dry_run_rolls_back(session, tmp_path):
    path = tmp_path / "w.xlsx"
    make_workbook(path)

    import_workbook(session, path, dry_run=True)

    assert session.scalars(select(Organization)).all() == []
