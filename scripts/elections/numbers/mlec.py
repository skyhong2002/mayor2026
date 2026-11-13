#!/usr/bin/env python3
"""苗栗縣選舉委員會 → data/elections/2026/numbers/mlec.csv

* 65362 苗栗縣選舉委員會辦理115年地方公職人員選舉姓名號次抽籤（2026-10-27 新聞稿內文；
  縣長及縣議員號次，「第一選區 / 1號　姓名」逐行列出）。原住民議員候選人僅印漢名
  （名冊為漢名+族名，見 explanations-mlec.csv）。

鄉鎮市長、鄉鎮市民代表、村里長: unresolved as of 2026-11-13. Those draws were held by each
鄉(鎮、市)公所 (65332), and mlec has published no result since — checked the bulletin walk
since 2026-10-15 and the 115 article lists 11466 新聞稿 / 11597 地方公職人員選舉公告 /
11600 候選人登記概況表 / 4048 / 10942. Expect them in the 候選人名單公告 (due 2026-11-17).

Not covered: 鄉鎮市長 / 鄉鎮市民代表 / 村里長. Those draws were run by the township
offices (公所) on 2026-10-27 and, as of 2026-11-13, the commission's menu and bulletin
chains (since 2026-10-15) carry no result list for them. Add the 候選人名單公告
(due 2026-11-17) or 選舉公報 when published.

    uv run --no-project python3 scripts/elections/numbers/mlec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, cn_number, write_numbers  # noqa: E402

ROUTE = "mlec"
COUNTY = "苗栗縣"
PRESS = "65362"


def press_rows() -> list[dict]:
    art = fetch.article(ROUTE, PRESS)
    url = fetch.article_url(ROUTE, PRESS)
    fetched = fetch.meta(f"{fetch.BASE}/api/{ROUTE}/article/{PRESS}").get("fetchedAt", "")
    rows = []
    cat = district = None
    for line in fetch.article_text(art).splitlines():
        line = line.strip()
        if line.startswith("縣長候選人"):
            cat, district = "county-mayor", COUNTY
            continue
        if line.startswith("縣議員候選人"):
            cat, district = "county-councilor", None
            continue
        m = re.fullmatch(r"第([一二三四五六七八九十]+)選(舉)?區", line)
        if m and cat == "county-councilor":
            district = f"{COUNTY}第{cn_number(m.group(1))}選舉區"
            continue
        m = re.fullmatch(r"(\d+)\s*號\s*(.+)", line)
        if m and cat and district:
            rows.append({"category": cat, "district": district, "number": m.group(1), "name": m.group(2),
                         "source": url, "fetchedAt": fetched})
    return rows


def main() -> int:
    path = write_numbers(ROUTE, press_rows())
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
