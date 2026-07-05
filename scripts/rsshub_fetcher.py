#!/usr/bin/env python3
"""Fetch Instagram / Threads updates via a RSSHub instance.

Defaults to https://rss.observe.tw, the same RSSHub deployment used by the
Harmonica-in-Taiwan project. Override with MAYOR_RSSHUB_BASE if a different
instance should be used (e.g. a local one on the Hsinchu machine).

Facebook is deliberately NOT fetched here: this RSSHub instance has no
matching `/facebook/*` route registered at all (verified live — no
`x-rsshub-route` response header, vs. Instagram/Threads which do match but
can still 503 under rate limiting). Facebook goes through
apify_facebook_fetcher.py instead. A single source failing here does not
stop the rest of the batch (see feed_common.record_error).
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

import feed_common

IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
VIDEO_POSTER_RE = re.compile(r"<video\b[^>]*\bposter=[\"']([^\"']+)[\"']", re.IGNORECASE)

DEFAULT_RSSHUB_BASE = os.environ.get("MAYOR_RSSHUB_BASE", "https://rss.observe.tw").rstrip("/")
REQUEST_TIMEOUT_SECS = 15
USER_AGENT = "Mozilla/5.0 (compatible; 2026mayor-fetcher/0.1)"

RSSHUB_ROUTE_BUILDERS = {
    "instagram": lambda username: f"/instagram/user/{username}",
    # NOTE: on rss.observe.tw the Threads route is /threads/:user directly;
    # /threads/user/:user would treat the literal "user" as the username.
    "threads": lambda username: f"/threads/{username}",
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
        # src attributes are HTML-escaped in the feed; unescape or the signed
        # CDN URLs' query params break (403).
        media = [html.unescape(u) for u in IMG_SRC_RE.findall(description) + VIDEO_POSTER_RE.findall(description)]
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
                "media": media,
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
        print("rsshub_fetcher: no instagram/threads sources configured; nothing to do.")
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
