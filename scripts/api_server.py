#!/usr/bin/env python3
"""Query-parameter layer over the published static JSON API.

The site is a static snapshot (Caddy `file_server` on published/current). Requests
to /api/*.json or /feeds/*.json WITHOUT a query string keep being served as static
files; Caddy proxies requests that carry a query string, plus the two virtual
endpoints below, to this process. It only reads the published snapshot, so every
answer is consistent with the static files of the same release.

List endpoints accept:
  limit=N            return at most N items (N >= 0)
  offset=N           skip the first N matching items
  fields=a,b,c       keep only these keys in every item
plus endpoint-specific filters (see ENDPOINT_DOCS / docs/api.md).

Virtual (dynamic-only) endpoints:
  /api/posts.json                     every tracked post, newest first (full records)
  /api/elections/2026/candidates.json every 2026 local-election candidate as a flat list

Responses keep the static payload shape: the list is sliced, `count` becomes the
number of items returned, and `total` / `offset` / `limit` / `next` are added.
Standard library only (python3.9+). Deployed as container mayor2026-api; see deploy/sky-server/.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE = ROOT / "published" / "current"
DEFAULT_PORT = 8341
API_VERSION = 1
COMMON_PARAMS = ("limit", "offset", "fields")
POST_FILTERS = ("candidate", "city", "platform", "topic", "intent", "since", "until", "q")
ELECTION_FILTERS = ("county", "category", "township", "district", "districtKey", "village",
                    "party", "incumbent", "number", "q")
# Every query key this API understands. Unknown keys (e.g. ?v= cache busters) are ignored.
KNOWN_PARAMS = set(COMMON_PARAMS) | set(POST_FILTERS) | set(ELECTION_FILTERS) | {"sort"}


class ApiError(Exception):
    def __init__(self, status: int, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra


# ---------------------------------------------------------------------------
# Snapshot cache: parsed files keyed by (resolved release dir, relative path).
# A new release is a new directory, so entries never go stale; old releases are dropped.
# ---------------------------------------------------------------------------

class Snapshot:
    def __init__(self, site: Path) -> None:
        self.site = site
        self._lock = threading.Lock()
        self._release: Optional[Path] = None
        self._cache: Dict[str, Any] = {}

    def release(self) -> Path:
        real = self.site.resolve()
        with self._lock:
            if real != self._release:
                self._release = real
                self._cache = {}
        return real

    def cached(self, key: str, build: Callable[[Path], Any]) -> Any:
        release = self.release()
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        value = build(release)
        with self._lock:
            if self._release == release:
                self._cache[key] = value
        return value

    def json(self, rel: str) -> Any:
        def load(release: Path) -> Any:
            path = (release / rel).resolve()
            if release not in path.parents or not path.is_file():
                raise ApiError(404, "Not found", path="/" + rel)
            return json.loads(path.read_text(encoding="utf-8"))
        return self.cached("json:" + rel, load)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_ts(value: Any) -> Optional[dt.datetime]:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        ts = dt.datetime.fromisoformat(text)
    except ValueError:
        try:
            ts = dt.datetime.fromisoformat(text[:10])
        except ValueError:
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone(dt.timedelta(hours=8)))  # bare dates are Taiwan time
    return ts


def int_param(params: Dict[str, str], name: str) -> Optional[int]:
    raw = params.get(name)
    if raw is None or raw == "":
        return None
    if not re.fullmatch(r"\d{1,9}", raw.strip()):
        raise ApiError(400, f"`{name}` must be a non-negative integer", param=name, value=raw)
    return int(raw)


def split_values(raw: Optional[str]) -> List[str]:
    return [v.strip() for v in (raw or "").split(",") if v.strip()]


def bool_param(params: Dict[str, str], name: str) -> Optional[bool]:
    raw = params.get(name)
    if raw is None or raw == "":
        return None
    low = raw.strip().lower()
    if low in ("1", "true", "yes", "y"):
        return True
    if low in ("0", "false", "no", "n"):
        return False
    raise ApiError(400, f"`{name}` must be true or false", param=name, value=raw)


# ---------------------------------------------------------------------------
# Post filters
# ---------------------------------------------------------------------------

def candidate_cities(snap: Snapshot) -> Dict[str, str]:
    def build(_release: Path) -> Dict[str, str]:
        try:
            payload = snap.json("api/candidates.json")
        except ApiError:
            return {}
        return {c.get("id"): c.get("city") for c in payload.get("candidates") or [] if c.get("id")}
    return snap.cached("candidate-cities", build)


def post_filter(snap: Snapshot, params: Dict[str, str]) -> Callable[[Dict[str, Any]], bool]:
    candidates = set(split_values(params.get("candidate")))
    cities = set(split_values(params.get("city")))
    platforms = set(split_values(params.get("platform")))
    topics = set(split_values(params.get("topic")))
    intents = set(split_values(params.get("intent")))
    for intent in intents:
        if intent not in ("self_initiated", "responsive"):
            raise ApiError(400, "`intent` must be self_initiated or responsive", param="intent", value=intent)
    since = until = None
    for name in ("since", "until"):
        if params.get(name):
            ts = parse_ts(params[name])
            if ts is None:
                raise ApiError(400, f"`{name}` must be an ISO 8601 date or datetime", param=name, value=params[name])
            if name == "since":
                since = ts
            else:
                until = ts
    terms = [t.casefold() for t in (params.get("q") or "").split() if t]
    city_of = candidate_cities(snap) if cities else {}

    def match(post: Dict[str, Any]) -> bool:
        if candidates and post.get("candidateId") not in candidates:
            return False
        if cities and city_of.get(post.get("candidateId")) not in cities:
            return False
        if platforms and (post.get("platform") or "website") not in platforms:
            return False
        if topics:
            have = set(post.get("topics") or []) | set((post.get("topicScores") or {}).keys())
            if not topics & have:
                return False
        if intents:
            intent = post.get("postingIntent")
            kind = intent.get("type") if isinstance(intent, dict) else intent
            if kind not in intents:
                return False
        if since or until:
            ts = parse_ts(post.get("postedAt"))
            if ts is None or (since and ts < since) or (until and ts >= until):
                return False
        if terms:
            text = (post.get("text") or "").casefold()
            if not all(t in text for t in terms):
                return False
        return True
    return match


def all_posts(snap: Snapshot) -> List[Dict[str, Any]]:
    def build(release: Path) -> List[Dict[str, Any]]:
        posts: List[Dict[str, Any]] = []
        for path in sorted((release / "api" / "posts").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            posts.extend(payload.get("posts") or [])
        epoch0 = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
        posts.sort(key=lambda p: parse_ts(p.get("postedAt")) or epoch0, reverse=True)
        return posts
    return snap.cached("all-posts", build)


# ---------------------------------------------------------------------------
# Election candidates (flat list from the published CSV)
# ---------------------------------------------------------------------------

def election_rows(snap: Snapshot) -> List[Dict[str, Any]]:
    def build(release: Path) -> List[Dict[str, Any]]:
        path = release / "api" / "elections" / "2026" / "candidates.csv"
        if not path.is_file():
            raise ApiError(404, "Election data not published yet", path="/api/elections/2026/candidates.csv")
        index = snap.json("api/elections/2026/index.json")
        county_label = {c["id"]: c["label"] for c in index.get("counties") or []}
        category_label = {c["id"]: c.get("label") for c in index.get("categories") or []}
        rows: List[Dict[str, Any]] = []
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                out: Dict[str, Any] = dict(row)
                out["number"] = int(row["number"]) if row.get("number", "").isdigit() else None
                out["birthYear"] = int(row["birthYear"]) if (row.get("birthYear") or "").isdigit() else None
                out["incumbent"] = row.get("incumbent") == "Y"
                out["countyLabel"] = county_label.get(row["county"], row["county"])
                out["categoryLabel"] = category_label.get(row["category"], row["category"])
                rows.append({k: v for k, v in out.items() if v not in ("", None)})
        return rows
    return snap.cached("election-rows", build)


def election_filter(params: Dict[str, str]) -> Callable[[Dict[str, Any]], bool]:
    exact = {}
    for name in ("category", "districtKey"):
        vals = set(split_values(params.get(name)))
        if vals:
            exact[name] = vals
    counties = set(split_values(params.get("county")))
    townships = set(split_values(params.get("township")))
    contains = {name: params[name].strip() for name in ("district", "village", "party") if (params.get(name) or "").strip()}
    incumbent = bool_param(params, "incumbent")
    number = int_param(params, "number")
    terms = [t for t in (params.get("q") or "").split() if t]

    def match(row: Dict[str, Any]) -> bool:
        for name, vals in exact.items():
            if row.get(name) not in vals:
                return False
        if counties and row.get("county") not in counties and row.get("countyLabel") not in counties:
            return False
        if townships and row.get("township") not in townships:
            return False
        for name, needle in contains.items():
            if needle not in (row.get(name) or ""):
                return False
        if incumbent is not None and bool(row.get("incumbent")) != incumbent:
            return False
        if number is not None and row.get("number") != number:
            return False
        if terms:
            hay = " ".join(str(row.get(k) or "") for k in ("name", "district", "township", "village", "party"))
            if not all(t in hay for t in terms):
                return False
        return True
    return match


# ---------------------------------------------------------------------------
# Endpoint table
# ---------------------------------------------------------------------------

# (path regex, list key, allowed filters, kind). kind: "posts" | "elections" | "plain"
ENDPOINTS: List[Tuple[str, str, Tuple[str, ...], str]] = [
    (r"api/posts\.json", "posts", POST_FILTERS, "posts-all"),
    (r"api/latest\.json", "posts", POST_FILTERS, "posts"),
    (r"api/posts/[a-z0-9-]+\.json", "posts", POST_FILTERS, "posts"),
    (r"feeds/[a-z0-9-]+\.json", "posts", POST_FILTERS, "posts"),
    (r"api/topic-index\.json", "posts", POST_FILTERS, "posts"),
    (r"api/candidates\.json", "candidates", ("city",), "plain"),
    (r"api/sources\.json", "sources", ("candidate", "city"), "plain"),
    (r"api/spectrum\.json", "candidates", ("candidate", "city"), "plain"),
    (r"api/cities\.json", "cities", (), "plain"),
    (r"api/status\.json", "sources", ("candidate", "platform"), "plain"),
    (r"api/elections/2026/candidates\.json", "candidates", ELECTION_FILTERS, "elections"),
]


def plain_filter(params: Dict[str, str], allowed: Tuple[str, ...]) -> Callable[[Dict[str, Any]], bool]:
    wanted = {name: set(split_values(params.get(name))) for name in allowed if split_values(params.get(name))}
    keys = {"candidate": ("candidateId", "candidate_id", "id"), "city": ("city",), "platform": ("platform",)}

    def match(item: Dict[str, Any]) -> bool:
        for name, vals in wanted.items():
            if not any(item.get(k) in vals for k in keys[name] if k in item):
                return False
        return True
    return match


def resolve(rel: str) -> Optional[Tuple[str, Tuple[str, ...], str]]:
    for pattern, key, filters, kind in ENDPOINTS:
        if re.fullmatch(pattern, rel):
            return key, filters, kind
    return None


def handle(snap: Snapshot, rel: str, params: Dict[str, str], base_path: str) -> Any:
    if rel.startswith("api/elections/") and rel.endswith(".json") and rel != "api/elections/2026/candidates.json":
        given = sorted(set(params) & KNOWN_PARAMS)
        if given:
            raise ApiError(400, "Per-county election files are nested; use /api/elections/2026/candidates.json "
                                "with county=<id> and limit/offset instead.",
                           params=given, use="/api/elections/2026/candidates.json?county=taipei&limit=20")
        return snap.json(rel)
    spec = resolve(rel)
    if spec is None:
        given = sorted(set(params) & KNOWN_PARAMS)
        payload = snap.json(rel)  # 404 if missing
        if given:
            raise ApiError(400, "This endpoint is not a list and takes no parameters.", params=given)
        return payload
    key, filters, kind = spec
    allowed = set(COMMON_PARAMS) | set(filters) | ({"sort"} if kind == "elections" else set())
    unsupported = sorted((set(params) & KNOWN_PARAMS) - allowed)
    if unsupported:
        raise ApiError(400, "Unsupported parameter(s) for this endpoint", params=unsupported,
                       allowed=sorted(allowed))

    if kind == "posts-all":
        payload: Dict[str, Any] = {"version": API_VERSION}
        items = all_posts(snap)
    elif kind == "elections":
        index = snap.json("api/elections/2026/index.json")
        payload = {"schemaVersion": index.get("schemaVersion"), "generatedAt": index.get("generatedAt"),
                   "electionDay": index.get("electionDay")}
        items = election_rows(snap)
    else:
        source = snap.json(rel)
        if not isinstance(source, dict) or not isinstance(source.get(key), list):
            raise ApiError(500, "Unexpected payload shape", path="/" + rel)
        payload = {k: v for k, v in source.items() if k != key}
        items = source[key]

    if kind in ("posts", "posts-all"):
        if set(params) & set(POST_FILTERS):
            match = post_filter(snap, params)
            items = [p for p in items if match(p)]
    elif kind == "elections":
        if set(params) & set(ELECTION_FILTERS):
            match = election_filter(params)
            items = [r for r in items if match(r)]
        sort = params.get("sort")
        if sort:
            if sort not in ("number", "name"):
                raise ApiError(400, "`sort` must be number or name", param="sort", value=sort)
            items = sorted(items, key=lambda r: (r.get("county", ""), r.get("category", ""),
                                                 r.get("districtKey", ""),
                                                 r.get(sort) or (0 if sort == "number" else "")))
    elif set(params) & set(filters):
        match = plain_filter(params, filters)
        items = [i for i in items if match(i)]

    total = len(items)
    offset = int_param(params, "offset") or 0
    limit = int_param(params, "limit")
    page = items[offset:] if limit is None else items[offset:offset + limit]
    fields = split_values(params.get("fields"))
    if fields:
        page = [{k: item[k] for k in fields if k in item} for item in page]
    payload[key] = page
    payload["count"] = len(page)
    payload["total"] = total
    payload["offset"] = offset
    payload["limit"] = limit
    nxt = offset + len(page)
    if limit is not None and limit > 0 and nxt < total:
        query = dict(params)
        query["offset"] = str(nxt)
        payload["next"] = base_path + "?" + urlencode(query)
    else:
        payload["next"] = None
    return payload


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "mayor2026-api/1"
    snapshot: Snapshot  # set on the class by serve()

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet; Caddy keeps the access log
        if os.environ.get("MAYOR_API_LOG"):
            super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, head_only: bool = False, cache: str = "public, max-age=60") -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", cache)
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET(head_only=True)

    def do_GET(self, head_only: bool = False) -> None:  # noqa: N802
        raw = self.path
        try:  # http.server decodes the request line as latin-1; recover raw UTF-8 (unencoded CJK)
            raw = raw.encode("iso-8859-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        parts = urlsplit(raw)
        rel = parts.path.lstrip("/")
        params = {k: v[-1] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
        try:
            if rel == "healthz":
                body = {"ok": True, "release": self.snapshot.release().name}
            elif ".." in rel or not re.fullmatch(r"(api|feeds)/[A-Za-z0-9_./-]+\.json", rel):
                raise ApiError(404, "Not found", path=parts.path)
            else:
                body = handle(self.snapshot, rel, params, parts.path)
            data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._send(200, data, head_only)
        except ApiError as exc:
            err = {"error": exc.message, "status": exc.status, **exc.extra, "docs": "https://mayor2026.observe.tw/api/"}
            self._send(exc.status, json.dumps(err, ensure_ascii=False).encode("utf-8"), head_only, cache="no-store")
        except Exception as exc:  # pragma: no cover - last resort, keep the process alive
            print(f"api_server error on {self.path}: {exc!r}", file=sys.stderr)
            self._send(500, b'{"error":"Internal error","status":500}', head_only, cache="no-store")


def make_server(site: Path, host: str, port: int) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"snapshot": Snapshot(site)})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", type=Path, default=Path(os.environ.get("MAYOR_API_SITE", DEFAULT_SITE)))
    parser.add_argument("--host", default=os.environ.get("MAYOR_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MAYOR_API_PORT", DEFAULT_PORT)))
    args = parser.parse_args(argv)
    server = make_server(args.site, args.host, args.port)
    print(f"mayor2026 api_server on http://{args.host}:{args.port} serving {args.site}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
