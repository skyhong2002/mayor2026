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
import generate_site_pages

SITE_ROOT = feed_common.PROJECT_ROOT / "site"
API_DIR = SITE_ROOT / "api"
STATUS_JSON_OUT = API_DIR / "status.json"
STATUS_PAGE_OUT = SITE_ROOT / "status" / "index.html"
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
         "每個來源的最近成功、下次排程、停用設定及既有查證紀錄見下方明細。", *[
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


def render_badge(status: str, label: str | None = None) -> str:
    return f'<span class="status-badge status-{html_escape(status)}">{html_escape(label or STATUS_LABELS.get(status, status))}</span>'


def render_metric(label: str, value: Any, note: str = "") -> str:
    return f"""
      <article class="status-metric-card">
        <span>{html_escape(label)}</span>
        <strong>{html_escape(value)}</strong>
        <p>{html_escape(note)}</p>
      </article>
    """


def render_component_card(item: dict[str, Any]) -> str:
    details = "".join(f"<li>{html_escape(detail)}</li>" for detail in item.get("details", []))
    details_html = f'<ul class="status-detail-list">{details}</ul>' if details else ""
    return f"""
      <article class="status-component-card status-card-{html_escape(item.get('status'))}">
        <div class="status-component-head">
          <h2>{html_escape(item.get('name'))}</h2>
          {render_badge(str(item.get('status')), str(item.get('label')))}
        </div>
        <p>{html_escape(item.get('summary'))}</p>
        {details_html}
      </article>
    """


PLATFORM_LABELS = {
    "website": "官網",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "threads": "Threads",
    "youtube": "YouTube",
    "x": "X",
    "podcast": "Podcast",
    "line_oa": "LINE 官方帳號",
    "line_openchat": "LINE 社群",
    "tiktok": "TikTok",
}


def render_platform_rows(rows: list[dict[str, Any]]) -> str:
    rendered = []
    for row in rows:
        status = str(row.get("status") or "unknown")
        rendered.append(
            f"""
            <tr>
              <th scope="row">{html_escape(PLATFORM_LABELS.get(row.get('platform'), row.get('platform')))}</th>
              <td>{html_escape(row.get('sources'))}</td>
              <td>{html_escape(row.get('currentErrors'))}</td>
              <td>{render_badge(status)}</td>
            </tr>
            """
        )
    return "\n".join(rendered)


def render_error_list(errors: list[dict[str, Any]]) -> str:
    if not errors:
        return f'<div class="empty-state">近 {RECENT_ERROR_DAYS} 天沒有抓取錯誤。</div>'
    items = []
    for row in reversed(errors):
        if row.get("resolved"):
            badge = render_badge("ok", "已恢復")
        elif row.get("inactive"):
            badge = render_badge("disabled", "來源已停用／僅連結")
        elif row.get("unverified"):
            badge = render_badge("unknown", "歷史紀錄，恢復時間未記錄")
        else:
            badge = render_badge("error", "尚未恢復")
        items.append(
            f"""
            <article class="status-error-item">
              <div>
                <span class="feed-latest-meta">{html_escape(row.get('recordedAt'))} · {html_escape(PLATFORM_LABELS.get(row.get('platform'), row.get('platform')))}</span>
                <strong>{html_escape(row.get('sourceName'))}</strong>
              </div>
              {badge}
              <p>{html_escape(row.get('message'))}</p>
            </article>
            """
        )
    return "\n".join(items)


def render_source_table(rows: list[dict]) -> str:
    rendered = []
    for row in rows:
        search = f"{row['name']} {row['id']} {PLATFORM_LABELS.get(row['platform'], row['platform'])}"
        group = "active" if row["fetchable"] else "inactive"
        attention = "true" if row["status"] in {"error", "overdue", "blocked"} else "false"
        content = taipei_label(parse_time(row.get("latestPostAt")))
        if row["contentStatus"] == "quiet":
            content += "（久未發文）"
        success = taipei_label(parse_time(row.get("lastSuccess")))
        if row.get("successEvidence") == "inbox":
            success += "（歷史收錄）"
        detail = row.get("reason") or row.get("lastError") or ""
        if row.get("consecutiveFailures"):
            detail += f"（連續失敗 {row['consecutiveFailures']} 次）"
        if row["status"] == "disabled":
            detail += "；" + row.get("evidence", "")
        interval = row.get("targetIntervalHours")
        schedule = taipei_label(parse_time(row.get("nextScheduledAt"))) if row["fetchable"] else "不排程"
        if interval:
            schedule += f"（約 {interval:g} 小時）"
        rendered.append(f"""<tr data-source-group="{group}" data-source-attention="{attention}" data-source-search="{html_escape(search)}">
          <th scope="row"><a href="{html_escape(row['url'])}">{html_escape(row['name'])}</a><small>{html_escape(row['id'])}</small><small>{html_escape(PLATFORM_LABELS.get(row['platform'], row['platform']))} · {html_escape(row['backend'])}</small></th>
          <td>{render_badge(row['status'])}<small>{html_escape(detail)}</small></td>
          <td>{html_escape(success)}<small>最近嘗試：{html_escape(taipei_label(parse_time(row.get('lastAttempt'))))}</small><small>最近回傳：{html_escape(row.get('lastItems') if row.get('lastItems') is not None else '未記錄')} 筆</small></td>
          <td>{html_escape(schedule)}</td><td>{html_escape(content)}</td></tr>""")
    return '<div class="status-table-wrap"><table class="status-table status-source-table"><thead><tr><th>來源</th><th>狀態／原因</th><th>最近成功</th><th>下次預計排程</th><th>最新內容</th></tr></thead><tbody>' + "".join(rendered) + '</tbody></table></div>'


def render_status_page(status: dict[str, Any], *, asset_version: str) -> str:
    overall = status["overall"]
    metrics = status["metrics"]
    component_cards = "\n".join(render_component_card(item) for item in status["components"])
    platform_rows = render_platform_rows(status["watchSources"]["platformRows"])
    error_list = render_error_list(status["recentErrors"])
    return f"""<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>資料管線狀態｜2026 市長官方來源觀測站</title>
    <meta name="robots" content="noindex,follow">
    <link rel="icon" href="../assets/favicon.svg?v={asset_version}" type="image/svg+xml">
    <link rel="stylesheet" href="../assets/styles.css?v={asset_version}">
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="../">
        <img class="brand-logo-img" src="../assets/logo.svg?v={asset_version}" alt="">
        <span>2026 市長官方來源觀測站</span>
      </a>
      <nav class="site-nav">
        <a href="../">六都總覽</a>
        <a href="../policy-match/">議題選擇器</a>
        <a href="../spectrum/">議題光譜</a>
        <a href="../source/">公開來源</a>
      </nav>
    </header>

    <main>
      <section class="feed-page-hero status-hero">
        <div class="band-inner split-layout">
          <div>
            <p class="section-kicker">Status</p>
            <h1>資料管線狀態</h1>
          </div>
          <div class="feed-page-summary status-summary-panel">
            <div class="status-summary-line">
              {render_badge(overall["status"], overall["label"])}
              <strong>{html_escape(overall["summary"])}</strong>
            </div>
            <p>快照時間 <time id="status-generated-at" datetime="{html_escape(status.get("generatedAt"))}">{html_escape(status.get("generatedAt"))}</time></p>
            <p id="status-stale-warning" hidden>此快照已超過 8 小時未更新，請檢查排程或發布狀態。</p>
            <div class="feed-links">
              <a href="../api/status.json">Status JSON</a>
              <a href="../feeds/">RSS</a>
            </div>
          </div>
        </div>
      </section>

      <section class="band status-overview-band">
        <div class="band-inner">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Metrics</p>
              <h2>收錄統計</h2>
            </div>
          </div>
          <div class="status-metric-grid">
            {render_metric("監看候選人", metrics.get("candidates"), "candidates.json")}
            {render_metric("監看帳號", metrics.get("watchAccounts"), "sources.json")}
            {render_metric("已收錄貼文", metrics.get("totalPosts"), "social_candidates.jsonl")}
            {render_metric("目前錯誤", metrics.get("currentErrors"), "仍未恢復的來源，成功後解除")}
          </div>
        </div>
      </section>

      <section class="band status-component-band">
        <div class="band-inner">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Collectors</p>
              <h2>元件狀態</h2>
            </div>
          </div>
          <div class="status-component-grid">
            {component_cards}
          </div>
        </div>
      </section>

      <section class="band status-platform-band">
        <div class="band-inner split-layout">
          <div>
            <p class="section-kicker">Platforms</p>
            <h2>平台來源</h2>
          </div>
          <div class="status-table-wrap">
            <table class="status-table">
              <thead>
                <tr>
                  <th scope="col">平台</th>
                  <th scope="col">來源數</th>
                  <th scope="col">目前錯誤</th>
                  <th scope="col">狀態</th>
                </tr>
              </thead>
              <tbody>
                {platform_rows}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section class="band status-sources-band">
        <div class="band-inner">
          <div class="section-heading"><div><p class="section-kicker">Sources</p><h2>逐來源抓取狀態</h2></div></div>
          <p>時間為臺灣時間。每 6 小時執行排程；下次時間為預估，仍受冷卻、批次容量與預算影響。歷史內容時間不代表最近抓取時間。</p>
          <div class="status-source-controls">
            <label>搜尋來源 <input id="source-search" type="search" placeholder="候選人、平台或帳號"></label>
            <label>顯示 <select id="source-filter"><option value="active">可抓取來源</option><option value="attention">需要注意</option><option value="inactive">停用／僅連結</option><option value="all">全部來源</option></select></label>
            <span id="source-visible-count" aria-live="polite"></span>
          </div>
          {render_source_table(status.get("sources", []))}
        </div>
      </section>
      <section class="band status-errors-band">
        <div class="band-inner">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Latest Errors</p>
              <h2>近期錯誤紀錄</h2>
            </div>
            <p class="data-date">近 {RECENT_ERROR_DAYS} 天，最多顯示 {RECENT_ERROR_LIMIT} 筆</p>
          </div>
          <div class="status-error-list">
            {error_list}
          </div>
        </div>
      </section>
    </main>
    <script src="../assets/status.js?v={asset_version}" defer></script>

    <footer class="site-footer">
      <div class="site-footer-inner">
        <div class="footer-brand">
          <span class="footer-title">2026 市長官方來源觀測站</span>
          <p>以公開資料為主的六都市長候選人官方發文索引。非官方認證資料庫。</p>
        </div>
        <div class="footer-links">
          <a href="../status/">狀態</a>
          <a href="../feeds/">RSS</a>
          <a href="https://github.com/skyhong2002/mayor2026">GitHub</a>
          <a href="https://github.com/skyhong2002/mayor2026/issues/new/choose">資料回報</a>
        </div>
        <p class="footer-meta">資料來源為候選人公開帳號；貼文著作權屬原作者。MIT License.</p>
      </div>
    </footer>
  </body>
</html>
"""


def main() -> int:
    status = build_status()
    feed_common.save_json_atomic(STATUS_JSON_OUT, status)
    STATUS_PAGE_OUT.parent.mkdir(parents=True, exist_ok=True)
    version = generate_site_pages.asset_version()
    STATUS_PAGE_OUT.write_text(render_status_page(status, asset_version=version), encoding="utf-8")
    print(
        f"build_status_page: overall={status['overall']['status']}, "
        f"{len(status['components'])} component(s), {len(status['recentErrors'])} recent error(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
