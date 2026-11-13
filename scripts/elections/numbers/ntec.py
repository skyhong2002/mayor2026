#!/usr/bin/env python3
"""南投縣選舉委員會 → data/elections/2026/numbers/ntec.csv

Status 2026-11-13: ntec has NOT published any 2026 號次 yet. Checked (bulletin walk
since 2026-10-15 and every 115-related menu / article-list section):

* 65211 / 65210 (2026-10-16) 辦理115年地方公職人員選舉候選人姓名號次抽籤 — schedule only;
  縣長/縣議員 drawn at ntec, 鄉鎮市長/代表/村里長 drawn at each 鄉(鎮、市)公所.
* 65345 / 65285 — draw postponed to 2026-10-27 (typhoon). No result article followed.
* 65646 / 65647 (2026-11-10) 公辦電視政見發表會 + 行事曆 PDF — per-district counts and
  number ranges only, no names.
* 65209 / 65208 (2026-10-16) 審定鄉(鎮、市)候選人資格 — counts only (代表 4 人、村里長 4 人資格不符;
  埔里鎮北梅里 第二次登記).

The 候選人名單公告 (due 2026-11-17) or 選舉公報 should carry the numbers. When it appears,
add its article id to ARTICLES; ``draw_pdf_rows`` (shared with chec/ilec/hccec) reads the
CEC PDF export (選舉區/姓名/[性別/推薦之政黨]/抽籤號次). Run with ``--discover`` to re-list
ntec's sections (bypassing the cache) and print articles whose title looks relevant.

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/ntec.py [--discover]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "ntec"
COUNTY = "南投縣"
# Article ids of official 號次 publications (抽籤結果 / 候選人名單公告) — none published yet.
ARTICLES: list[str] = []
SINCE = "20261020"
RELEVANT = re.compile(r"號次|抽籤結果|候選人名單|選舉公報")
# Section ids of ntec's 公告 / 新聞稿 / 最新消息 article lists (menu directType 004).
SECTIONS = ["498", "499", "500"]


def discover() -> list[tuple[str, str, str]]:
    """Fresh listing of ntec's bulletin sections → (id, date, title) of relevant articles."""
    hits = []
    for section in SECTIONS:
        url = (f"{fetch.BASE}/api/{ROUTE}/article/list?id={section}&page=1&keyword=&beginDate=&endDate="
               f"&webRoute={ROUTE}")
        for item in fetch.get_json(url, refresh=True).get("data", {}).get("articleList") or []:
            date = str(item.get("beginTime") or "")[:8]
            title = item.get("directName") or ""
            if date >= SINCE and RELEVANT.search(title) and "抽籤，" not in title:
                hits.append((str(item.get("directPath")), date, title))
    return sorted(set(hits), key=lambda h: h[1], reverse=True)


def main(argv: list[str]) -> int:
    if "--discover" in argv:
        for hit in discover():
            print("candidate article", *hit, sep="\t")
    rows: list[dict] = []
    if ARTICLES:
        from chec import draw_pdf_rows

        for article_id in ARTICLES:
            rows += draw_pdf_rows(ROUTE, COUNTY, article_id)
    else:
        print(f"{ROUTE}: no official 號次 publication yet (see docstring); writing header-only CSV")
    path = write_numbers(ROUTE, rows)
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
