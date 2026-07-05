#!/usr/bin/env python3
"""Fetch Facebook / Instagram / Threads updates via a RSSHub instance.

This is a working skeleton: it can already fetch and normalize real RSS
output from any RSSHub deployment (e.g. the public https://rsshub.app demo
instance) into `data/feeds/social_feed_inbox.jsonl`. The Hsinchu machine's
own RSSHub instance is not reachable from this dev environment, so:

  TODO: point MAYOR_RSSHUB_BASE at the Hsinchu RSSHub before scheduling this
  for real. RSSHub's Facebook/Instagram routes are notoriously unstable —
  expect --dry-run testing against public demo routes to sometimes 404.
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import os
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

import feed_common

DEFAULT_RSSHUB_BASE = os.environ.get("MAYOR_RSSHUB_BASE", "https://rsshub.app").rstrip("/")
REQUEST_TIMEOUT_SECS = 15
USER_AGENT = "Mozilla/5.0 (compatible; 2026mayor-fetcher/0.1)"

RSSHUB_ROUTE_BUILDERS = {
    "facebook": lambda username: f"/facebook/page/{username}",
    "instagram": lambda username: f"/instagram/user/{username}",
    "threads": lambda username: f"/threads/user/{username}",
}


def parse_pubdate(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def fetch_rss(url: str) -> ET.Element:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECS) as response:
        return ET.fromstring(response.read())


def normalize_items(source: dict[str, Any], root: ET.Element, *, limit: int) -> list[dict[str, Any]]:
    rows = []
    items = root.findall("./channel/item")[:limit]
    for item in items:
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        if not guid:
            continue
        title = (item.findtext("title") or "").strip()
        description = item.findtext("description") or ""
        text = feed_common.strip_html(description) or title
        rows.append(
            {
                "id": f"{source['platform']}:{guid}",
                "candidate_id": source["candidate_id"],
                "city": source["city"],
                "platform": source["platform"],
                "source_id": source["id"],
                "url": link or guid,
                "posted_at": parse_pubdate(item.findtext("pubDate") or ""),
                "text": text,
                "media": [],
                "fetched_at": feed_common.utc_now_iso(),
            }
        )
    return rows


def fetch_source(source: dict[str, Any], *, rsshub_base: str, limit: int) -> list[dict[str, Any]]:
    platform = source.get("platform")
    username = source.get("username")
    builder = RSSHUB_ROUTE_BUILDERS.get(platform)
    if not builder or not username:
        return []
    base = source.get("rsshub_base") or rsshub_base
    url = base.rstrip("/") + builder(username)
    try:
        root = fetch_rss(url)
    except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError) as exc:
        feed_common.record_error(source["id"], f"rsshub fetch failed for {url}: {exc}")
        return []
    return normalize_items(source, root, limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rsshub-base", default=DEFAULT_RSSHUB_BASE)
    parser.add_argument("--limit", type=int, default=10, help="Max items to keep per source per run.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print, but do not write to inbox.")
    args = parser.parse_args()

    sources = feed_common.load_sources(platforms=set(RSSHUB_ROUTE_BUILDERS))
    if not sources:
        print("rsshub_fetcher: no facebook/instagram/threads sources configured; nothing to do.")
        return 0

    all_rows: list[dict[str, Any]] = []
    for source in sources:
        rows = fetch_source(source, rsshub_base=args.rsshub_base, limit=args.limit)
        all_rows.extend(rows)
        print(f"rsshub_fetcher: {source['id']} -> {len(rows)} item(s)")

    if args.dry_run:
        print(f"rsshub_fetcher: dry-run, fetched {len(all_rows)} item(s) total, not writing.")
        return 0

    appended = feed_common.append_jsonl_dedup(feed_common.INBOX_JSONL, all_rows)
    print(f"rsshub_fetcher: appended {appended} new item(s) to {feed_common.INBOX_JSONL.relative_to(feed_common.PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
