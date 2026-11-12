#!/usr/bin/env python3
"""金門縣選舉委員會 → data/elections/2026/numbers/kmec.csv

* 65458 115年地方公職人員選舉候選人號次一欄表 — five text-layer PDF attachments
  (候選人登記冊 with 推薦之政黨 and 抽籤號次, 製表日期 115/10/23): 縣長, 縣議員,
  鄉鎮長, 鄉鎮民代表, 村里長.

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/kmec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "kmec"
COUNTY = "金門縣"
ARTICLE = "65458"
CATEGORY_BY_TITLE = {
    "[115年縣市長選舉]": "county-mayor",
    "[115年縣市議員選舉]": "county-councilor",
    "[115年鄉鎮市長選舉]": "township-mayor",
    "[115年鄉鎮市民代表選舉]": "township-rep",
    "[115年村里長選舉]": "village-chief",
}
LINE = re.compile(rf"^({COUNTY}\S*)\s+(\S+)\s+(\S+)\s+(\d+)$")


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
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        category = next((c for t, c in CATEGORY_BY_TITLE.items() if t in text), None)
        if not category:
            raise SystemExit(f"{file_name}: unknown election type")
        expected = int(re.search(r"列印筆數：(\d+)", text).group(1))
        got = 0
        for line in text.splitlines():
            m = LINE.match(line.strip())
            if not m:
                continue
            district, name, party, num = m.groups()
            out.append({"category": category, "district": district, "number": num, "name": name,
                        "party": party, "source": url, "sourceFile": file_url, "fetchedAt": fetched})
            got += 1
        if got != expected:
            raise SystemExit(f"{file_name}: parsed {got} rows, PDF says 列印筆數 {expected}")
    return out


def main() -> int:
    path = write_numbers(ROUTE, rows())
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
