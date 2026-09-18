#!/usr/bin/env python3
"""Fetch press releases / news posts from candidate official websites.

Official campaign sites don't share a common structure, so there is no
generic scraper here. Instead this script looks for a per-candidate adapter
module under `scripts/official_site_adapters/<candidate_id>.py` exposing a
`fetch(url: str) -> list[dict]` function that returns raw
`{"post_id", "url", "posted_at", "text"}` dicts. Candidates without an
adapter are skipped with a clear message.

  TODO: once the real candidate list lands, add one adapter module per
  official website under scripts/official_site_adapters/.
"""

from __future__ import annotations

import argparse
import importlib
from typing import Any

import feed_common
import source_status

ADAPTER_PACKAGE = "official_site_adapters"


def load_adapter(candidate_id: str):
    module_name = f"{ADAPTER_PACKAGE}.{candidate_id.replace('-', '_')}"
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        return None


def normalize_raw_posts(source: dict[str, Any], raw_posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for post in raw_posts:
        post_id = post.get("post_id")
        if not post_id:
            continue
        rows.append(
            {
                "id": f"website:{post_id}",
                "candidate_id": source["candidate_id"],
                "city": source["city"],
                "platform": "website",
                "source_id": source["id"],
                "url": post.get("url") or source["url"],
                "posted_at": post.get("posted_at") or "",
                "text": post.get("text") or "",
                "media": post.get("media") or [],
                "fetched_at": feed_common.utc_now_iso(),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sources = feed_common.load_sources(platforms={"website"})
    if not sources:
        print("official_site_fetcher: no website sources configured; nothing to do.")
        return 0

    all_rows: list[dict[str, Any]] = []
    appended = 0
    for source in sources:
        reason = source_status.link_only_reason(source)
        if reason:
            print(f"official_site_fetcher: {source['id']} link only: {reason}")
            continue
        if not source_status.retry_ready(source):
            continue
        adapter = load_adapter(source["candidate_id"])
        if adapter is None:
            print(f"official_site_fetcher: no adapter for {source['candidate_id']}; skipping {source['url']}")
            continue
        try:
            raw_posts = adapter.fetch(source["url"])
        except Exception as exc:  # adapters are third-party-ish and vary a lot; keep the batch alive.
            if not args.dry_run:
                source_status.record_fetch(source, ok=False, error=exc)
                feed_common.record_error(source["id"], f"adapter fetch failed: {source_status.safe_error(exc)}")
            continue
        rows = normalize_raw_posts(source, raw_posts)
        if not args.dry_run:
            appended += feed_common.append_jsonl_dedup(feed_common.INBOX_JSONL, rows)
            source_status.record_fetch(source, ok=True, items=len(rows))
        all_rows.extend(rows)
        print(f"official_site_fetcher: {source['id']} -> {len(rows)} item(s)")

    if args.dry_run:
        print(f"official_site_fetcher: dry-run, fetched {len(all_rows)} item(s), not writing.")
        return 0

    print(f"official_site_fetcher: appended {appended} new item(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
