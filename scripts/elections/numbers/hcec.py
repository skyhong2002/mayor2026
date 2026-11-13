#!/usr/bin/env python3
"""新竹市選舉委員會 → data/elections/2026/numbers/hcec.csv

* 65374 新竹市第12屆市長、市議員及第23屆里長選舉候選人號次抽定（新聞稿內文，市長與市議員號次）
* 65417 新竹市第23屆里長選舉候選人號次抽籤結果一覽表（xls 附件）

    uv run --no-project --with xlrd python3 scripts/elections/numbers/hcec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "hcec"
COUNTY = "新竹市"


def text_rows() -> list[dict]:
    art = fetch.article(ROUTE, "65374")
    url = fetch.article_url(ROUTE, "65374")
    fetched = fetch.meta(f"{fetch.BASE}/api/{ROUTE}/article/65374").get("fetchedAt", "")
    text = fetch.article_text(art)
    rows = []
    mayor = re.search(r"市長選舉候選人號次如下[:：](.+?)。", text)
    for num, name in re.findall(r"(\d+)\s*號\s*([^\s、。,，0-9]+)", mayor.group(1)):
        rows.append({"category": "county-mayor", "district": COUNTY, "number": num, "name": name,
                     "source": url, "fetchedAt": fetched})
    for district, body in re.findall(r"第\s*(\d+)\s*選舉區[:：](.+?)。", text):
        for num, name in re.findall(r"(\d+)\s*號\s*([^\s、。,，0-9]+)", body):
            rows.append({"category": "county-councilor", "district": f"{COUNTY}第{district}選舉區", "number": num,
                         "name": name, "source": url, "fetchedAt": fetched})
    return rows


def village_rows() -> list[dict]:
    import xlrd

    art = fetch.article(ROUTE, "65417")
    url = fetch.article_url(ROUTE, "65417")
    rows = []
    for file_name in art["files"]:
        file_url = fetch.file_url(file_name)
        book = xlrd.open_workbook(str(fetch.cached_file(file_name)))
        fetched = fetch.meta(file_url).get("fetchedAt", "")
        for sheet in book.sheets():
            for i in range(sheet.nrows):
                district, cell = (str(v).strip() for v in sheet.row_values(i)[:2])
                if not district.startswith(COUNTY):
                    continue
                for num, name in re.findall(r"[（(]\s*(\d+)\s*[）)]\s*([^\s（(]+)", cell):
                    rows.append({"category": "village-chief", "district": district, "number": num, "name": name,
                                 "source": url, "sourceFile": file_url, "fetchedAt": fetched})
    return rows


def main() -> int:
    path = write_numbers(ROUTE, text_rows() + village_rows())
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
