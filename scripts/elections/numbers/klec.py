#!/usr/bin/env python3
"""基隆市選舉委員會 → data/elections/2026/numbers/klec.csv

* 65421 基隆市第20屆市長、市議會第21屆議員及第23屆里長選舉候選人姓名號次抽籤結果
  — three text-layer PDF 一覽表 (製表日期 115/10/27) with 抽籤號次, 姓名, 性別, 推薦之政黨.

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/klec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "klec"
COUNTY = "基隆市"
ARTICLE = "65421"
CATEGORY_BY_TITLE = [("市長選舉", "county-mayor"), ("議員選舉", "county-councilor"), ("里長選舉", "village-chief")]
LINE = re.compile(rf"^({COUNTY}\S*)\s+(\d+)\s+(.+?)\s+([男女])\s+(\S+)$")


def rows() -> list[dict]:
    import pdfplumber

    art = fetch.article(ROUTE, ARTICLE)
    url = fetch.article_url(ROUTE, ARTICLE)
    out = []
    for file_name in art["files"]:
        file_url = fetch.file_url(file_name)
        fetched = fetch.meta(file_url).get("fetchedAt", "")
        with pdfplumber.open(str(fetch.cached_file(file_name))) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        title = next(line for line in text.splitlines() if "一覽表" in line)
        category = next(c for key, c in CATEGORY_BY_TITLE if key in title)
        expected = re.search(r"列印筆數：(\d+)", text)
        got = 0
        for line in text.splitlines():
            m = LINE.match(line.strip())
            if not m:
                continue
            district, num, name, gender, party = m.groups()
            out.append({"category": category, "district": district, "number": num, "name": name,
                        "gender": gender, "party": party, "source": url, "sourceFile": file_url,
                        "fetchedAt": fetched})
            got += 1
        if expected and int(expected.group(1)) != got:
            raise SystemExit(f"{file_name}: parsed {got}, PDF says 列印筆數 {expected.group(1)}")
        print(f"{file_name}: {category} {got} rows", file=sys.stderr)
    return out


def main() -> int:
    path = write_numbers(ROUTE, rows())
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
