#!/usr/bin/env python3
"""臺北市選舉委員會 → data/elections/2026/numbers/mect.csv

* 65401 臺北市第9屆市長、第15屆議員及第15屆里長選舉候選人姓名號次抽籤結果
  （3 個 pdf 附件「候選人登記冊(有號次)」：市長、議員、里長；含推薦之政黨）

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/mect.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "mect"
COUNTY = "臺北市"
ARTICLE = "65401"
FILE_CATEGORY = {
    "直轄市長": "municipal-mayor",
    "直轄市議員": "municipal-councilor",
    "村里長": "village-chief",
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


def rows() -> list[dict]:
    art = fetch.article(ROUTE, ARTICLE)
    url = fetch.article_url(ROUTE, ARTICLE)
    result = []
    for file_name in art["files"]:
        label = art["fileNames"][file_name] or ""
        cat = next((c for key, c in FILE_CATEGORY.items() if f"115年{key}選舉" in label), None)
        if not cat:
            raise SystemExit(f"unexpected attachment {file_name} {label}")
        file_url = fetch.file_url(file_name)
        path = fetch.cached_file(file_name)
        fetched = fetch.meta(file_url).get("fetchedAt", "")
        for r in table_rows(path):
            result.append({"category": cat, "district": r["選舉區"], "number": r["抽籤號次"], "name": r["姓名"],
                           "party": r.get("推薦之政黨", ""), "source": url, "sourceFile": file_url,
                           "fetchedAt": fetched})
    return result


def main() -> int:
    path = write_numbers(ROUTE, rows())
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
