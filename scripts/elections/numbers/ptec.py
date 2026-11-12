#!/usr/bin/env python3
"""屏東縣選舉委員會 → data/elections/2026/numbers/ptec.csv

* 65365 屏東縣第20屆縣長暨屏東縣議會第21屆議員選舉候選人姓名號次抽籤結果（2026-10-27；
  PDF 表格「選舉區 抽籤號次 姓名 性別 推薦之政黨 備註」→ gender / party from it;
  原住民 names wrap inside the cell, so the PDF is read as a table）

鄉鎮市長 / 鄉鎮市民代表 / 村里長: ptec has not published those draws on its own
site (bulletin walk 2026-10-15…11-13 and menu); they are left out.

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/ptec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "ptec"
COUNTY = "屏東縣"
ARTICLE = "65365"


def rows() -> list[dict]:
    import pdfplumber

    art = fetch.article(ROUTE, ARTICLE)
    url = fetch.article_url(ROUTE, ARTICLE)
    out = []
    for file_name in art["files"]:
        file_url = fetch.file_url(file_name)
        path = fetch.cached_file(file_name)
        fetched = fetch.meta(file_url).get("fetchedAt", "")
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    for cells in table:
                        cells = [(c or "").strip() for c in cells]
                        if len(cells) < 5 or not cells[0].startswith(COUNTY) or not cells[1].isdigit():
                            continue
                        district, number, name, gender, party = cells[:5]
                        if gender not in ("男", "女") or not name:
                            raise SystemExit(f"unexpected row {cells}")
                        cat = "county-mayor" if district == COUNTY else "county-councilor"
                        if cat == "county-councilor" and not re.fullmatch(COUNTY + r"第\d+選舉區", district):
                            raise SystemExit(f"unexpected district {cells}")
                        out.append({"category": cat, "district": district, "number": number,
                                    "name": " ".join(name.split()), "gender": gender, "party": party,
                                    "source": url, "sourceFile": file_url, "fetchedAt": fetched})
    return out


def main() -> int:
    print(write_numbers(ROUTE, rows()))
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
