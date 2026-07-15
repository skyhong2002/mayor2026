#!/usr/bin/env python3
"""Build the public JSON API from candidates.csv + watchlist_accounts.csv + classified posts."""

from __future__ import annotations

from typing import Any

import classify_topics
import feed_common

API_DIR = feed_common.PROJECT_ROOT / "site" / "api"
IMAGE_CACHE_JSON = feed_common.PROJECT_ROOT / "state" / "feed_image_cache.json"
AVATAR_CACHE_JSON = feed_common.PROJECT_ROOT / "state" / "source_avatar_cache.json"

LINK_PLATFORMS = ["website", "facebook", "instagram", "threads", "youtube", "x", "line_oa", "line_openchat", "tiktok", "podcast"]

IMAGE_CACHE = feed_common.load_json(IMAGE_CACHE_JSON, {})
AVATAR_CACHE = feed_common.load_json(AVATAR_CACHE_JSON, {})  # keyed by account id
PROFILES = feed_common.load_json(feed_common.SOURCE_PROFILES_JSON, {})


def account_avatar_url(account_id: str) -> str | None:
    cached = AVATAR_CACHE.get(account_id)
    return f"assets/source-avatars/{cached['file']}" if cached else None


def build_candidate_entries(candidates: list[dict[str, str]], accounts_by_candidate: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    entries = []
    for candidate in candidates:
        accounts = accounts_by_candidate.get(candidate["candidate_id"], [])
        best = feed_common.best_accounts_per_platform(accounts)
        links = {platform: best[platform]["url"] if platform in best else None for platform in LINK_PLATFORMS}
        # Candidate-level avatar (city cards, hero): best-ranked account that has one.
        avatar_url = None
        for account in sorted(accounts, key=feed_common.account_sort_key):
            avatar_url = account_avatar_url(account.get("account_id", ""))
            if avatar_url:
                break
        entries.append(
            {
                "id": candidate["candidate_id"],
                "name": candidate["name"],
                "city": candidate["city"],
                "cityLabel": feed_common.CITY_LABELS[candidate["city"]],
                "party": candidate["party"],
                "links": links,
                "avatarUrl": avatar_url,
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


def matched_keywords(post: dict[str, Any]) -> list[str]:
    """Keyword sub-items this post actually hits, for the timeline's 小 tag filter."""
    text = post.get("text") or ""
    found = []
    for topic in post.get("topics") or []:
        for keyword in classify_topics.TOPIC_KEYWORDS.get(topic, ()):
            if keyword in text and keyword not in found:
                found.append(keyword)
    return found


def to_api_post(post: dict[str, Any]) -> dict[str, Any]:
    cached_image = IMAGE_CACHE.get(post["id"])
    return {
        "id": post["id"],
        "candidateId": post.get("candidate_id"),
        "sourceId": post.get("source_id"),
        "platform": post.get("platform"),
        "url": post.get("url"),
        "postedAt": post.get("posted_at"),
        "text": post.get("text"),
        "imageUrl": f"assets/feed-images/{cached_image['file']}" if cached_image else None,
        "imageAspect": cached_image["aspect"] if cached_image else None,
        "topics": post.get("topics") or [],
        "topicScores": post.get("topic_scores") or {},
        "keywords": matched_keywords(post),
        "postingIntent": post.get("postingIntent") or {
            "type": "self_initiated", "label": "主動發文", "confidence": 0, "reason": "AI 分類處理中"
        },
        "agendaRelevance": post.get("agendaRelevance", 0),
        "classification": post.get("classification") or {"method": "pending", "model": "", "rubricVersion": ""},
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


def build_sources_index(
    candidates: list[dict[str, Any]],
    accounts_by_candidate: dict[str, list[dict[str, Any]]],
    grouped_posts: dict[str, list[dict[str, Any]]],
) -> None:
    entries = []
    for candidate in candidates:
        posts = grouped_posts.get(candidate["id"], [])
        accounts = []
        for account in accounts_by_candidate.get(candidate["id"], []):
            account_id = account.get("account_id", "")
            profile = PROFILES.get(account_id, {})
            accounts.append(
                {
                    "id": account_id,
                    "platform": account["platform"],
                    "url": account["url"],
                    "handle": account.get("handle", ""),
                    "role": account.get("account_role", ""),
                    "verification": account.get("verification", ""),
                    "displayName": profile.get("display_name") or None,
                    "avatarUrl": account_avatar_url(account_id),
                }
            )
        entries.append(
            {
                **candidate,
                "accounts": accounts,
                "postCount": len(posts),
                "latestPostAt": posts[0].get("posted_at") if posts else None,
            }
        )
    feed_common.save_json_atomic(
        API_DIR / "sources.json",
        {"version": 1, "count": len(entries), "sources": entries},
    )


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
    build_sources_index(candidates, accounts_by_candidate, grouped_posts)
    build_cities_index(candidates)
    build_candidate_pages(candidates, grouped_posts)
    build_latest_feed(posts)

    print(f"build_public_data: {len(candidates)} candidate(s), {len(posts)} post(s) -> {API_DIR.relative_to(feed_common.PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
