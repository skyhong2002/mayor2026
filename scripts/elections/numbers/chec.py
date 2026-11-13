#!/usr/bin/env python3
"""彰化縣選舉委員會 → data/elections/2026/numbers/chec.csv

* 65434 115年地方公職人員選舉候選人姓名號次抽籤概況表（2026-10-29；5 個 PDF 附件：
  縣長、縣議員、鄉鎮市長、鄉鎮市民代表、村里長；欄位 選舉區/姓名/性別/推薦之政黨/抽籤號次/備註）

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/chec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "chec"
COUNTY = "彰化縣"
ARTICLE = "65434"
# attachment title keyword (followed by 選舉) → category
CATEGORY_BY_TITLE = [
    ("縣長", "county-mayor"),
    ("縣市長", "county-mayor"),
    ("縣議員", "county-councilor"),
    ("縣市議員", "county-councilor"),
    ("鄉鎮市長", "township-mayor"),
    ("鄉鎮市民代表", "township-rep"),
    ("村里長", "village-chief"),
]


MISSING_NAME = "（姓名缺字）"
PUA = re.compile(r"[\ue000-\uf8ff]")


def clean(cell: str | None) -> str:
    return re.sub(r"\s+", "", cell or "")


def body(page):
    """Page without the 第 n 頁，共 m 頁 footer (it otherwise bleeds into the last table row)."""
    tops = [w["top"] for w in page.extract_words()
            if ("頁，共" in w["text"] or w["text"] == "頁") and w["top"] > page.height / 2]
    if not tops:
        return page
    footer = min(tops) - 1
    # Drop only the footer characters; the table's ruling lines may extend below it.
    return page.filter(lambda obj: obj.get("object_type") != "char" or obj["top"] < footer)


def fill_pua(rows: list[dict], county: str) -> None:
    """The PDFs print 造字 (private-use code points). Where the roster has exactly one
    registrant in that district matching the other characters, use the roster's spelling."""
    from numbers_common import read_registered

    roster: dict = {}
    for r in read_registered(county):
        roster.setdefault((r["category"], r["district"]), []).append(r["name"])
    for row in rows:
        if not PUA.search(row["name"]):
            continue
        pattern = re.compile("^" + PUA.sub(".", re.escape(row["name"])) + "$")
        hits = [n for n in roster.get((row["category"], row["district"]), []) if pattern.match(n)]
        raw = row["name"].encode("unicode_escape").decode()
        if len(hits) == 1:
            row["note"] = "; ".join(filter(None, [row.get("note"), f"PDF 造字 {raw}，依中選會登記名冊作「{hits[0]}」"]))
            row["name"] = hits[0]
        else:
            row["note"] = "; ".join(filter(None, [row.get("note"), f"PDF 造字 {raw} 無法辨識（名冊亦缺字）"]))


def draw_pdf_rows(route: str, county: str, article_id: str, category_by_title=CATEGORY_BY_TITLE) -> list[dict]:
    """Rows from the CEC 候選人抽籤概況表/抽籤結果 PDF export.

    Columns are located by the header row (選舉區/姓名/抽籤號次 and, when printed,
    性別/推薦之政黨/備註), so both the 6-column and the 3-column layouts work."""
    import pdfplumber

    art = fetch.article(route, article_id)
    url = fetch.article_url(route, article_id)
    rows = []
    for file_name in art["files"]:
        title = art["fileNames"][file_name] or ""
        cat = next((c for key, c in category_by_title if f"{key}選舉" in title), None)
        if not cat:
            raise ValueError(f"unknown attachment {file_name} {title}")
        file_url = fetch.file_url(file_name)
        path = fetch.cached_file(file_name)
        fetched = fetch.meta(file_url).get("fetchedAt", "")
        cols: dict[str, int] = {}
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                for table in body(page).extract_tables():
                    for raw in table:
                        cells = [clean(c) for c in raw]
                        if "選舉區" in cells and "姓名" in cells:
                            cols = {h: i for i, h in enumerate(cells)}
                            continue
                        if not cols:
                            continue

                        def col(header: str) -> str:
                            i = cols.get(header)
                            return cells[i] if i is not None and i < len(cells) else ""

                        district, name, number = col("選舉區"), col("姓名"), col("抽籤號次")
                        gender, party, note = col("性別"), col("推薦之政黨"), col("備註")
                        if not number.isdigit():
                            continue
                        if not district.startswith(county):
                            raise ValueError(f"{file_name}: unexpected district {district}")
                        rows.append({"category": cat, "district": district, "number": number, "name": name,
                                     "gender": gender, "party": party, "note": note,
                                     "source": url, "sourceFile": file_url, "fetchedAt": fetched})
    for row in rows:
        if not row["name"]:
            # The PDF prints no glyph at all for this name (and the central roster is blank too).
            row["name"] = MISSING_NAME
            row["note"] = "; ".join(filter(None, [row["note"], "PDF 未印出姓名字元（中選會名冊亦空白）"]))
    fill_pua(rows, county)
    return rows


def main() -> int:
    path = write_numbers(ROUTE, draw_pdf_rows(ROUTE, COUNTY, ARTICLE))
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
