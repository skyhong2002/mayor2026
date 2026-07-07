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
    "交通": ["交通", "捷運", "公車", "道路", "停車", "塞車", "鐵路", "台鐵", "高鐵", "輕軌", "自行車", "人行道", "路平", "通勤", "機場", "航線"],
    "住宅": ["住宅", "房價", "囤房", "社會住宅", "社宅", "都更", "租屋", "租金", "危老", "居住正義", "包租代管", "公共住宅"],
    "社福": ["社福", "長照", "托育", "托嬰", "育兒", "老人", "長輩", "敬老", "身心障礙", "身障", "弱勢", "社會福利", "補助", "津貼", "銀髮", "社工", "照顧"],
    "環境": ["環境", "空污", "空氣品質", "垃圾", "淨零", "碳排", "綠地", "污染", "汙染", "氣候", "資源回收", "治水", "水質", "生態", "節能", "永續"],
    "教育": ["教育", "學校", "師資", "課綱", "校園", "幼兒園", "營養午餐", "雙語", "國小", "國中", "高中", "大學", "課後", "教師", "學費"],
    "經濟": ["經濟", "產業", "就業", "薪資", "招商", "中小企業", "創業", "攤商", "商圈", "物價", "投資", "科技", "半導體", "AI", "青創"],
    "治安": ["治安", "警察", "員警", "詐騙", "詐欺", "犯罪", "消防", "救護", "毒品", "幫派", "販毒"],
    "醫療": ["醫療", "醫院", "健保", "疫苗", "公衛", "護理", "診所", "醫師", "心理健康", "防疫", "急診"],
    "競選": ["競選", "選舉", "參選", "造勢", "後援會", "拜票", "掃街", "投票", "民調", "提名", "連任", "競總", "選戰", "站台", "助選", "参選", "主視覺", "凍蒜", "催票", "參香", "車掃"],
    "體育": ["棒球", "籃球", "足球", "羽球", "排球", "桌球", "運動", "選手", "球隊", "球場", "賽事", "奧運", "世大運", "全運會", "馬拉松", "健身", "電競", "冠軍"],
    "文化觀光": ["文化", "藝術", "音樂", "展覽", "表演", "節慶", "燈會", "觀光", "旅遊", "美食", "廟會", "古蹟", "歷史", "電影", "演唱會", "市集", "藝文", "節日", "耶誕", "跨年", "動漫"],
    "兩岸外交": ["中共", "兩岸", "統戰", "國防", "外交", "邦交", "台海", "主權", "國安", "共軍", "認知作戰", "飛彈"],
    "防災": ["颱風", "地震", "豪雨", "鋒面", "淹水", "災害", "防災", "停班停課", "大雨", "警戒", "土石流", "強降雨", "災情"],
    "議會監督": ["質詢", "預算", "議會", "法案", "修法", "委員會", "公聽會", "審查", "立法院", "監督", "議事", "覆議", "彈劾", "罷免"],
}

# Posts that match nothing (daily-life snippets, behind-the-scenes clips,
# greetings...) still get one bucket so every post lands somewhere.
FALLBACK_TOPIC = "生活"

# ASCII slugs for per-topic page URLs (/spectrum/<slug>/).
TOPIC_SLUGS = {
    "交通": "transport",
    "住宅": "housing",
    "社福": "welfare",
    "環境": "environment",
    "教育": "education",
    "經濟": "economy",
    "治安": "safety",
    "醫療": "health",
    "競選": "campaign",
    "體育": "sports",
    "文化觀光": "culture",
    "兩岸外交": "cross-strait",
    "防災": "disaster",
    "議會監督": "oversight",
    "生活": "life",
}


def classify(text: str) -> dict[str, Any]:
    text = text or ""
    counts = {topic: sum(text.count(kw) for kw in keywords) for topic, keywords in TOPIC_KEYWORDS.items()}
    total = sum(counts.values())
    matched = {topic: count for topic, count in counts.items() if count > 0}
    if not matched:
        return {"topics": [FALLBACK_TOPIC], "topic_scores": {FALLBACK_TOPIC: 1.0}}
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
