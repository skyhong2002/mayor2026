#!/usr/bin/env python3
"""Fetch Facebook posts via Apify's facebook-posts-scraper actor.

Facebook is only reachable through Apify (the rss.observe.tw RSSHub has no
facebook route), and the actor is pay-per-result, so this fetcher enforces
the same budget discipline as Harmonica-in-Taiwan's version via a ledger
(state/apify_facebook_fetcher.json), with dynamic pacing: the remaining
monthly budget (default $5 x 95% utilization) is spread evenly over the rest
of the month, so the run interval adapts to actual usage — overspend early
and the interval grows, underspend and it shrinks. Freshness floor: at most
one run per 4h.

Requires APIFY_TOKEN in the environment / .env; without it this prints a
skip message and exits 0 (non-fatal).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

import feed_common

APIFY_BASE = "https://api.apify.com/v2"
FACEBOOK_POSTS_ACTOR = "apify~facebook-posts-scraper"
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"}
POLL_INTERVAL_SECS = 5
MAX_POLL_ATTEMPTS = 24

LEDGER_JSON = feed_common.PROJECT_ROOT / "state" / "apify_facebook_fetcher.json"
COST_PER_RESULT_USD = 0.005  # facebook-posts-scraper list price: $5 / 1000 results
DEFAULT_MONTHLY_BUDGET_USD = float(os.environ.get("MAYOR_APIFY_MONTHLY_BUDGET_USD", "5"))
DEFAULT_BUDGET_UTILIZATION = float(os.environ.get("MAYOR_APIFY_BUDGET_UTILIZATION", "0.95"))
DEFAULT_POSTS_PER_PAGE = int(os.environ.get("MAYOR_APIFY_POSTS_PER_PAGE", "3"))
MIN_RUN_INTERVAL_HOURS = 4.0  # freshness floor: never hammer more often than this
MAX_RUN_INTERVAL_HOURS = 24.0 * 7  # staleness ceiling used only for logging


def apify_token() -> str:
    return os.environ.get("APIFY_TOKEN", "").strip()


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


def month_key(now: dt.datetime) -> str:
    return now.strftime("%Y-%m")


def ledger_month_spend(ledger: dict[str, Any], now: dt.datetime) -> float:
    months = ledger.get("months") or {}
    entry = months.get(month_key(now)) or {}
    return float(entry.get("estimated_spend_usd") or 0.0)


def month_end(now: dt.datetime) -> dt.datetime:
    if now.month == 12:
        return dt.datetime(now.year + 1, 1, 1, tzinfo=dt.timezone.utc)
    return dt.datetime(now.year, now.month + 1, 1, tzinfo=dt.timezone.utc)


def dynamic_run_decision(
    ledger: dict[str, Any],
    *,
    now: dt.datetime,
    run_cost_usd: float,
    budget_usd: float,
    utilization: float,
) -> tuple[bool, str]:
    """Spread the remaining monthly budget evenly over the rest of the month.

    interval = remaining_time / affordable_runs_left. Overspending early makes
    the interval grow; an underspent budget near month-end makes it shrink.
    """
    target = budget_usd * utilization
    spent = ledger_month_spend(ledger, now)
    remaining = target - spent
    if remaining < run_cost_usd:
        return False, (
            f"monthly budget target reached (~${spent:.2f} of ${target:.2f}, run costs ~${run_cost_usd:.2f}); "
            "waiting for next month"
        )

    affordable_runs = remaining / run_cost_usd
    seconds_left = max((month_end(now) - now).total_seconds(), 1.0)
    interval_hours = max(seconds_left / affordable_runs / 3600.0, MIN_RUN_INTERVAL_HOURS)

    last_run = parse_time(ledger.get("last_run_at"))
    if last_run is None:
        return True, f"first run this ledger; pacing thereafter ~every {interval_hours:.1f}h"
    due_at = last_run + dt.timedelta(hours=interval_hours)
    if now >= due_at:
        return True, (
            f"due (pace ~every {interval_hours:.1f}h; ~${spent:.2f} of ${target:.2f} spent, "
            f"~{affordable_runs:.0f} runs left this month)"
        )
    return False, (
        f"not due yet (pace ~every {interval_hours:.1f}h, next at {due_at.isoformat(timespec='seconds')}; "
        f"~${spent:.2f} of ${target:.2f} spent)"
    )


def record_run(ledger: dict[str, Any], *, now: dt.datetime, results: int) -> None:
    ledger["last_run_at"] = now.isoformat(timespec="seconds")
    months = ledger.setdefault("months", {})
    entry = months.setdefault(month_key(now), {"runs": 0, "results": 0, "estimated_spend_usd": 0.0})
    entry["runs"] += 1
    entry["results"] += results
    entry["estimated_spend_usd"] = round(entry["estimated_spend_usd"] + results * COST_PER_RESULT_USD, 4)


def start_run(token: str, page_urls: list[str], *, posts_per_page: int) -> str:
    payload = {
        "startUrls": [{"url": url} for url in page_urls],
        "resultsLimit": posts_per_page,
    }
    request = urllib.request.Request(
        f"{APIFY_BASE}/acts/{FACEBOOK_POSTS_ACTOR}/runs?token={token}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read())
    return body["data"]["id"]


def poll_run(token: str, run_id: str) -> dict[str, Any]:
    for _ in range(MAX_POLL_ATTEMPTS):
        request = urllib.request.Request(f"{APIFY_BASE}/actor-runs/{run_id}?token={token}")
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read())["data"]
        if body["status"] in TERMINAL_STATUSES:
            return body
        time.sleep(POLL_INTERVAL_SECS)
    raise TimeoutError(f"Apify run {run_id} did not finish in time")


def fetch_dataset_items(token: str, dataset_id: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(f"{APIFY_BASE}/datasets/{dataset_id}/items?token={token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def extract_media_urls(item: dict[str, Any]) -> list[str]:
    """Pull image URLs out of the actor's media entries (objects, not strings)."""
    urls: list[str] = []
    for entry in item.get("media") or []:
        if isinstance(entry, str):
            urls.append(entry)
            continue
        if not isinstance(entry, dict):
            continue
        for key in ("thumbnail", "photo_image", "image"):
            value = entry.get(key)
            if isinstance(value, str) and value.startswith("http"):
                urls.append(value)
                break
            if isinstance(value, dict) and isinstance(value.get("uri"), str):
                urls.append(value["uri"])
                break
    return urls


def update_source_profiles(rows_by_page: dict[str, tuple[dict[str, Any], dict[str, Any]]]) -> None:
    """Record each page's own display name and avatar URL, keyed by account id."""
    profiles = feed_common.load_json(feed_common.SOURCE_PROFILES_JSON, {})
    changed = False
    for source, item in rows_by_page.values():
        user = item.get("user") or {}
        display_name = user.get("name") or item.get("pageName") or ""
        profile_pic = user.get("profilePic") or ""
        if not display_name and not profile_pic:
            continue
        entry = profiles.setdefault(source["id"], {})
        updates = {
            "candidate_id": source["candidate_id"],
            "platform": "facebook",
            "display_name": display_name or entry.get("display_name", ""),
            "avatar_url": profile_pic or entry.get("avatar_url", ""),
        }
        if any(entry.get(key) != value for key, value in updates.items()):
            entry.update(updates)
            entry["updated_at"] = feed_common.utc_now_iso()
            changed = True
    if changed:
        feed_common.save_json_atomic(feed_common.SOURCE_PROFILES_JSON, profiles)
        print("apify_facebook_fetcher: updated account profiles in source_profiles.json")


def normalize_items(source_by_url: dict[str, dict[str, Any]], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    latest_item_by_page: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for item in items:
        post_url = item.get("url") or item.get("postUrl") or ""
        page_url = item.get("facebookUrl") or item.get("pageUrl") or ""
        source = source_by_url.get(page_url)
        if not source or not post_url:
            continue
        latest_item_by_page[page_url] = (source, item)
        post_id = item.get("postId") or post_url
        rows.append(
            {
                "id": f"facebook:{post_id}",
                "candidate_id": source["candidate_id"],
                "city": source["city"],
                "platform": "facebook",
                "source_id": source["id"],
                "url": post_url,
                "posted_at": item.get("time") or "",
                "text": item.get("text") or "",
                "media": extract_media_urls(item),
                "fetched_at": feed_common.utc_now_iso(),
            }
        )
    update_source_profiles(latest_item_by_page)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--posts-per-page", type=int, default=DEFAULT_POSTS_PER_PAGE)
    parser.add_argument("--monthly-budget-usd", type=float, default=DEFAULT_MONTHLY_BUDGET_USD)
    parser.add_argument("--budget-utilization", type=float, default=DEFAULT_BUDGET_UTILIZATION)
    parser.add_argument("--force", action="store_true", help="Ignore the dynamic budget pacing.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = apify_token()
    if not token:
        print("apify_facebook_fetcher: APIFY_TOKEN not set; skipping Facebook fallback fetch.")
        return 0

    sources = feed_common.load_sources(platforms={"facebook"})
    if not sources:
        print("apify_facebook_fetcher: no facebook sources configured; nothing to do.")
        return 0

    ledger = feed_common.load_json(LEDGER_JSON, {})
    now = dt.datetime.now(dt.timezone.utc)
    run_cost = len(sources) * args.posts_per_page * COST_PER_RESULT_USD
    if not args.force:
        should_run, reason = dynamic_run_decision(
            ledger,
            now=now,
            run_cost_usd=run_cost,
            budget_usd=args.monthly_budget_usd,
            utilization=args.budget_utilization,
        )
        print(f"apify_facebook_fetcher: {reason}")
        if not should_run:
            return 0

    source_by_url = {s["url"]: s for s in sources}
    try:
        run_id = start_run(token, list(source_by_url), posts_per_page=args.posts_per_page)
        run = poll_run(token, run_id)
        if run["status"] != "SUCCEEDED":
            raise RuntimeError(f"Apify run ended with status {run['status']}")
        items = fetch_dataset_items(token, run["defaultDatasetId"])
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, TimeoutError) as exc:
        feed_common.record_error("apify_facebook_fetcher", f"Apify run failed: {exc}")
        return 0

    rows = normalize_items(source_by_url, items)
    print(f"apify_facebook_fetcher: fetched {len(rows)} normalized item(s) from {len(items)} raw item(s).")

    record_run(ledger, now=now, results=len(items))
    feed_common.save_json_atomic(LEDGER_JSON, ledger)
    print(
        f"apify_facebook_fetcher: ledger updated — this month ~${ledger_month_spend(ledger, now):.2f} "
        f"of ${args.monthly_budget_usd:.2f} budget."
    )

    if args.dry_run:
        return 0

    appended = feed_common.append_jsonl_dedup(feed_common.INBOX_JSONL, rows)
    print(f"apify_facebook_fetcher: appended {appended} new item(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
