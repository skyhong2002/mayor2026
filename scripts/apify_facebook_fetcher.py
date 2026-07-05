#!/usr/bin/env python3
"""Fetch Facebook posts via Apify's facebook-posts-scraper actor.

Fallback fetcher for when the RSSHub Facebook route is down (a frequent
occurrence). Requires an Apify account and API token.

  TODO: set APIFY_TOKEN in the environment before this can actually run.
  Without it, this prints a skip message and exits 0 (non-fatal).
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

import feed_common

APIFY_BASE = "https://api.apify.com/v2"
FACEBOOK_POSTS_ACTOR = "apify~facebook-posts-scraper"
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"}
POLL_INTERVAL_SECS = 5
MAX_POLL_ATTEMPTS = 24


def apify_token() -> str:
    return os.environ.get("APIFY_TOKEN", "").strip()


def start_run(token: str, page_urls: list[str], *, posts_per_page: int) -> str:
    payload = {
        "startUrls": [{"url": url} for url in page_urls],
        "resultsLimit": posts_per_page,
    }
    request = urllib.request.Request(
        f"{APIFY_BASE}/acts/{FACEBOOK_POSTS_ACTOR}/runs?token={token}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read())
    return body["data"]["id"]


def poll_run(token: str, run_id: str) -> dict[str, Any]:
    for _ in range(MAX_POLL_ATTEMPTS):
        request = urllib.request.Request(f"{APIFY_BASE}/actor-runs/{run_id}?token={token}")
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read())["data"]
        if body["status"] in TERMINAL_STATUSES:
            return body
        time.sleep(POLL_INTERVAL_SECS)
    raise TimeoutError(f"Apify run {run_id} did not finish in time")


def fetch_dataset_items(token: str, dataset_id: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(f"{APIFY_BASE}/datasets/{dataset_id}/items?token={token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def normalize_items(source_by_url: dict[str, dict[str, Any]], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        post_url = item.get("url") or item.get("postUrl") or ""
        page_url = item.get("facebookUrl") or item.get("pageUrl") or ""
        source = source_by_url.get(page_url)
        if not source or not post_url:
            continue
        post_id = item.get("postId") or post_url
        rows.append(
            {
                "id": f"facebook:{post_id}",
                "candidate_id": source["candidate_id"],
                "city": source["city"],
                "platform": "facebook",
                "source_id": source["id"],
                "url": post_url,
                "posted_at": item.get("time") or "",
                "text": item.get("text") or "",
                "media": [m for m in (item.get("media") or []) if isinstance(m, str)],
                "fetched_at": feed_common.utc_now_iso(),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--posts-per-page", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = apify_token()
    if not token:
        print("apify_facebook_fetcher: APIFY_TOKEN not set; skipping Facebook fallback fetch.")
        return 0

    sources = feed_common.load_sources(platforms={"facebook"})
    if not sources:
        print("apify_facebook_fetcher: no facebook sources configured; nothing to do.")
        return 0

    source_by_url = {s["url"]: s for s in sources}
    try:
        run_id = start_run(token, list(source_by_url), posts_per_page=args.posts_per_page)
        run = poll_run(token, run_id)
        if run["status"] != "SUCCEEDED":
            raise RuntimeError(f"Apify run ended with status {run['status']}")
        items = fetch_dataset_items(token, run["defaultDatasetId"])
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, TimeoutError) as exc:
        feed_common.record_error("apify_facebook_fetcher", f"Apify run failed: {exc}")
        return 0

    rows = normalize_items(source_by_url, items)
    print(f"apify_facebook_fetcher: fetched {len(rows)} normalized item(s) from {len(items)} raw item(s).")

    if args.dry_run:
        return 0

    appended = feed_common.append_jsonl_dedup(feed_common.INBOX_JSONL, rows)
    print(f"apify_facebook_fetcher: appended {appended} new item(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
