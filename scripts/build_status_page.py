#!/usr/bin/env python3
"""Publish collector and per-source health using Chumei-style durable telemetry."""

from __future__ import annotations

import collections
import datetime as dt
import html
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

import feed_common
import source_status

SITE_ROOT = feed_common.PROJECT_ROOT / "site"
API_DIR = SITE_ROOT / "api"
STATUS_JSON_OUT = API_DIR / "status.json"
FETCH_STATE_JSON = feed_common.PROJECT_ROOT / "state" / "social_fetch_state.json"
APIFY_LEDGER_JSON = feed_common.PROJECT_ROOT / "state" / "apify_facebook_fetcher.json"
PIPELINE_RUNTIME_JSON = API_DIR / "pipeline-runtime.json"
PUBLIC_BASE_URL = os.environ.get("MAYOR_SITE_BASE_URL", "https://mayor2026.observe.tw").rstrip("/")
RSSHUB_BASE = os.environ.get("MAYOR_RSSHUB_BASE", "https://rss.observe.tw").rstrip("/")
RECENT_ERROR_LIMIT = 20
RECENT_ERROR_DAYS = 7  # errors shown on the page
CURRENT_ERROR_WINDOW_HOURS = 24  # historical event count only
FRESH_PIPELINE_HOURS = 8  # Six-hour schedule plus a two-hour grace period

STATUS_LABELS = {
    "ok": "正常",
    "paused": "節流中",
    "degraded": "部分異常",
    "down": "停止",
    "unknown": "未知",
    "scheduled": "等待排程",
    "blocked": "冷卻／額度限制",
    "error": "抓取失敗",
    "due": "待執行",
    "overdue": "執行逾期",
    "disabled": "已停用",
    "link_only": "僅提供連結",
}


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def taipei_label(value: dt.datetime | None) -> str:
    if value is None:
        return "未記錄"
    taipei = value.astimezone(dt.timezone(dt.timedelta(hours=8)))
    return taipei.strftime("%Y-%m-%d %H:%M:%S")


def taipei_iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec="seconds")


def hours_since(value: dt.datetime | None, now: dt.datetime) -> float | None:
    if value is None:
        return None
    return max(0.0, (now - value).total_seconds() / 3600)


def max_time(values: list[dt.datetime | None]) -> dt.datetime | None:
    parsed = [value for value in values if value is not None]
    return max(parsed) if parsed else None


def format_usd(value: Any) -> str:
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def probe_url(url: str, timeout: int = 6) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mayor2026StatusBot/1.0"})
    started = dt.datetime.now(dt.timezone.utc)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "ok": 200 <= int(response.status) < 400,
                "statusCode": int(response.status),
                "elapsedMs": int((dt.datetime.now(dt.timezone.utc) - started).total_seconds() * 1000),
            }
    except urllib.error.HTTPError as exc:
        return {"ok": False, "statusCode": int(exc.code), "elapsedMs": None, "error": str(exc.reason)}
    except (TimeoutError, OSError, urllib.error.URLError) as exc:
        return {"ok": False, "statusCode": None, "elapsedMs": None, "error": str(exc)}


def apify_check() -> dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, "scripts/apify_facebook_fetcher.py", "--check"],
            cwd=feed_common.PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    if result.returncode != 0:
        return {"ok": False, "error": (result.stderr or result.stdout).strip()[:300]}
    try:
        return {"ok": True, **json.loads(result.stdout)}
    except json.JSONDecodeError:
        return {"ok": False, "error": "apify --check did not return JSON"}


def component(component_id: str, name: str, status: str, summary: str, details: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": component_id,
        "name": name,
        "status": status,
        "label": STATUS_LABELS.get(status, status),
        "summary": summary,
        "details": details or [],
    }


def annotate_errors(errors: list[dict[str, Any]], source_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    annotated = []
    for row in errors:
        source_id = str(row.get("source_id") or "")
        source = source_by_id.get(source_id, {})
        annotated.append(
            {
                "recordedAt": row.get("recorded_at"),
                "sourceId": source_id,
                "sourceName": source.get("candidate_name") and f"{source['candidate_name']}（{source_id}）" or source_id or "unknown",
                "platform": source.get("platform") or "unknown",
                "message": source_status.safe_error(row.get("message") or ""),
            }
        )
    return annotated


def build_status() -> dict[str, Any]:
    now = dt.datetime.now(dt.timezone.utc)

    candidates = feed_common.load_candidates()
    accounts = feed_common.load_accounts()
    sources_payload = feed_common.load_json(feed_common.SOCIAL_SOURCES_JSON, {"sources": []})
    sources = [s for s in sources_payload.get("sources", []) if s.get("enabled", True)]
    source_by_id = {str(s.get("id")): s for s in sources if s.get("id")}
    watch_platforms = collections.Counter(str(s.get("platform") or "unknown") for s in sources)

    # The JSONL keeps rows for removed candidates as history (append-only);
    # public metrics only count the current roster.
    roster_ids = {c["candidate_id"] for c in candidates}
    posts = [p for p in feed_common.read_jsonl(feed_common.CANDIDATES_JSONL) if p.get("candidate_id") in roster_ids]
    by_platform: dict[str, int] = {}
    for post in posts:
        by_platform[post["platform"]] = by_platform.get(post["platform"], 0) + 1
    latest_post_time = max_time([parse_time(p.get("posted_at")) for p in posts])
    latest_post_at = taipei_iso(latest_post_time) if latest_post_time else None

    # Keep incident history separate from latest per-source fetch outcomes.
    errors = feed_common.read_jsonl(feed_common.ERRORS_JSONL)

    def errors_within(hours: float) -> list[dict[str, Any]]:
        cutoff = now - dt.timedelta(hours=hours)
        kept = []
        for row in errors:
            recorded = parse_time(row.get("recorded_at"))
            if recorded is not None and recorded >= cutoff:
                kept.append(row)
        return kept

    fetch_state = source_status.load_state()
    pipeline_runtime = feed_common.load_json(PIPELINE_RUNTIME_JSON, {})
    apify = apify_check()
    snapshot = source_status.build_snapshot(
        accounts=feed_common.read_csv_rows(feed_common.ACCOUNTS_CSV), sources=sources,
        inbox=feed_common.read_jsonl(feed_common.INBOX_JSONL), errors=errors, apify=apify, now=now)
    source_rows = snapshot["sources"]
    row_by_id = {row["id"]: row for row in source_rows}
    current_errors = [
        {"sourceId": row["id"], "sourceName": row["name"], "platform": row["platform"],
         "recordedAt": row["lastErrorAt"], "message": row["lastError"]}
        for row in source_rows if row["fetchable"] and row["lastError"]
    ]
    error_platforms = collections.Counter(row["platform"] for row in current_errors)
    annotated_errors = annotate_errors(errors_within(RECENT_ERROR_DAYS * 24)[-RECENT_ERROR_LIMIT:], source_by_id)
    for event in annotated_errors:
        row = row_by_id.get(event["sourceId"], {})
        success = parse_time(row.get("lastSuccess"))
        stamp = parse_time(event.get("recordedAt"))
        event["resolved"] = bool(success and stamp and success >= stamp)
        event["inactive"] = bool(row and not row.get("fetchable"))
        event["unverified"] = bool(row and not row.get("lastAttempt"))
        if event["sourceId"] == "apify_facebook_fetcher":
            success = parse_time(apify.get("last_run_at"))
            event["resolved"] = bool(success and stamp and success >= stamp)

    components: list[dict[str, Any]] = []

    # --- 主排程與輸出 -------------------------------------------------
    pipeline_status = "ok"
    generated_at = parse_time(pipeline_runtime.get("heartbeatAt"))
    pipeline_details = [f"最近一次執行心跳：{taipei_label(generated_at)}"]
    runtime_status = pipeline_runtime.get("status")
    runtime_age = hours_since(generated_at, now)
    runtime_step = str(pipeline_runtime.get("currentStep") or "")
    if runtime_status == "running" and runtime_age is not None and runtime_age < 0.25 and runtime_step != "build status page":
        pipeline_details.insert(0, f"執行中：{runtime_step or 'pipeline'}")
    elif runtime_status == "failed" and runtime_age is not None and runtime_age < FRESH_PIPELINE_HOURS:
        pipeline_status = "degraded"
        pipeline_details.insert(0, f"最近 pipeline 失敗：{pipeline_runtime.get('currentStep') or '未記錄'}")
    elif runtime_age is None or runtime_age > FRESH_PIPELINE_HOURS:
        pipeline_status = "degraded"
        pipeline_details.append(f"公開資料超過 {FRESH_PIPELINE_HOURS} 小時未更新")
    components.append(
        component(
            "pipeline",
            "主排程與輸出",
            pipeline_status,
            "定期 pipeline 已產生公開資料快照。" if pipeline_status == "ok" else "排程或輸出時間需要檢查。",
            pipeline_details,
        )
    )

    # --- 公開 API -------------------------------------------------------
    api_status = "ok" if candidates and sources else "degraded"
    components.append(
        component(
            "public-api",
            "公開 API",
            api_status,
            f"{len(candidates)} 位候選人，{snapshot['fetchableSources']} 個可抓取來源。",
            [f"已收錄貼文：{len(posts)}", f"監看帳號：{len(accounts)}"],
        )
    )

    # --- RSSHub 服務 ------------------------------------------------------
    rsshub_probe = probe_url(RSSHUB_BASE + "/")
    components.append(
        component(
            "rsshub",
            "RSSHub 服務",
            "ok" if rsshub_probe.get("ok") else "degraded",
            f"{RSSHUB_BASE} 回應 {'正常' if rsshub_probe.get('ok') else '異常'}。",
            [
                f"HTTP：{rsshub_probe.get('statusCode') or '無回應'}",
                f"耗時：{rsshub_probe.get('elapsedMs')} ms" if rsshub_probe.get("elapsedMs") is not None else f"錯誤：{rsshub_probe.get('error', '-')}",
            ],
        )
    )

    # --- Instagram / Threads RSSHub -------------------------------------
    ig_threads_platforms = {"instagram", "threads", "x"}
    ig_threads_errors = sum(error_platforms.get(p, 0) for p in ig_threads_platforms)
    fetch_entries = fetch_state.get("sources") or {}
    last_attempts = [
        parse_time(entry.get("last_attempt_at"))
        for source_id, entry in fetch_entries.items()
        if source_by_id.get(source_id, {}).get("platform") in ig_threads_platforms
    ]
    components.append(
        component(
            "instagram-threads",
            "Instagram / Threads / X RSSHub",
            "degraded" if any(r["fetchable"] and r["platform"] in ig_threads_platforms and r["status"] in {"error", "blocked", "overdue"} for r in source_rows) else "ok",
            (
                f"{watch_platforms.get('instagram', 0)} 個 Instagram、{watch_platforms.get('threads', 0)} 個 Threads、"
                f"{watch_platforms.get('x', 0)} 個 X 來源；目前 {ig_threads_errors} 個來源尚未恢復。"
            ),
            [
                f"最新抓取時間：{taipei_label(max_time(last_attempts))}",
                "IG 依發文頻率每 12–168 小時抓取，每輪最多 6 個，較早到期者優先；401／429 會共用冷卻 24–72 小時。",
            ],
        )
    )

    # --- Facebook Apify ---------------------------------------------------
    apify_errors = error_platforms.get("facebook", 0)
    apify_status = "ok"
    apify_summary = f"{watch_platforms.get('facebook', 0)} 個 Facebook 來源。"
    apify_details: list[str] = []
    if not apify.get("ok"):
        apify_status = "degraded"
        apify_details.append(f"Apify check 失敗：{apify.get('error')}")
    elif not apify.get("has_token"):
        apify_status = "degraded"
        apify_details.append("Apify check：未偵測到 APIFY_TOKEN")
    else:
        apify_details.extend(
            [
                f"最近成功 run：{taipei_label(parse_time(apify.get('last_run_at')))}",
                f"本月已花費：{format_usd(apify.get('month_spend_usd'))} / 目標 {format_usd(apify.get('month_target_usd'))}",
                f"單次預估花費：{format_usd(apify.get('estimated_run_cost_usd'))}",
            ]
        )
        if apify.get("budget_exhausted"):
            apify_status = "blocked"
            apify_summary += " 本月預算已用完，下月自動恢復。"
        elif not apify.get("should_run"):
            apify_status = "scheduled"
            apify_summary += " 正常等待預算配速排程。"
        else:
            apify_summary += " 已到期，下次排程可執行。"
        if apify.get("interval_hours"):
            apify_details.append(f"目前目標間隔：約 {apify['interval_hours']:.1f} 小時")
        eligible = parse_time(apify.get("next_eligible_at"))
        if eligible:
            apify_details.append(f"下次可執行：{taipei_label(eligible)}")
            apify_details.append(f"預計排程：{taipei_label(source_status.scheduled_tick(max(eligible, now)))}（配速會隨剩餘預算調整）")
    if apify_errors:
        apify_status = "degraded"
        apify_summary += f" 目前 {apify_errors} 個來源尚未恢復。"
    components.append(component("facebook-apify", "Facebook Apify", apify_status, apify_summary, apify_details))

    # --- YouTube yt-dlp -----------------------------------------------------
    youtube_errors = error_platforms.get("youtube", 0)
    components.append(
        component(
            "youtube",
            "YouTube yt-dlp",
            "degraded" if youtube_errors else "ok",
            f"{watch_platforms.get('youtube', 0)} 個 YouTube 來源；目前 {youtube_errors} 個來源尚未恢復。",
            [f"已收錄影片：{by_platform.get('youtube', 0)}"],
        )
    )

    # --- 候選人官網 -----------------------------------------------------
    websites = [r for r in source_rows if r["active"] and r["platform"] == "website"]
    website_fetchable = [r for r in websites if r["fetchable"]]
    website_problems = [r for r in website_fetchable if r["status"] in {"error", "blocked", "overdue"}]
    components.append(component(
        "official-site", "候選人官網", "degraded" if website_problems else "ok",
        f"{len(website_fetchable)} 個文章來源、{len(websites) - len(website_fetchable)} 個僅連結；已收錄 {by_platform.get('website', 0)} 篇。",
        [f"{r['name']}：{r['reason']}" for r in websites if not r["fetchable"]]))

    active_rows = [r for r in source_rows if r["fetchable"]]
    quiet = [r for r in active_rows if r["contentStatus"] == "quiet"]
    overdue = [r for r in active_rows if r["status"] == "overdue"]
    blocked = [r for r in active_rows if r["status"] == "blocked"]
    components.append(component(
        "source-health", "來源抓取健康",
        "degraded" if current_errors or overdue or blocked else "ok",
        f"{len(active_rows)} 個可抓取來源；{len(current_errors)} 個未恢復錯誤、{len(overdue)} 個排程逾期、{len(blocked)} 個受冷卻／額度限制。",
        [f"{len(quiet)} 個來源久未發文；內容時間與抓取是否成功分開判斷，不因沉寂自動停用。",
         "逐來源抓取紀錄與停用資訊可在 Status JSON 查閱。", *[
             f"久未發文：{r['name']}（{r['id']}），最新內容 {(r['latestPostAt'] or '')[:10]}" for r in quiet]]))

    degraded = [c for c in components if c["status"] in {"down", "degraded", "blocked"}]
    paused = [c for c in components if c["status"] == "scheduled"]
    if degraded:
        overall_status = "degraded"
        overall_summary = f"核心 pipeline 有產出；需要注意：{'、'.join(c['name'] for c in degraded)}。"
    else:
        overall_status = "ok"
        overall_summary = "核心資料抓取與公開 API 正常。"
    if paused:
        overall_summary += f" {'、'.join(c['name'] for c in paused)} 正常等待下次排程。"

    platform_rows = []
    for platform, count in sorted(watch_platforms.items()):
        error_count = error_platforms.get(platform, 0)
        members = [r for r in source_rows if r["platform"] == platform and r["fetchable"]]
        health = "degraded" if any(r["status"] in {"error", "blocked", "overdue"} for r in members) else "ok"
        platform_rows.append(
            {"platform": platform, "sources": len(members), "currentErrors": error_count, "status": health}
        )

    return {
        **snapshot,
        "version": 2,
        "generatedAt": taipei_iso(now),
        "site": PUBLIC_BASE_URL,
        "overall": {"status": overall_status, "label": STATUS_LABELS[overall_status], "summary": overall_summary},
        "metrics": {
            "candidates": len(candidates),
            "watchAccounts": len(accounts),
            "totalPosts": len(posts),
            "postsByPlatform": by_platform,
            "latestPostAt": latest_post_at or None,
            "currentErrors": len(current_errors),
            "fetchableSources": snapshot["fetchableSources"],
            "errors24h": len(errors_within(CURRENT_ERROR_WINDOW_HOURS)),
        },
        "watchSources": {"platforms": dict(watch_platforms), "platformRows": platform_rows},
        "components": components,
        "recentErrors": annotated_errors,
    }


def html_escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render_error_list(errors: list[dict[str, Any]]) -> str:
    """Recent-error list HTML, shared with the /status/ page renderer."""
    from render import status as status_page

    return status_page.error_list(errors)


def main() -> int:
    status = build_status()
    feed_common.save_json_atomic(STATUS_JSON_OUT, status)
    # site/status/index.html is rendered by generate_site_pages.py (scripts/render/status.py).
    print(
        f"build_status_page: overall={status['overall']['status']}, "
        f"{len(status['components'])} component(s), {len(status['recentErrors'])} recent error(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
