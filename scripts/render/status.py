"""`/status/` — 資料來源狀態（DESIGN.md §7.6）.

Pure presentation of the published snapshot in ``site/api/status.json`` (v2,
written by scripts/build_status_page.py) plus ``site/api/pipeline-runtime.json``.
Nothing here recomputes health: every state shown comes from the snapshot
(docs/ingestion-health.md — never turn things green in the renderer).

Sections: headline · 系統總覽 · 抓取方式 · 元件狀態 · 平台來源 ＋ 近 7 天錯誤紀錄 ·
來源表（前端篩選／搜尋／排序由 assets/pages/status.js 增強）.
"""

from __future__ import annotations

import shutil
import statistics
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from . import shell as S

ROUTE = "/status/"
OUT_DIR = S.SITE_ROOT / "status"

# Mirrors build_status_page.RECENT_ERROR_DAYS / RECENT_ERROR_LIMIT (not imported:
# that module pulls in the fetch stack and probes the network on import paths).
RECENT_ERROR_DAYS = 7
RECENT_ERROR_LIMIT = 20

STATUS_LABELS = {
    "ok": "正常", "paused": "節流中", "degraded": "部分異常", "down": "停止", "unknown": "未知",
    "scheduled": "等待排程", "blocked": "冷卻／額度限制", "error": "抓取失敗", "due": "待執行",
    "overdue": "執行逾期", "disabled": "已停用", "link_only": "僅提供連結",
}

# snapshot status → .badge-status[data-state]
BADGE_STATE = {
    "ok": "ok", "scheduled": "paused", "paused": "paused", "degraded": "warn", "blocked": "warn",
    "overdue": "warn", "due": "pending", "down": "error", "error": "error", "unknown": "pending",
    "disabled": "paused", "link_only": "paused",
}

# Source-table filter groups (chip label, statuses). Order = chip order.
FILTER_GROUPS = [
    ("ok", "正常", ("ok", "scheduled")),
    ("due", "待執行", ("due",)),
    ("overdue", "逾期", ("overdue",)),
    ("blocked", "冷卻", ("blocked",)),
    ("error", "錯誤", ("error",)),
    ("disabled", "已停用", ("disabled",)),
    ("link_only", "僅連結", ("link_only",)),
]
GROUP_OF = {status: key for key, _, statuses in FILTER_GROUPS for status in statuses}
# Default sort: problems first.
STATUS_RANK = {"error": 0, "blocked": 1, "overdue": 2, "due": 3, "ok": 4, "scheduled": 4, "link_only": 5, "disabled": 6}

PLATFORM_ORDER = ["facebook", "instagram", "threads", "x", "youtube", "website", "podcast",
                  "line_oa", "line_openchat", "tiktok"]

# backend (source_status.BACKENDS) → (card title, method chip)
METHOD_COPY = {
    "Apify": ("Facebook 粉專貼文", "Apify・預算配速"),
    "RSSHub Instagram": ("Instagram 貼文", "RSSHub・依發文頻率"),
    "RSSHub Threads": ("Threads 公開貼文", "RSSHub"),
    "RSSHub X": ("X 公開貼文", "RSSHub"),
    "yt-dlp": ("YouTube 影片", "yt-dlp"),
    "官網 adapter": ("候選人官網", "網頁爬蟲"),
    "原生 RSS": ("Podcast", "原生 RSS"),
}
METHOD_ORDER = ["Apify", "RSSHub Instagram", "RSSHub Threads", "RSSHub X", "yt-dlp", "官網 adapter", "原生 RSS"]
METHOD_COMPONENT = {"Apify": "facebook-apify", "RSSHub Instagram": "instagram-threads",
                    "RSSHub Threads": "instagram-threads", "RSSHub X": "instagram-threads",
                    "yt-dlp": "youtube", "官網 adapter": "official-site"}
CLASSIFY_STEP = "classify post topics and posting intent with AI"

EVIDENCE_LABELS = {"fetch": "抓取紀錄", "inbox": "歷史收錄", "none": "無紀錄"}
EVIDENCE_HINTS = {
    "fetch": "由抓取器寫入的成功紀錄",
    "inbox": "舊版收錄匣中的收錄時間；不代表已知的排程執行時間",
    "none": "尚無成功抓取紀錄",
}
CONTENT_LABELS = {"available": "", "quiet": "久未發文", "empty": "尚無內容紀錄"}

STEP_LABELS = {
    "restore pipeline data": "還原 pipeline 資料",
    "build social sources": "建立來源清單",
    "fetch rsshub": "抓取 RSSHub",
    "fetch youtube": "抓取 YouTube",
    "fetch facebook apify": "抓取 Facebook（Apify）",
    "fetch official sites": "抓取候選人官網",
    "watch social feeds": "監看社群來源",
    "cache media": "快取圖片",
    CLASSIFY_STEP: "AI 議題與動機分類",
    "build public data": "建立公開資料",
    "build spectrum": "建立議題光譜",
    "build qualitative comparisons": "建立議題比較",
    "generate rss feeds": "產生 RSS",
    "build status page": "建立狀態資料",
    "generate site pages": "產生網站頁面",
    "generate SEO pages": "產生 sitemap／robots",
    "check source coverage": "檢查來源覆蓋",
    "validate public outputs": "驗證公開輸出",
    "publish pipeline data": "發布 pipeline 資料",
    "publish local snapshot": "發布本機快照",
    "publish github pages": "發布 GitHub Pages",
}
STEP_STATE = {"ok": ("ok", "完成"), "running": ("pending", "執行中"), "pending": ("paused", "等待"),
              "deferred": ("paused", "延後"), "skipped": ("paused", "略過"),
              "optional_failed": ("warn", "選用步驟失敗"), "failed": ("error", "失敗")}
RUNTIME_STATE = {"running": ("pending", "執行中"), "ok": ("ok", "完成"), "failed": ("error", "失敗")}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _badge(status: Any, label: Optional[str] = None) -> str:
    status = str(status or "unknown")
    return S.render_badge(BADGE_STATE.get(status, "pending"), label or STATUS_LABELS.get(status, status))


def _time(iso: Any, rel: bool = True, with_year: Optional[bool] = None) -> str:
    """<time> with absolute GMT+8 text; ``rel`` lets shell.js rewrite it as relative."""
    if not S.parse_ts(iso):
        return '<span class="muted">未記錄</span>'
    text = S.fmt_time_tpe(iso, with_year)
    rel_attr = " data-rel" if rel else ""
    return f'<time datetime="{S.esc(iso)}"{rel_attr} title="{S.esc(S.fmt_time_tpe(iso, True))}（GMT+8）">{S.esc(text)}</time>'


def _num(value: Any) -> str:
    return f"{value:,}" if isinstance(value, int) else S.esc(value if value is not None else "–")


def _hours(value: Any) -> str:
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return ""
    if hours >= 48 and hours % 24 < 0.5:
        return f"{hours / 24:.0f} 天"
    return f"{hours:.0f} 小時" if abs(hours - round(hours)) < 0.15 else f"{hours:.1f} 小時"


def _handle(row: Dict[str, Any], account: Optional[Dict[str, Any]]) -> str:
    if account:
        handle = (account.get("handle") or "").strip()
        if handle and handle.lower() != "unknown":
            return handle if account.get("platform") in ("website", "podcast") or handle.startswith("@") else "@" + handle
        if account.get("displayName"):
            return str(account["displayName"])
    url = str(row.get("url") or "")
    parsed = urlparse(url)
    host = (parsed.netloc or "").replace("www.", "")
    path = parsed.path.strip("/")
    if row.get("platform") in ("website", "podcast", "line_oa", "line_openchat") or not path:
        return host or url or row.get("id") or ""
    return path.split("/")[-1] or host


def _section(sid: str, title: str, inner: str, note: str = "") -> str:
    note_html = f'<p class="section-note">{note}</p>' if note else ""
    return (f'<section class="section status-section" id="{sid}" aria-labelledby="{sid}-title">'
            f'<div class="section-head"><h2 id="{sid}-title">{S.esc(title)}</h2>{note_html}</div>{inner}</section>')


# ---------------------------------------------------------------------------
# headline + overview
# ---------------------------------------------------------------------------

def _headline(status: Dict[str, Any]) -> str:
    overall = status.get("overall") or {}
    state = str(overall.get("status") or "unknown")
    generated = status.get("generatedAt")
    return (
        f'<div class="status-hero card" data-state="{S.esc(BADGE_STATE.get(state, "pending"))}">'
        f'<div class="status-hero-main">{_badge(state, overall.get("label"))}'
        f'<p class="status-hero-summary">{S.esc(overall.get("summary") or "尚無資料")}</p></div>'
        f'<p class="status-hero-time">快照時間 <time datetime="{S.esc(generated)}">'
        f'{S.esc(S.fmt_time_tpe(generated, True) or "未記錄")}</time>（GMT+8）'
        f'・主排程每 {S.esc(status.get("pipelineIntervalHours") or 6)} 小時（臺灣時間 00、06、12、18 時）</p>'
        "</div>"
        f'<div class="notice" data-tone="info">{S.icon("about")}<p>本頁是發布當下的靜態快照，不是即時監控。'
        "外部監控請讀取 <a href=\"/api/status.json\">/api/status.json</a> 的 <code>generatedAt</code>，"
        "不能只依快照內的 <code>overall</code> 判斷目前健康。主排程逾期門檻為 8 小時（6 小時週期加 2 小時寬限）。</p></div>"
    )


def _overview(status: Dict[str, Any]) -> str:
    m = status.get("metrics") or {}
    rows = status.get("sources") or []
    counts = status.get("sourceCounts") or {}
    overdue = sum(1 for r in rows if r.get("status") == "overdue")
    fetchable = m.get("fetchableSources", status.get("fetchableSources"))
    by_platform = m.get("postsByPlatform") or {}
    top = sorted(by_platform.items(), key=lambda kv: -kv[1])[:3]
    tiles = [
        (m.get("candidates"), "監看候選人", "六都市長候選人"),
        (m.get("watchAccounts"), "監看帳號", "watchlist 啟用中的公開帳號"),
        (m.get("totalPosts"), "已收錄貼文", "、".join(f"{S.PLATFORM_LABELS.get(p, p)} {n:,}" for p, n in top) or "尚無資料"),
        (fetchable, "可抓取來源", f"另 {counts.get('link_only', 0)} 個僅連結、{counts.get('disabled', 0)} 個停用"),
        (m.get("currentErrors"), "目前錯誤", "仍未恢復的來源，成功後解除"),
        (overdue, "逾期來源", "超過預計排程 2 小時仍未執行"),
        (m.get("errors24h"), "近 24 小時錯誤", "錯誤事件數（含已恢復）"),
    ]
    tone = {"目前錯誤": "error", "逾期來源": "warn", "近 24 小時錯誤": "error"}
    out = []
    for value, label, hint in tiles:
        flag = tone.get(label) if isinstance(value, int) and value > 0 else None
        attr = f' data-tone="{flag}"' if flag else ""
        out.append(f'<div class="stat-tile"{attr}><span class="stat-value">{_num(value)}</span>'
                   f'<span class="stat-label">{S.esc(label)}</span><span class="stat-hint">{S.esc(hint)}</span></div>')
    latest = m.get("latestPostAt")
    lede = (f'最新收錄內容 {_time(latest)}。可抓取來源 {_num(fetchable)} 個：'
            f'{counts.get("due", 0)} 個待執行、{overdue} 個執行逾期、{counts.get("blocked", 0)} 個冷卻／額度限制、'
            f'{counts.get("error", 0)} 個抓取失敗。')
    return _section("overview", "系統總覽",
                    f'<p class="status-lede">{lede}</p><div class="status-tiles">{"".join(out)}</div>',
                    "數字取自本快照")


# ---------------------------------------------------------------------------
# 抓取方式
# ---------------------------------------------------------------------------

def _method_card(method: Dict[str, Any], members: List[Dict[str, Any]], comp: Optional[Dict[str, Any]]) -> str:
    backend = str(method.get("backend") or "")
    title, chip = METHOD_COPY.get(backend, (backend, backend))
    counts = {key: 0 for key, _, _ in FILTER_GROUPS}
    for r in members:
        counts[GROUP_OF.get(str(r.get("status")), "ok")] = counts.get(GROUP_OF.get(str(r.get("status")), "ok"), 0) + 1
    errors = int(method.get("errors") or 0)
    blocked = int(method.get("blocked") or 0)
    if errors:
        state, label = "error", f"{errors} 個錯誤"
    elif blocked:
        state, label = "warn", "冷卻／額度限制"
    elif counts.get("overdue"):
        state, label = "warn", "部分逾期"
    elif counts.get("due"):
        state, label = "pending", "待執行"
    else:
        state, label = "ok", "正常"
    intervals = [float(r["targetIntervalHours"]) for r in members if r.get("targetIntervalHours")]
    target = ""
    if intervals:
        lo, hi, med = min(intervals), max(intervals), statistics.median(intervals)
        target = f"目標每 {_hours(med)}" if hi - lo < 1 else f"目標每 {_hours(lo)}～{_hours(hi)}（中位 {_hours(med)}）"
    successes = [r.get("lastSuccess") for r in members if S.parse_ts(r.get("lastSuccess"))]
    last_success = max(successes, key=S.epoch) if successes else None
    parts = [("正常", counts.get("ok", 0), False), ("待執行", counts.get("due", 0), False),
             ("逾期", counts.get("overdue", 0), True), ("冷卻", blocked, True), ("錯誤", errors, True)]
    stats = "".join(f'<span{" data-hot" if hot and n else ""}>{k} <b>{n}</b></span>' for k, n, hot in parts)
    extra = ""
    if backend == "Apify" and comp:
        budget = [d for d in comp.get("details") or [] if d.startswith(("本月已花費", "目前目標間隔"))]
        if budget:
            extra = f'<p class="method-extra">{S.esc("・".join(budget))}</p>'
    return (
        f'<article class="card method-card" data-state="{state}">'
        f'<div class="method-head"><h3 class="card-title">{S.esc(title)}</h3>{S.render_badge(state, label)}</div>'
        f'<span class="chip-soft method-chip">{S.esc(chip)}</span>'
        f'<p class="method-count"><span class="method-num">{_num(method.get("sources"))}</span> 個排程來源</p>'
        + (f'<p class="method-line">{S.esc(target)}</p>' if target else "")
        + f'<p class="method-stats">{stats}</p>'
        f'<p class="method-line muted">最近成功 {_time(last_success)}</p>{extra}'
        "</article>"
    )


def _classify_card(status: Dict[str, Any], runtime: Dict[str, Any]) -> str:
    step = next((s for s in runtime.get("steps") or [] if s.get("name") == CLASSIFY_STEP), None)
    total = (status.get("metrics") or {}).get("totalPosts")
    if step:
        state, label = STEP_STATE.get(str(step.get("status")), ("pending", str(step.get("status"))))
        when = step.get("finishedAt") or step.get("startedAt")
        line = f'最近一輪 {_time(when)}（{S.esc(label)}）'
    else:
        state, label = "pending", "無執行紀錄"
        line = "本次快照的 pipeline 紀錄中沒有分類步驟。"
    return (
        f'<article class="card method-card" data-state="{state}">'
        f'<div class="method-head"><h3 class="card-title">AI 分類</h3>{S.render_badge(state, label)}</div>'
        '<span class="chip-soft method-chip">議題＋發文動機</span>'
        f'<p class="method-count"><span class="method-num">{_num(total)}</span> 則已分類貼文</p>'
        '<p class="method-line">每輪 pipeline 分類新收錄貼文；延後時下輪續做。未分類貼文不公開。</p>'
        f'<p class="method-line muted">{line}</p>'
        "</article>"
    )


def _methods(status: Dict[str, Any], runtime: Dict[str, Any]) -> str:
    rows = status.get("sources") or []
    comps = {c.get("id"): c for c in status.get("components") or []}
    methods = sorted(status.get("methods") or [],
                     key=lambda m: METHOD_ORDER.index(m.get("backend")) if m.get("backend") in METHOD_ORDER else 99)
    cards = [_method_card(m, [r for r in rows if r.get("fetchable") and r.get("backend") == m.get("backend")],
                          comps.get(METHOD_COMPONENT.get(str(m.get("backend")))))
             for m in methods]
    cards.append(_classify_card(status, runtime))
    note = ("主排程每 6 小時啟動；Instagram 依帳號近期發文頻率採 12～168 小時間隔，每輪最多 6 個；"
            "Facebook 依 Apify 月預算配速。時間皆為估計，仍受批次上限與預算調整。")
    return _section("methods", "抓取方式", f'<div class="method-grid">{"".join(cards)}</div>', S.esc(note))


# ---------------------------------------------------------------------------
# 元件狀態 (+ pipeline runtime)
# ---------------------------------------------------------------------------

def _runtime_block(runtime: Dict[str, Any]) -> str:
    if not runtime:
        return '<p class="runtime-empty muted small">尚無 pipeline 執行紀錄（pipeline-runtime.json）。</p>'
    state, label = RUNTIME_STATE.get(str(runtime.get("status")), ("pending", str(runtime.get("status") or "未知")))
    step = str(runtime.get("currentStep") or "")
    facts = [
        ("執行狀態", S.render_badge(state, label)),
        ("目前步驟", S.esc(STEP_LABELS.get(step, step) or "未記錄")),
        ("最近心跳", _time(runtime.get("heartbeatAt"))),
        ("本輪開始", _time(runtime.get("startedAt"))),
    ]
    if runtime.get("message"):
        facts.append(("訊息", S.esc(runtime["message"])))
    dl = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in facts)
    steps = []
    for s in runtime.get("steps") or []:
        st, st_label = STEP_STATE.get(str(s.get("status")), ("pending", str(s.get("status"))))
        name = str(s.get("name") or "")
        start, end = S.parse_ts(s.get("startedAt")), S.parse_ts(s.get("finishedAt"))
        dur = ""
        if start and end:
            secs = (end - start).total_seconds()
            dur = f"{secs:.1f} 秒" if secs < 60 else f"{secs / 60:.1f} 分"
        steps.append(
            f'<li data-state="{st}" title="{S.esc(name)}"><span class="step-dot" aria-hidden="true"></span>'
            f'<span class="step-name">{S.esc(STEP_LABELS.get(name, name))}</span>'
            f'<span class="step-meta">{S.esc(st_label)}{"・" + dur if dur else ""}</span></li>'
        )
    steps_html = (f'<details class="runtime-steps"><summary>步驟紀錄（{len(steps)}）</summary>'
                  f'<ol>{"".join(steps)}</ol></details>') if steps else ""
    return (f'<div class="runtime"><p class="runtime-title">產生本快照時的 pipeline 執行紀錄</p>'
            f'<dl class="runtime-facts">{dl}</dl>{steps_html}</div>')


def _components(status: Dict[str, Any], runtime: Dict[str, Any]) -> str:
    cards = []
    for item in status.get("components") or []:
        details = "".join(f"<li>{S.esc(d)}</li>" for d in item.get("details") or [])
        details_html = f'<ul class="comp-details">{details}</ul>' if details else ""
        extra = _runtime_block(runtime) if item.get("id") == "pipeline" else ""
        state = BADGE_STATE.get(str(item.get("status")), "pending")
        cards.append(
            f'<article class="card comp-card" id="comp-{S.esc(item.get("id"))}" data-state="{state}">'
            f'<div class="comp-head"><h3 class="card-title">{S.esc(item.get("name"))}</h3>'
            f'{_badge(item.get("status"), item.get("label"))}</div>'
            f'<p class="comp-summary">{S.esc(item.get("summary"))}</p>{details_html}{extra}</article>'
        )
    if not cards:
        return _section("components", "元件狀態", S.render_empty("尚無元件狀態資料"))
    return _section("components", "元件狀態", f'<div class="comp-grid">{"".join(cards)}</div>')


# ---------------------------------------------------------------------------
# 平台來源 + 錯誤紀錄
# ---------------------------------------------------------------------------

def _platform_table(status: Dict[str, Any]) -> str:
    ws = status.get("watchSources") or {}
    posts = (status.get("metrics") or {}).get("postsByPlatform") or {}
    rows = []
    for row in ws.get("platformRows") or []:
        p = str(row.get("platform") or "")
        rows.append(
            f'<tr><th scope="row"><span class="plat-cell">{S.icon(p)}{S.esc(S.PLATFORM_LABELS.get(p, p))}</span></th>'
            f'<td class="num">{_num(row.get("sources"))}</td><td class="num">{_num(posts.get(p, 0))}</td>'
            f'<td class="num">{_num(row.get("currentErrors"))}</td><td>{_badge(row.get("status"))}</td></tr>'
        )
    if not rows:
        return S.render_empty("尚無平台資料")
    return ('<div class="table-wrap"><table class="table platform-table"><thead><tr>'
            '<th scope="col">平台</th><th scope="col" class="num">可抓取來源</th><th scope="col" class="num">已收錄</th>'
            '<th scope="col" class="num">目前錯誤</th><th scope="col">狀態</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def _error_marker(row: Dict[str, Any]) -> str:
    if row.get("resolved"):
        return S.render_badge("ok", "已恢復")
    if row.get("inactive"):
        return S.render_badge("paused", "來源已停用／僅連結")
    if row.get("unverified"):
        return S.render_badge("pending", "歷史紀錄，恢復時間未記錄")
    return S.render_badge("error", "尚未恢復")


def error_list(recent_errors: List[Dict[str, Any]]) -> str:
    """recentErrors (oldest first, as in status.json) → newest-first list with
    recovery markers. Also used by build_status_page.render_error_list (tests)."""
    errors = list(reversed(recent_errors or []))
    if not errors:
        return S.render_empty(f"近 {RECENT_ERROR_DAYS} 天沒有抓取錯誤", "錯誤發生時會列在這裡，並標示是否已恢復。")
    items = []
    for row in errors:
        p = str(row.get("platform") or "")
        msg = str(row.get("message") or "")
        items.append(
            f'<li class="err-item"><div class="err-head">{_time(row.get("recordedAt"))}'
            f'<span class="err-source">{S.icon(p)}{S.esc(row.get("sourceName"))}</span>{_error_marker(row)}</div>'
            f'<p class="err-msg mono" title="{S.esc(msg)}">{S.esc(msg)}</p></li>'
        )
    return f'<ol class="err-list">{"".join(items)}</ol>'


def _platform_and_errors(status: Dict[str, Any]) -> str:
    return (
        '<div class="status-split">'
        + _section("platforms", "平台來源", _platform_table(status))
        + _section("errors", f"近 {RECENT_ERROR_DAYS} 天錯誤紀錄", error_list(status.get("recentErrors") or []),
                   f"最多顯示 {RECENT_ERROR_LIMIT} 筆，新到舊")
        + "</div>"
    )


# ---------------------------------------------------------------------------
# 來源表
# ---------------------------------------------------------------------------

def _source_row(row: Dict[str, Any], data, accounts: Dict[str, Dict[str, Any]], order: int) -> str:
    sid = str(row.get("id") or "")
    status = str(row.get("status") or "unknown")
    platform = str(row.get("platform") or "")
    cid = str(row.get("candidateId") or "")
    cand = data.by_id.get(cid)
    handle = _handle(row, accounts.get(sid))
    name = S.esc(row.get("name") or cid)
    name_html = f'<a href="/source/{S.esc(cid)}/">{name}</a>' if cand else f'<span>{name}</span><span class="chip-soft src-off">已下架</span>'
    avatar = S.render_avatar(cand, "xs") if cand else ""
    url = S.safe_url(row.get("url"), internal=False)
    handle_html = (f'<a class="src-handle" href="{S.esc(url)}" target="_blank" rel="noopener" title="{S.esc(url)}">'
                   f'{S.icon(platform)}<span>{S.esc(handle)}</span></a>') if url else \
        f'<span class="src-handle">{S.icon(platform)}<span>{S.esc(handle)}</span></span>'
    ident = (f'<div class="src-ident">{avatar}<div class="src-text"><div class="src-name">{name_html}</div>'
             f'<div class="src-sub">{handle_html}<span class="src-id mono">{S.esc(sid)}</span></div></div></div>')

    reason = str(row.get("reason") or "")
    fails = int(row.get("consecutiveFailures") or 0)
    status_html = _badge(status)
    if reason:
        status_html += f'<p class="src-reason" title="{S.esc(reason)}">{S.esc(reason)}</p>'
    if fails:
        status_html += f'<p class="src-reason">連續失敗 {fails} 次</p>'

    evidence = str(row.get("successEvidence") or "none")
    items = row.get("lastItems")
    attempt = f'<div><span class="k">嘗試</span>{_time(row.get("lastAttempt"))}</div>'
    success = (f'<div><span class="k">成功</span>{_time(row.get("lastSuccess"))}'
               f'<span class="chip-soft ev" data-ev="{S.esc(evidence)}" title="{S.esc(EVIDENCE_HINTS.get(evidence, ""))}">'
               f'{S.esc(EVIDENCE_LABELS.get(evidence, evidence))}</span></div>')
    if isinstance(items, int):
        success += f'<div class="muted xs">回傳 {items} 筆</div>'

    if row.get("fetchable"):
        nxt = row.get("nextScheduledAt")
        elig = row.get("nextEligibleAt")
        nxt_html = (f'<div><span class="k">排程</span>{_time(nxt, rel=False)}</div>' if S.parse_ts(nxt)
                    else '<div class="muted">下一輪排程</div>')
        if S.parse_ts(elig):
            nxt_html += f'<div class="muted xs">可執行 {_time(elig, rel=False)}</div>'
        freq = _hours(row.get("targetIntervalHours"))
        if freq:
            nxt_html += f'<div class="muted xs">目標每 {S.esc(freq)}</div>'
    else:
        nxt_html = '<span class="muted">不排程</span>'

    content = str(row.get("contentStatus") or "")
    latest_html = _time(row.get("latestPostAt")) if S.parse_ts(row.get("latestPostAt")) else '<span class="muted">–</span>'
    if CONTENT_LABELS.get(content):
        latest_html += f'<div><span class="chip-soft cs" data-cs="{S.esc(content)}">{S.esc(CONTENT_LABELS[content])}</span></div>'

    err = str(row.get("lastError") or "")
    if err:
        short = err if len(err) <= 70 else err[:68] + "…"
        err_html = f'<p class="src-err mono" title="{S.esc(err)}">{S.esc(short)}</p>'
        if S.parse_ts(row.get("lastErrorAt")):
            err_html += f'<div class="muted xs">{_time(row.get("lastErrorAt"))}</div>'
    else:
        err_html = '<span class="muted">–</span>'

    search = " ".join(str(x) for x in (row.get("name"), cid, sid, handle, platform, S.PLATFORM_LABELS.get(platform, ""),
                                       row.get("backend"), url) if x).lower()
    attrs = {
        "data-status": GROUP_OF.get(status, "ok"), "data-platform": platform, "data-q": search,
        "data-rank": STATUS_RANK.get(status, 9), "data-order": order,
        "data-success": S.epoch(row.get("lastSuccess")), "data-latest": S.epoch(row.get("latestPostAt")),
    }
    attr_html = "".join(f' {k}="{S.esc(v)}"' for k, v in attrs.items())
    return (
        f"<tr{attr_html}>"
        f'<td data-label="來源／帳號">{ident}</td>'
        f'<td data-label="抓取方式" class="src-backend">{S.esc(row.get("backend") or "")}</td>'
        f'<td data-label="狀態" class="src-status">{status_html}</td>'
        f'<td data-label="最近抓取" class="src-times">{attempt}{success}</td>'
        f'<td data-label="下次／頻率" class="src-times">{nxt_html}</td>'
        f'<td data-label="最新內容" class="src-times">{latest_html}</td>'
        f'<td data-label="錯誤" class="src-errcell">{err_html}</td>'
        "</tr>"
    )


def _sources(status: Dict[str, Any], data) -> str:
    rows = list(status.get("sources") or [])
    if not rows:
        return _section("sources", "來源表", S.render_empty("尚無逐來源資料", "Status JSON 尚未提供 sources[]。"))
    accounts = {a.get("id"): a for s in data.sources for a in s.get("accounts") or []}
    cand_order = {c["id"]: i for i, c in enumerate(data.candidates)}
    plat_rank = {p: i for i, p in enumerate(PLATFORM_ORDER)}
    rows.sort(key=lambda r: (STATUS_RANK.get(str(r.get("status")), 9), cand_order.get(r.get("candidateId"), 99),
                             plat_rank.get(r.get("platform"), 99), str(r.get("id"))))
    total = len(rows)

    group_counts: Dict[str, int] = {}
    plat_counts: Dict[str, int] = {}
    for r in rows:
        g = GROUP_OF.get(str(r.get("status")), "ok")
        group_counts[g] = group_counts.get(g, 0) + 1
        p = str(r.get("platform") or "")
        plat_counts[p] = plat_counts.get(p, 0) + 1

    status_chips = [S.render_chip("全部", pressed=True, count=total, attrs={"data-value": ""})]
    for key, label, _ in FILTER_GROUPS:
        n = group_counts.get(key, 0)
        status_chips.append(S.render_chip(label, pressed=False, count=n,
                                          attrs={"data-value": key, "disabled": n == 0 or None}))
    plats = sorted(plat_counts, key=lambda p: plat_rank.get(p, 99))
    plat_chips = [S.render_chip("全部", pressed=True, count=total, attrs={"data-value": ""})]
    plat_chips += [S.render_chip(S.PLATFORM_LABELS.get(p, p), pressed=False, count=plat_counts[p], icon_name=p,
                                 attrs={"data-value": p}) for p in plats]

    filters = (
        '<div class="src-filters">'
        f'<div class="filter-row" data-filter="status" role="group" aria-label="狀態篩選"><span class="filter-label">狀態</span>'
        f'<div class="chips">{"".join(status_chips)}</div></div>'
        f'<div class="filter-row" data-filter="platform" role="group" aria-label="平台篩選"><span class="filter-label">平台</span>'
        f'<div class="chips">{"".join(plat_chips)}</div></div>'
        '<div class="src-search"><label class="sr-only" for="src-q">搜尋來源</label>'
        '<input class="input" id="src-q" type="search" placeholder="搜尋候選人、帳號、平台或來源 ID" autocomplete="off"></div>'
        "</div>"
    )
    count = f'<p class="src-count" aria-live="polite">顯示 <b data-shown>{total}</b> / {total} 筆</p>'
    body = "".join(_source_row(r, data, accounts, i) for i, r in enumerate(rows))
    table = (
        '<div class="table-wrap src-wrap"><table class="table src-table" id="src-table"><thead><tr>'
        '<th scope="col">來源／帳號</th><th scope="col">抓取方式</th>'
        '<th scope="col" data-sort="status" aria-sort="ascending">狀態</th>'
        '<th scope="col" data-sort="success">最近抓取</th><th scope="col">下次／頻率</th>'
        '<th scope="col" data-sort="latest">最新內容</th><th scope="col">錯誤</th>'
        f"</tr></thead><tbody>{body}</tbody></table></div>"
        '<div class="src-empty" hidden>'
        + S.render_empty("沒有符合條件的來源", "試著清除狀態、平台篩選或搜尋字詞。",
                         '<button class="btn btn-sm" type="button" data-reset>清除篩選</button>')
        + "</div>"
    )
    note = ("「成功」時間標示來源：抓取紀錄＝抓取器寫入；歷史收錄＝舊收錄匣時間，不冒充排程執行時間。"
            "抓取狀態與最新內容時間分開判斷，久未發文不會自動停用。")
    return _section("sources", "來源表", filters + f'<p class="status-lede small muted">{S.esc(note)}</p>' + count + table)


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------

def render(data) -> None:
    status = data.status or {}
    runtime = S.read_json("api/pipeline-runtime.json", {}) or {}
    shutil.rmtree(OUT_DIR, ignore_errors=True)

    actions = (f'<a class="btn btn-sm" href="/api/status.json">{S.icon("json")}Status JSON</a>'
               f'<a class="btn btn-sm" href="/feeds/updates.xml">{S.icon("rss")}RSS</a>')
    lede = ("每個監看帳號的抓取排程、最近結果與錯誤。抓取成功與「有沒有新內容」分開判斷；"
            "本頁只呈現紀錄，不會為了顯示正常而修改資料。")
    if not status:
        body = S.page_head("資料來源狀態", S.esc(lede), actions, eyebrow="Status") + S.render_empty(
            "尚無狀態資料", "site/api/status.json 尚未產生；請先執行 scripts/build_status_page.py。")
    else:
        body = (
            S.page_head("資料來源狀態", S.esc(lede), actions, eyebrow="Status")
            + _headline(status)
            + _overview(status)
            + _methods(status, runtime)
            + _components(status, runtime)
            + _platform_and_errors(status)
            + _sources(status, data)
            + f'<p class="snapshot">資料快照：{S.esc(S.fmt_time_tpe(status.get("generatedAt"), True))}（GMT+8）'
              "・本站為非官方觀測站，狀態僅反映公開資料抓取流程。</p>"
        )
    html = S.layout("status", "資料來源狀態",
                    "2026 市長官方來源觀測站的資料管線與逐來源抓取狀態快照。", ROUTE, body,
                    extra_css=["pages/status.css"], extra_js=["pages/status.js"], noindex=True)
    S.write_page(ROUTE, html)
