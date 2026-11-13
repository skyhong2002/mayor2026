#!/usr/bin/env python3
"""Contract + self-check for per-commission 號次 (ballot number) files.

Each commission parser ``scripts/elections/numbers/<route>.py`` turns the
commission's own official publications (fetched via fetch.py, cached) into
``data/elections/2026/numbers/<route>.csv`` with NUMBER_FIELDS. Rules:

* ``district`` uses the exact label style of registered.csv (中選會登記名冊):
  ``臺北市`` (mayor), ``臺北市第1選舉區`` (council), ``南投縣中寮鄉`` (township
  head), ``南投縣中寮鄉第1選舉區`` (township rep), ``南投縣中寮鄉中寮村``
  (village chief). Use ``district_label()`` helpers below.
* one row per candidate on the ballot; ``number`` is the drawn 號次.
* ``source`` = the public article URL (fetch.article_url) of the publication
  the row came from; ``sourceFile`` = attachment download URL if the data was in
  an attachment; ``fetchedAt`` from fetch.meta(url)["fetchedAt"].
* gender / birthYear (西元) / party only when *that 2026 publication* prints them.
* never invent or carry over rows from other years or from news.

    python3 scripts/elections/numbers_common.py check <route>   # per-category diff vs roster
"""

from __future__ import annotations

import collections
import csv
import re
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import CATEGORIES, COUNTIES, COUNTY_NAME, COUNTY_ROUTE, DATA_DIR  # noqa: E402

NUMBERS_DIR = DATA_DIR / "numbers"
NUMBER_FIELDS = ["category", "district", "number", "name", "gender", "birthYear", "party",
                 "source", "sourceFile", "fetchedAt", "note"]
ROUTE_COUNTY = {route: COUNTY_NAME[slug] for slug, route in COUNTY_ROUTE.items()}

_FULLWIDTH = str.maketrans("０１２３４５６７８９", "0123456789")
CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_number(text: str) -> int:
    """'十二' → 12, '二十一' → 21, '12' → 12."""
    text = text.translate(_FULLWIDTH).strip()
    if text.isdigit():
        return int(text)
    total, cur = 0, 0
    for ch in text:
        if ch in CN_DIGITS:
            cur = CN_DIGITS[ch]
        elif ch == "十":
            total += (cur or 1) * 10
            cur = 0
        elif ch == "百":
            total += (cur or 1) * 100
            cur = 0
    return total + cur


def norm_name(name: str) -> str:
    """Comparable form of a person's name (spacing, middle dots, 臺/台 only)."""
    name = re.sub(r"[\s　]", "", name or "")
    name = name.replace("．", "‧").replace("·", "‧").replace("・", "‧").replace("•", "‧")
    return name


def norm_district(label: str) -> str:
    label = re.sub(r"[\s　]", "", label or "").translate(_FULLWIDTH)
    label = label.replace("台", "臺") if label.startswith("台") else label
    label = re.sub(r"第([零〇一二兩三四五六七八九十百]+)選舉區", lambda m: f"第{cn_number(m.group(1))}選舉區", label)
    return label


def write_numbers(route: str, rows: Iterable[dict]) -> Path:
    NUMBERS_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    for row in rows:
        missing = [f for f in ("category", "district", "number", "name", "source") if not str(row.get(f) or "").strip()]
        if missing:
            raise ValueError(f"{route}: row missing {missing}: {row}")
        if row["category"] not in CATEGORIES:
            raise ValueError(f"{route}: unknown category {row['category']}")
        row["district"] = norm_district(row["district"])
        row["name"] = norm_name(row["name"])
        row["number"] = str(int(str(row["number"]).translate(_FULLWIDTH)))
    rows.sort(key=lambda r: (list(CATEGORIES).index(r["category"]), r["district"], int(r["number"])))
    path = NUMBERS_DIR / f"{route}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=NUMBER_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({f: row.get(f, "") for f in NUMBER_FIELDS})
    return path


def read_numbers(route: str) -> list[dict[str, str]]:
    path = NUMBERS_DIR / f"{route}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_registered(county_name: str | None = None) -> list[dict[str, str]]:
    with (DATA_DIR / "registered.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if county_name:
        rows = [r for r in rows if r["district"].startswith(county_name)]
    return rows


def check(route: str, *, verbose: bool = True) -> dict:
    """Compare a commission's numbers file against the roster for that county."""
    county = ROUTE_COUNTY[route]
    reg = read_registered(county)
    nums = read_numbers(route)
    report: dict = {"route": route, "county": county, "categories": {}}
    for cat in CATEGORIES:
        r_rows = [r for r in reg if r["category"] == cat]
        n_rows = [r for r in nums if r["category"] == cat]
        if not r_rows and not n_rows:
            continue
        r_keys = collections.Counter((norm_district(r["district"]), norm_name(r["name"])) for r in r_rows)
        n_keys = collections.Counter((r["district"], r["name"]) for r in n_rows)
        problems = []
        by_d: dict[str, list[int]] = collections.defaultdict(list)
        for r in n_rows:
            by_d[r["district"]].append(int(r["number"]))
        for d, ns in sorted(by_d.items()):
            if sorted(ns) != list(range(1, len(ns) + 1)):
                problems.append(f"號次不連續或重複 {d}: {sorted(ns)}")
        entry = {
            "registered": len(r_rows), "numbered": len(n_rows),
            "notNumbered": sorted(f"{d} {n}" for (d, n) in (r_keys - n_keys)),
            "notRegistered": sorted(f"{d} {n}" for (d, n) in (n_keys - r_keys)),
            "problems": problems,
        }
        report["categories"][cat] = entry
        if verbose:
            print(f"{county} {CATEGORIES[cat]['label']}: 登記 {entry['registered']} / 有號次 {entry['numbered']}"
                  f" / 未見號次 {len(entry['notNumbered'])} / 名冊無此人 {len(entry['notRegistered'])} / 號次問題 {len(problems)}")
            for label, items in (("  未見號次", entry["notNumbered"]), ("  名冊無此人", entry["notRegistered"]), ("  ", problems)):
                for item in items[:15]:
                    print(label, item)
                if len(items) > 15:
                    print(label, f"… 另 {len(items) - 15} 筆")
    return report


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "check":
        for route in sys.argv[2:]:
            check(route)
    else:
        print(__doc__)
