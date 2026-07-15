#!/usr/bin/env python3
"""Build auditable qualitative summary and policy-matching payloads."""

from __future__ import annotations

from collections import Counter
import classify_context
import feed_common
import classify_topics

API_DIR = feed_common.PROJECT_ROOT / "site" / "api"


def main() -> int:
    posts = feed_common.read_jsonl(feed_common.CANDIDATES_JSONL)
    candidates = {row["candidate_id"]: row for row in feed_common.load_candidates()}

    nature_counts = Counter((post.get("nature") or {}).get("type", "other") for post in posts)
    feed_common.save_json_atomic(API_DIR / "qualitative-summary.json", {
        "version": 2, "postCount": len(posts), "natureCounts": dict(nature_counts),
        "natureLabels": classify_context.NATURE_LABELS,
    })
    # Candidate agenda vectors use only autonomous policy-advocacy posts.  This
    # avoids treating typhoon notices or replies to opponents as manifestos.
    agenda_entries = []
    for candidate_id, candidate in candidates.items():
        eligible = [post for post in posts if post.get("candidate_id") == candidate_id
                    and (post.get("nature") or {}).get("type") == "policy_proposal"
                    and float(post.get("agendaRelevance") or 0) >= 0.6]
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
    print(f"build_qualitative: summary and policy matcher over {len(posts)} classified post(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
