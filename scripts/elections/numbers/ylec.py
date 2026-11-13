#!/usr/bin/env python3
"""雲林縣選舉委員會 → data/elections/2026/numbers/ylec.csv

* 65422 115年地方公職人員選舉候選人姓名號次抽籤結果（2026-10-28；五個 PDF 附件：
  縣長、縣議員、鄉鎮市長、鄉鎮市民代表、村里長；每列「選舉區 姓名 抽籤號次」）

A few names contain 造字 and are embedded as images or Private-Use-Area glyphs
(no usable text). Those rows
are filled by elimination against the CEC roster (registered.csv) only when
exactly one registrant of that district is left unmatched; the row's ``note``
says so. Otherwise the row is left out and reported (no OCR).

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/ylec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, norm_name, read_registered, write_numbers  # noqa: E402

ROUTE = "ylec"
COUNTY = "雲林縣"
ARTICLE = "65422"
# attachment title keyword → category
CATEGORY_BY_TITLE = [("村里長", "village-chief"), ("村長", "village-chief"), ("里長", "village-chief"), ("代表", "township-rep"), ("議員", "county-councilor"),
                     ("鄉鎮市長", "township-mayor"), ("長", "county-mayor")]
PUA = re.compile(r"[\ue000-\uf8ff]")
LINE = re.compile(r"^(" + COUNTY + r"\S*)\s+(.*?)\s*(\d+)$")


def rows() -> list[dict]:
    import pdfplumber

    art = fetch.article(ROUTE, ARTICLE)
    url = fetch.article_url(ROUTE, ARTICLE)
    out = []
    for file_name in art["files"]:
        title = art["fileNames"][file_name] or ""
        cat = next(c for key, c in CATEGORY_BY_TITLE if key in title)
        file_url = fetch.file_url(file_name)
        path = fetch.cached_file(file_name)
        fetched = fetch.meta(file_url).get("fetchedAt", "")
        declared = None
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                for line in (page.extract_text() or "").splitlines():
                    line = line.strip()
                    m = re.search(r"列印筆數[:：]\s*(\d+)", line)
                    if m:
                        declared = int(m.group(1))
                    m = LINE.match(line)
                    if m:
                        out.append({"category": cat, "district": m.group(1), "name": m.group(2).strip(), "number": m.group(3),
                                    "source": url, "sourceFile": file_url, "fetchedAt": fetched})
        got = sum(1 for r in out if r["sourceFile"] == file_url)
        if declared is not None and got != declared:
            raise SystemExit(f"{title}: parsed {got} rows, PDF declares 列印筆數 {declared}")
    return out


def good(name: str) -> bool:
    return bool(name) and not PUA.search(name) and "(cid:" not in name


def fill_image_names(rows: list[dict]) -> list[dict]:
    """Resolve rows whose name is an image by roster elimination (see docstring)."""
    reg: dict[tuple[str, str], list[str]] = {}
    for r in read_registered(COUNTY):
        reg.setdefault((r["category"], r["district"]), []).append(norm_name(r["name"]))
    out = []
    for row in rows:
        if good(row["name"]):
            out.append(row)
            continue
        printed = row["name"]
        key = (row["category"], row["district"])
        named = {norm_name(r["name"]) for r in rows if (r["category"], r["district"]) == key and good(r["name"])}
        left = [n for n in reg.get(key, []) if n and n not in named]
        blanks = [r for r in rows if (r["category"], r["district"]) == key and not good(r["name"])]
        if len(left) == 1 and len(blanks) == 1:
            row = dict(row, name=left[0])
            row["note"] = "號次表姓名為造字圖檔，依中選會登記名冊排除法補入姓名"
            out.append(row)
        else:
            print(f"UNRESOLVED 造字 name: {row['district']} 號次 {row['number']} printed {printed!r}"
                  f" (roster leftovers {left})")
    return out


def main() -> int:
    print(write_numbers(ROUTE, fill_image_names(rows())))
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
