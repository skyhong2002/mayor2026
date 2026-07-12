#!/usr/bin/env python3
"""Build auditable event and qualitative-comparison API payloads."""

from __future__ import annotations

from collections import Counter
from typing import Any

import classify_context
import feed_common
import classify_topics
from build_public_data import to_api_post

API_DIR = feed_common.PROJECT_ROOT / "site" / "api"


def main() -> int:
    events = classify_context.load_events()
    posts = feed_common.read_jsonl(feed_common.CANDIDATES_JSONL)
    candidates = {row["candidate_id"]: row for row in feed_common.load_candidates()}
    event_rows: list[dict[str, Any]] = []

    for event in events:
        matched = [post for post in posts if (post.get("trigger") or {}).get("eventId") == event["id"]]
        by_candidate: dict[str, list[dict[str, Any]]] = {}
        for post in matched:
            by_candidate.setdefault(post["candidate_id"], []).append(post)
        comparisons = []
        for candidate_id, rows in sorted(by_candidate.items()):
            action_counts = Counter(action for row in rows for action in row.get("actions", []))
            trigger_counts = Counter((row.get("trigger") or {}).get("type", "unclear") for row in rows)
            comparisons.append({
                "candidateId": candidate_id,
                "candidateName": candidates.get(candidate_id, {}).get("name", candidate_id),
                "postCount": len(rows),
                "actionCounts": dict(action_counts),
                "triggerCounts": dict(trigger_counts),
                "firstPostAt": min((row.get("posted_at") or "" for row in rows), default=None),
                "latestPostAt": max((row.get("posted_at") or "" for row in rows), default=None),
            })
        detail = {**event, "postCount": len(matched), "candidateCount": len(by_candidate), "comparisons": comparisons,
                  "posts": [to_api_post(row) for row in sorted(matched, key=lambda r: r.get("posted_at") or "", reverse=True)]}
        feed_common.save_json_atomic(API_DIR / "events" / f"{event['id']}.json", {"version": 1, "event": detail})
        event_rows.append({key: detail[key] for key in ("id", "name", "category", "startAt", "endAt", "description", "postCount", "candidateCount")})

    trigger_counts = Counter((post.get("trigger") or {}).get("type", "unclear") for post in posts)
    action_counts = Counter(action for post in posts for action in post.get("actions", []))
    review_count = sum(bool((post.get("classification") or {}).get("needsReview")) for post in posts)
    feed_common.save_json_atomic(API_DIR / "events.json", {"version": 1, "count": len(event_rows), "events": event_rows})
    feed_common.save_json_atomic(API_DIR / "qualitative-summary.json", {
        "version": 1, "postCount": len(posts), "triggerCounts": dict(trigger_counts),
        "actionCounts": dict(action_counts), "needsReviewCount": review_count,
        "triggerLabels": classify_context.TRIGGER_LABELS, "actionLabels": classify_context.ACTION_LABELS,
    })
    # Candidate agenda vectors use only autonomous policy-advocacy posts.  This
    # avoids treating typhoon notices or replies to opponents as manifestos.
    agenda_entries = []
    for candidate_id, candidate in candidates.items():
        eligible = [post for post in posts if post.get("candidate_id") == candidate_id
                    and (post.get("trigger") or {}).get("type") == "self_initiated"
                    and "policy_proposal" in post.get("actions", [])]
        totals: Counter[str] = Counter()
        evidence: dict[str, list[dict[str, str]]] = {}
        for post in eligible:
            for topic, score in (post.get("topic_scores") or {}).items():
                if topic == classify_topics.FALLBACK_TOPIC:
                    continue
                totals[topic] += score
                if score > 0 and len(evidence.setdefault(topic, [])) < 3:
                    excerpt = (post.get("text") or "")[:180]
                    if excerpt and not any(item["text"] == excerpt for item in evidence[topic]):
                        evidence[topic].append({"postId": post["id"], "url": post.get("url") or "", "text": excerpt})
        grand = sum(totals.values())
        agenda_entries.append({
            "candidateId": candidate_id, "candidateName": candidate["name"], "city": candidate["city"],
            "eligiblePostCount": len(eligible),
            "topicWeights": {topic: round(value / grand, 4) for topic, value in totals.items()} if grand else {},
            "evidence": evidence,
        })
    questions = feed_common.load_json(feed_common.PROJECT_ROOT / "data" / "sources" / "policy_questions.json", {})
    feed_common.save_json_atomic(API_DIR / "policy-match.json", {**questions, "candidates": agenda_entries})
    print(f"build_qualitative: {len(event_rows)} event(s), {len(posts)} classified post(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
