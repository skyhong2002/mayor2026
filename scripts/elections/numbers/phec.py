#!/usr/bin/env python3
"""澎湖縣選舉委員會 → data/elections/2026/numbers/phec.csv

* 65367 澎湖縣115年地方公職人員選舉候選人姓名號次抽籤一覽表 (pinned in 最新消息;
  not reached by the bulletin walk) — five text-layer PDF tables, 製表日期 115/10/27,
  columns 選舉區, 抽籤號次, 姓名, 性別, 推薦之政黨, 備註: 縣長, 縣議員, 鄉(市)長,
  鄉(市)民代表, 村(里)長. 備註 (本會代抽 / 免辦抽籤) is kept in ``note``.
  (65359 新聞稿 prints the same 縣長/縣議員 numbers.)

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/phec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "phec"
COUNTY = "澎湖縣"
ARTICLE = "65367"
CATEGORY_BY_TITLE = [("縣市長選舉", "county-mayor"), ("縣市議員選舉", "county-councilor"),
                     ("鄉鎮市長選舉", "township-mayor"), ("鄉鎮市民代表選舉", "township-rep"),
                     ("村里長選舉", "village-chief")]


def clean(cell: str | None) -> str:
    return re.sub(r"\s+", "", cell or "")


def rows() -> list[dict]:
    import pdfplumber

    art = fetch.article(ROUTE, ARTICLE)
    url = fetch.article_url(ROUTE, ARTICLE)
    out = []
    for file_name in art["files"]:
        file_url = fetch.file_url(file_name)
        fetched = fetch.meta(file_url).get("fetchedAt", "")
        got = 0
        with pdfplumber.open(str(fetch.cached_file(file_name))) as pdf:
            text = pdf.pages[0].extract_text() or ""
            category = next(c for key, c in CATEGORY_BY_TITLE if key in text)
            expected = int(re.search(r"列印筆數：(\d+)", text).group(1))
            for page in pdf.pages:
                for table in page.extract_tables():
                    for cells in table:
                        cells = [clean(c) for c in cells] + [""] * 6
                        district, num, name, gender, party, note = cells[:6]
                        if not district.startswith(COUNTY) or not num.isdigit():
                            continue
                        out.append({"category": category, "district": district, "number": num, "name": name,
                                    "gender": gender, "party": party, "note": note, "source": url,
                                    "sourceFile": file_url, "fetchedAt": fetched})
                        got += 1
        if got != expected:
            # 村里長: header says 列印筆數 154 but the body lists 152 — 黃文隆 (菜園里) and 鄭秋香 (中屯村) were
            # ruled 不得登記 at the 第317次委員會議 (article 65657) and are not on the ballot.
            print(f"WARNING {file_name}: parsed {got}, PDF header says 列印筆數 {expected}", file=sys.stderr)
        print(f"{file_name}: {category} {got}", file=sys.stderr)
    return out


def main() -> int:
    path = write_numbers(ROUTE, rows())
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
