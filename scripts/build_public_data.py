#!/usr/bin/env python3
"""Build the public JSON API from candidates.csv + watchlist_accounts.csv + classified posts."""

from __future__ import annotations

from typing import Any

import feed_common

API_DIR = feed_common.PROJECT_ROOT / "site" / "api"

LINK_PLATFORMS = ["website", "facebook", "instagram", "threads", "youtube", "x", "line_oa", "line_openchat", "tiktok", "podcast"]


def build_candidate_entries(candidates: list[dict[str, str]], accounts_by_candidate: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    entries = []
    for candidate in candidates:
        accounts = accounts_by_candidate.get(candidate["candidate_id"], [])
        best = feed_common.best_accounts_per_platform(accounts)
        links = {platform: best[platform]["url"] if platform in best else None for platform in LINK_PLATFORMS}
        entries.append(
            {
                "id": candidate["candidate_id"],
                "name": candidate["name"],
                "city": candidate["city"],
                "cityLabel": feed_common.CITY_LABELS[candidate["city"]],
                "party": candidate["party"],
                "links": links,
            }
        )
    return entries


def posts_by_candidate(posts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        grouped.setdefault(post["candidate_id"], []).append(post)
    for rows in grouped.values():
        rows.sort(key=lambda r: r.get("posted_at") or "", reverse=True)
    return grouped


def to_api_post(post: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": post["id"],
        "platform": post.get("platform"),
        "url": post.get("url"),
        "postedAt": post.get("posted_at"),
        "text": post.get("text"),
        "media": post.get("media") or [],
        "topics": post.get("topics") or [],
        "topicScores": post.get("topic_scores") or {},
    }


def build_candidate_pages(candidates: list[dict[str, Any]], grouped_posts: dict[str, list[dict[str, Any]]]) -> None:
    posts_dir = API_DIR / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)
    for candidate in candidates:
        posts = grouped_posts.get(candidate["id"], [])
        payload = {
            "version": 1,
            "candidate": candidate,
            "count": len(posts),
            "posts": [to_api_post(p) for p in posts],
        }
        feed_common.save_json_atomic(posts_dir / f"{candidate['id']}.json", payload)


def build_candidates_index(candidates: list[dict[str, Any]], grouped_posts: dict[str, list[dict[str, Any]]]) -> None:
    entries = []
    for candidate in candidates:
        posts = grouped_posts.get(candidate["id"], [])
        entries.append(
            {
                **candidate,
                "postCount": len(posts),
                "latestPostAt": posts[0].get("posted_at") if posts else None,
            }
        )
    feed_common.save_json_atomic(
        API_DIR / "candidates.json",
        {"version": 1, "count": len(entries), "candidates": entries},
    )


def build_cities_index(candidates: list[dict[str, Any]]) -> None:
    cities = []
    for city_id, label in feed_common.CITY_LABELS.items():
        city_candidates = [c["id"] for c in candidates if c["city"] == city_id]
        cities.append({"id": city_id, "label": label, "candidateIds": city_candidates})
    feed_common.save_json_atomic(API_DIR / "cities.json", {"version": 1, "cities": cities})


def build_latest_feed(posts: list[dict[str, Any]], *, limit: int = 100) -> None:
    ordered = sorted(posts, key=lambda r: r.get("posted_at") or "", reverse=True)[:limit]
    feed_common.save_json_atomic(
        API_DIR / "latest.json",
        {"version": 1, "count": len(ordered), "posts": [to_api_post(p) for p in ordered]},
    )


def main() -> int:
    candidates_csv = feed_common.load_candidates()
    accounts = feed_common.load_accounts()
    accounts_by_candidate = feed_common.accounts_by_candidate(accounts)
    candidates = build_candidate_entries(candidates_csv, accounts_by_candidate)

    posts = feed_common.read_jsonl(feed_common.CANDIDATES_JSONL)
    grouped_posts = posts_by_candidate(posts)

    build_candidates_index(candidates, grouped_posts)
    build_cities_index(candidates)
    build_candidate_pages(candidates, grouped_posts)
    build_latest_feed(posts)

    print(f"build_public_data: {len(candidates)} candidate(s), {len(posts)} post(s) -> {API_DIR.relative_to(feed_common.PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
