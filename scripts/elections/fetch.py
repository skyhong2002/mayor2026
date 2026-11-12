#!/usr/bin/env python3
"""Polite, cached fetcher for election-commission (選委會) web sources.

Every network read for the 2026 candidate import goes through ``get()``:

* one request at a time across *all* processes on the host (``fcntl`` lock on
  a shared stamp file) with a minimum gap of ``MIN_INTERVAL`` seconds, so
  running several parsers in parallel never fans out against web.cec.gov.tw;
* a content cache under ``state/elections/cache`` (re-runs are offline);
* at most ``MAX_TRIES`` attempts with exponential backoff;
* a provenance log (``state/elections/fetch-log.jsonl``): URL, fetched-at
  (UTC ISO), HTTP status, byte size, sha256. The importer copies the rows it
  relies on into the committed source manifest.

CLI (debugging/discovery):

    python3 scripts/elections/fetch.py menu khec           # 115-related menu articles
    python3 scripts/elections/fetch.py article khec 65370  # title, date, attachments
    python3 scripts/elections/fetch.py walk ylec --since 20261015
    python3 scripts/elections/fetch.py lists ptec --since 20261110   # paginated section lists (incl. pinned)
    python3 scripts/elections/fetch.py file <fileId>.<ext> # cached path
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = Path(os.environ.get("MAYOR_ELECTIONS_STATE", PROJECT_ROOT / "state" / "elections"))
CACHE_DIR = STATE_DIR / "cache"
FETCH_LOG = STATE_DIR / "fetch-log.jsonl"
# Shared across worktrees/processes on this host on purpose: the limit is per host.
LOCK_PATH = Path(os.environ.get("MAYOR_ELECTIONS_LOCK", Path.home() / ".cache" / "mayor2026-cec-fetch.lock"))

BASE = "https://web.cec.gov.tw"
USER_AGENT = "Mozilla/5.0 (compatible; observe-tw-candidate-import; +https://mayor2026.observe.tw/about/)"
MIN_INTERVAL = float(os.environ.get("MAYOR_ELECTIONS_MIN_INTERVAL", "1.5"))
MAX_TRIES = 3
TIMEOUT = 60

# 22 直轄市、縣（市）選舉委員會 web routes on web.cec.gov.tw.
COMMISSIONS = {
    "mect": "臺北市", "tpcec": "新北市", "tyec": "桃園市", "tcec": "臺中市", "tnec": "臺南市", "khec": "高雄市",
    "ilec": "宜蘭縣", "hccec": "新竹縣", "mlec": "苗栗縣", "chec": "彰化縣", "ntec": "南投縣", "ylec": "雲林縣",
    "cycec": "嘉義縣", "ptec": "屏東縣", "ttec": "臺東縣", "hlec": "花蓮縣", "phec": "澎湖縣", "klec": "基隆市",
    "hcec": "新竹市", "cyec": "嘉義市", "kmec": "金門縣", "lcec": "連江縣",
}


class FetchError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / digest[:2] / digest


def _throttle_and_fetch(url: str) -> tuple[int, bytes]:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            lock.seek(0)
            raw = lock.read().strip()
            last = float(raw) if raw else 0.0
            wait = MIN_INTERVAL - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    return resp.status, resp.read()
            except urllib.error.HTTPError as exc:
                return exc.code, exc.read() if exc.fp else b""
        finally:
            lock.seek(0)
            lock.truncate()
            lock.write(str(time.time()))
            lock.flush()
            fcntl.flock(lock, fcntl.LOCK_UN)


def get(url: str, *, refresh: bool = False) -> bytes:
    """Return the body of ``url`` (cached). Raises FetchError after MAX_TRIES."""
    path = _cache_path(url)
    meta_path = path.with_suffix(".json")
    if path.exists() and not refresh:
        return path.read_bytes()
    last_err = ""
    for attempt in range(MAX_TRIES):
        try:
            status, body = _throttle_and_fetch(url)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            status, body, last_err = 0, b"", repr(exc)
        if status == 200:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            meta = {"url": url, "fetchedAt": utc_now(), "status": status, "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest()}
            meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            with FETCH_LOG.open("a", encoding="utf-8") as log:
                log.write(json.dumps(meta, ensure_ascii=False) + "\n")
            return body
        if 400 <= status < 500 and status != 429:
            raise FetchError(f"{url}: HTTP {status}")
        last_err = last_err or f"HTTP {status}"
        time.sleep(min(60, 5 * (2 ** attempt)))
    raise FetchError(f"{url}: gave up after {MAX_TRIES} tries ({last_err})")


def meta(url: str) -> dict[str, Any]:
    """Provenance of a cached URL (fetchedAt/sha256); {} if never fetched."""
    path = _cache_path(url).with_suffix(".json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def get_json(url: str, *, refresh: bool = False) -> Any:
    return json.loads(get(url, refresh=refresh).decode("utf-8"))


# -- web.cec.gov.tw CMS helpers ------------------------------------------------

def article_url(route: str, article_id: str | int) -> str:
    """Human-facing article page (what we cite as the source)."""
    return f"{BASE}/{route}/article/{article_id}"


def file_url(file_name: str) -> str:
    """``<fileId>.<ext>`` → public download URL."""
    return f"{BASE}/api/file/{file_name}"


def article(route: str, article_id: str | int, *, refresh: bool = False) -> dict[str, Any]:
    data = get_json(f"{BASE}/api/{route}/article/{article_id}", refresh=refresh).get("data") or {}
    data["files"] = [f"{f['fileId']}.{f['fileExt']}" for f in data.get("fileList") or []]
    data["fileNames"] = {f"{f['fileId']}.{f['fileExt']}": f.get("fileName") for f in data.get("fileList") or []}
    return data


def article_text(data: dict[str, Any]) -> str:
    """Plain text of an article's HTML blocks (for press-release style lists)."""
    import html as html_mod
    try:
        blocks = json.loads(data.get("content") or "{}").get("content") or []
    except ValueError:
        blocks = []
    parts = []
    for block in blocks:
        raw = block.get("content") or ""
        raw = re.sub(r"</(p|div|li|tr|h\d)>|<br\s*/?>", "\n", raw, flags=re.I)
        raw = re.sub(r"</t[dh]>", "\t", raw, flags=re.I)
        parts.append(html_mod.unescape(re.sub(r"<[^>]+>", "", raw)))
    text = "\n".join(parts).replace("\xa0", " ")
    return re.sub(r"[ \t]*\n[ \t\n]*", "\n", text).strip()


def menu_articles(route: str, *, refresh: bool = False) -> list[dict[str, str]]:
    """Every article (directType 005) linked from the commission's menu tree."""
    payload = get_json(f"{BASE}/api/{route}/home/menu", refresh=refresh).get("data")
    out: list[dict[str, str]] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if node.get("directType") == "005":
                out.append({"id": str(node.get("directPath")), "path": node.get("directMessage") or node.get("name") or ""})
            for value in node.values():
                if isinstance(value, (list, dict)):
                    walk(value)

    walk(payload)
    return out


def walk_bulletins(route: str, since: str = "20261015", limit: int = 120, *, refresh: bool = False) -> list[dict[str, Any]]:
    """Follow each home bulletin section's nextPage chain back to ``since`` (yyyymmdd)."""
    sections = get_json(f"{BASE}/api/{route}/home/bulletin", refresh=refresh)["data"]["bulletinList"]
    seen: dict[str, dict[str, Any]] = {}
    for section in sections:
        ids = [a["articleId"] for a in section.get("articleList") or []]
        if not ids:
            continue
        cur: str | None = str(max(ids))
        steps = 0
        while cur and cur not in seen and steps < limit:
            steps += 1
            data = article(route, cur)
            seen[cur] = {"id": cur, "section": section.get("name"), "date": data.get("beginTime", ""),
                         "title": data.get("title", ""), "files": data["files"], "fileNames": data["fileNames"]}
            if (data.get("beginTime") or "")[:8] and data["beginTime"][:8] < since:
                break
            cur = data.get("nextPage")
    return sorted(seen.values(), key=lambda a: a["date"], reverse=True)


def list_sections(route: str) -> list[tuple[str, str]]:
    """(menu id, path) of every article-list section (directType 004) in the menu."""
    payload = get_json(f"{BASE}/api/{route}/home/menu").get("data")
    out: list[tuple[str, str]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item, path)
        elif isinstance(node, dict):
            here = f"{path}/{node.get('name') or ''}"
            if node.get("directType") == "004":
                out.append((str(node.get("directPath")), here))
            for value in node.values():
                if isinstance(value, (list, dict)):
                    walk(value, here)

    walk(payload, "")
    return out


def list_articles(route: str, section_id: str, since: str = "20261015", *, refresh: bool = True) -> list[dict[str, str]]:
    """Paginated article list of one menu section, newest first, back to ``since``.
    Unlike the bulletin chain this also reaches pinned articles."""
    out: list[dict[str, str]] = []
    page = 1
    while True:
        data = get_json(f"{BASE}/api/{route}/article/list?id={section_id}&page={page}", refresh=refresh).get("data") or {}
        stop = False
        for item in data.get("articleList") or []:
            begin = str(item.get("beginTime") or "")
            if begin and begin[:8] < since:
                stop = True
                continue
            out.append({"id": str(item.get("directPath")), "date": begin[:8], "title": item.get("directName") or ""})
        if stop or page >= int((data.get("pages") or {}).get("totalPage") or 1):
            return out
        page += 1


def cached_file(file_name: str) -> Path:
    """Download an attachment (cached) and return a local path with its real extension."""
    url = file_url(file_name)
    get(url)
    src = _cache_path(url)
    dst = CACHE_DIR / "files" / file_name
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(src, dst)
        except OSError:
            dst.write_bytes(src.read_bytes())
    return dst


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, *rest = argv
    if cmd == "menu":
        kw = re.compile(r"號次|候選人|公報|名額|選舉區")
        for a in menu_articles(rest[0]):
            if ("115" in a["path"] or "屆" in a["path"]) and kw.search(a["path"]):
                print(a["id"], a["path"], sep="\t")
    elif cmd == "article":
        data = article(rest[0], rest[1])
        print(data.get("beginTime"), data.get("title"))
        for name in data["files"]:
            print("  FILE", name, data["fileNames"][name])
        print(article_text(data)[:4000])
    elif cmd == "walk":
        since = rest[rest.index("--since") + 1] if "--since" in rest else "20261015"
        for a in walk_bulletins(rest[0], since):
            print(a["id"], a["date"], a["section"], a["title"], ";".join(f"{f}|{a['fileNames'][f]}" for f in a["files"]), sep="\t")
    elif cmd == "lists":
        since = rest[rest.index("--since") + 1] if "--since" in rest else "20261015"
        kw = re.compile(r"號次|候選人|公報|名單")
        for sid, path in list_sections(rest[0]):
            if not ("115" in path or "最新" in path or "公告" in path or "新聞" in path):
                continue
            for a in list_articles(rest[0], sid, since):
                if kw.search(a["title"]):
                    print(sid, a["id"], a["date"], a["title"], sep="\t")
    elif cmd == "file":
        print(cached_file(rest[0]))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
