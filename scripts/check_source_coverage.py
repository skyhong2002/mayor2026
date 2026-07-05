#!/usr/bin/env python3
"""Verify watchlist accounts are actually covered by the fetch configuration."""

from __future__ import annotations

import sys

import feed_common

FETCHABLE_PLATFORMS = {"facebook", "instagram", "threads", "youtube", "website"}


def main() -> int:
    errors: list[str] = []

    candidates = feed_common.load_candidates()
    accounts = feed_common.load_accounts()
    config = feed_common.load_json(feed_common.SOCIAL_SOURCES_JSON, {"sources": []})
    source_ids = {s["id"] for s in config.get("sources", [])}

    fetchable_accounts = [a for a in accounts if a["platform"] in FETCHABLE_PLATFORMS]
    for account in fetchable_accounts:
        if account["account_id"] not in source_ids:
            errors.append(f"active fetchable account missing from social_sources.json: {account['account_id']}")

    accounts_by_candidate = feed_common.accounts_by_candidate(fetchable_accounts)
    for candidate in candidates:
        if not accounts_by_candidate.get(candidate["candidate_id"]):
            errors.append(f"candidate has no fetchable source: {candidate['candidate_id']} ({candidate['name']})")

    candidate_ids = {c["candidate_id"] for c in candidates}
    for account in accounts:
        if account["candidate_id"] not in candidate_ids:
            errors.append(f"account references unknown candidate: {account['account_id']} -> {account['candidate_id']}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Source coverage OK: {len(fetchable_accounts)} fetchable account(s) across {len(candidates)} candidate(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
