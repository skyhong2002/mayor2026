#!/usr/bin/env python3
"""Classify why a post appeared and what communicative action it takes.

This complements topic classification.  The rules deliberately prefer
``unclear`` over unsupported claims, especially for direct responses.  Every
decision carries evidence and a confidence score so it remains auditable and
can later be replaced by a structured-output model without changing the API.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

import feed_common

EVENTS_JSON = feed_common.PROJECT_ROOT / "data" / "sources" / "events.json"
RUBRIC_VERSION = "context-v1"

TRIGGER_LABELS = {
    "self_initiated": "自主議程",
    "external_event": "外部事件驅動",
    "direct_response": "直接回應",
    "routine": "例行發布",
    "unclear": "待確認",
}

ACTION_LABELS = {
    "policy_proposal": "政策倡議",
    "position_statement": "立場表態",
    "public_information": "資訊轉達",
    "administrative_update": "行政進度",
    "clarification": "回應澄清",
    "criticism": "批評究責",
    "mobilization": "動員宣傳",
    "personal_content": "個人／日常",
    "other": "其他／待細分",
}

RESPONSE_PATTERNS = [
    r"(?:回應|針對|有關).{0,28}(?:說法|發言|批評|質疑|指控|報導|提問)",
    r"(?:媒體|記者).{0,12}(?:詢問|提問)",
    r"我要(?:澄清|說明)",
]
ROUTINE_WORDS = ["行程", "直播預告", "活動預告", "早安", "晚安", "生日快樂", "節快樂", "歡迎大家", "一起來"]
ACTION_WORDS: dict[str, list[str]] = {
    "policy_proposal": ["主張", "政見", "政策", "應該", "必須", "將推動", "提出", "方案", "計畫"],
    "position_statement": ["我支持", "我反對", "我們相信", "我的立場", "不能接受", "認為"],
    "public_information": ["請注意", "提醒", "停班停課", "警戒", "避難", "開放", "專線", "最新資訊"],
    "administrative_update": ["視察", "勘災", "已完成", "處理進度", "市府團隊", "搶修", "部署", "成立應變中心"],
    "clarification": ["澄清", "說明如下", "並非事實", "回應", "事實是"],
    "criticism": ["批評", "質疑", "荒謬", "失職", "負責", "下台", "說清楚", "雙標"],
    "mobilization": ["投票", "支持", "拜票", "造勢", "競選", "加入我們", "懇請", "凍蒜"],
    "personal_content": ["我的一天", "家人", "午餐", "晚餐", "日常", "回憶", "生日"],
}


def _parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return dt.date.fromisoformat(value[:10])
        except ValueError:
            return None


def load_events() -> list[dict[str, Any]]:
    return feed_common.load_json(EVENTS_JSON, {"events": []}).get("events", [])


def match_event(text: str, posted_at: str | None, events: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[str]]:
    posted = _parse_date(posted_at)
    best: tuple[int, dict[str, Any], list[str]] | None = None
    for event in events:
        start, end = _parse_date(event.get("startAt")), _parse_date(event.get("endAt"))
        if posted and start and posted < start or posted and end and posted > end:
            continue
        hits = [word for word in event.get("keywords", []) if word in text]
        # One incidental keyword deep in a long post is not enough to say the
        # event caused the post.  Accept one hit only when it appears in the
        # opening context; otherwise require two distinct signals.
        central = len(hits) >= 2 or any(word in text[:160] for word in hits)
        if central and (best is None or len(hits) > best[0]):
            best = (len(hits), event, hits)
    return (best[1], best[2]) if best else (None, [])


def classify(post: dict[str, Any], events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    text = post.get("text") or ""
    events = load_events() if events is None else events
    event, event_hits = match_event(text, post.get("posted_at"), events)
    response_evidence = next((m.group(0) for pattern in RESPONSE_PATTERNS if (m := re.search(pattern, text))), None)

    if response_evidence:
        trigger_type, confidence, evidence = "direct_response", 0.9, response_evidence
    elif event:
        trigger_type, confidence = "external_event", min(0.95, 0.72 + 0.06 * len(event_hits))
        evidence = "、".join(event_hits[:5])
    elif any(word in text for word in ACTION_WORDS["policy_proposal"] + ACTION_WORDS["position_statement"]):
        trigger_type, confidence, evidence = "self_initiated", 0.68, "貼文主動提出政策或立場，未偵測到明確回應對象"
    elif any(word in text for word in ROUTINE_WORDS):
        trigger_type, confidence = "routine", 0.72
        evidence = next(word for word in ROUTINE_WORDS if word in text)
    else:
        trigger_type, confidence, evidence = "unclear", 0.35, "沒有足夠文字證據判斷觸發原因"

    actions = []
    action_evidence: dict[str, list[str]] = {}
    for action, words in ACTION_WORDS.items():
        hits = [word for word in words if word in text]
        if hits:
            actions.append(action)
            action_evidence[action] = hits[:5]
    if not actions:
        actions = ["personal_content"] if trigger_type == "routine" else ["other"]
        action_evidence[actions[0]] = ["規則未找到更明確的溝通行動，需人工複核"]

    targets = []
    if trigger_type == "direct_response":
        targets.append({"type": "unspecified", "name": None, "evidence": response_evidence})

    needs_review = confidence < 0.7 or trigger_type == "direct_response" or any("需人工複核" in v for values in action_evidence.values() for v in values)
    return {
        "trigger": {
            "type": trigger_type,
            "label": TRIGGER_LABELS[trigger_type],
            "eventId": event.get("id") if event else None,
            "confidence": round(confidence, 2),
            "evidence": evidence,
        },
        "actions": actions,
        "actionLabels": [ACTION_LABELS[action] for action in actions],
        "actionEvidence": action_evidence,
        "targets": targets,
        "classification": {
            "method": "rules",
            "rubricVersion": RUBRIC_VERSION,
            "needsReview": needs_review,
        },
    }


def main() -> int:
    rows = feed_common.read_jsonl(feed_common.CANDIDATES_JSONL)
    events = load_events()
    for row in rows:
        row.update(classify(row, events))
    with feed_common.CANDIDATES_JSONL.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"classify_context: classified {len(rows)} post(s) with {len(events)} curated event(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
