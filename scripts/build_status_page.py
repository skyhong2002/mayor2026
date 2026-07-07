#!/usr/bin/env python3
"""Build the public ingestion status page and JSON snapshot.

Ported from Harmonica-in-Taiwan's build_status_page.py: rather than shipping
a client-rendered shell, this renders per-collector health cards (pipeline,
public API, RSSHub, Instagram/Threads, Facebook Apify, YouTube, official
sites) directly to HTML, alongside the same data as api/status.json for
anyone curl-ing it. Adapted to this project's simpler mechanics — a single
rsshub_fetcher covering both Instagram and Threads, a global (not
per-source) Apify budget ledger, and no launchd/local-RSSHub deployment yet
(the fetch machine setup is still pending), so those checks are omitted
rather than faked.
"""

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
FRESH_PIPELINE_HOURS = 4

STATUS_LABELS = {
    "ok": "正常",
    "paused": "節流中",
    "degraded": "部分異常",
    "down": "停止",
    "unknown": "未知",
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
    for row in errors[-RECENT_ERROR_LIMIT:]:
        source_id = str(row.get("source_id") or "")
        source = source_by_id.get(source_id, {})
        annotated.append(
            {
                "recordedAt": row.get("recorded_at"),
                "sourceId": source_id,
                "sourceName": source.get("candidate_name") and f"{source['candidate_name']}（{source_id}）" or source_id or "unknown",
                "platform": source.get("platform") or "unknown",
                "message": row.get("message") or "",
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

    posts = feed_common.read_jsonl(feed_common.CANDIDATES_JSONL)
    by_platform: dict[str, int] = {}
    for post in posts:
        by_platform[post["platform"]] = by_platform.get(post["platform"], 0) + 1
    latest_post_at = max((p.get("posted_at") or "" for p in posts), default="")

    errors = feed_common.read_jsonl(feed_common.ERRORS_JSONL)
    annotated_errors = annotate_errors(errors, source_by_id)
    error_platforms = collections.Counter(row["platform"] for row in annotated_errors)

    fetch_state = feed_common.load_json(FETCH_STATE_JSON, {"sources": {}})
    pipeline_runtime = feed_common.load_json(PIPELINE_RUNTIME_JSON, {})
    apify_ledger = feed_common.load_json(APIFY_LEDGER_JSON, {})

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
            f"candidates.json 有 {len(candidates)} 位候選人，sources.json 有 {len(sources)} 個監看帳號。",
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
    ig_threads_platforms = {"instagram", "threads"}
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
            "Instagram / Threads RSSHub",
            "degraded" if ig_threads_errors else "ok",
            (
                f"{watch_platforms.get('instagram', 0)} 個 Instagram、{watch_platforms.get('threads', 0)} 個 "
                f"Threads 來源；最新抓取批次目前 {ig_threads_errors} 個錯誤。"
            ),
            [
                f"最新抓取時間：{taipei_label(max_time(last_attempts))}",
                "IG 節流：每來源至少間隔 12 小時抓取一次，避免消耗 RSSHub 的 IG_COOKIE 額度。",
            ],
        )
    )

    # --- Facebook Apify ---------------------------------------------------
    apify = apify_check()
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
        if not apify.get("should_run"):
            apify_status = "paused"
            apify_summary += " 目前依預算 pacing 暫停開 run。"
        else:
            apify_summary += " 目前額度足夠，下次排程會開新 run。"
        apify_details.append(f"pacing 判斷：{apify.get('reason')}")
    if apify_errors:
        apify_status = "degraded"
        apify_summary += f" 最新抓取批次有 {apify_errors} 個錯誤。"
    components.append(component("facebook-apify", "Facebook Apify", apify_status, apify_summary, apify_details))

    # --- YouTube yt-dlp -----------------------------------------------------
    youtube_errors = error_platforms.get("youtube", 0)
    components.append(
        component(
            "youtube",
            "YouTube yt-dlp",
            "degraded" if youtube_errors else "ok",
            f"{watch_platforms.get('youtube', 0)} 個 YouTube 來源；最新抓取批次目前 {youtube_errors} 個錯誤。",
            [f"已收錄影片：{by_platform.get('youtube', 0)}"],
        )
    )

    # --- 候選人官網 -----------------------------------------------------
    website_sources = watch_platforms.get("website", 0)
    official_posts = by_platform.get("website", 0)
    components.append(
        component(
            "official-site",
            "候選人官網",
            "paused" if website_sources and not official_posts else "ok",
            f"{website_sources} 個候選人官網已列入監看，目前尚未有逐站 adapter，已收錄 {official_posts} 篇。",
            ["official_site_fetcher.py 目前是骨架；每個官網需要個別撰寫解析邏輯才能抓到內容。"],
        )
    )

    degraded = [c for c in components if c["status"] in {"down", "degraded"}]
    paused = [c for c in components if c["status"] == "paused"]
    if degraded:
        overall_status = "degraded"
        overall_summary = f"核心 pipeline 有產出；需要注意：{'、'.join(c['name'] for c in degraded)}。"
    else:
        overall_status = "ok"
        overall_summary = "核心資料抓取與公開 API 正常。"
    if paused:
        overall_summary += f" {'、'.join(c['name'] for c in paused)} 目前依排程或預算節流。"

    platform_rows = []
    for platform, count in sorted(watch_platforms.items()):
        error_count = error_platforms.get(platform, 0)
        platform_rows.append(
            {"platform": platform, "sources": count, "currentErrors": error_count, "status": "degraded" if error_count else "ok"}
        )

    return {
        "version": 1,
        "generatedAt": now.isoformat(timespec="seconds"),
        "site": PUBLIC_BASE_URL,
        "overall": {"status": overall_status, "label": STATUS_LABELS[overall_status], "summary": overall_summary},
        "metrics": {
            "candidates": len(candidates),
            "watchAccounts": len(accounts),
            "totalPosts": len(posts),
            "postsByPlatform": by_platform,
            "latestPostAt": latest_post_at or None,
        },
        "watchSources": {"platforms": dict(watch_platforms), "platformRows": platform_rows},
        "components": components,
        "recentErrors": annotated_errors,
    }


def html_escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


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
        return '<div class="empty-state">近期沒有抓取錯誤。</div>'
    items = []
    for row in reversed(errors):
        items.append(
            f"""
            <article class="status-error-item">
              <div>
                <span class="feed-latest-meta">{html_escape(row.get('recordedAt'))} · {html_escape(PLATFORM_LABELS.get(row.get('platform'), row.get('platform')))}</span>
                <strong>{html_escape(row.get('sourceName'))}</strong>
              </div>
              <p>{html_escape(row.get('message'))}</p>
            </article>
            """
        )
    return "\n".join(items)


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
            <p>快照時間 {html_escape(status.get("generatedAt"))}</p>
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
            {render_metric("目前錯誤", len(status["recentErrors"]), "最新抓取批次")}
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

      <section class="band status-errors-band">
        <div class="band-inner">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Latest Errors</p>
              <h2>最新錯誤</h2>
            </div>
            <p class="data-date">最多顯示 {RECENT_ERROR_LIMIT} 筆</p>
          </div>
          <div class="status-error-list">
            {error_list}
          </div>
        </div>
      </section>
    </main>

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
