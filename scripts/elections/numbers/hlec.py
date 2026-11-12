#!/usr/bin/env python3
"""花蓮縣選舉委員會 → data/elections/2026/numbers/hlec.csv

* 65438 115年花蓮縣地方公職人員選舉候選人姓名號次抽籤結果（2026-10-29; five PDFs:
  縣長「抽籤號次 姓名 推薦之政黨」, 縣議員「選舉區 抽籤號次 姓名 推薦之政黨」,
  鄉鎮市長/代表/村里長「選舉區 姓名 抽籤號次」）→ read as tables, columns mapped by
  header; party only where the table prints it.

Names with 造字 (images / Private-Use-Area glyphs) are filled by elimination
against the CEC roster only when exactly one registrant of that district is
left unmatched (row ``note`` says so); otherwise left out and reported.

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/hlec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, norm_name, read_registered, write_numbers  # noqa: E402

ROUTE = "hlec"
COUNTY = "花蓮縣"
ARTICLE = "65438"
CATEGORY_BY_TITLE = [("村里長", "village-chief"), ("代表", "township-rep"), ("議員", "county-councilor"),
                     ("鄉鎮市長", "township-mayor"), ("縣市長", "county-mayor")]
PUA = re.compile(r"[\ue000-\uf8ff]")


def cell_text(page, bbox) -> str:
    """Text of the chars whose centre lies inside a table cell (wrapped text overflows cell edges)."""
    x0, top, x1, bottom = bbox

    def inside(obj: dict) -> bool:
        if "x0" not in obj or "top" not in obj:
            return False
        cx, cy = (obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2
        return x0 <= cx <= x1 and top <= cy <= bottom

    return page.filter(inside).extract_text() or ""


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
        cols = None  # header carries over to continuation pages
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                images = page.images
                for table in page.find_tables():
                    for trow in table.rows:
                        cells = ["".join((cell_text(page, c) if c else "").split("\n")) for c in trow.cells]
                        if "抽籤號次" in cells and "姓名" in cells:
                            cols = {name: i for i, name in enumerate(cells)}
                            continue
                        if cols is None or len(cells) != len(cols):
                            continue
                        number = cells[cols["抽籤號次"]].strip()
                        district = "".join(cells[cols["選舉區"]].split()) if "選舉區" in cols else COUNTY
                        if not number.isdigit() or not district.startswith(COUNTY):
                            continue
                        name_cell = trow.cells[cols["姓名"]]
                        name = " ".join((cell_text(page, name_cell) or "").split())
                        x0, top, x1, bottom = name_cell
                        if any(im["x0"] < x1 and im["x1"] > x0 and im["top"] < bottom and im["bottom"] > top
                               for im in images):
                            name = ""  # part of the name is an embedded image (造字)
                        row = {"category": cat, "district": district, "number": number, "name": name,
                               "source": url, "sourceFile": file_url, "fetchedAt": fetched}
                        if "推薦之政黨" in cols:
                            row["party"] = cells[cols["推薦之政黨"]].strip()
                        out.append(row)
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
