import argparse
import csv
import sys
from pathlib import Path

import openpyxl
from sqlalchemy.orm import Session

from app.db import get_engine
from app.importer.workbook import Report, import_rows
from app.seed import seed_vocabularies

SHEET = "Sports Tech PT"


def read_rows(path: Path) -> list[dict]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook[SHEET]
    iterator = sheet.iter_rows(values_only=True)
    headers = next(iterator)
    rows = []
    for values in iterator:
        row = {h: v for h, v in zip(headers, values) if h is not None}
        if any(v not in (None, "") for v in row.values()):
            rows.append(row)
    return rows


def import_workbook(session: Session, path: Path, dry_run: bool = False) -> Report:
    seed_vocabularies(session)
    report = import_rows(session, read_rows(path))
    if dry_run:
        session.rollback()
    else:
        session.commit()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the sports tech workbook")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="roll back at the end")
    parser.add_argument("--issues-csv", type=Path, help="write the issue report here")
    args = parser.parse_args()

    with Session(get_engine()) as session:
        report = import_workbook(session, args.workbook, dry_run=args.dry_run)

    print(f"created {report.created}, skipped {len(report.skipped)}, issues {len(report.issues)}")
    if args.dry_run:
        print("dry run: nothing was saved")
    if args.issues_csv:
        with args.issues_csv.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["organization", "column", "value", "message"])
            for issue in report.issues:
                writer.writerow([issue.name, issue.column, issue.value, issue.message])
    elif report.issues:
        print("(use --issues-csv to save the issues)", file=sys.stderr)


if __name__ == "__main__":
    main()
