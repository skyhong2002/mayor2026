#!/usr/bin/env python3
"""Build api/status.json with pipeline and source health metrics."""

from __future__ import annotations

import datetime as dt
from typing import Any

import feed_common

API_DIR = feed_common.PROJECT_ROOT / "site" / "api"
FETCH_STATE_JSON = feed_common.PROJECT_ROOT / "state" / "social_fetch_state.json"
RECENT_ERROR_LIMIT = 20


def recent_errors() -> list[dict[str, Any]]:
    rows = feed_common.read_jsonl(feed_common.ERRORS_JSONL)
    return [
        {"sourceId": row.get("source_id"), "message": row.get("message"), "recordedAt": row.get("recorded_at")}
        for row in rows[-RECENT_ERROR_LIMIT:]
    ]


def source_health() -> list[dict[str, Any]]:
    fetch_state = feed_common.load_json(FETCH_STATE_JSON, {})
    entries = fetch_state.get("sources") or {}
    health = []
    for source_id, entry in sorted(entries.items()):
        health.append(
            {
                "sourceId": source_id,
                "lastAttemptAt": entry.get("last_attempt_at"),
                "lastSuccessAt": entry.get("last_success_at"),
                "lastError": entry.get("last_error"),
                "lastErrorAt": entry.get("last_error_at"),
            }
        )
    return health


def main() -> int:
    posts = feed_common.read_jsonl(feed_common.CANDIDATES_JSONL)
    candidates = feed_common.load_candidates()
    accounts = feed_common.load_accounts()

    by_platform: dict[str, int] = {}
    for post in posts:
        by_platform[post["platform"]] = by_platform.get(post["platform"], 0) + 1

    latest_at = max((p.get("posted_at") or "" for p in posts), default="")

    payload = {
        "version": 1,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "metrics": {
            "candidates": len(candidates),
            "watchAccounts": len(accounts),
            "totalPosts": len(posts),
            "postsByPlatform": by_platform,
            "latestPostAt": latest_at or None,
        },
        "sourceHealth": source_health(),
        "recentErrors": recent_errors(),
    }
    feed_common.save_json_atomic(API_DIR / "status.json", payload)
    print(f"build_status_page: {len(posts)} post(s), {len(payload['sourceHealth'])} tracked source(s), {len(payload['recentErrors'])} recent error(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
