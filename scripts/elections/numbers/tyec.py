#!/usr/bin/env python3
"""桃園市選舉委員會 → data/elections/2026/numbers/tyec.csv

* 65650 115年市長選舉候選人名單公告（2026-11-12，pdf 文字層「（1）黃世杰（2）張善政」，無政黨）→ 市長
* 65400 115年桃園市市長及市議員選舉候選人姓名號次抽籤結果（2026-10-27，pdf，含推薦之政黨）→ 市議員
* 65506 115年桃園市里長、復興區長及區民代表選舉候選人姓名號次抽籤結果（2026-11-02，pdf，含推薦之政黨）
  → 里長（含中壢區普強里第2次登記）、復興區長、復興區民代表

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/tyec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "tyec"
COUNTY = "桃園市"
MAYOR_NOTICE = "65650"
ARTICLES = ["65400", "65506"]
FILE_CATEGORY = {  # attachment-name keyword → category (order matters: 區民代表 before 區長)
    "直轄市長選舉": "municipal-mayor",
    "直轄市議員選舉": "municipal-councilor",
    "山地原住民區民代表選舉": "indigenous-district-rep",
    "山地原住民區長選舉": "indigenous-district-chief",
    "村里長選舉": "village-chief",
    "里長選舉第2次登記": "village-chief",
}


def clean(cell: str | None) -> str:
    return re.sub(r"\s+", "", cell or "")


def table_rows(path: Path) -> list[dict[str, str]]:
    """Rows of the 選舉區/姓名/推薦之政黨/抽籤號次 table across all pages (cells may wrap)."""
    import pdfplumber

    out: list[dict[str, str]] = []
    cols: dict[str, int] | None = None
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for raw in table:
                    cells = [clean(c) for c in raw]
                    if "選舉區" in cells and "姓名" in cells:
                        cols = {name: cells.index(name) for name in cells if name}
                        continue
                    if cols is None or not cells[cols["選舉區"]].startswith(COUNTY) or not cells[cols["抽籤號次"]].isdigit():
                        continue
                    out.append({key: cells[idx] for key, idx in cols.items()})
    return out


def mayor_rows() -> list[dict]:
    """65650 公告桃園市第4屆市長選舉候選人名單 (pdf 文字層：（1）黃世杰（2）張善政)."""
    import pdfplumber

    art = fetch.article(ROUTE, MAYOR_NOTICE)
    url = fetch.article_url(ROUTE, MAYOR_NOTICE)
    file_name = next(f for f in art["files"] if "關防" not in (art["fileNames"][f] or ""))
    file_url = fetch.file_url(file_name)
    with pdfplumber.open(str(fetch.cached_file(file_name))) as pdf:
        text = "".join(page.extract_text() or "" for page in pdf.pages)
    names = re.search(r"市長選舉候選人名單[:：](.+?)二、", re.sub(r"\s+", "", text)).group(1)
    return [{"category": "municipal-mayor", "district": COUNTY, "number": num, "name": name,
             "source": url, "sourceFile": file_url, "fetchedAt": fetch.meta(file_url).get("fetchedAt", "")}
            for num, name in re.findall(r"[（(](\d+)[）)]([^（(]+)", names)]


def rows() -> list[dict]:
    result = mayor_rows()
    for article_id in ARTICLES:
        art = fetch.article(ROUTE, article_id)
        url = fetch.article_url(ROUTE, article_id)
        for file_name in art["files"]:
            file_url = fetch.file_url(file_name)
            path = fetch.cached_file(file_name)
            fetched = fetch.meta(file_url).get("fetchedAt", "")
            label = art["fileNames"][file_name] or ""
            cat = next((c for key, c in FILE_CATEGORY.items() if key in label), None)
            if cat is None:
                raise SystemExit(f"unexpected attachment {file_name} {label}")
            if cat == "municipal-mayor":
                continue  # taken from the 候選人名單公告 (MAYOR_NOTICE) instead
            for r in table_rows(path):
                note = "第2次登記" if "第2次登記" in label else ""
                result.append({"category": cat, "district": r["選舉區"], "number": r["抽籤號次"], "name": r["姓名"],
                               "party": r.get("推薦之政黨", ""), "source": url, "sourceFile": file_url,
                               "fetchedAt": fetched, "note": note})
    return result


def main() -> int:
    path = write_numbers(ROUTE, rows())
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
