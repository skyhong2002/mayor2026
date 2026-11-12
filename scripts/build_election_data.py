#!/usr/bin/env python3
"""Publish the 2026 local-election candidate list (data/elections/2026/) as
static JSON, CSV, a compact search index and an RSS feed.

Reads only committed files (stdlib, Python 3.9) so the scheduled pipeline can
run it every time without network access:

  site/api/elections/2026/index.json            totals, counties, categories, reconciliation summary
  site/api/elections/2026/<county>.json         every candidate in one county (grouped by category/district)
  site/api/elections/2026/candidates.csv        the full list (same columns as data/…/candidates.csv)
  site/api/elections/2026/reconciliation.json   copied verbatim
  site/api/elections/2026/sources.json          copied verbatim
  site/data/elections/search-2026.json          compact rows for /search/ (name, district, village, number)
  site/feeds/elections-2026.xml                 one item per county × category: list published/updated

Existing /api/* files and feeds are untouched (API compatibility).
"""

from __future__ import annotations

import csv
import datetime as dt
import email.utils
import json
import shutil
import sys
import xml.sax.saxutils as saxutils
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS / "elections"))
from model import (CANDIDATES_CSV, CATEGORIES, COUNTIES, COUNTY_NAME, ELECTION_DAY, FIELDS,  # noqa: E402
                   MUNICIPALITIES, RECONCILIATION_JSON, SOURCES_JSON, party_short)

PROJECT_ROOT = SCRIPTS.parent
SITE = PROJECT_ROOT / "site"
API_DIR = SITE / "api" / "elections" / "2026"
SEARCH_JSON = SITE / "data" / "elections" / "search-2026.json"
FEED_XML = SITE / "feeds" / "elections-2026.xml"
BASE_URL = "https://mayor2026.observe.tw"
SCHEMA_VERSION = 1

# Candidates whose official posts the site already tracks (data/sources/candidates.csv),
# keyed by (county slug, name) so the election pages can link to the feed pages.
TRACKED_CSV = PROJECT_ROOT / "data" / "sources" / "candidates.csv"


def load_candidates() -> list[dict[str, str]]:
    if not CANDIDATES_CSV.exists():
        return []
    with CANDIDATES_CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def tracked_index() -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    if TRACKED_CSV.exists():
        with TRACKED_CSV.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                out[(row["city"], row["name"])] = f"/{row['city']}/{row['candidate_id']}/"
    return out


def public_row(row: dict[str, str], tracked: dict[tuple[str, str], str]) -> dict[str, Any]:
    out: dict[str, Any] = {k: row[k] for k in FIELDS}
    out["number"] = int(row["number"])
    out["birthYear"] = int(row["birthYear"]) if row.get("birthYear") else None
    out["incumbent"] = row.get("incumbent") == "Y"
    out["partyShort"] = party_short(row["party"])
    feed = tracked.get((row["county"], row["name"])) if row["category"] == "municipal-mayor" else None
    out["trackedFeed"] = feed
    out["url"] = page_url(row)
    # county / category / township / district / village are given by the enclosing
    # county → category → group → district objects; rosterSource is the same CEC URL
    # for every row (index.json "sources"). Empty values are omitted.
    for key in ("county", "category", "township", "district", "village", "rosterSource"):
        out.pop(key, None)
    return {k: v for k, v in out.items() if v not in ("", None)}


def page_url(row: dict[str, str]) -> str:
    """Public page that lists this candidate (anchor = candidate id)."""
    return f"{group_path(row['county'], row['category'], row)}#{row['districtKey']}-{int(row['number'])}"


# Categories big enough to need one page per township (others: one page per county+category).
PER_TOWNSHIP = {"township-rep", "village-chief"}
SINGLE_SEAT = {"municipal-mayor", "county-mayor", "township-mayor", "indigenous-district-chief", "village-chief"}


def group_key(row: dict[str, str]) -> str:
    """Page grouping inside county/category: one page per township only for
    鄉鎮市民代表 and 村里長; every other race fits one county-wide page."""
    if row["category"] not in PER_TOWNSHIP:
        return ""
    return row["districtKey"].split("-")[0]  # t<code>


def load_seats() -> dict[tuple[str, str], int]:
    """(category, 縣市+選舉區 label) → 應選名額, from the CEC seat tables."""
    out: dict[tuple[str, str], int] = {}
    path = CANDIDATES_CSV.parent / "registered-seats.csv"
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["district"] != "總計" and row["seats"].isdigit():
                    out[(row["category"], row["district"])] = int(row["seats"])
    return out


def group_path(county: str, category: str, row: dict[str, str] | None = None) -> str:
    base = f"/elections/{county}/{category}/"
    if row is None:
        return base
    key = group_key(row)
    return f"{base}{key}/" if key else base


def rfc822(iso: str) -> str:
    try:
        parsed = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return email.utils.format_datetime(parsed)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def build() -> dict[str, Any]:
    rows = load_candidates()
    tracked = tracked_index()
    seats = load_seats()
    shutil.rmtree(API_DIR, ignore_errors=True)
    API_DIR.mkdir(parents=True, exist_ok=True)
    report = json.loads(RECONCILIATION_JSON.read_text(encoding="utf-8")) if RECONCILIATION_JSON.exists() else {}
    generated = report.get("generatedAt") or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    by_county: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_county[row["county"]].append(row)

    counties_out = []
    for slug, name, route in COUNTIES:
        crow = by_county.get(slug, [])
        cats: dict[str, Any] = OrderedDict()
        for cat in CATEGORIES:
            cr = [r for r in crow if r["category"] == cat]
            if not cr:
                continue
            groups: dict[str, Any] = OrderedDict()
            for r in cr:
                gk = group_key(r)
                g = groups.setdefault(gk, {"key": gk, "label": r["township"] or name, "path": group_path(slug, cat, r),
                                           "districts": OrderedDict()})
                d = g["districts"].get(r["districtKey"])
                if d is None:
                    seat = 1 if cat in SINGLE_SEAT else seats.get((cat, name + (r["district"] if r["district"] != name else "")))
                    d = g["districts"][r["districtKey"]] = {"key": r["districtKey"], "label": r["district"],
                                                            "township": r["township"], "seats": seat, "candidates": []}
                d["candidates"].append(public_row(r, tracked))
            cats[cat] = {
                "id": cat, "label": CATEGORIES[cat]["label"], "path": group_path(slug, cat),
                "count": len(cr), "incumbents": sum(1 for r in cr if r["incumbent"] == "Y"),
                "groups": [{**g, "districts": list(g["districts"].values())} for g in groups.values()],
            }
        fetched = max((r["numberFetchedAt"] for r in crow if r["numberFetchedAt"]), default="")
        county_payload = {
            "schemaVersion": SCHEMA_VERSION, "generatedAt": generated, "electionDay": ELECTION_DAY,
            "county": {"id": slug, "label": name, "municipality": slug in MUNICIPALITIES, "commission": f"https://web.cec.gov.tw/{route}"},
            "count": len(crow), "numbersFetchedAt": fetched, "categories": list(cats.values()),
        }
        if crow:
            write_json(API_DIR / f"{slug}.json", county_payload)
        counties_out.append({
            "id": slug, "label": name, "municipality": slug in MUNICIPALITIES, "count": len(crow),
            "path": f"/elections/{slug}/", "api": f"/api/elections/2026/{slug}.json" if crow else None,
            "numbersFetchedAt": fetched,
            "categories": {cat: v["count"] for cat, v in cats.items()},
        })

    totals = report.get("totals") or {}
    index = {
        "schemaVersion": SCHEMA_VERSION, "generatedAt": generated, "electionDay": ELECTION_DAY,
        "count": len(rows),
        "categories": [{"id": cat, **meta, "count": sum(1 for r in rows if r["category"] == cat),
                        "official": {k: totals.get(cat, {}).get(k) for k in ("officialRegistered", "officialQualified", "officialSeats")}}
                       for cat, meta in CATEGORIES.items()],
        "counties": counties_out,
        "reconciliation": {
            "unexplained": sum(1 for i in report.get("issues", []) if i.get("status") == "unexplained"),
            "pendingSource": sum(1 for i in report.get("issues", []) if i.get("status") == "pending-source"),
            "explained": sum(1 for i in report.get("issues", []) if i.get("status") == "explained"),
            "api": "/api/elections/2026/reconciliation.json",
        },
        "sources": {"roster": "https://web.cec.gov.tw/central/article/64709"},
        "files": {"csv": "/api/elections/2026/candidates.csv", "sources": "/api/elections/2026/sources.json",
                  "search": "/data/elections/search-2026.json", "rss": "/feeds/elections-2026.xml"},
    }
    write_json(API_DIR / "index.json", index)
    if CANDIDATES_CSV.exists():
        shutil.copyfile(CANDIDATES_CSV, API_DIR / "candidates.csv")
    for src in (RECONCILIATION_JSON, SOURCES_JSON):
        if src.exists():
            shutil.copyfile(src, API_DIR / src.name)

    # Compact search rows: [name, number, categoryIdx, countyIdx, township, district, url, partyShort, incumbent]
    cat_ids = list(CATEGORIES)
    county_ids = [c[0] for c in COUNTIES]
    search_rows = [[r["name"], int(r["number"]), cat_ids.index(r["category"]), county_ids.index(r["county"]),
                    r["township"], r["district"], page_url(r), party_short(r["party"]), 1 if r["incumbent"] == "Y" else 0]
                   for r in rows]
    write_json(SEARCH_JSON, {"schemaVersion": SCHEMA_VERSION, "generatedAt": generated,
                             "categories": [CATEGORIES[c]["short"] for c in cat_ids],
                             "counties": [COUNTY_NAME[c] for c in county_ids],
                             "fields": ["name", "number", "category", "county", "township", "district", "url", "party", "incumbent"],
                             "rows": search_rows})
    write_feed(rows, generated)
    return index


def write_feed(rows: list[dict[str, str]], generated: str) -> None:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        groups[(r["county"], r["category"])].append(r)
    items = []
    for (county, cat), rs in groups.items():
        fetched = max((r["numberFetchedAt"] for r in rs if r["numberFetchedAt"]), default=generated)
        title = f"{COUNTY_NAME[county]}{CATEGORIES[cat]['label']}候選人名單與號次（{len(rs)} 人）"
        link = f"{BASE_URL}{group_path(county, cat)}"
        sources = sorted({r["numberSource"] for r in rs})
        desc = f"依選委會公告整理，共 {len(rs)} 位候選人。號次來源：" + "、".join(sources[:5]) + ("…" if len(sources) > 5 else "")
        items.append((fetched, title, link, f"elections-2026:{county}:{cat}:{len(rs)}:{fetched}", desc))
    items.sort(reverse=True)
    body = "\n".join(
        "    <item>\n"
        f"      <title>{saxutils.escape(t)}</title>\n"
        f"      <link>{saxutils.escape(l)}</link>\n"
        f"      <guid isPermaLink=\"false\">{saxutils.escape(g)}</guid>\n"
        f"      <pubDate>{rfc822(f)}</pubDate>\n"
        f"      <description>{saxutils.escape(d)}</description>\n"
        "    </item>"
        for f, t, l, g, d in items
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n  <channel>\n'
           "    <title>2026 地方選舉候選人名單更新</title>\n"
           f"    <link>{BASE_URL}/elections/</link>\n"
           "    <description>各選委會公告的 2026 地方公職人員選舉候選人名單與號次，本站匯入或更新時發布。</description>\n"
           "    <language>zh-Hant</language>\n"
           f"    <lastBuildDate>{rfc822(generated)}</lastBuildDate>\n"
           f"{body}\n  </channel>\n</rss>\n")
    FEED_XML.parent.mkdir(parents=True, exist_ok=True)
    FEED_XML.write_text(xml, encoding="utf-8")


def main() -> int:
    index = build()
    print(f"build_election_data: {index['count']} candidates, "
          f"{sum(1 for c in index['counties'] if c['count'])} counties; "
          f"unexplained {index['reconciliation']['unexplained']}, pending {index['reconciliation']['pendingSource']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
