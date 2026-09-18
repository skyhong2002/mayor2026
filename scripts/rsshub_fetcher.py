#!/usr/bin/env python3
"""Fetch Instagram / Threads / X updates via a RSSHub instance, plus
direct-RSS platforms (podcast) via their native feed URLs.

Chumei-style per-source telemetry and scheduling:
- Bounded, oldest-due Instagram batches with adaptive 12–168 hour intervals.
- Persisted retry backoff and shared 401/429 cooldown; success clears errors.
- RSSHub error pages expose the upstream failure, not merely HTTP 503.
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
import source_status

DEFAULT_RSSHUB_BASE = os.environ.get("MAYOR_RSSHUB_BASE", "https://rss.observe.tw").rstrip("/")
REQUEST_TIMEOUT_SECS = 30
USER_AGENT = "Mayor2026SocialWatcher/1.0"

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
    "x": lambda username: f"/twitter/user/{username}",
}

# Platforms fetched from a direct RSS feed URL (source["feed_url"] from the
# watchlist CSV) instead of a RSSHub route.
DIRECT_FEED_PLATFORMS = {"podcast"}


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


def fetch_source(source: dict[str, Any], *, rsshub_base: str, limit: int) -> list[dict[str, Any]]:
    platform = source.get("platform")
    if platform in DIRECT_FEED_PLATFORMS:
        url = source.get("feed_url") or ""
        if not url:
            return []
    else:
        username = source.get("username")
        builder = RSSHUB_ROUTE_BUILDERS.get(platform)
        if not builder or not username:
            return []
        url = rsshub_base.rstrip("/") + builder(username)
    root = fetch_rss(url)
    return normalize_items(source, root, limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rsshub-base",
        default=None,
        help=f"RSSHub base URL for every source (default: MAYOR_RSSHUB_BASE or per-source value or {DEFAULT_RSSHUB_BASE}).",
    )
    parser.add_argument("--limit", type=int, default=10, help="Max items to keep per source per run.")
    parser.add_argument("--instagram-interval-hours", type=float, default=DEFAULT_INSTAGRAM_INTERVAL_HOURS)
    parser.add_argument("--full-refresh", action="store_true", help="Ignore regular intervals; retain failure backoff and platform cooldown.")
    parser.add_argument("--instagram-batch-size", type=int, default=6, help="Oldest-due Instagram accounts per run.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print, but do not write to inbox.")
    args = parser.parse_args()

    sources = feed_common.load_sources(platforms=set(RSSHUB_ROUTE_BUILDERS) | DIRECT_FEED_PLATFORMS)
    if not sources:
        print("rsshub_fetcher: no RSS-fetchable sources configured; nothing to do.")
        return 0

    if args.instagram_batch_size < 1 or args.instagram_interval_hours <= 0:
        parser.error("Instagram batch size and interval must be positive")
    fetch_state = source_status.load_state()
    now = dt.datetime.now(dt.timezone.utc)
    ig_sources = [s for s in sources if s["platform"] == "instagram"]
    oldest = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    ig_sources.sort(key=lambda s: (source_status.next_eligible(s, fetch_state,
        instagram_hours=args.instagram_interval_hours) or oldest, s["id"]))
    selected_ig = {s["id"] for s in ig_sources if args.full_refresh or
                   (source_status.next_eligible(s, fetch_state, instagram_hours=args.instagram_interval_hours) or oldest) <= now}
    selected_ig = {s["id"] for s in [s for s in ig_sources if s["id"] in selected_ig][:args.instagram_batch_size]}
    cooldown = parse_time(fetch_state.get("platforms", {}).get("instagram", {}).get("cooldown_until"))
    all_rows: list[dict[str, Any]] = []
    appended = 0
    skipped = 0
    # Keep due-time ordering during execution as well as batch selection.
    ordered = [s for s in sources if s["platform"] != "instagram"] + ig_sources
    for source in ordered:
        platform = source["platform"]
        if not source_status.retry_ready(source, now=now) or (
            platform == "instagram" and (source["id"] not in selected_ig or (cooldown and cooldown > now))
        ):
            skipped += 1
            continue
        try:
            rows = fetch_source(source, rsshub_base=args.rsshub_base or DEFAULT_RSSHUB_BASE, limit=args.limit)
        except (RuntimeError, OSError, urllib.error.URLError, ET.ParseError) as exc:
            if not args.dry_run:
                source_status.record_fetch(source, ok=False, error=exc)
                feed_common.record_error(source["id"], f"rsshub fetch failed: {source_status.safe_error(exc)}")
            if platform == "instagram" and source_status.is_rate_limited(exc):
                # Stop this shared-session batch immediately. Other platforms continue.
                cooldown = now + dt.timedelta(hours=24)
                if not args.dry_run:
                    source_status.set_instagram_cooldown(exc)
            print(f"rsshub_fetcher: {source['id']} failed: {source_status.safe_error(exc)}")
        else:
            interval = source_status.instagram_interval(rows, minimum=args.instagram_interval_hours) if platform == "instagram" else 6
            if not args.dry_run:
                appended += feed_common.append_jsonl_dedup(feed_common.INBOX_JSONL, rows)
                all_rows.extend(rows)
                source_status.record_fetch(source, ok=True, items=len(rows), interval_hours=interval)
                if platform == "instagram":
                    source_status.clear_instagram_cooldown()
            else:
                all_rows.extend(rows)
            print(f"rsshub_fetcher: {source['id']} -> {len(rows)} item(s); target interval {interval:g}h")
        time.sleep(DEFAULT_INSTAGRAM_DELAY_SECS if platform == "instagram" else DEFAULT_RSS_DELAY_SECS)

    if skipped:
        print(f"rsshub_fetcher: {skipped} source(s) waiting for schedule, batch capacity or retry cooldown.")
    if args.dry_run:
        print(f"rsshub_fetcher: dry-run, fetched {len(all_rows)} item(s) total, not writing.")
        return 0
    print(f"rsshub_fetcher: appended {appended} new item(s) to {feed_common.INBOX_JSONL.relative_to(feed_common.PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
