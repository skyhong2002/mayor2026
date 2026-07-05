#!/usr/bin/env python3
"""Keyword-rule topic classification for candidate posts.

Cheap first pass: count keyword hits per topic in the post text and turn
counts into normalized proportions. `classify()` is imported by
`social_feed_watchdog.py` for new posts, and this file's `main()` lets you
re-run classification over the whole `social_candidates.jsonl` after editing
the keyword table below, without re-fetching anything.

  TODO: once keyword rules prove too coarse, swap `classify()` for an LLM
  batch classifier — everything downstream only depends on `topics` /
  `topic_scores` being present, not on how they were computed.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import feed_common

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "交通": ["交通", "捷運", "公車", "道路", "停車", "塞車", "鐵路", "自行車", "人行道"],
    "住宅": ["住宅", "房價", "囤房", "社會住宅", "都更", "租屋", "buying", "危老"],
    "社福": ["社福", "長照", "托育", "育兒", "老人", "身心障礙", "弱勢", "社會福利", "補助"],
    "環境": ["環境", "空污", "垃圾", "淨零", "碳排", "綠地", "污染", "氣候", "資源回收"],
    "教育": ["教育", "學校", "師資", "課綱", "校園", "幼兒園", "營養午餐"],
    "經濟": ["經濟", "產業", "就業", "薪資", "招商", "觀光", "中小企業", "創業"],
    "治安": ["治安", "警察", "詐騙", "犯罪", "消防", "救護"],
    "醫療": ["醫療", "醫院", "健保", "疫苗", "公衛"],
}


def classify(text: str) -> dict[str, Any]:
    text = text or ""
    counts = {topic: sum(text.count(kw) for kw in keywords) for topic, keywords in TOPIC_KEYWORDS.items()}
    total = sum(counts.values())
    matched = {topic: count for topic, count in counts.items() if count > 0}
    if not matched:
        return {"topics": [], "topic_scores": {}}
    scores = {topic: round(count / total, 4) for topic, count in matched.items()}
    topics = sorted(scores, key=scores.get, reverse=True)
    return {"topics": topics, "topic_scores": scores}


def main() -> int:
    parser = argparse.ArgumentParser(description="Reclassify all candidate posts in-place.")
    parser.parse_args()

    rows = feed_common.read_jsonl(feed_common.CANDIDATES_JSONL)
    if not rows:
        print("classify_topics: no rows in social_candidates.jsonl; nothing to reclassify.")
        return 0

    for row in rows:
        row.update(classify(row.get("text", "")))

    with feed_common.CANDIDATES_JSONL.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    print(f"classify_topics: reclassified {len(rows)} row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
