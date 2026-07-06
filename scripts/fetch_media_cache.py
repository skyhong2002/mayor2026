#!/usr/bin/env python3
"""Cache post images and candidate avatars as local WebP files.

Remote CDN URLs (especially fbcdn) are signed and expire within weeks, so the
pipeline snapshots the first image of every post into
`site/assets/feed-images/` and every candidate avatar into
`site/assets/source-avatars/`, both as WebP named by the SHA-256 of the
remote URL (first 20 hex chars) — the same convention the Harmonica-in-Taiwan
project uses. Lookup maps live under `state/` so already-cached URLs are
never re-downloaded.
"""

from __future__ import annotations

import hashlib
import io
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image

import feed_common

FEED_IMAGES_DIR = feed_common.PROJECT_ROOT / "site" / "assets" / "feed-images"
AVATARS_DIR = feed_common.PROJECT_ROOT / "site" / "assets" / "source-avatars"
IMAGE_CACHE_JSON = feed_common.PROJECT_ROOT / "state" / "feed_image_cache.json"
AVATAR_CACHE_JSON = feed_common.PROJECT_ROOT / "state" / "source_avatar_cache.json"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
REQUEST_TIMEOUT_SECS = 20
FEED_IMAGE_MAX_WIDTH = 1200
AVATAR_SIZE = 320
WEBP_QUALITY = 82

FB_CROP_SIZE_RE = re.compile(r"ctp=s\d+x\d+")
FB_SOURCE_MAX_RE = re.compile(r"cstp=mx(\d+)x(\d+)")


def request_larger_avatar(url: str) -> str:
    """Apify's Facebook `user.profilePic` links carry a `ctp=s50x50` crop
    parameter — a 50x50 thumbnail that looks blurry once shown at hero size.
    The signed URL isn't tied to this parameter, so bumping it up gets a
    sharper photo instead, capped at the source's own `cstp=mxWxH` ceiling
    when present (requesting past it 400s)."""
    if "fbcdn" not in url:
        return url
    wanted = AVATAR_SIZE * 2
    source_max = FB_SOURCE_MAX_RE.search(url)
    if source_max:
        wanted = min(wanted, int(source_max.group(1)), int(source_max.group(2)))
    return FB_CROP_SIZE_RE.sub(f"ctp=s{wanted}x{wanted}", url)


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECS) as response:
        return response.read()


def to_webp(raw: bytes, *, max_width: int, square: bool = False) -> tuple[bytes, float]:
    """Convert image bytes to WebP; returns (bytes, aspect_ratio w/h)."""
    image = Image.open(io.BytesIO(raw))
    image = image.convert("RGB")
    if square:
        side = min(image.size)
        left = (image.width - side) // 2
        top = (image.height - side) // 2
        image = image.crop((left, top, left + side, top + side))
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=WEBP_QUALITY)
    return buffer.getvalue(), image.width / image.height


def cache_image(url: str, target_dir: Path, *, max_width: int, square: bool = False) -> dict[str, Any] | None:
    filename = f"{url_hash(url)}.webp"
    target = target_dir / filename
    if target.exists():
        with Image.open(target) as existing:
            return {"file": filename, "aspect": round(existing.width / existing.height, 4)}
    try:
        raw = download(url)
        webp, aspect = to_webp(raw, max_width=max_width, square=square)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        print(f"fetch_media_cache: failed {url[:90]}...: {exc}")
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(webp)
    return {"file": filename, "aspect": round(aspect, 4)}


def first_image_url(media: list[Any]) -> str:
    for entry in media:
        if isinstance(entry, str) and entry.startswith("http"):
            return entry
    return ""


def cache_post_images() -> None:
    cache = feed_common.load_json(IMAGE_CACHE_JSON, {})
    posts = feed_common.read_jsonl(feed_common.CANDIDATES_JSONL)
    fetched = 0
    for post in posts:
        post_id = post["id"]
        if post_id in cache:
            continue
        url = first_image_url(post.get("media") or [])
        if not url:
            continue
        result = cache_image(url, FEED_IMAGES_DIR, max_width=FEED_IMAGE_MAX_WIDTH)
        # Cache failures too (as null) so expired CDN URLs aren't retried every run.
        cache[post_id] = result
        if result:
            fetched += 1
    feed_common.save_json_atomic(IMAGE_CACHE_JSON, cache)
    total = sum(1 for value in cache.values() if value)
    print(f"fetch_media_cache: {fetched} new post image(s) cached ({total} total).")


def cache_avatars() -> None:
    """Cache one avatar per watched account (profiles are keyed by account id)."""
    profiles = feed_common.load_json(feed_common.SOURCE_PROFILES_JSON, {})
    cache = feed_common.load_json(AVATAR_CACHE_JSON, {})
    fetched = 0
    for account_id, profile in profiles.items():
        url = profile.get("avatar_url")
        if not url:
            continue
        fetch_url = request_larger_avatar(url)
        cached = cache.get(account_id)
        if cached and cached.get("url") == url and cached.get("fetchUrl", url) == fetch_url:
            continue
        result = cache_image(fetch_url, AVATARS_DIR, max_width=AVATAR_SIZE, square=True)
        if result:
            cache[account_id] = {"url": url, "fetchUrl": fetch_url, "file": result["file"]}
            fetched += 1
    feed_common.save_json_atomic(AVATAR_CACHE_JSON, cache)
    print(f"fetch_media_cache: {fetched} new avatar(s) cached ({len(cache)} total).")


def prune_orphaned_files() -> None:
    """Delete cached files no longer referenced by either cache — old
    resolutions superseded by a re-fetch (e.g. after request_larger_avatar
    started asking for bigger crops), or posts/accounts dropped from the
    watchlist."""
    image_cache = feed_common.load_json(IMAGE_CACHE_JSON, {})
    avatar_cache = feed_common.load_json(AVATAR_CACHE_JSON, {})
    referenced = {v["file"] for v in image_cache.values() if v} | {v["file"] for v in avatar_cache.values() if v}
    removed = 0
    for directory in (FEED_IMAGES_DIR, AVATARS_DIR):
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.name not in referenced:
                path.unlink()
                removed += 1
    if removed:
        print(f"fetch_media_cache: pruned {removed} orphaned cached file(s).")


def main() -> int:
    cache_post_images()
    cache_avatars()
    prune_orphaned_files()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
