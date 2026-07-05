#!/usr/bin/env python3
"""Build fetchable social sources from candidates.csv + watchlist_accounts.csv.

Every active account row for a fetchable platform becomes one fetch source
(not just the "best" one per platform) — a candidate's campaign FB page and
personal FB profile are both worth watching, for example.
"""

from __future__ import annotations

from typing import Any

import feed_common

OUTPUT_JSON = feed_common.PROJECT_ROOT / "data" / "feeds" / "social_sources.json"
GENERATED_BY = "scripts/build_social_sources.py"

DEFAULT_RSSHUB_BASE = "https://rss.observe.tw"

# Platforms we actually know how to fetch. line_oa/tiktok/x still show up in
# candidate link lists (see build_public_data.py) but aren't fetched yet.
FETCHABLE_PLATFORMS = {"facebook", "instagram", "threads", "youtube", "website"}


def build_sources(candidates: list[dict[str, str]], accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates_by_id = {c["candidate_id"]: c for c in candidates}
    sources: list[dict[str, Any]] = []
    for account in accounts:
        if account["platform"] not in FETCHABLE_PLATFORMS:
            continue
        candidate = candidates_by_id.get(account["candidate_id"])
        if not candidate:
            print(f"build_social_sources: skipping account {account['account_id']!r}, unknown candidate_id {account['candidate_id']!r}")
            continue
        sources.append(
            {
                "id": account["account_id"],
                "enabled": True,
                "candidate_id": candidate["candidate_id"],
                "candidate_name": candidate["name"],
                "city": candidate["city"],
                "party": candidate["party"],
                "platform": account["platform"],
                "username": account.get("handle", ""),
                "url": account["url"],
                "account_role": account.get("account_role", ""),
                "verification": account.get("verification", ""),
                "rsshub_base": DEFAULT_RSSHUB_BASE,
                "generated_by": GENERATED_BY,
            }
        )
    return sources


def main() -> int:
    candidates = feed_common.load_candidates()
    accounts = feed_common.load_accounts()
    sources = build_sources(candidates, accounts)
    payload = {
        "version": 1,
        "generated_by": GENERATED_BY,
        "count": len(sources),
        "sources": sources,
    }
    feed_common.save_json_atomic(OUTPUT_JSON, payload)
    print(f"build_social_sources: wrote {len(sources)} source(s) for {len(candidates)} candidate(s) to {OUTPUT_JSON.relative_to(feed_common.PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
