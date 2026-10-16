#!/usr/bin/env python3
"""Fetch Instagram through logged-out web queries, with budgeted Apify fallback."""
from __future__ import annotations

import argparse
import datetime as dt
import http.cookiejar
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import feed_common
import source_status
import ig_public_host
import apify_facebook_fetcher as facebook

PUBLIC_APP_ID = "936619743392459"
PUBLIC_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
PROFILE_POSTS_DOC_ID = "9310670392322965"
PROFILE_COST_USD = 0.006
DIRECT_MAX_CONSECUTIVE_FAILURES = 3
APIFY_RUN_DEADLINE_SECS = 345
UTC = dt.timezone.utc


def timestamp(value):
    if isinstance(value, (int, float)):
        return float(value)
    parsed = source_status.parse_time(value)
    return parsed.timestamp() if parsed else 0


def iso(value):
    return dt.datetime.fromtimestamp(value, UTC).isoformat(timespec="seconds")


def post_row(source, ident, caption, url, posted_at, images):
    match = re.search(r"/(p|reel)/([^/?#]+)", url)
    if not match:
        raise ValueError("Instagram post URL missing shortcode")
    url = f"https://www.instagram.com/{match[1]}/{match[2]}/"
    return {"id": f"instagram:{url}", "candidate_id": source["candidate_id"],
            "city": source["city"], "platform": "instagram", "source_id": source["id"],
            "url": url, "posted_at": posted_at, "text": caption or "", "media": images,
            "fetched_at": feed_common.utc_now_iso()}


class PublicWebError(OSError):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def is_rate_limited(exc):
    return getattr(exc, "code", None) in {401, 429} or "please wait a few minutes" in str(exc).casefold()


class PublicInstagramClient:
    """Logged-out instagram.com client; needs no cookie or Instagram login.

    The profile page hands every anonymous visitor an LSD token plus
    ``csrftoken``/``mid`` cookies. With them, the web app's own profile-posts
    GraphQL query answers without an account. The older ``web_profile_info``
    API now answers logged-out server IPs with 401 ``require_login``.
    """

    def __init__(self, base="https://www.instagram.com", doc_id=None):
        self.base = base.rstrip("/")
        self.doc_id = doc_id or os.environ.get("MAYOR_IG_PROFILE_POSTS_DOC_ID") or PROFILE_POSTS_DOC_ID
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.lsd = None

    def _cookie(self, name):
        return next((cookie.value for cookie in self.cookies if cookie.name == name), "")

    def _open(self, request, label):
        try:
            with self.opener.open(request, timeout=30) as response:
                if "/accounts/login" in response.geturl():
                    raise PublicWebError("Instagram redirect to login", 401)
                return response.read(5_000_000).decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            with exc:
                body = exc.read(500).decode("utf-8", "replace")
            raise PublicWebError(f"Instagram public web HTTP {exc.code} for {label}: {body[:120]}", exc.code) from None

    def _bootstrap(self, username):
        page = self._open(urllib.request.Request(f"{self.base}/{username}/", headers={
            "Accept": "text/html", "Accept-Language": "en", "User-Agent": PUBLIC_USER_AGENT}), f"@{username} page")
        match = re.search(r'"LSD",\[\],\{"token":"([^"]+)"', page)
        if not match or not self._cookie("csrftoken"):
            raise ValueError("Instagram public web page carried no anonymous LSD/csrf token")
        self.lsd = match.group(1)

    def fetch(self, source, limit=5):
        username = source["username"]
        if self.lsd is None:
            self._bootstrap(username)
        variables = {"data": {"count": max(12, limit), "include_reel_media_seen_timestamp": True,
                              "include_relationship_info": True, "latest_besties_reel_media": True,
                              "latest_reel_media": True},
                     "username": username,
                     "__relay_internal__pv__PolarisIsLoggedInrelayprovider": False,
                     "__relay_internal__pv__PolarisShareSheetV3relayprovider": True}
        body = urllib.parse.urlencode({"lsd": self.lsd, "doc_id": self.doc_id, "variables": json.dumps(variables)}).encode()
        text = self._open(urllib.request.Request(f"{self.base}/graphql/query", body, {
            "Accept": "*/*", "Content-Type": "application/x-www-form-urlencoded", "Origin": self.base,
            "Referer": f"{self.base}/{username}/", "Sec-Fetch-Site": "same-origin", "User-Agent": PUBLIC_USER_AGENT,
            "X-CSRFToken": self._cookie("csrftoken"), "X-FB-LSD": self.lsd, "X-IG-App-ID": PUBLIC_APP_ID},
            method="POST"), f"@{username}")
        try:
            payload = json.loads(text)
        except ValueError:
            raise ValueError(f"Instagram public web returned no JSON for @{username}") from None
        connection = (payload.get("data") or {}).get("xdt_api__v1__feed__user_timeline_graphql_connection")
        if connection is None:
            if payload.get("require_login") or payload.get("status") == "fail" and "login" in str(payload).lower():
                raise PublicWebError("Instagram public query requires login", 401)
            errors = "; ".join(str(e.get("message")) for e in payload.get("errors") or [])
            raise ValueError(f"Instagram public web query failed for @{username}: "
                             f"{errors or payload.get('message') or 'no timeline'}")
        return parse_public_timeline(source, connection, limit)


def _best_image(media):
    candidates = (media.get("image_versions2") or {}).get("candidates") or []
    if candidates and candidates[0].get("url"):
        return candidates[0]["url"]
    return media.get("display_uri")


def parse_public_timeline(source, connection, limit=5):
    """Return (avatar, posts) from the logged-out timeline; pinned posts are flagged."""
    nodes = [edge.get("node") or {} for edge in connection.get("edges") or []]
    user = next((node.get("user") for node in nodes if node.get("user")), None) or {}
    if user.get("is_private"):
        raise ValueError("Public Instagram profile unavailable")
    posts = []
    for node in sorted(nodes, key=lambda node: node.get("taken_at") or 0, reverse=True)[:limit]:
        ident = str(node.get("pk") or str(node.get("id") or "").split("_")[0])
        if not node.get("code") or not ident or not node.get("taken_at"):
            continue
        images = [url for url in map(_best_image, (node.get("carousel_media") or [node])[:2]) if url]
        post = post_row(source, ident, (node.get("caption") or {}).get("text") or "",
                        f"https://www.instagram.com/p/{node['code']}/", iso(node["taken_at"]), images)
        posts.append(post)
    avatar = (user.get("hd_profile_pic_url_info") or {}).get("url") or user.get("profile_pic_url")
    return avatar, posts


def fetch_public_profile(source, client=None):
    return (client or PublicInstagramClient()).fetch(source)[1]


def normalize_profile(source, item):
    if item.get("isPrivate") or "latestPosts" not in item or item.get("error"):
        raise ValueError("Apify did not return a public profile")
    posts = []
    for raw in (item.get("latestPosts") or [])[:5]:
        shortcode = raw.get("shortCode") or raw.get("shortcode")
        if not shortcode or not raw.get("id") or not timestamp(raw.get("timestamp")):
            continue
        images = raw.get("images") or ([raw["displayUrl"]] if raw.get("displayUrl") else [])
        post = post_row(source, raw["id"], raw.get("caption"), raw.get("url") or f"https://www.instagram.com/p/{shortcode}/",
                        iso(timestamp(raw["timestamp"])), images[:2])
        posts.append(post)
    return posts


def api(method, path, token, *, body=None):
    request = urllib.request.Request(f"{facebook.APIFY_BASE}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Apify request failed: {getattr(exc, 'code', 'network error')}") from None


def apify_profiles(sources, *, now, dry_run=False):
    token = facebook.apify_token()
    if dry_run or not token:
        raise RuntimeError("Apify skipped: dry-run or APIFY_TOKEN missing")
    ledger = feed_common.load_json(facebook.LEDGER_JSON, {})
    entry = ledger.setdefault("months", {}).setdefault(facebook.month_key(now), {})
    instagram = entry.setdefault("instagram", {"estimated_spend_usd": 0, "runs": 0})
    cost = round(len(sources) * PROFILE_COST_USD, 6)
    cap = float(os.environ.get("MAYOR_APIFY_INSTAGRAM_MONTHLY_BUDGET_USD", "0.75"))
    target = facebook.DEFAULT_MONTHLY_BUDGET_USD * facebook.DEFAULT_BUDGET_UTILIZATION
    if instagram["estimated_spend_usd"] + cost > cap or facebook.ledger_month_spend(ledger, now) + cost > target:
        raise RuntimeError("Apify skipped: monthly budget exhausted")
    limits = api("GET", "/users/me/limits", token)["data"]
    remaining = min(float(limits.get("limits", {}).get("maxMonthlyUsageUsd") or 0),
                    facebook.DEFAULT_MONTHLY_BUDGET_USD) - float(limits.get("current", {}).get("monthlyUsageUsd") or 0)
    if remaining < cost + 0.25:
        raise RuntimeError("Apify skipped: live credit reserve")
    # Persist before the paid request; unknown outcomes keep their reservation.
    instagram["estimated_spend_usd"] = round(instagram["estimated_spend_usd"] + cost, 6)
    instagram["runs"] += 1
    instagram["last_run_at"] = source_status.iso(now)
    feed_common.save_json_atomic(facebook.LEDGER_JSON, ledger)
    run = api("POST", f"/acts/apify~instagram-profile-scraper/runs?maxTotalChargeUsd={cost}&restartOnError=false", token,
              body={"usernames": [s["username"] for s in sources], "includeAboutSection": False})["data"]
    deadline = time.monotonic() + APIFY_RUN_DEADLINE_SECS
    while run.get("status") not in facebook.TERMINAL_STATUSES and time.monotonic() < deadline:
        time.sleep(facebook.POLL_INTERVAL_SECS)
        run = api("GET", f"/actor-runs/{run['id']}", token)["data"]
    usage = run.get("usageTotalUsd")
    if isinstance(usage, (int, float)) and usage >= 0:
        instagram["reported_usage_usd"] = round(instagram.get("reported_usage_usd", 0) + usage, 6)
        instagram["estimated_spend_usd"] = round(instagram["estimated_spend_usd"] + max(cost, usage) - cost, 6)
        feed_common.save_json_atomic(facebook.LEDGER_JSON, ledger)
    if run.get("status") != "SUCCEEDED":
        raise RuntimeError(f"Apify run ended with {run.get('status')}; budget reserved")
    items = api("GET", f"/datasets/{run['defaultDatasetId']}/items", token)
    return {str(item.get("username", "")).casefold(): item for item in items}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Fetch direct only; do not write inbox or telemetry.")
    parser.add_argument("--full-refresh", action="store_true", help="Ignore intervals; retain backoff and cooldown.")
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--instagram-interval-hours", type=float,
                        default=float(os.environ.get("MAYOR_INSTAGRAM_INTERVAL_HOURS", "12")))
    args = parser.parse_args()
    if args.batch_size < 1 or args.instagram_interval_hours <= 0:
        parser.error("Batch size and interval must be positive")
    now = dt.datetime.now(UTC)
    state = source_status.load_state()
    oldest = dt.datetime.min.replace(tzinfo=UTC)
    sources = feed_common.load_sources(platforms={"instagram"})
    due = lambda s: source_status.next_eligible(s, state, instagram_hours=args.instagram_interval_hours) or oldest
    cooldown = source_status.parse_time(state.get("platforms", {}).get("instagram", {}).get("cooldown_until"))
    selected = sorted((s for s in sources if (args.full_refresh or due(s) <= now)
                       and source_status.retry_ready(s, now=now) and not (cooldown and cooldown > now)),
                      key=lambda s: (due(s), s["id"]))[:args.batch_size]
    selected_ids = {s["id"] for s in selected}
    for source in sources:
        if source["id"] not in selected_ids:
            print(f"instagram_public_fetcher: {source['id']} waiting for schedule, batch capacity or retry cooldown")
    client = PublicInstagramClient()
    fallback = []
    errors = {}
    appended = 0

    def success(source, rows):
        nonlocal appended
        interval = source_status.instagram_interval(rows, minimum=args.instagram_interval_hours)
        if not args.dry_run:
            appended += feed_common.append_jsonl_dedup(feed_common.INBOX_JSONL, rows)
            source_status.record_fetch(source, ok=True, items=len(rows), interval_hours=interval)
            source_status.clear_instagram_cooldown()
        print(f"instagram_public_fetcher: {source['id']} -> {len(rows)} item(s); target interval {interval:g}h")

    direct = True
    failures = 0
    for source in selected:
        # A host block set by any collector skips the query without re-reporting it.
        if not direct or not ig_public_host.wait_turn():
            direct = False
            fallback.append(source)
            continue
        try:
            success(source, fetch_public_profile(source, client))
            failures = 0
        except (OSError, ValueError) as exc:
            fallback.append(source)
            errors[source["id"]] = exc
            failures += 1
            if is_rate_limited(exc):
                # Instagram refused this host: every collector stops direct queries.
                ig_public_host.report_block("mayor2026")
                direct = False
            else:
                # Repeated failures point at the query itself (e.g. a rotated doc id).
                direct = failures < DIRECT_MAX_CONSECUTIVE_FAILURES
    if fallback:
        try:
            found = apify_profiles(fallback, now=now, dry_run=args.dry_run)
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            found = {}
            fallback_error = exc
        else:
            fallback_error = "Apify profile result unavailable"
        cooled = False
        for source in fallback:
            try:
                item = found.get(source["username"].casefold())
                if item is None:
                    raise ValueError(str(fallback_error))
                success(source, normalize_profile(source, item))
            except ValueError as exc:
                if not args.dry_run:
                    source_status.record_fetch(source, ok=False, error=exc)
                    feed_common.record_error(source["id"], source_status.safe_error(exc))
                    if not cooled and is_rate_limited(errors.get(source["id"])):
                        source_status.set_instagram_cooldown(errors[source["id"]])
                        cooled = True
                print(f"instagram_public_fetcher: {source['id']} failed: {source_status.safe_error(exc)}")
    print(f"instagram_public_fetcher: appended {appended} new item(s)" + (" (dry-run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
