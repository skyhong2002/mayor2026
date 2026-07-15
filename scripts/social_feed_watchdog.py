#!/usr/bin/env python3
"""Promote newly fetched inbox posts into the candidates feed.

Fetch adapters (rsshub_fetcher.py, youtube_ytdlp_fetcher.py,
apify_facebook_fetcher.py, official_site_fetcher.py) already normalize and
dedupe raw posts into `data/feeds/social_feed_inbox.jsonl`. This script is
the next stage: it finds inbox rows that have not been promoted yet and appends
them to `data/feeds/social_candidates.jsonl`. The following pipeline step is
the only classifier and uses structured AI output for both topic and posting intent.
"""

from __future__ import annotations

import argparse
import datetime as dt

import feed_common


def is_too_old(posted_at: str, *, max_age_days: int) -> bool:
    if not posted_at:
        return False
    try:
        posted = dt.datetime.fromisoformat(posted_at)
    except ValueError:
        return False
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=dt.timezone.utc)
    age = dt.datetime.now(dt.timezone.utc) - posted
    return age > dt.timedelta(days=max_age_days)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-post-age-days", type=int, default=30)
    args = parser.parse_args()

    inbox = feed_common.read_jsonl(feed_common.INBOX_JSONL)
    already_promoted = {row.get("id") for row in feed_common.read_jsonl(feed_common.CANDIDATES_JSONL)}

    new_rows = []
    skipped_old = 0
    for entry in inbox:
        if entry.get("id") in already_promoted:
            continue
        if is_too_old(entry.get("posted_at", ""), max_age_days=args.max_post_age_days):
            skipped_old += 1
            continue
        new_rows.append(dict(entry))

    if skipped_old:
        print(f"social_feed_watchdog: skipped {skipped_old} row(s) older than {args.max_post_age_days} days.")

    if not new_rows:
        print("social_feed_watchdog: no new inbox rows to classify.")
        return 0

    appended = feed_common.append_jsonl_dedup(feed_common.CANDIDATES_JSONL, new_rows)
    print(f"social_feed_watchdog: promoted {appended} new row(s) for AI classification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
