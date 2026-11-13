#!/usr/bin/env python3
"""臺南市選舉委員會 → data/elections/2026/numbers/tnec.csv

Text PDFs (選舉區 / 姓名 / 推薦之政黨 / 抽籤號次; no 性別/出生年), published 2026-10-27:

* 65387 臺南市第5屆直轄市長、市議員選舉候選人姓名號次抽籤結果
  (two attachments: 115年直轄市長… / 115年直轄市議員…選舉候選人姓名號次抽籤結果)
* 65390 臺南市第5屆里長選舉候選人姓名號次抽籤結果

Cross-checks (the script asserts identical 號次/姓名; these are not used as row sources):
* 65386 新聞稿「…號次抽籤順利完成」, whose body text lists the 市長 and each district's 議員號次
* 65615 公告臺南市第5屆市長選舉候選人名單 (2026-11-12; 號次＋姓名 only)

臺南市 has no 山地原住民區 or 鄉鎮市; the 原住民 councillors are 第13選舉區.

    nice -n 10 uv run --no-project --with pdfplumber python3 scripts/elections/numbers/tnec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402
from numbers_common import check, norm_name, read_registered, write_numbers  # noqa: E402
from tcec import fix_cid, join_cell  # noqa: E402

ROUTE = "tnec"
COUNTY = "臺南市"
LISTS = ["65387", "65390"]
PRESS = "65386"
ANNOUNCEMENT = "65615"

# The 里長 PDF draws a few rare-glyph cells as inline images (no text). Village
# cells are resolved from the official village list (64339 attachment
# 02718011-9a4b-4665-b71d-f7790a49a550.pdf, 第5屆里長競選經費最高金額-公告用), keyed by
# the neighbouring text rows. That list prints 檨林里 as text, but it also drops the
# glyph of the two 安南區 villages, so those keep 〓 (geta mark) for the missing
# character. Name cells drawn as images are reported (IMAGE_NAMES) and left out.
VILLAGE_LIST_ARTICLE = "64339"
IMAGE_VILLAGES = {  # (previous text-row district, next text-row district) → label, note
    ("臺南市西港區港東里", "臺南市西港區後營里"): ("臺南市西港區檨林里", "里名於號次PDF為圖片，依64339公告附件里別一覽補（檨林里）"),
    ("臺南市安南區安順里", "臺南市安南區州南里"): ("臺南市安南區〓南里", "里名於號次PDF為圖片；64339公告附件里別一覽亦缺字（印為「南里」），〓為缺字"),
    ("臺南市安南區佃西里", "臺南市安南區南興里"): ("臺南市安南區公〓里", "里名於號次PDF為圖片；64339公告附件里別一覽亦缺字（印為「公 里」），〓為缺字"),
}
IMAGE_NAMES: list[str] = []


def category_of(title: str) -> str:
    if "直轄市長" in title:
        return "municipal-mayor"
    if "直轄市議員" in title:
        return "municipal-councilor"
    if "里長" in title:
        return "village-chief"
    raise ValueError(title)


def pdf_rows(article_id: str, roster: list[dict]) -> list[dict]:
    import pdfplumber

    art = fetch.article(ROUTE, article_id)
    url = fetch.article_url(ROUTE, article_id)
    rows = []
    for file_name in art["files"]:
        furl = fetch.file_url(file_name)
        fetched = fetch.meta(furl).get("fetchedAt", "")
        with pdfplumber.open(str(fetch.cached_file(file_name))) as pdf:
            title = (pdf.pages[0].extract_text() or "").split("\n")[0]
            category = category_of(title)
            raw = []
            for page in pdf.pages:
                for table in page.extract_tables():
                    for cells in table:
                        cells = [c or "" for c in cells]
                        if len(cells) >= 4 and cells[3].strip().isdigit():
                            raw.append((page.page_number, cells))
            texts = [join_cell(c[0], latin_space=False) for _, c in raw]
            for i, (page_no, cells) in enumerate(raw):
                row = {"category": category, "district": texts[i], "number": cells[3].strip(),
                       "name": join_cell(cells[1]), "party": join_cell(cells[2], latin_space=False),
                       "source": url, "sourceFile": furl, "fetchedAt": fetched}
                if not row["district"]:
                    prev = next(t for t in reversed(texts[:i]) if t)
                    nxt = next(t for t in texts[i + 1:] if t)
                    row["district"], row["note"] = IMAGE_VILLAGES[(prev, nxt)]
                if not row["district"].startswith(COUNTY):
                    raise ValueError(f"unexpected district cell {cells}")
                if not row["name"]:
                    IMAGE_NAMES.append(f"{row['district']} 號次{row['number']}（{row['party']}）PDF第{page_no}頁")
                    continue
                rows.append(fix_cid(row, roster))
    if not rows:
        raise ValueError(f"{ROUTE} {article_id}: no rows parsed")
    return rows


def _pairs(text: str) -> set[tuple[str, str]]:
    return {(n, norm_name(m)) for n, m in re.findall(r"[（(]\s*(\d+)\s*[）)]\s*([^\s（(。、]+)", text)}


def _strip_latin(name: str) -> str:
    return re.sub(r"[A-Za-z·‧ㆍ].*$", "", norm_name(name))


def cross_check(rows: list[dict]) -> None:
    import pdfplumber

    mayor = {(r["number"], norm_name(r["name"])) for r in rows if r["category"] == "municipal-mayor"}
    # 11/12 公告名單 (clean copy is the one with a text layer)
    for file_name in fetch.article(ROUTE, ANNOUNCEMENT)["files"]:
        with pdfplumber.open(str(fetch.cached_file(file_name))) as pdf:
            text = "".join(p.extract_text() or "" for p in pdf.pages)
        if "候選人名單" in text:
            got = _pairs(text.split("候選人名單", 1)[1].split("二、", 1)[0])
            if got != mayor:
                raise ValueError(f"公告名單 {got} != 抽籤結果 {mayor}")
            break
    else:
        raise ValueError("no text copy of the 公告名單 found")
    # 新聞稿 body: 市長 + 議員 (indigenous names there carry romanization after a space)
    text = fetch.article_text(fetch.article(ROUTE, PRESS))
    sections = re.split(r"(第\d+選舉區)[:：]", text.split("二、議員", 1)[1])
    press = {(f"{COUNTY}{d}", n, _strip_latin(m)) for d, body in zip(sections[1::2], sections[2::2])
             for n, m in _pairs(body)}
    want = {(r["district"], r["number"], _strip_latin(r["name"])) for r in rows if r["category"] == "municipal-councilor"}
    if press != want:
        raise ValueError(f"新聞稿 vs 抽籤結果 differ: {sorted(press ^ want)}")


def main() -> int:
    roster = read_registered(COUNTY)
    rows: list[dict] = []
    for article_id in LISTS:
        rows += pdf_rows(article_id, roster)
    cross_check(rows)
    path = write_numbers(ROUTE, rows)
    print(path)
    for item in IMAGE_NAMES:
        print("姓名為圖片、未收錄:", item)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
