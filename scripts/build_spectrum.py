#!/usr/bin/env python3
"""Compute per-candidate topic proportions from classified posts.

Pure read-of-files computation: sums each candidate's `topic_scores` across
all their posts and normalizes into a proportion per topic. This is what the
candidate page's topic chart and the cross-candidate spectrum comparison
read from.
"""

from __future__ import annotations

from typing import Any

import feed_common

API_DIR = feed_common.PROJECT_ROOT / "site" / "api"


import classify_topics


def aggregate_topic_proportions(posts: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for post in posts:
        for topic, score in (post.get("topic_scores") or {}).items():
            # The fallback bucket (daily-life posts with no issue content)
            # stays on the post cards but is excluded from the spectrum —
            # otherwise it dominates every bar and hides the actual issues.
            if topic == classify_topics.FALLBACK_TOPIC:
                continue
            totals[topic] = totals.get(topic, 0.0) + score
    grand_total = sum(totals.values())
    if not grand_total:
        return {}
    return {topic: round(value / grand_total, 4) for topic, value in totals.items()}


def build_topic_index(posts: list[dict[str, Any]]) -> None:
    """Post-level index so the spectrum page can recompute with filters
    (time range, excluded topics) entirely client-side."""
    rows = [
        {
            "id": post["id"],
            "candidateId": post["candidate_id"],
            "postedAt": post.get("posted_at") or None,
            "topicScores": post.get("topic_scores") or {},
            "nature": (post.get("nature") or {}).get("type") or "other",
        }
        for post in posts
    ]
    feed_common.save_json_atomic(
        API_DIR / "topic-index.json",
        {"version": 2, "count": len(rows), "fallbackTopic": classify_topics.FALLBACK_TOPIC, "posts": rows},
    )


def build_topic_details(posts: list[dict[str, Any]]) -> None:
    """Per topic, per candidate: which topic keywords their posts actually hit
    and how often — the raw material for "在同一議題內談的東西有何不同"."""
    details: dict[str, dict[str, dict[str, int]]] = {}
    for post in posts:
        text = post.get("text") or ""
        candidate_id = post["candidate_id"]
        for topic in post.get("topics") or []:
            keywords = classify_topics.TOPIC_KEYWORDS.get(topic)
            if not keywords:
                continue
            bucket = details.setdefault(topic, {}).setdefault(candidate_id, {})
            for keyword in keywords:
                hits = text.count(keyword)
                if hits:
                    bucket[keyword] = bucket.get(keyword, 0) + hits
    payload = {
        "version": 1,
        "slugs": classify_topics.TOPIC_SLUGS,
        "topics": {
            topic: {
                candidate_id: sorted(counts.items(), key=lambda kv: -kv[1])
                for candidate_id, counts in by_candidate.items()
            }
            for topic, by_candidate in details.items()
        },
    }
    feed_common.save_json_atomic(API_DIR / "topic-details.json", payload)


def main() -> int:
    posts = feed_common.read_jsonl(feed_common.CANDIDATES_JSONL)
    by_candidate: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        by_candidate.setdefault(post["candidate_id"], []).append(post)

    entries = []
    for candidate_id, candidate_posts in sorted(by_candidate.items()):
        proportions = aggregate_topic_proportions(candidate_posts)
        entries.append(
            {
                "candidateId": candidate_id,
                "postCount": len(candidate_posts),
                "topicProportions": proportions,
                "dominantTopic": max(proportions, key=proportions.get) if proportions else None,
            }
        )

    feed_common.save_json_atomic(
        API_DIR / "spectrum.json",
        {"version": 1, "count": len(entries), "candidates": entries},
    )
    build_topic_index(posts)
    build_topic_details(posts)
    print(f"build_spectrum: topic proportions for {len(entries)} candidate(s), topic index over {len(posts)} post(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
