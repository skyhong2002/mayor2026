#!/usr/bin/env python3
"""Fetch Threads / X via RSSHub and podcasts through native RSS.

Instagram is handled by instagram_public_fetcher without an RSSHub cookie.
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import http.cookiejar
import json
import os
import re
import time
import urllib.error
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import feed_common
import source_status

DEFAULT_RSSHUB_BASE = os.environ.get("MAYOR_RSSHUB_BASE", "https://rss.observe.tw").rstrip("/")
REQUEST_TIMEOUT_SECS = 30
USER_AGENT = "Mayor2026SocialWatcher/1.0"

DEFAULT_RSS_DELAY_SECS = 0.25


# Public, logged-out Threads protocol constants from the existing Harmonica adapter.
THREADS_BASE_URL = "https://www.threads.com"
THREADS_GRAPHQL_OPERATION = "BarcelonaProfileThreadsTabRefetchableDirectQuery"
THREADS_GRAPHQL_FALLBACK_DOC_ID = "27422205010763282"
THREADS_WEB_APP_ID = "238260118697367"
THREADS_ASBD_ID = "359341"
THREADS_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
)
THREADS_LSD_RE = re.compile(r'"LSD",\[\],\{"token":"([^"]+)"')
THREADS_PROFILE_USER_ID_RE = re.compile(
    r'"initial_thread_count":\d+.*?"user_id":"(\d+)"',
    re.DOTALL,
)
THREADS_SCRIPT_SRC_RE = re.compile(r'<script[^>]+src="(https://static\.cdninstagram\.com/[^"]+\.js)"')
THREADS_QUERY_DOC_ID_RE = re.compile(
    rf'{THREADS_GRAPHQL_OPERATION}_threadsRelayOperation".*?exports="(\d+)"',
    re.DOTALL,
)
THREADS_RELAY_VARIABLE_RE = re.compile(r'name:"(__relay_internal__pv__[A-Za-z0-9_]+)"')
THREADS_RELAY_TRUE_VARIABLES = {
    "__relay_internal__pv__BarcelonaHasCommunitiesrelayprovider",
    "__relay_internal__pv__BarcelonaHasDearAlgoConsumptionrelayprovider",
    "__relay_internal__pv__BarcelonaHasGameScoreSharerelayprovider",
    "__relay_internal__pv__BarcelonaHasMusicrelayprovider",
    "__relay_internal__pv__BarcelonaHasPublicViewCountCardrelayprovider",
    "__relay_internal__pv__BarcelonaHasViewerRepliedrelayprovider",
    "__relay_internal__pv__BarcelonaOptionalCookiesEnabledrelayprovider",
}
THREADS_RELAY_DEFAULT_VARIABLES = THREADS_RELAY_TRUE_VARIABLES | {
    "__relay_internal__pv__BarcelonaCanSeeSponsoredContentrelayprovider",
    "__relay_internal__pv__BarcelonaGenAIRepliesEnabledrelayprovider",
    "__relay_internal__pv__BarcelonaHasCommunityEntityCardrelayprovider",
    "__relay_internal__pv__BarcelonaHasCommunityTopContributorsrelayprovider",
    "__relay_internal__pv__BarcelonaHasDearAlgoWebProductionrelayprovider",
    "__relay_internal__pv__BarcelonaHasEventBadgerelayprovider",
    "__relay_internal__pv__BarcelonaHasGhostPostEmojiActivationrelayprovider",
    "__relay_internal__pv__BarcelonaHasMessagingrelayprovider",
    "__relay_internal__pv__BarcelonaHasNewspaperLinkStylerelayprovider",
    "__relay_internal__pv__BarcelonaHasPodcastTextFragmentsrelayprovider",
    "__relay_internal__pv__BarcelonaHasPrivateRepliesDeprecationrelayprovider",
    "__relay_internal__pv__BarcelonaHasProfileSelfReplyContextrelayprovider",
    "__relay_internal__pv__BarcelonaHasScorecardCommunityrelayprovider",
    "__relay_internal__pv__BarcelonaHasSportTeamAllegianceCardrelayprovider",
    "__relay_internal__pv__BarcelonaHasWebFaviconsrelayprovider",
    "__relay_internal__pv__BarcelonaIsCrawlerrelayprovider",
    "__relay_internal__pv__BarcelonaIsInternalUserrelayprovider",
    "__relay_internal__pv__BarcelonaIsLoggedInrelayprovider",
    "__relay_internal__pv__BarcelonaIsSearchDiscoveryEnabledrelayprovider",
    "__relay_internal__pv__BarcelonaShouldFulfillLightboxQueryrelayprovider",
    "__relay_internal__pv__BarcelonaShouldShowFediverseM075Featuresrelayprovider",
}
THREADS_TOTAL_TIMEOUT_SECS = 30
THREADS_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
THREADS_MAX_METADATA_SCRIPTS = 2
_THREADS_QUERY_METADATA_CACHE = None

IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
VIDEO_POSTER_RE = re.compile(r"<video\b[^>]*\bposter=[\"']([^\"']+)[\"']", re.IGNORECASE)
RSSHUB_ERROR_MESSAGE_RE = re.compile(
    r"Error Message:\s*<br\s*/?>\s*<code[^>]*>(.*?)</code>", re.IGNORECASE | re.DOTALL
)

RSSHUB_ROUTE_BUILDERS = {
    "threads": lambda username: f"/threads/{username}",
    "x": lambda username: f"/twitter/user/{username}",
}

# Platforms fetched from a direct RSS feed URL (source["feed_url"] from the
# watchlist CSV) instead of a RSSHub route.
DIRECT_FEED_PLATFORMS = {"podcast"}


def rsshub_error_message(body: bytes) -> str:
    """Extract the human-readable error out of a RSSHub error page."""
    text = body.decode("utf-8", "replace")
    match = RSSHUB_ERROR_MESSAGE_RE.search(text)
    if match:
        text = match.group(1)
    return " ".join(feed_common.strip_html(text).split())[:500]


def parse_pubdate(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def fetch_rss(url: str) -> ET.Element:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECS) as response:
            return ET.fromstring(response.read())
    except urllib.error.HTTPError as exc:
        message = rsshub_error_message(exc.read())
        raise RuntimeError(f"HTTP {exc.code}: {message or exc.reason}") from exc


def normalize_items(source: dict[str, Any], root: ET.Element, *, limit: int) -> list[dict[str, Any]]:
    rows = []
    items = root.findall("./channel/item")[:limit]
    for item in items:
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        if not guid:
            continue
        title = (item.findtext("title") or "").strip()
        description = item.findtext("description") or ""
        text = feed_common.strip_html(description) or title
        # src attributes are HTML-escaped in the feed; unescape or the signed
        # CDN URLs' query params break (403).
        media = [html.unescape(u) for u in IMG_SRC_RE.findall(description) + VIDEO_POSTER_RE.findall(description)]
        rows.append(
            {
                "id": f"{source['platform']}:{guid}",
                "candidate_id": source["candidate_id"],
                "city": source["city"],
                "platform": source["platform"],
                "source_id": source["id"],
                "url": link or guid,
                "posted_at": parse_pubdate(item.findtext("pubDate") or ""),
                "text": text,
                "media": media,
                "fetched_at": feed_common.utc_now_iso(),
            }
        )
    return rows


class _NoThreadsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _threads_profile_redirect(previous: str, location: str) -> str:
    target = urllib.parse.urljoin(previous, location)
    old, new = urllib.parse.urlsplit(previous), urllib.parse.urlsplit(target)
    try:
        valid = (old.scheme == new.scheme == "https"
                 and old.hostname in {"www.threads.com", "threads.com"}
                 and new.hostname in {"www.threads.com", "threads.com"}
                 and new.port in (None, 443) and not new.username and not new.password
                 and not new.query and not new.fragment
                 and re.fullmatch(r"/@[A-Za-z0-9._]{1,30}/?", new.path)
                 and old.path.rstrip("/") == new.path.rstrip("/"))
    except ValueError:
        valid = False
    if not valid:
        raise RuntimeError("Threads public profile redirect rejected")
    return target


def _threads_profile_request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "identity",
        "User-Agent": THREADS_USER_AGENT,
    })


def _threads_read(opener, request, *, deadline: float, stage: str,
                  profile_redirects: bool = False) -> tuple[bytes, str]:
    """Bound each response and share one source deadline; never retry a request.

    Only profile GETs can follow up to two canonical same-profile redirects.
    Redirects use newly constructed profile headers, never ephemeral API headers.
    """
    for redirect in range(3 if profile_redirects else 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Threads source request deadline exceeded")
        try:
            with opener.open(request, timeout=min(10, remaining)) as response:
                if response.status != 200:
                    raise RuntimeError(f"Threads {stage} response not successful")
                if response.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
                    raise RuntimeError(f"Threads {stage} compressed response rejected")
                chunks = bytearray()
                while True:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Threads source request deadline exceeded")
                    chunk = response.read(min(65536, THREADS_MAX_RESPONSE_BYTES + 1 - len(chunks)))
                    if not chunk:
                        break
                    chunks.extend(chunk)
                    if len(chunks) > THREADS_MAX_RESPONSE_BYTES:
                        raise RuntimeError(f"Threads {stage} response too large")
                return bytes(chunks), request.full_url
        except urllib.error.HTTPError as exc:
            try:
                location = exc.headers.get("Location") if exc.headers else None
                if (profile_redirects and request.get_method() == "GET" and redirect < 2
                        and exc.code in {301, 302, 303, 307, 308} and location):
                    request = _threads_profile_request(_threads_profile_redirect(request.full_url, location))
                    continue
                raise RuntimeError(f"Threads {stage} HTTP failure ({exc.code})") from None
            finally:
                exc.close()
        except (urllib.error.URLError, TimeoutError, OSError):
            # No endpoint, ephemeral token, response body or raw exception text.
            raise RuntimeError(f"Threads {stage} transport unavailable") from None
    raise RuntimeError("Threads public profile redirect budget exceeded")


def _threads_query_metadata(opener, profile_html: str, *, deadline: float) -> tuple[str, set[str]]:
    global _THREADS_QUERY_METADATA_CACHE
    if _THREADS_QUERY_METADATA_CACHE is not None:
        return _THREADS_QUERY_METADATA_CACHE
    urls = list(dict.fromkeys(html.unescape(url) for url in THREADS_SCRIPT_SRC_RE.findall(profile_html)))
    for url in list(reversed(urls))[:THREADS_MAX_METADATA_SCRIPTS]:
        parsed = urllib.parse.urlsplit(url)
        try:
            valid = (parsed.scheme == "https" and parsed.hostname == "static.cdninstagram.com"
                     and parsed.port in (None, 443) and not parsed.username and not parsed.password
                     and not parsed.fragment)
        except ValueError:
            valid = False
        if not valid:
            continue
        try:
            raw, _ = _threads_read(opener, urllib.request.Request(url, headers={
                "User-Agent": THREADS_USER_AGENT, "Accept-Encoding": "identity"}),
                deadline=deadline, stage="metadata")
        except RuntimeError:
            continue
        script = raw.decode("utf-8", "replace")
        match = THREADS_QUERY_DOC_ID_RE.search(script)
        if match:
            variables = set(THREADS_RELAY_VARIABLE_RE.findall(script))
            _THREADS_QUERY_METADATA_CACHE = (match.group(1), variables)
            return _THREADS_QUERY_METADATA_CACHE
    return THREADS_GRAPHQL_FALLBACK_DOC_ID, set(THREADS_RELAY_DEFAULT_VARIABLES)


def _threads_media(post: dict[str, Any]) -> list[str]:
    rows = post.get("carousel_media") if isinstance(post.get("carousel_media"), list) else [post]
    result = []
    for row in rows[:10]:
        if not isinstance(row, dict):
            continue
        image = row.get("image_versions2")
        candidates = image.get("candidates", []) if isinstance(image, dict) else []
        videos = row.get("video_versions", [])
        for options in (candidates, videos):
            if not isinstance(options, list) or not options or not isinstance(options[0], dict):
                continue
            url = options[0].get("url")
            if not isinstance(url, str) or len(url) > 4096:
                continue
            try:
                parsed = urllib.parse.urlsplit(url)
            except ValueError:
                continue
            if (parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password
                    and url not in result):
                result.append(url)
    return result


def normalize_threads_posts(source: dict[str, Any], payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise RuntimeError("Threads public timeline shape unavailable")
    data = payload.get("data") if isinstance(payload, dict) else None
    media = data.get("mediaData") if isinstance(data, dict) else None
    edges = media.get("edges") if isinstance(media, dict) else None
    if payload.get("errors") or not isinstance(edges, list):
        raise RuntimeError("Threads public timeline unavailable")
    username = source["username"].lstrip("@")
    rows, seen = [], set()
    valid_threads = False
    for edge in edges:
        node = edge.get("node") if isinstance(edge, dict) else None
        items = node.get("thread_items") if isinstance(node, dict) else None
        if not isinstance(items, list):
            continue
        valid_threads = True
        for item in items:
            post = item.get("post") if isinstance(item, dict) else None
            if not isinstance(post, dict):
                continue
            author = post.get("user")
            if (not isinstance(author, dict) or not isinstance(author.get("username"), str)
                    or not re.fullmatch(r"[A-Za-z0-9._]{1,30}", author["username"])
                    or author["username"].casefold() != username.casefold()):
                continue
            code = post.get("code")
            if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", code) or code in seen:
                continue
            seen.add(code)
            # RSSHub's historic guid is /t/<code>, not the GraphQL numeric pk.
            # Keep that exact identity across both adapters and do not rewrite history.
            guid = f"https://www.threads.com/t/{code}"
            caption = post.get("caption")
            text = caption.get("text", "") if isinstance(caption, dict) else caption
            stamp = post.get("taken_at")
            try:
                posted = (dt.datetime.fromtimestamp(stamp, dt.timezone.utc).isoformat(timespec="seconds")
                          if type(stamp) in (int, float) else "")
            except (ValueError, OverflowError, OSError):
                posted = ""
            rows.append({"id": "threads:" + guid, "candidate_id": source["candidate_id"],
                         "city": source["city"], "platform": "threads", "source_id": source["id"],
                         "url": f"{THREADS_BASE_URL}/@{urllib.parse.quote(author['username'])}/post/{code}",
                         "posted_at": posted, "text": text if isinstance(text, str) else "",
                         "media": _threads_media(post), "fetched_at": feed_common.utc_now_iso()})
            if len(rows) >= max(1, min(limit, 15)):
                return rows
    if edges and not valid_threads:
        raise RuntimeError("Threads public timeline shape unavailable")
    return rows


def fetch_threads_graphql(source: dict[str, Any], *, limit: int, opener=None,
                         deadline: float | None = None) -> list[dict[str, Any]]:
    username = source.get("username")
    if not isinstance(username, str) or not re.fullmatch(r"@?[A-Za-z0-9._]{1,30}", username):
        raise RuntimeError("Threads public username invalid")
    username = username.lstrip("@")
    deadline = deadline if deadline is not None else time.monotonic() + THREADS_TOTAL_TIMEOUT_SECS
    cookies = http.cookiejar.CookieJar()
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),
                  urllib.request.HTTPCookieProcessor(cookies), _NoThreadsRedirect())
    raw, profile_url = _threads_read(opener, _threads_profile_request(f"{THREADS_BASE_URL}/@{username}"),
                                    deadline=deadline, stage="profile", profile_redirects=True)
    profile = raw.decode("utf-8", "replace")
    lsd, user_id = THREADS_LSD_RE.search(profile), THREADS_PROFILE_USER_ID_RE.search(profile)
    if not lsd or not user_id:
        raise RuntimeError("Threads public profile metadata unavailable")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", lsd.group(1)) or len(user_id.group(1)) > 32:
        raise RuntimeError("Threads public profile metadata invalid")
    doc_id, names = _threads_query_metadata(opener, profile, deadline=deadline)
    variables = {"after": None, "allow_page_info_for_lox_user": True, "before": None,
                 "first": max(1, min(limit, 15)), "last": None, "userID": user_id.group(1)}
    variables.update({name: name in THREADS_RELAY_TRUE_VARIABLES for name in names})
    variables["__relay_internal__pv__BarcelonaHasProfileSelfReplyContextrelayprovider"] = False
    token = lsd.group(1)
    body = urllib.parse.urlencode({"lsd": token, "doc_id": doc_id,
        "fb_api_req_friendly_name": THREADS_GRAPHQL_OPERATION, "fb_api_caller_class": "RelayModern",
        "server_timestamps": "true", "variables": json.dumps(variables, separators=(",", ":"))}).encode()
    origin = "https://" + urllib.parse.urlsplit(profile_url).netloc
    request = urllib.request.Request(origin + "/graphql/query", data=body, method="POST", headers={
        "Accept": "*/*", "Accept-Encoding": "identity", "Content-Type": "application/x-www-form-urlencoded",
        "Origin": origin, "Referer": profile_url, "User-Agent": THREADS_USER_AGENT,
        "X-ASBD-ID": THREADS_ASBD_ID, "X-FB-Friendly-Name": THREADS_GRAPHQL_OPERATION,
        "X-FB-LSD": token, "X-IG-App-ID": THREADS_WEB_APP_ID,
        "X-LOGGED-OUT-THREADS-MIGRATED-REQUEST": "true",
        "X-Root-Field-Name": "xdt_api__v1__text_feed__user_id__profile__connection",
    })
    # Public session cookies stay in memory; no browser/account cookies or credentials.
    csrf = next((cookie.value for cookie in cookies if cookie.name == "csrftoken"), "")
    if csrf:
        request.add_header("X-CSRFToken", csrf)
    raw, _ = _threads_read(opener, request, deadline=deadline, stage="timeline")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise RuntimeError("Threads public timeline JSON unavailable") from None
    if not isinstance(payload, dict):
        raise RuntimeError("Threads public timeline shape unavailable")
    return normalize_threads_posts(source, payload, limit=limit)


def fetch_threads_source(source: dict[str, Any], *, rsshub_url: str, limit: int) -> list[dict[str, Any]]:
    username = source.get("username")
    if not isinstance(username, str) or not re.fullmatch(r"@?[A-Za-z0-9._]{1,30}", username):
        raise RuntimeError("Threads public username invalid")
    deadline = time.monotonic() + THREADS_TOTAL_TIMEOUT_SECS
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoThreadsRedirect())
    try:
        raw, _ = _threads_read(opener, urllib.request.Request(rsshub_url, headers={
            "User-Agent": USER_AGENT, "Accept-Encoding": "identity"}), deadline=deadline, stage="RSSHub")
        root = ET.fromstring(raw)
        if root.find("./channel") is None:
            raise RuntimeError("Threads RSSHub feed shape unavailable")
        return normalize_items(source, root, limit=limit)
    except (RuntimeError, ET.ParseError):
        # Only an actual RSSHub failure opens the bounded public fallback.
        # Failure propagates to the unchanged per-source retry/backoff machinery.
        try:
            return fetch_threads_graphql(source, limit=limit, deadline=deadline)
        except RuntimeError:
            raise RuntimeError("Threads RSSHub and public fallback unavailable") from None


def probe_threads_source(source: dict[str, Any], *, limit: int = 1) -> dict[str, Any]:
    """Explicit read-only probe hook; never called by main or during preparation.

    Returns aggregate facts only; does not record source health or append rows.
    """
    rows = fetch_threads_graphql(source, limit=max(1, min(limit, 15)))
    return {"backend": "Threads public logged-out", "rows": len(rows),
            "rows_with_valid_time": sum(bool(row["posted_at"]) for row in rows),
            "rows_with_media": sum(bool(row["media"]) for row in rows),
            "state_or_inbox_written": False}


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


def fetch_source(source: dict[str, Any], *, rsshub_base: str, limit: int) -> list[dict[str, Any]]:
    platform = source.get("platform")
    if platform in DIRECT_FEED_PLATFORMS:
        url = source.get("feed_url") or ""
        if not url:
            return []
    else:
        username = source.get("username")
        builder = RSSHUB_ROUTE_BUILDERS.get(platform)
        if not builder or not username:
            return []
        url = rsshub_base.rstrip("/") + builder(username)
    if platform == "threads":
        return fetch_threads_source(source, rsshub_url=url, limit=limit)
    root = fetch_rss(url)
    return normalize_items(source, root, limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rsshub-base",
        default=None,
        help=f"RSSHub base URL for every source (default: MAYOR_RSSHUB_BASE or per-source value or {DEFAULT_RSSHUB_BASE}).",
    )
    parser.add_argument("--limit", type=int, default=10, help="Max items to keep per source per run.")
    parser.add_argument("--full-refresh", action="store_true", help="Ignore regular intervals; retain failure backoff and platform cooldown.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print, but do not write to inbox.")
    args = parser.parse_args()

    sources = [s for s in feed_common.load_sources(platforms=set(RSSHUB_ROUTE_BUILDERS) | DIRECT_FEED_PLATFORMS)
               if s["platform"] in set(RSSHUB_ROUTE_BUILDERS) | DIRECT_FEED_PLATFORMS]
    if not sources:
        print("rsshub_fetcher: no RSS-fetchable sources configured; nothing to do.")
        return 0

    now = dt.datetime.now(dt.timezone.utc)
    all_rows: list[dict[str, Any]] = []
    appended = 0
    skipped = 0
    for source in sources:
        if not source_status.retry_ready(source, now=now):
            skipped += 1
            continue
        try:
            rows = fetch_source(source, rsshub_base=args.rsshub_base or DEFAULT_RSSHUB_BASE, limit=args.limit)
        except (RuntimeError, OSError, urllib.error.URLError, ET.ParseError) as exc:
            if not args.dry_run:
                source_status.record_fetch(source, ok=False, error=exc)
                feed_common.record_error(source["id"], f"rsshub fetch failed: {source_status.safe_error(exc)}")
            print(f"rsshub_fetcher: {source['id']} failed: {source_status.safe_error(exc)}")
        else:
            interval = 6
            if not args.dry_run:
                appended += feed_common.append_jsonl_dedup(feed_common.INBOX_JSONL, rows)
                all_rows.extend(rows)
                source_status.record_fetch(source, ok=True, items=len(rows), interval_hours=interval)
            else:
                all_rows.extend(rows)
            print(f"rsshub_fetcher: {source['id']} -> {len(rows)} item(s); target interval {interval:g}h")
        time.sleep(DEFAULT_RSS_DELAY_SECS)

    if skipped:
        print(f"rsshub_fetcher: {skipped} source(s) waiting for schedule, batch capacity or retry cooldown.")
    if args.dry_run:
        print(f"rsshub_fetcher: dry-run, fetched {len(all_rows)} item(s) total, not writing.")
        return 0
    print(f"rsshub_fetcher: appended {appended} new item(s) to {feed_common.INBOX_JSONL.relative_to(feed_common.PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
