#!/usr/bin/env python3
"""Build social watcher sources from the candidate watchlist CSV."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import feed_common


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WATCHLIST_CSV = PROJECT_ROOT / "data" / "sources" / "candidate-watchlist.csv"
OUTPUT_JSON = PROJECT_ROOT / "data" / "feeds" / "social_sources.json"
GENERATED_BY = "scripts/build_social_sources.py"

DEFAULT_RSSHUB_BASE = "https://rsshub.app"

VALID_CITIES = {
    "taipei",
    "new-taipei",
    "taoyuan",
    "taichung",
    "tainan",
    "kaohsiung",
}

PLATFORM_URL_COLUMNS = {
    "facebook": "fb_url",
    "instagram": "ig_url",
    "threads": "threads_url",
    "youtube": "youtube_url",
    "x": "x_url",
}


def clean(value: str | None) -> str:
    return (value or "").strip()


def normalize_url(value: str) -> str:
    url = clean(value)
    if not url or url.upper() == "TODO":
        return ""
    if url.startswith("//"):
        return "https:" + url
    if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.IGNORECASE):
        url = "https://" + url.lstrip("@")
    return url


def username_from_url(url: str) -> str:
    match = re.search(r"(?:facebook|instagram|x)\.com/@?([^/?#]+)|threads\.net/@?([^/?#]+)", url, re.IGNORECASE)
    if match:
        return match.group(1) or match.group(2)
    match = re.search(r"youtube\.com/(?:@|channel/|c/)?([^/?#]+)", url, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"watchlist CSV not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def build_sources(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for row in rows:
        city = clean(row.get("city"))
        if city not in VALID_CITIES:
            print(f"build_social_sources: skipping row with unknown city {city!r} (public_id={row.get('public_id')!r})")
            continue
        candidate_id = feed_common.candidate_id_from_row(row)
        candidate_name = clean(row.get("candidate_name"))
        keywords = [kw for kw in re.split(r"\s+", clean(row.get("keywords"))) if kw]

        for platform, column in PLATFORM_URL_COLUMNS.items():
            url = normalize_url(row.get(column, ""))
            if not url:
                continue
            username = username_from_url(url)
            source_id = f"{platform[:2]}_{candidate_id}"
            sources.append(
                {
                    "id": source_id,
                    "enabled": True,
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_name,
                    "city": city,
                    "party": clean(row.get("party")),
                    "platform": platform,
                    "username": username,
                    "url": url,
                    "keywords": keywords,
                    "rsshub_base": DEFAULT_RSSHUB_BASE,
                    "generated_by": GENERATED_BY,
                }
            )

        website_url = normalize_url(row.get("website_url", ""))
        if website_url:
            sources.append(
                {
                    "id": f"web_{candidate_id}",
                    "enabled": True,
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_name,
                    "city": city,
                    "party": clean(row.get("party")),
                    "platform": "website",
                    "username": "",
                    "url": website_url,
                    "keywords": keywords,
                    "rsshub_base": "",
                    "generated_by": GENERATED_BY,
                }
            )
    return sources


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


def main() -> int:
    rows = read_csv(WATCHLIST_CSV)
    sources = build_sources(rows)
    payload = {
        "version": 1,
        "generated_by": GENERATED_BY,
        "count": len(sources),
        "sources": sources,
    }
    save_json(OUTPUT_JSON, payload)
    print(f"build_social_sources: wrote {len(sources)} sources to {OUTPUT_JSON.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
