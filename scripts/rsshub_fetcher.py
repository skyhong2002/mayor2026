#!/usr/bin/env python3
"""Fetch Instagram / Threads updates via a RSSHub instance.

Mechanics ported from Harmonica-in-Taiwan's social_feed_watchdog.py:

- RSSHub error pages are parsed for the real error message ("Error Message:
  <code>...</code>") instead of logging a bare 503 — a ConfigNotFoundError or
  NotFoundError points straight at the misconfigured route.
- Per-source fetch state (state/social_fetch_state.json) rate-limits
  Instagram profile fetches to once per interval (default 12h) so the
  instance's IG cookie isn't burned by every pipeline tick.
- Politeness delays between requests (Instagram 8s, others 0.25s).

Route notes for rss.observe.tw:
- Instagram uses the V2 web-API route /instagram/2/user/:key (the instance
  configures IG_COOKIE for it; the V1 private-API route needs
  IG_USERNAME/IG_PASSWORD, deliberately unset because password login gets
  the account locked).
- Threads is /threads/:user directly; /threads/user/:user would treat the
  literal "user" as the username.
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

import feed_common

DEFAULT_RSSHUB_BASE = os.environ.get("MAYOR_RSSHUB_BASE", "https://rss.observe.tw").rstrip("/")
REQUEST_TIMEOUT_SECS = 30
USER_AGENT = "Mayor2026SocialWatcher/1.0"

FETCH_STATE_JSON = feed_common.PROJECT_ROOT / "state" / "social_fetch_state.json"

DEFAULT_INSTAGRAM_INTERVAL_HOURS = float(os.environ.get("MAYOR_INSTAGRAM_INTERVAL_HOURS", "12"))
DEFAULT_INSTAGRAM_DELAY_SECS = float(os.environ.get("MAYOR_INSTAGRAM_DELAY_SECS", "8"))
DEFAULT_RSS_DELAY_SECS = 0.25

IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
VIDEO_POSTER_RE = re.compile(r"<video\b[^>]*\bposter=[\"']([^\"']+)[\"']", re.IGNORECASE)
RSSHUB_ERROR_MESSAGE_RE = re.compile(
    r"Error Message:\s*<br\s*/?>\s*<code[^>]*>(.*?)</code>", re.IGNORECASE | re.DOTALL
)

RSSHUB_ROUTE_BUILDERS = {
    "instagram": lambda username: f"/instagram/2/user/{username}",
    "threads": lambda username: f"/threads/{username}",
}


def rsshub_error_message(body: bytes) -> str:
    """Extract the human-readable error out of a RSSHub error page."""
    text = body.decode("utf-8", "replace")
    match = RSSHUB_ERROR_MESSAGE_RE.search(text)
    if match:
        text = match.group(1)
    return " ".join(feed_common.strip_html(text).split())[:500]


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
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECS) as response:
            return ET.fromstring(response.read())
    except urllib.error.HTTPError as exc:
        message = rsshub_error_message(exc.read())
        raise RuntimeError(f"HTTP {exc.code}: {message or exc.reason}") from exc


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


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def instagram_due(fetch_state: dict[str, Any], source_id: str, *, interval_hours: float, now: dt.datetime) -> bool:
    entry = (fetch_state.get("sources") or {}).get(source_id) or {}
    last = parse_time(entry.get("last_attempt_at"))
    if last is None:
        return True
    return now - last >= dt.timedelta(hours=interval_hours)


def record_attempt(fetch_state: dict[str, Any], source_id: str, *, ok: bool, message: str = "") -> None:
    entry = fetch_state.setdefault("sources", {}).setdefault(source_id, {})
    now_iso = feed_common.utc_now_iso()
    entry["last_attempt_at"] = now_iso
    if ok:
        entry["last_success_at"] = now_iso
        entry.pop("last_error", None)
    else:
        entry["last_error"] = message[:500]
        entry["last_error_at"] = now_iso


def fetch_source(source: dict[str, Any], *, rsshub_base: str, limit: int) -> list[dict[str, Any]]:
    platform = source.get("platform")
    username = source.get("username")
    builder = RSSHUB_ROUTE_BUILDERS.get(platform)
    if not builder or not username:
        return []
    base = source.get("rsshub_base") or rsshub_base
    url = base.rstrip("/") + builder(username)
    root = fetch_rss(url)
    return normalize_items(source, root, limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rsshub-base", default=DEFAULT_RSSHUB_BASE)
    parser.add_argument("--limit", type=int, default=10, help="Max items to keep per source per run.")
    parser.add_argument("--instagram-interval-hours", type=float, default=DEFAULT_INSTAGRAM_INTERVAL_HOURS)
    parser.add_argument("--full-refresh", action="store_true", help="Ignore per-source fetch intervals.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print, but do not write to inbox.")
    args = parser.parse_args()

    sources = feed_common.load_sources(platforms=set(RSSHUB_ROUTE_BUILDERS))
    if not sources:
        print("rsshub_fetcher: no instagram/threads sources configured; nothing to do.")
        return 0

    fetch_state = feed_common.load_json(FETCH_STATE_JSON, {"version": 1, "sources": {}})
    now = dt.datetime.now(dt.timezone.utc)

    all_rows: list[dict[str, Any]] = []
    skipped = 0
    for source in sources:
        platform = source["platform"]
        if (
            platform == "instagram"
            and not args.full_refresh
            and not instagram_due(fetch_state, source["id"], interval_hours=args.instagram_interval_hours, now=now)
        ):
            skipped += 1
            continue

        try:
            rows = fetch_source(source, rsshub_base=args.rsshub_base, limit=args.limit)
        except (RuntimeError, urllib.error.URLError, ET.ParseError) as exc:
            record_attempt(fetch_state, source["id"], ok=False, message=str(exc))
            feed_common.record_error(source["id"], f"rsshub fetch failed: {exc}")
        else:
            record_attempt(fetch_state, source["id"], ok=True)
            all_rows.extend(rows)
            print(f"rsshub_fetcher: {source['id']} -> {len(rows)} item(s)")

        time.sleep(DEFAULT_INSTAGRAM_DELAY_SECS if platform == "instagram" else DEFAULT_RSS_DELAY_SECS)

    if skipped:
        print(f"rsshub_fetcher: skipped {skipped} instagram source(s) not yet due (interval {args.instagram_interval_hours}h).")

    if not args.dry_run:
        feed_common.save_json_atomic(FETCH_STATE_JSON, fetch_state)

    if args.dry_run:
        print(f"rsshub_fetcher: dry-run, fetched {len(all_rows)} item(s) total, not writing.")
        return 0

    appended = feed_common.append_jsonl_dedup(feed_common.INBOX_JSONL, all_rows)
    print(f"rsshub_fetcher: appended {appended} new item(s) to {feed_common.INBOX_JSONL.relative_to(feed_common.PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
