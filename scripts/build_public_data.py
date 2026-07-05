#!/usr/bin/env python3
"""Build the public JSON API from the watchlist CSV + classified posts."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import feed_common

WATCHLIST_CSV = feed_common.PROJECT_ROOT / "data" / "sources" / "candidate-watchlist.csv"
API_DIR = feed_common.PROJECT_ROOT / "site" / "api"

CITY_LABELS = {
    "taipei": "臺北市",
    "new-taipei": "新北市",
    "taoyuan": "桃園市",
    "taichung": "臺中市",
    "tainan": "臺南市",
    "kaohsiung": "高雄市",
}


def clean(value: str | None) -> str:
    return (value or "").strip()


def load_candidates() -> list[dict[str, Any]]:
    if not WATCHLIST_CSV.exists():
        return []
    with WATCHLIST_CSV.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    candidates = []
    for row in rows:
        city = clean(row.get("city"))
        if city not in CITY_LABELS:
            continue
        candidates.append(
            {
                "id": feed_common.candidate_id_from_row(row),
                "publicId": clean(row.get("public_id")),
                "name": clean(row.get("candidate_name")),
                "nameEn": clean(row.get("candidate_name_en")),
                "city": city,
                "cityLabel": CITY_LABELS[city],
                "party": clean(row.get("party")),
                "links": {
                    "facebook": clean(row.get("fb_url")) or None,
                    "instagram": clean(row.get("ig_url")) or None,
                    "threads": clean(row.get("threads_url")) or None,
                    "youtube": clean(row.get("youtube_url")) or None,
                    "x": clean(row.get("x_url")) or None,
                    "website": clean(row.get("website_url")) or None,
                },
            }
        )
    return candidates


def posts_by_candidate(posts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        grouped.setdefault(post["candidate_id"], []).append(post)
    for candidate_id, rows in grouped.items():
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
    for city_id, label in CITY_LABELS.items():
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
    candidates = load_candidates()
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
