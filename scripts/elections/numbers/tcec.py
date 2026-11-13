#!/usr/bin/env python3
"""臺中市選舉委員會 → data/elections/2026/numbers/tcec.csv

All five lists are text PDFs from the commission's 選務系統 report (選舉區 / 抽籤號次 /
姓名 / 性別 / 推薦之政黨 / 備註), published 2026-10-27:

* 65353 臺中市第5屆市長選舉候選人姓名號次抽籤結果
  (cross-checked against 65768 公告臺中市第5屆市長選舉候選人名單, 2026-11-12, which
  prints only 號次＋姓名; the 抽籤結果 is kept as the row source because it also prints
  性別／推薦之政黨)
* 65351 臺中市議會第5屆議員選舉候選人姓名號次抽籤結果
* 65378 臺中市和平區第4屆區長選舉候選人姓名號次抽籤結果
* 65376 臺中市和平區第4屆區民代表選舉候選人姓名號次抽籤結果
* 65380 臺中市第5屆里長選舉候選人姓名號次抽籤結果

Rare characters: the PDFs print 造字 as Private-Use-Area code points (kept, flagged
in ``note``) and one unmappable glyph as ``(cid:N)`` (replaced by the unique
中選會登記名冊 spelling in the same district, flagged in ``note``).

    nice -n 10 uv run --no-project --with pdfplumber python3 scripts/elections/numbers/tcec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, norm_name, read_registered, write_numbers  # noqa: E402

ROUTE = "tcec"
COUNTY = "臺中市"

LISTS = [  # (article id, category)
    ("65353", "municipal-mayor"),
    ("65351", "municipal-councilor"),
    ("65378", "indigenous-district-chief"),
    ("65376", "indigenous-district-rep"),
    ("65380", "village-chief"),
]
ANNOUNCEMENT = "65768"  # 11/12 公告市長候選人名單

PUA = re.compile("[-]")


def join_cell(cell: str | None, *, latin_space: bool = True) -> str:
    """Undo pdfplumber line wraps inside a table cell."""
    parts = [p.strip() for p in (cell or "").split("\n") if p.strip()]
    out = ""
    for part in parts:
        if out and latin_space and re.match(r"[A-Za-z]", part) and re.search(r"[A-Za-z·‧ㆍ]$", out):
            out += " "
        out += part
    return out


def note_pua(row: dict) -> dict:
    """The 選務系統 prints rare characters as 造字 in the Private Use Area; keep them, flag them."""
    hits = [f"{f}含造字 U+{ord(ch):04X}" for f in ("district", "name") for ch in PUA.findall(row[f])]
    if hits:
        row["note"] = "；".join(filter(None, [row.get("note", ""), "、".join(hits) + "（官方PDF私用區字元，非標準Unicode）"]))
    return row


def fix_cid(row: dict, roster: list[dict]) -> dict:
    """Glyphs the PDF font cannot map come out as (cid:N); take the roster spelling."""
    if "(cid:" not in row["name"]:
        return note_pua(row)
    pat = re.compile("^" + re.sub(r"\\\(cid:\d+\\\)", ".", re.escape(row["name"])) + "$")
    hits = [r["name"] for r in roster if r["district"] == row["district"] and pat.match(norm_name(r["name"]))]
    if len(hits) != 1:
        raise ValueError(f"cannot resolve unmapped glyph in {row}")
    row["note"] = f"PDF 字型缺字（{row['name']}），依中選會登記名冊用字補正"
    row["name"] = hits[0]
    return row


def pdf_rows(article_id: str, category: str, roster: list[dict]) -> list[dict]:
    import pdfplumber

    art = fetch.article(ROUTE, article_id)
    url = fetch.article_url(ROUTE, article_id)
    rows = []
    for file_name in art["files"]:
        furl = fetch.file_url(file_name)
        path = fetch.cached_file(file_name)
        fetched = fetch.meta(furl).get("fetchedAt", "")
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    for cells in table:
                        cells = [c or "" for c in cells]
                        if len(cells) < 5 or not cells[1].strip().isdigit():
                            continue
                        district = join_cell(cells[0], latin_space=False)
                        if not district.startswith(COUNTY):
                            raise ValueError(f"unexpected district cell {cells}")
                        row = {"category": category, "district": district, "number": cells[1].strip(),
                               "name": join_cell(cells[2]), "gender": cells[3].strip(),
                               "party": join_cell(cells[4], latin_space=False),
                               "source": url, "sourceFile": furl, "fetchedAt": fetched}
                        if not row["name"]:
                            raise ValueError(f"empty name (image glyph?) {cells}")
                        if len(cells) > 5 and cells[5].strip():
                            row["note"] = join_cell(cells[5], latin_space=False)
                        rows.append(fix_cid(row, roster))
    if not rows:
        raise ValueError(f"{ROUTE} {article_id}: no rows parsed")
    return rows


def cross_check_mayor(mayor_rows: list[dict]) -> None:
    """Assert the 11/12 公告名單 prints the same 號次/姓名 as the 抽籤結果."""
    import pdfplumber

    art = fetch.article(ROUTE, ANNOUNCEMENT)
    for file_name in art["files"]:
        with pdfplumber.open(str(fetch.cached_file(file_name))) as pdf:
            text = "".join(p.extract_text() or "" for p in pdf.pages)
        pairs = re.findall(r"[（(]\s*(\d+)\s*[）)]\s*([^\s（(]+)", text)
        if len(pairs) >= len(mayor_rows):  # the clean (non-scanned) copy
            got = {(n, norm_name(m)) for n, m in pairs}
            want = {(r["number"], norm_name(r["name"])) for r in mayor_rows}
            if got != want:
                raise ValueError(f"公告名單 {got} != 抽籤結果 {want}")
            return
    raise ValueError("no text copy of the 公告名單 found")


def main() -> int:
    roster = read_registered(COUNTY)
    rows: list[dict] = []
    for article_id, category in LISTS:
        rows += pdf_rows(article_id, category, roster)
    cross_check_mayor([r for r in rows if r["category"] == "municipal-mayor"])
    path = write_numbers(ROUTE, rows)
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
