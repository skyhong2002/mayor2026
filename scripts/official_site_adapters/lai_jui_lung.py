"""Adapter for zenolai.oen.tw — intentionally empty.

Verified 2026-08-23: the site is an OEN fundraising/link page (donation
amounts, subscription tabs) with no dated article or news section. The
/posts path renders an empty shell with no post links; /articles and /news
404. Nothing to ingest until the campaign publishes an actual news feed.
"""

from __future__ import annotations


def fetch(url: str) -> list[dict]:
    return []
