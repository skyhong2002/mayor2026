"""Durable per-source telemetry and pacing, adapted from Chumei.

Historical error events are retained separately; current health is determined by
an account's latest attempt. A successful empty response is still a fetch, not
proof that fresh content exists. Existing RSSHub state is read without migration.
"""
from __future__ import annotations

import collections
import datetime as dt
import fcntl
import importlib
import json
import os
import re
import statistics
from contextlib import contextmanager
from typing import Any

import feed_common

STATE_PATH = feed_common.PROJECT_ROOT / "state" / "social_fetch_state.json"
PIPELINE_INTERVAL_HOURS = 6
BACKENDS = {"instagram": "RSSHub Instagram", "threads": "RSSHub Threads", "x": "RSSHub X",
            "podcast": "原生 RSS", "youtube": "yt-dlp", "website": "官網 adapter", "facebook": "Apify"}


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp.replace(tzinfo=dt.timezone.utc) if stamp.tzinfo is None else stamp.astimezone(dt.timezone.utc)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.isoformat(timespec="seconds")


def safe_error(error: object) -> str:
    text = str(error)
    for key in ("APIFY_TOKEN", "OPENAI_API_KEY"):
        secret = os.environ.get(key, "")
        if secret:
            text = text.replace(secret, "[redacted]")
    text = re.sub(r"(?i)\b(authorization|cookie):[^\r\n]+", r"\1: [redacted]", text)
    text = re.sub(r"(?i)(token|api_key|authorization|cookie)([=:\s]+)[^\s&<>]+", r"\1\2[redacted]", text)
    return text[:500]


def load_state() -> dict:
    return feed_common.load_json(STATE_PATH, {"version": 2, "sources": {}, "platforms": {}})


@contextmanager
def locked_state():
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = load_state()
        yield state
        state["version"] = 2
        tmp = STATE_PATH.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(STATE_PATH)


def record_fetch(source: dict, *, ok: bool, items: int = 0, error: object = "",
                 interval_hours: float = 6, now: dt.datetime | None = None) -> None:
    now = now or utc_now()
    with locked_state() as state:
        entry = state.setdefault("sources", {}).setdefault(source["id"], {})
        entry.update(last_attempt_at=iso(now), backend=BACKENDS[source["platform"]], last_items=items)
        if ok:
            entry.update(last_success_at=iso(now), consecutive_failures=0, interval_hours=interval_hours)
            entry.pop("last_error", None)
            entry.pop("retry_after", None)
            history = entry.setdefault("success_history", [])
            history.append(iso(now))
            entry["success_history"] = history[-20:]
            entry["next_eligible_at"] = iso(now + dt.timedelta(hours=interval_hours))
        else:
            failures = int(entry.get("consecutive_failures", 0)) + 1
            delay = min(72, 6 * 2 ** min(failures - 1, 4))
            entry.update(last_error=safe_error(error), last_error_at=iso(now), consecutive_failures=failures,
                         retry_after=iso(now + dt.timedelta(hours=delay)),
                         next_eligible_at=iso(now + dt.timedelta(hours=delay)))


def is_rate_limited(error: object) -> bool:
    return bool(re.search(r"\b(401|429)\b|too many requests|rate limit|please wait a few minutes", str(error), re.I))


def set_instagram_cooldown(error: object, *, now: dt.datetime | None = None) -> None:
    now = now or utc_now()
    with locked_state() as state:
        entry = state.setdefault("platforms", {}).setdefault("instagram", {})
        streak = int(entry.get("rate_limit_streak", 0)) + 1
        delay = min(72, 24 * 2 ** min(streak - 1, 2))
        entry.update(rate_limit_streak=streak, cooldown_until=iso(now + dt.timedelta(hours=delay)),
                     reason=safe_error(error))


def clear_instagram_cooldown() -> None:
    with locked_state() as state:
        state.setdefault("platforms", {})["instagram"] = {"rate_limit_streak": 0}


def instagram_interval(rows: list[dict], *, minimum: float = 12, now: dt.datetime | None = None) -> float:
    """Chumei's cadence tiers: poll active profiles more often; keep quiet ones monitored."""
    now = now or utc_now()
    dates = sorted({stamp for row in rows if (stamp := parse_time(row.get("posted_at"))) and stamp <= now}, reverse=True)
    if not dates:
        target = 24  # Empty responses deserve a recheck, not a two-week silence.
    else:
        gaps = [(a - b).total_seconds() / 3600 for a, b in zip(dates, dates[1:])]
        target = max(statistics.median(gaps) / 2 if gaps else 24, (now - dates[0]).total_seconds() / 14400)
    tiers = sorted({max(minimum, float(t)) for t in (12, 24, 48, 72, 168)})
    return min(tiers, key=lambda t: (abs(t - target), t))


def next_eligible(source: dict, state: dict, *, instagram_hours: float = 12) -> dt.datetime | None:
    entry = state.get("sources", {}).get(source["id"], {})
    due = parse_time(entry.get("next_eligible_at"))
    if due is None and (last := parse_time(entry.get("last_attempt_at"))):
        due = last + dt.timedelta(hours=instagram_hours if source["platform"] == "instagram" else 6)
    return due


def retry_ready(source: dict, *, now: dt.datetime | None = None) -> bool:
    entry = load_state().get("sources", {}).get(source["id"], {})
    retry = parse_time(entry.get("retry_after"))
    return retry is None or retry <= (now or utc_now())


def scheduled_tick(eligible: dt.datetime) -> dt.datetime:
    """Next Taipei 00/06/12/18 tick at or after eligibility (not a promised start)."""
    local = eligible.astimezone(dt.timezone(dt.timedelta(hours=8)))
    tick = local.replace(hour=(local.hour // 6) * 6, minute=0, second=0, microsecond=0)
    if tick < local:
        tick += dt.timedelta(hours=6)
    return tick.astimezone(dt.timezone.utc)


def link_only_reason(source: dict) -> str:
    platform = source["platform"]
    if platform not in BACKENDS:
        return {"line_oa": "沒有可抓取的公開時間軸", "line_openchat": "沒有可抓取的公開時間軸",
                "tiktok": "目前未提供可用的抓取方式"}.get(platform, "尚無抓取方式")
    if platform == "website":
        module = f"official_site_adapters.{source['candidate_id'].replace('-', '_')}"
        try:
            adapter = importlib.import_module(module)
        except ModuleNotFoundError as exc:
            if exc.name != module:
                raise
            return "尚無此官網的文章解析器"
        return str(getattr(adapter, "NO_FEED_REASON", ""))
    if platform == "podcast" and not source.get("feed_url"):
        return "尚未提供 RSS 網址"
    return ""


def build_snapshot(*, accounts: list[dict], sources: list[dict], inbox: list[dict],
                   errors: list[dict], apify: dict, now: dt.datetime) -> dict:
    state = load_state()
    configured = {s["id"]: s for s in sources}
    candidates = {r["candidate_id"]: r["name"] for r in feed_common.load_candidates()}
    newest: dict[str, dt.datetime] = {}
    collected: dict[str, dt.datetime] = {}
    for post in inbox:
        sid = post.get("source_id", "")
        for key, target in (("posted_at", newest), ("fetched_at", collected)):
            stamp = parse_time(post.get(key))
            if stamp and (sid not in target or stamp > target[sid]):
                target[sid] = stamp
    latest_errors = {}
    for event in errors:
        stamp = parse_time(event.get("recorded_at"))
        sid = event.get("source_id")
        if stamp and (sid not in latest_errors or stamp > latest_errors[sid][0]):
            latest_errors[sid] = (stamp, str(event.get("message") or ""))
    rows = []
    for account in accounts:
        sid = account["account_id"]
        source = configured.get(sid, {**account, "id": sid})
        platform = source["platform"]
        active = str(account.get("active", "")).lower() in {"true", "1", "yes"}
        reason = "" if active else "watchlist 設定為停用；歷史資料保留"
        if active:
            reason = link_only_reason(source)
            if not reason and sid not in configured:
                reason = "未列入目前抓取設定"
        entry = state.get("sources", {}).get(sid, {})
        attempt = parse_time(entry.get("last_attempt_at"))
        success = parse_time(entry.get("last_success_at")) or collected.get(sid)
        evidence = "fetch" if entry.get("last_success_at") else ("inbox" if success else "none")
        event_time, event_error = latest_errors.get(sid, (None, ""))
        error_time = parse_time(entry.get("last_error_at")) or event_time
        # Legacy error logs do not record recovery; only fresh legacy events
        # can be treated as current until this collector writes telemetry.
        legacy_error = event_error if event_time and (now - event_time).total_seconds() <= 86400 else ""
        error = str(entry.get("last_error") or (event_error if attempt else legacy_error))
        if success and (not error_time or error_time <= success):
            error = ""
        interval = float(entry.get("interval_hours") or (12 if platform == "instagram" else 6))
        due = next_eligible(source, state)
        blocked = ""
        if platform == "instagram":
            cooldown = parse_time(state.get("platforms", {}).get("instagram", {}).get("cooldown_until"))
            if cooldown and cooldown > now:
                due = max(due or now, cooldown)
                blocked = "Instagram 401／429 共用冷卻；到期自動再試"
        if platform == "facebook":
            interval = apify.get("interval_hours")
            due = parse_time(apify.get("next_eligible_at"))
            retry = parse_time(entry.get("retry_after"))
            if retry:
                due = max(due or now, retry)
            if not apify.get("ok"):
                blocked = "無法取得 Apify 排程狀態"
            elif not apify.get("has_token"):
                blocked = "尚未設定 Apify 憑證"
                due = None
            elif apify.get("budget_exhausted"):
                blocked = "本月抓取預算已用完；下月自動恢復"
            aggregate = latest_errors.get("apify_facebook_fetcher")
            batch_success = parse_time(apify.get("last_run_at"))
            if aggregate and (not batch_success or aggregate[0] > batch_success) and (not success or aggregate[0] > success):
                error = aggregate[1]
                error_time = aggregate[0]
        tick = scheduled_tick(due) if due else None
        if not active:
            status = "disabled"
        elif reason:
            status = "link_only"
        elif blocked:
            status = "blocked"
        elif error:
            status = "error"
        elif tick and tick + dt.timedelta(hours=2) < now:
            status = "overdue"
        elif not due or due <= now:
            status = "due"
        else:
            status = "ok"
        latest = newest.get(sid)
        quiet_days = 60 if platform in {"youtube", "podcast"} else 14
        quiet = bool(latest and (now - latest).days > quiet_days)
        fetchable = active and not reason
        rows.append({
            "id": sid, "candidateId": source["candidate_id"],
            "name": candidates.get(source["candidate_id"], source["candidate_id"]),
            "platform": platform, "url": source.get("url", ""),
            "backend": BACKENDS.get(platform, "僅連結"), "active": active, "fetchable": fetchable,
            "status": status, "reason": reason or blocked,
            "lastAttempt": iso(attempt) if attempt else None,
            "lastSuccess": iso(success) if success else None, "successEvidence": evidence,
            "lastItems": entry.get("last_items"),
            "lastError": safe_error(error) if fetchable else "",
            "lastErrorAt": iso(error_time) if error and error_time and fetchable else None,
            "consecutiveFailures": int(entry.get("consecutive_failures", 0)),
            "targetIntervalHours": interval if fetchable else None,
            "nextEligibleAt": iso(due) if due and fetchable else None,
            "nextScheduledAt": iso(scheduled_tick(max(due, now))) if due and fetchable else None,
            "latestPostAt": iso(latest) if latest else None,
            "contentStatus": "quiet" if quiet else ("available" if latest else "empty"),
            "evidence": account.get("evidence", ""),
        })
    counts = dict(collections.Counter(r["status"] for r in rows))
    methods = []
    for backend in sorted({r["backend"] for r in rows if r["fetchable"]}):
        members = [r for r in rows if r["fetchable"] and r["backend"] == backend]
        methods.append({"backend": backend, "sources": len(members),
                        "errors": sum(bool(r["lastError"]) for r in members),
                        "blocked": sum(r["status"] == "blocked" for r in members),
                        "due": sum(r["status"] in {"due", "overdue"} for r in members)})
    return {"sources": rows, "sourceCounts": counts, "methods": methods,
            "fetchableSources": sum(r["fetchable"] for r in rows),
            "pipelineIntervalHours": PIPELINE_INTERVAL_HOURS}
