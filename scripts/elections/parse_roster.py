#!/usr/bin/env python3
"""Parse the CEC 115年地方公職人員選舉候選人登記名冊 (13 PDFs) into CSV.

Source: https://web.cec.gov.tw/central/article/64709 (中選會, 登記截止 2026-09-04).
Output: data/elections/2026/registered.csv — one row per registrant
(category, district label exactly as printed, registration date, name, party)
plus data/elections/2026/registered-seats.csv — 政黨推薦/合計/應選名額 per
district for the four categories whose summary tables carry them.

Needs pdfplumber, which the scheduled pipeline does not have; run on a dev box:

    uv run --with pdfplumber python3 scripts/elections/parse_roster.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402
from model import CATEGORIES, DATA_DIR  # noqa: E402

ARTICLE = ("central", "64709")
# Attachment name prefix → category id (see model.CATEGORIES).
FILE_CATEGORY = {
    "1-1": "municipal-mayor", "2-1": "municipal-councilor", "3-1": "county-mayor", "4-1": "county-councilor",
    "5-": "indigenous-district-chief", "6-": "indigenous-district-rep", "7-": "township-mayor",
    "8-": "township-rep", "9-": "village-chief",
}
SEAT_TABLES = {"1-2": "municipal-mayor", "2-2": "municipal-councilor", "3-2": "county-mayor", "4-2": "county-councilor"}


def clean(cell: object) -> str:
    return re.sub(r"\s+", "", str(cell or ""))


def parse_registrants(pdf_path: Path, category: str, source: str) -> list[dict[str, str]]:
    import pdfplumber

    rows: list[dict[str, str]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            for table in page.extract_tables():
                for raw in table:
                    cells = [clean(c) for c in raw]
                    if len(cells) < 4 or cells[0] in ("選舉區", "") and cells[2] in ("姓名", ""):
                        continue
                    if not re.match(r"\d{3}/\d{2}/\d{2}$", cells[1]):
                        continue
                    rows.append({"category": category, "district": cells[0], "registeredOn": cells[1],
                                 "name": cells[2], "party": cells[3], "note": cells[4] if len(cells) > 4 else "",
                                 "page": str(page_no), "source": source})
    return rows


def parse_seats(pdf_path: Path, category: str) -> list[dict[str, str]]:
    import pdfplumber

    out: list[dict[str, str]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for raw in table:
                    cells = [clean(c) for c in raw]
                    if not cells or not cells[0] or cells[0] in ("選舉區",) or not cells[-1].isdigit():
                        continue
                    # last three numeric columns: 未經政黨推薦, 合計, 應選名額
                    out.append({"category": category, "district": cells[0], "registered": cells[-2], "seats": cells[-1]})
    return out


def main() -> int:
    art = fetch.article(*ARTICLE)
    source = fetch.article_url(*ARTICLE)
    out_dir = DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    registrants: list[dict[str, str]] = []
    seats: list[dict[str, str]] = []
    for file_name in art["files"]:
        label = art["fileNames"][file_name] or ""
        prefix = label.split("(")[0]
        path = fetch.cached_file(file_name)
        if prefix in FILE_CATEGORY:
            rows = parse_registrants(path, FILE_CATEGORY[prefix], source)
            print(f"{label}: {len(rows)} registrants", file=sys.stderr)
            registrants.extend(rows)
        elif prefix in SEAT_TABLES:
            rows = parse_seats(path, SEAT_TABLES[prefix])
            print(f"{label}: {len(rows)} districts", file=sys.stderr)
            seats.extend(rows)
    fields = ["category", "district", "registeredOn", "name", "party", "note", "page", "source"]
    with (out_dir / "registered.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(registrants)
    with (out_dir / "registered-seats.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["category", "district", "registered", "seats"])
        writer.writeheader()
        writer.writerows(seats)
    by_cat: dict[str, int] = {}
    for row in registrants:
        by_cat[row["category"]] = by_cat.get(row["category"], 0) + 1
    for cat in CATEGORIES:
        print(f"{cat}: {by_cat.get(cat, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
