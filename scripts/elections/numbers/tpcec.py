#!/usr/bin/env python3
"""新北市選舉委員會 → data/elections/2026/numbers/tpcec.csv

候選人姓名號次抽籤結果一覽表（2026-10-27，各一個 pdf 附件，欄位：選舉區／抽籤號次／姓名，無政黨）：

* 65360 新北市第5屆市長選舉
* 65361 新北市第5屆議會市議員選舉（含第12、13 原住民選舉區）
* 65393 新北市第5屆里長選舉
* 65394 新北市第4屆烏來區區長選舉
* 65395 新北市第4屆烏來區區民代表選舉

65778/65780「公告新北市第5屆市長選舉候選人名單」(2026-11-12) 的兩個 pdf 均為掃描影像、無文字層，
故市長號次採 65360 抽籤結果。

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/tpcec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "tpcec"
COUNTY = "新北市"
ARTICLES = {
    "65360": "municipal-mayor",
    "65361": "municipal-councilor",
    "65393": "village-chief",
    "65394": "indigenous-district-chief",
    "65395": "indigenous-district-rep",
}
# 65393 里長號次表: one character of these names is a 造字 drawn as vector curves (no text layer),
# so pdfplumber silently drops it. Position verified from the curve x-coordinates (pages 38/41/49).
# (district, extracted) → (name with □ at the glyph position, spelling in 64393 登記情形一覽表)
CUSTOM_GLYPH = {
    ("新北市三峽區插角里", "簡梁"): ("簡梁□", "簡梁育"),
    ("新北市淡水區新市里", "亞倫"): ("□亞倫", "亞倫"),
    ("新北市蘆洲區恆德里", "曾樺"): ("曾□樺", "曾 樺"),
}


def clean(cell: str | None) -> str:
    # The romanized indigenous names use a middle-dot glyph that pdfplumber cannot map
    # ("(cid:504)"); it is the 間隔號 ‧ (cf. 中選會登記名冊 王月裡Amuy‧Losing).
    return re.sub(r"\s+", "", cell or "").replace("(cid:504)", "‧")


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
    result = []
    for article_id, cat in ARTICLES.items():
        art = fetch.article(ROUTE, article_id)
        url = fetch.article_url(ROUTE, article_id)
        for file_name in art["files"]:
            file_url = fetch.file_url(file_name)
            path = fetch.cached_file(file_name)
            fetched = fetch.meta(file_url).get("fetchedAt", "")
            for r in table_rows(path):
                name = r["姓名"]
                note = "PDF 字型以 (cid:504) 呈現間隔號，轉為‧" if "‧" in name else ""
                fix = CUSTOM_GLYPH.pop((r["選舉區"], name), None)
                if fix:
                    name, note = fix[0], ("號次表姓名含造字（以向量圖形繪製、無文字層），以□標示其位置；"
                                          f"本會候選人登記情形一覽表（{fetch.article_url(ROUTE, '64393')}）作「{fix[1]}」")
                result.append({"category": cat, "district": r["選舉區"], "number": r["抽籤號次"], "name": name,
                               "source": url, "sourceFile": file_url, "fetchedAt": fetched, "note": note})
    if CUSTOM_GLYPH:
        raise SystemExit(f"custom-glyph rows not found (PDF changed?): {CUSTOM_GLYPH}")
    return result


def main() -> int:
    path = write_numbers(ROUTE, rows())
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
