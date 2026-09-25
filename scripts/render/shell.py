"""Shared shell for every page: <head>, app shell (sidebar / rail / tab bar),
footer, icons, formatting helpers and the canonical post card.

Everything here is pure standard library. Page modules import from here and
never hand-write the shell. Keep ``render_post`` byte-for-byte isomorphic with
``MO.postHTML`` in site/assets/shell.js.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = PROJECT_ROOT / "site"
ASSETS_DIR = SITE_ROOT / "assets"

SITE_NAME = "2026 市長官方來源觀測站"
SITE_SHORT = "市長觀測站"
BASE_URL = "https://mayor2026.observe.tw"
GITHUB_URL = "https://github.com/skyhong2002/mayor2026"
REPORT_URL = "https://github.com/skyhong2002/mayor2026/issues/new/choose"
DEFAULT_DESCRIPTION = (
    "獨立、非官方的公開資料觀測站：彙整 2026 六都市長候選人在官方帳號的公開發文，"
    "依議題與發文動機分類，所有內容皆連回原文。"
)
TPE = dt.timezone(dt.timedelta(hours=8), "Asia/Taipei")

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

CITY_ORDER = ["taipei", "new-taipei", "taoyuan", "taichung", "tainan", "kaohsiung"]
CITY_LABELS = {
    "taipei": "臺北市", "new-taipei": "新北市", "taoyuan": "桃園市",
    "taichung": "臺中市", "tainan": "臺南市", "kaohsiung": "高雄市",
}
CITY_SHORT = {
    "taipei": "臺北", "new-taipei": "新北", "taoyuan": "桃園",
    "taichung": "臺中", "tainan": "臺南", "kaohsiung": "高雄",
}
PARTY_SLUGS = {
    "民主進步黨": "dpp", "民進黨": "dpp",
    "中國國民黨": "kmt", "國民黨": "kmt",
    "台灣民眾黨": "tpp", "臺灣民眾黨": "tpp", "民眾黨": "tpp",
    "司法改革黨": "jrp",
}
TOPIC_SLUGS = {
    "交通": "transport", "住宅": "housing", "社福": "welfare", "環境": "environment",
    "教育": "education", "經濟": "economy", "治安": "safety", "醫療": "health",
    "競選": "campaign", "體育": "sports", "文化觀光": "culture", "兩岸外交": "cross-strait",
    "防災": "disaster", "議會監督": "oversight", "生活": "life",
}
SLUG_TOPICS = {slug: topic for topic, slug in TOPIC_SLUGS.items()}
PLATFORM_LABELS = {
    "website": "官網", "facebook": "Facebook", "instagram": "Instagram", "threads": "Threads",
    "youtube": "YouTube", "x": "X", "line_oa": "LINE 官方帳號", "line_openchat": "LINE 社群",
    "tiktok": "TikTok", "podcast": "Podcast",
}
PLATFORM_ICON = {"line_oa": "line", "line_openchat": "line"}
INTENT_LABELS = {"self_initiated": "主動發文", "responsive": "回應他方觀點"}

# Sidebar / tab bar. ``tab`` = shown in the mobile bottom bar; the rest move
# into the 更多 menu on phones. ``match`` = page_ids that highlight the item.
nav_items: list[dict[str, Any]] = [
    {"id": "home", "label": "最新", "short": "最新", "href": "/", "icon": "home", "tab": True, "match": ["home"]},
    {"id": "spectrum", "label": "議題光譜", "short": "光譜", "href": "/spectrum/", "icon": "spectrum", "tab": True, "match": ["spectrum", "topic"]},
    {"id": "policy", "label": "議題選擇器", "short": "選擇器", "href": "/policy-match/", "icon": "match", "tab": True, "match": ["policy"]},
    {"id": "source", "label": "候選人", "short": "候選人", "href": "/source/", "icon": "people", "tab": True, "match": ["source", "directory", "candidate", "source-detail"]},
    {"id": "search", "label": "搜尋", "short": "搜尋", "href": "/search/", "icon": "search", "tab": False, "match": ["search"]},
    {"id": "feeds", "label": "訂閱", "short": "訂閱", "href": "/feeds/", "icon": "rss", "tab": False, "match": ["feeds"]},
    {"id": "status", "label": "資料狀態", "short": "狀態", "href": "/status/", "icon": "status", "tab": False, "match": ["status"]},
    {"id": "about", "label": "關於", "short": "關於", "href": "/about/", "icon": "about", "tab": False, "match": ["about"]},
]

# ---------------------------------------------------------------------------
# Icons (single source of truth; shell.js reads the generated assets/icons.js)
# ---------------------------------------------------------------------------

_STROKE = {
    "home": '<path d="M3.5 10.2 12 3.5l8.5 6.7V19a1.5 1.5 0 0 1-1.5 1.5h-4.2v-6h-5.6v6H5A1.5 1.5 0 0 1 3.5 19z"/>',
    "spectrum": '<path d="M4.5 20V11M9.5 20V4.5M14.5 20v-6.5M19.5 20V8"/>',
    "match": '<path d="M10 6.5h10M10 12h10M10 17.5h10"/><path d="m3.8 6.4 1.4 1.4 2.6-2.8M3.8 11.9l1.4 1.4 2.6-2.8M3.8 17.4l1.4 1.4 2.6-2.8"/>',
    "people": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.1-5.6 6.5-5.6s5.9 2 6.5 5.6"/><path d="M15.8 4.7a3.4 3.4 0 0 1 0 6.6M17.8 14.7c2 .7 3.2 2.4 3.7 5.3"/>',
    "search": '<circle cx="11" cy="11" r="6.8"/><path d="m20 20-4.2-4.2"/>',
    "rss": '<path d="M5 11.5a7.5 7.5 0 0 1 7.5 7.5M5 5a14 14 0 0 1 14 14"/><circle cx="6" cy="18" r="1.4" fill="currentColor" stroke="none"/>',
    "status": '<path d="M3 12.5h4l2.5-6.5 5 13 2.5-6.5h4"/>',
    "about": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6v.2"/>',
    "more": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6 6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"/>',
    "moon": '<path d="M20 14.6A8 8 0 0 1 9.4 4 8 8 0 1 0 20 14.6z"/>',
    "system": '<rect x="3" y="4" width="18" height="12.5" rx="2"/><path d="M8.5 20.5h7M12 16.5v4"/>',
    "share": '<path d="M12 14.5V3.5M7.8 7.5 12 3.3l4.2 4.2"/><path d="M5 11.5v7A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5v-7"/>',
    "external": '<path d="M14 4h6v6M20 4l-8.5 8.5"/><path d="M18 14v4.5A1.5 1.5 0 0 1 16.5 20h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10"/>',
    "json": '<path d="M8.5 4H7.4A2.4 2.4 0 0 0 5 6.4v3.2A2.4 2.4 0 0 1 2.6 12 2.4 2.4 0 0 1 5 14.4v3.2A2.4 2.4 0 0 0 7.4 20h1.1M15.5 4h1.1A2.4 2.4 0 0 1 19 6.4v3.2a2.4 2.4 0 0 0 2.4 2.4 2.4 2.4 0 0 0-2.4 2.4v3.2a2.4 2.4 0 0 1-2.4 2.4h-1.1"/>',
    "filter": '<path d="M4 5.5h16M7 12h10M10 18.5h4"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
    "chevron": '<path d="m6 9 6 6 6-6"/>',
    "website": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.4 2.5 3.7 5.5 3.7 9s-1.3 6.5-3.7 9M12 3C9.6 5.5 8.3 8.5 8.3 12s1.3 6.5 3.7 9"/>',
    "podcast": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
}
_FILL = {
    "facebook": '<path d="M14 13.5h2.5l1-4H14v-2c0-1.03 0-2 2-2h1.5V2.14c-.33-.04-1.56-.14-2.86-.14C11.93 2 10 3.66 10 6.7V9.5H7v4h3V22h4z"/>',
    "instagram": '<path d="M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm0-2a5 5 0 1 1 0 10 5 5 0 0 1 0-10zm6.5-.25a1.25 1.25 0 1 1-2.5 0 1.25 1.25 0 0 1 2.5 0zM12 4c-2.47 0-2.88.01-4.03.06-.78.04-1.3.14-1.8.33-.43.17-.74.37-1.08.7-.33.34-.53.65-.7 1.08-.19.5-.3 1.02-.33 1.8C4.01 9.08 4 9.46 4 12c0 2.47.01 2.88.06 4.03.04.78.14 1.31.33 1.8.17.43.37.75.7 1.08.34.33.65.53 1.08.7.5.19 1.02.3 1.8.33 1.1.05 1.49.06 4.03.06 2.47 0 2.88-.01 4.03-.06.78-.04 1.3-.14 1.8-.33.43-.17.74-.37 1.08-.7.33-.34.53-.65.7-1.08.19-.5.3-1.02.33-1.8.05-1.1.06-1.49.06-4.03 0-2.47-.01-2.88-.06-4.03-.04-.78-.14-1.31-.33-1.8a2.9 2.9 0 0 0-.7-1.08 2.9 2.9 0 0 0-1.08-.7c-.49-.19-1.02-.3-1.8-.33C14.93 4.01 14.54 4 12 4zm0-2c2.72 0 3.06.01 4.12.06 1.07.05 1.8.22 2.43.46.66.26 1.22.6 1.77 1.16.56.55.9 1.11 1.16 1.77.24.64.41 1.36.46 2.43.05 1.06.06 1.4.06 4.12s-.01 3.06-.06 4.12c-.05 1.07-.22 1.8-.46 2.43a4.9 4.9 0 0 1-1.16 1.77c-.55.55-1.11.9-1.77 1.15-.64.25-1.36.42-2.43.47-1.06.05-1.4.06-4.12.06s-3.06-.01-4.12-.06c-1.07-.05-1.79-.22-2.43-.47a4.9 4.9 0 0 1-1.77-1.15 4.9 4.9 0 0 1-1.15-1.77c-.25-.64-.42-1.36-.47-2.43C2.01 15.06 2 14.72 2 12s.01-3.06.06-4.12c.05-1.07.22-1.79.47-2.43.25-.66.6-1.22 1.15-1.77.56-.56 1.11-.9 1.77-1.16.64-.24 1.36-.41 2.43-.46C8.94 2.01 9.28 2 12 2z"/>',
    "threads": '<path d="M12.18 1.41c-3.09.02-5.48 1.06-7.09 3.11C3.67 6.33 2.93 8.86 2.91 12c.02 3.15.76 5.67 2.18 7.48 1.61 2.04 4.01 3.09 7.1 3.11 2.75-.02 4.7-.74 6.3-2.34 2.11-2.1 2.05-4.74 1.35-6.36-.53-1.24-1.57-2.23-2.97-2.84-.18-2.98-1.86-4.72-4.62-4.74-1.63-.01-3.1.72-4 2.09l1.65 1.13c.53-.8 1.38-1.19 2.34-1.18 1.39 0 2.3.77 2.55 2.12-.77-.12-1.6-.16-2.48-.1-2.64.15-4.37 1.71-4.25 3.87.12 2.27 2.31 3.5 4.39 3.38 2.49-.13 3.97-1.97 4.33-4.32.57.38 1 .85 1.24 1.41.44 1.03.47 2.72-.92 4.1-1.21 1.21-2.68 1.74-4.91 1.76-2.47-.02-4.33-.81-5.54-2.34C5.52 16.77 4.93 14.69 4.9 12c.03-2.69.62-4.77 1.75-6.21 1.2-1.54 3.06-2.33 5.54-2.35 2.49.02 4.38.82 5.64 2.36.69.85 1.12 1.87 1.41 2.91l1.94-.52c-.36-1.34-.94-2.61-1.82-3.69-1.65-2.03-4.08-3.07-7.18-3.09zm.24 10.97c.88-.05 1.7 0 2.43.16-.14 1.57-.79 2.94-2.51 3.04-1.11.06-2.24-.44-2.29-1.46-.04-.77.52-1.63 2.37-1.74z"/>',
    "youtube": '<path d="M12.24 4c.54 0 1.87.02 3.29.07l.5.02c1.43.07 2.86.19 3.57.38.94.27 1.69 1.04 1.94 2.03.4 1.56.45 4.6.45 5.34v.32c0 .74-.05 3.78-.45 5.34-.25.99-1 1.76-1.94 2.02-.71.2-2.14.31-3.57.38l-.5.02c-1.42.06-2.75.07-3.29.07h-.49c-1.13 0-5.86-.06-7.36-.47-.94-.27-1.69-1.04-1.94-2.02C2.05 15.94 2 12.9 2 12.16v-.32c0-.74.05-3.78.45-5.34.25-.99 1-1.76 1.94-2.03C5.9 4.06 10.62 4 11.75 4zM10 8.5v7l6-3.5z"/>',
    "x": '<path d="M10.49 14.65 15.25 21h7l-7.86-10.48L20.93 3h-2.65l-5.12 5.89L8.75 3h-7l7.51 10.01L2.32 21h2.65zM16.25 19 5.75 5h2l10.5 14z"/>',
    "line": '<path d="M12 3C6.48 3 2 6.63 2 11.1c0 4 3.55 7.35 8.35 7.99.33.07.77.21.88.49.1.25.07.64.03.9l-.14.85c-.04.25-.2.99.87.54 1.07-.45 5.76-3.39 7.86-5.8C21.3 14.47 22 12.86 22 11.1 22 6.63 17.52 3 12 3z"/>',
    "tiktok": '<path d="M16.6 3c.35 2.3 1.8 3.8 4.1 4v3.1c-1.5.1-2.84-.38-4.1-1.18v6.23c0 3.97-3.4 6.4-6.84 5.78-4.28-.78-5.74-6.2-2.66-9 1.2-1.1 2.8-1.5 4.47-1.3v3.2c-.52-.13-1.04-.18-1.57-.08-1.5.3-2.32 1.8-1.82 3.2.58 1.62 2.9 2 3.96.62.4-.52.53-1.1.53-1.73V3z"/>',
}
ICON_NAMES = sorted([*_STROKE, *_FILL])


def icon(name: str, cls: str = "icon") -> str:
    """Inline SVG for ``name`` (see ICON_NAMES). Unknown names fall back to website."""
    name = PLATFORM_ICON.get(name, name)
    if name in _FILL:
        return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" '
                f'focusable="false">{_FILL[name]}</svg>')
    body = _STROKE.get(name, _STROKE["website"])
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{body}</svg>')


def icons_js() -> str:
    """Source of site/assets/icons.js (generated by generate_site_pages)."""
    payload = {name: icon(name) for name in ICON_NAMES}
    return ("/* Generated by scripts/render/shell.py — do not edit. */\n"
            "window.MO_ICONS = " + json.dumps(payload, ensure_ascii=False, indent=0) + ";\n")


def write_icons_js() -> None:
    path = ASSETS_DIR / "icons.js"
    text = icons_js()
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
    asset_hash.cache_clear()

# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

_ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}


def esc(value: Any) -> str:
    """HTML-escape text and attribute values (same table as MO.esc)."""
    if value is None:
        return ""
    return re.sub(r"[&<>\"']", lambda m: _ESC[m.group(0)], str(value))


_SAFE_SCHEME_RE = re.compile(r"^https?://", re.I)


def safe_url(value: Any, *, internal: bool = True) -> str:
    """Return a link target that is safe to put in href/src, or "".

    Accepts absolute http(s) URLs and (when ``internal``) root-absolute site
    paths ("/x/", not "//host"). Everything else (javascript:, data:, relative
    paths, protocol-relative URLs) is rejected. The result still needs esc().
    """
    if value is None:
        return ""
    url = str(value).strip()
    if not url or any(ord(c) < 0x20 or ord(c) == 0x7f for c in url):
        return ""
    if _SAFE_SCHEME_RE.match(url):
        return url
    if internal and url.startswith("/") and not url.startswith("//") and not url.startswith("/\\"):
        return url
    return ""


def json_for_script(value: Any, **kwargs: Any) -> str:
    """json.dumps for inline <script> blocks: no literal <, >, & or U+2028/9."""
    kwargs.setdefault("ensure_ascii", False)
    text = json.dumps(value, **kwargs)
    return (text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def read_json(path: Path | str, default: Any = None) -> Any:
    path = Path(path)
    if not path.is_absolute():
        path = SITE_ROOT / path
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_text(path: Path | str, text: str) -> Path:
    """Write a file under site/ (relative paths are site-relative), creating dirs."""
    path = Path(path)
    if not path.is_absolute():
        path = SITE_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_page(route: str, html: str) -> Path:
    """Write ``html`` for a root route such as "/spectrum/" → site/spectrum/index.html."""
    rel = route.strip("/")
    return write_text(SITE_ROOT / rel / "index.html" if rel else SITE_ROOT / "index.html", html)


def asset_abs(path: str | None) -> str | None:
    """"assets/x.webp" → "/assets/x.webp"; absolute/http URLs pass through."""
    if not path:
        return None
    if path.startswith(("http://", "https://", "/", "data:")):
        return path
    return "/" + path.lstrip("./")


@lru_cache(maxsize=1)
def asset_hash() -> str:
    """10-hex sha256 over every shipped CSS/JS asset (tokens, styles, shell, icons, pages/*)."""
    digest = hashlib.sha256()
    files = [ASSETS_DIR / n for n in ("tokens.css", "styles.css", "shell.js", "icons.js")]
    files += sorted((ASSETS_DIR / "pages").glob("*")) if (ASSETS_DIR / "pages").is_dir() else []
    for file in files:
        if file.is_file():
            digest.update(file.name.encode())
            digest.update(file.read_bytes())
    return digest.hexdigest()[:10]


def asset_url(path: str) -> str:
    """"styles.css" / "assets/pages/home.js" / "/assets/x" → "/assets/…?v=<hash>"."""
    clean = path.lstrip("/")
    if not clean.startswith("assets/"):
        clean = "assets/" + clean
    return f"/{clean}?v={asset_hash()}"


def party_slug(party: str | None) -> str:
    return PARTY_SLUGS.get((party or "").strip(), "none")


def city_label(slug: str | None, short: bool = True) -> str:
    return (CITY_SHORT if short else CITY_LABELS).get(slug or "", slug or "")


def topic_slug(topic: str) -> str:
    return TOPIC_SLUGS.get(topic, "life")

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

def parse_ts(value: Any) -> dt.datetime | None:
    """Parse "…Z" / "…+00:00" / "…+08:00" (naive = UTC). None/garbage → None."""
    if not value:
        return None
    if isinstance(value, dt.datetime):
        parsed = value
    else:
        try:
            parsed = dt.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def epoch(value: Any) -> int:
    parsed = parse_ts(value)
    return int(parsed.timestamp()) if parsed else 0


def fmt_time_tpe(value: Any, with_year: bool | None = None) -> str:
    """"9/25 12:00" in Asia/Taipei; prefixes the year when it differs from now."""
    parsed = parse_ts(value)
    if not parsed:
        return ""
    local = parsed.astimezone(TPE)
    if with_year is None:
        with_year = local.year != dt.datetime.now(TPE).year
    prefix = f"{local.year}/" if with_year else ""
    return f"{prefix}{local.month}/{local.day} {local:%H:%M}"


def fmt_date_tpe(value: Any) -> str:
    parsed = parse_ts(value)
    if not parsed:
        return ""
    local = parsed.astimezone(TPE)
    return f"{local.year}/{local.month}/{local.day}"


def rel_time_tpe(value: Any, now: dt.datetime | None = None) -> str:
    """Same rules as MO.relTime: 剛剛 / N 分鐘前 / N 小時前 / 昨天 / N 天前 / M/D / YYYY/M/D."""
    parsed = parse_ts(value)
    if not parsed:
        return ""
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(TPE)
    local = parsed.astimezone(TPE)
    seconds = (now - local).total_seconds()
    if seconds < 60:
        return "剛剛"
    if seconds < 3600:
        return f"{int(seconds // 60)} 分鐘前"
    if seconds < 86400:
        return f"{int(seconds // 3600)} 小時前"
    days = (now.date() - local.date()).days
    if days <= 1:
        return "昨天"
    if days < 7:
        return f"{days} 天前"
    if local.year != now.year:
        return f"{local.year}/{local.month}/{local.day}"
    return f"{local.month}/{local.day}"

# ---------------------------------------------------------------------------
# Small components
# ---------------------------------------------------------------------------

def _attrs(attrs: Mapping[str, Any] | None) -> str:
    out = []
    for key, value in (attrs or {}).items():
        if value is None or value is False:
            continue
        out.append(f" {key}" if value is True else f' {key}="{esc(value)}"')
    return "".join(out)


def render_avatar(entity: Mapping[str, Any] | None, size: str = "sm", href: str | None = None,
                  cls: str = "", label: str | None = None) -> str:
    """Round avatar with a party ring. ``entity`` = candidate or account dict
    (uses avatarUrl, name/displayName, party). size ∈ sm (36) | md (48) | lg (88)."""
    entity = entity or {}
    name = entity.get("name") or entity.get("displayName") or entity.get("handle") or ""
    src = asset_abs(entity.get("avatarUrl"))
    px = {"xs": 24, "sm": 36, "md": 48, "lg": 88}.get(size, 36)
    inner = (f'<img src="{esc(src)}" alt="" width="{px}" height="{px}" loading="lazy" decoding="async">'
             if src else f'<span class="avatar-initial" aria-hidden="true">{esc(name[:1])}</span>')
    classes = " ".join(c for c in (cls, "avatar", f"avatar-{size}") if c)
    party = party_slug(entity.get("party"))
    if href:
        aria = esc(label if label is not None else name)
        return (f'<a class="{classes}" data-party="{party}" href="{esc(href)}" aria-label="{aria}" '
                f'tabindex="-1">{inner}</a>')
    return f'<span class="{classes}" data-party="{party}">{inner}</span>'


def render_chip(label: str, href: str | None = None, *, soft: bool = False, cls: str = "",
                count: int | str | None = None, pressed: bool | None = None,
                party: str | None = None, city: str | None = None, icon_name: str | None = None,
                attrs: Mapping[str, Any] | None = None) -> str:
    """Pill chip. ``href`` → <a>; ``pressed`` not None → <button aria-pressed>; else <span>.
    ``party`` adds .chip-party + data-party slug; ``city`` adds .chip-city + data-city."""
    classes = ["chip-soft" if soft else "chip"]
    extra: dict[str, Any] = dict(attrs or {})
    if party is not None:
        classes.append("chip-party")
        extra["data-party"] = party_slug(party)
    if city is not None:
        classes.append("chip-city")
        extra["data-city"] = city
    if cls:
        classes.append(cls)
    body = (icon(icon_name) if icon_name else "") + f"<span>{esc(label)}</span>"
    if count is not None:
        body += f'<span class="chip-count">{esc(count)}</span>'
    cattr = f' class="{" ".join(classes)}"'
    if href:
        return f'<a{cattr} href="{esc(href)}"{_attrs(extra)}>{body}</a>'
    if pressed is not None:
        extra["aria-pressed"] = "true" if pressed else "false"
        return f'<button{cattr} type="button"{_attrs(extra)}>{body}</button>'
    return f"<span{cattr}{_attrs(extra)}>{body}</span>"


def render_badge(state: str, label: str) -> str:
    """Status badge; state ∈ ok|warn|error|paused|pending."""
    return f'<span class="badge-status" data-state="{esc(state)}">{esc(label)}</span>'


def render_empty(title: str, body: str = "", action_html: str = "") -> str:
    parts = [f'<p class="empty-title">{esc(title)}</p>']
    if body:
        parts.append(f'<p class="empty-body">{esc(body)}</p>')
    return f'<div class="empty">{"".join(parts)}{action_html}</div>'

# ---------------------------------------------------------------------------
# Post card (keep isomorphic with MO.postHTML)
# ---------------------------------------------------------------------------

URL_RE = re.compile(r"https?://[^\s<>\"'「」『』（）【】，。、！？]+")
_URL_TRAIL = ".,;:!?)]}'\""


def _link_label(url: str) -> str:
    label = re.sub(r"^https?://(www\.)?", "", url)
    return label if len(label) <= 40 else label[:38] + "…"


def format_post_text(text: str | None) -> str:
    """Escape, linkify bare URLs and turn newlines into <br>."""
    raw = re.sub(r"\n{3,}", "\n\n", (text or "").replace("\r\n", "\n").strip())
    out: list[str] = []
    pos = 0
    for match in URL_RE.finditer(raw):
        url = match.group(0)
        while url and url[-1] in _URL_TRAIL:
            url = url[:-1]
        if not url:
            continue
        start = match.start()
        out.append(esc(raw[pos:start]))
        out.append(f'<a href="{esc(url)}" target="_blank" rel="noopener nofollow ugc">{esc(_link_label(url))}</a>')
        pos = start + len(url)
    out.append(esc(raw[pos:]))
    return "".join(out).replace("\n", "<br>")


def _ctx_get(ctx: Any, key: str, default: Any = None) -> Any:
    if ctx is None:
        return default
    if isinstance(ctx, Mapping):
        return ctx.get(key, default)
    return getattr(ctx, key, default)


def render_post(post: Mapping[str, Any], ctx: Any = None) -> str:
    """Canonical `.feed-post` card (DESIGN.md §5.1).

    ctx: a Data object or a dict with ``by_id`` (candidate map). Optional keys:
    ``show_city`` (default True), ``show_json`` (default True).
    """
    by_id = _ctx_get(ctx, "by_id", {}) or {}
    show_city = _ctx_get(ctx, "show_city", True)
    show_json = _ctx_get(ctx, "show_json", True)
    cid = post.get("candidateId") or ""
    cand = by_id.get(cid) or {"name": cid, "city": "", "party": ""}
    city = cand.get("city") or ""
    name = cand.get("name") or cid
    platform = post.get("platform") or "website"
    plat_label = PLATFORM_LABELS.get(platform, platform)
    url = safe_url(post.get("url"), internal=False)
    topics = [t for t in (post.get("topics") or []) if t]
    intent = post.get("postingIntent") if isinstance(post.get("postingIntent"), Mapping) else None
    cand_href = f"/{city}/{cid}/" if city else "/source/"
    ts = epoch(post.get("postedAt"))

    head = [f'<a class="feed-name" href="{esc(cand_href)}">{esc(name)}</a>']
    if show_city and city:
        head.append(f'<span class="feed-sep" aria-hidden="true">›</span><a class="feed-city chip-city" '
                    f'data-city="{esc(city)}" href="/?city={esc(city)}">{esc(city_label(city))}</a>')
    if ts:
        iso = str(post.get("postedAt")).strip()
        head.append(f'<time class="feed-time" datetime="{esc(iso)}" data-rel>{esc(fmt_time_tpe(post.get("postedAt")))}</time>')
    else:
        head.append('<span class="feed-time">時間不明</span>')
    if url:
        head.append(f'<a class="feed-plat" href="{esc(url)}" target="_blank" rel="noopener" '
                    f'aria-label="在 {esc(plat_label)} 開啟原文" title="{esc(plat_label)}">{icon(platform)}</a>')
    else:
        head.append(f'<span class="feed-plat" title="{esc(plat_label)}">{icon(platform)}</span>')

    body = [f'<div class="feed-text" data-clamp>{format_post_text(post.get("text"))}</div>',
            '<button class="feed-text-toggle" type="button" hidden>顯示全文</button>']
    image = asset_abs(post.get("imageUrl"))
    if image and url:
        aspect = post.get("imageAspect")
        ratio = f"{round(float(aspect), 4)}" if isinstance(aspect, (int, float)) and aspect > 0 else "4/3"
        body.append(f'<a class="feed-media" href="{esc(url)}" target="_blank" rel="noopener" tabindex="-1">'
                    f'<img loading="lazy" decoding="async" src="{esc(image)}" alt="" style="aspect-ratio: {ratio}"></a>')
    tags = [f'<a class="chip-soft chip-topic" href="/spectrum/{topic_slug(t)}/">{esc(t)}</a>' for t in topics]
    if intent and intent.get("type"):
        itype = intent.get("type")
        label = intent.get("label") or INTENT_LABELS.get(itype, itype)
        conf = intent.get("confidence")
        pct = f" {round(float(conf) * 100)}%" if isinstance(conf, (int, float)) else ""
        tags.append(f'<span class="chip-soft chip-intent" data-intent="{esc(itype)}" '
                    f'title="{esc(intent.get("reason") or "")}">{esc(label)}{pct}</span>')
    if tags:
        body.append(f'<div class="feed-tags">{"".join(tags)}</div>')
    share_title = f"{name}：{(post.get('text') or '').strip()[:40]}"
    actions = [
        f'<a class="feed-action" href="{esc(url)}" target="_blank" rel="noopener">{icon("external")}<span>原文</span></a>',
        f'<button class="feed-action btn-share" type="button" data-url="{esc(url)}" data-title="{esc(share_title)}">'
        f'{icon("share")}<span>分享</span></button>',
    ] if url else []
    if show_json and cid:
        actions.append(f'<a class="feed-action" href="/api/posts/{esc(cid)}.json" '
                       f'title="{esc(name)} 的貼文 JSON">{icon("json")}<span>JSON</span></a>')
    body.append(f'<div class="feed-actions">{"".join(actions)}</div>')

    attrs = _attrs({
        "data-id": post.get("id") or "", "data-candidate": cid, "data-city": city,
        "data-platform": platform, "data-intent": (intent or {}).get("type") or "",
        "data-topics": ",".join(topics), "data-ts": ts,
    })
    avatar = render_avatar({**cand, "name": name}, "sm", href=cand_href, cls="feed-avatar")
    return (f'<article class="feed-post"{attrs}>{avatar}<div class="feed-content">'
            f'<header class="feed-head">{"".join(head)}</header>{"".join(body)}</div></article>')

# ---------------------------------------------------------------------------
# Document shell
# ---------------------------------------------------------------------------

THEME_SCRIPT = (
    "(function(){try{var d=document.documentElement,"
    "q=new URLSearchParams(location.search).get('theme'),"
    "t=(q==='dark'||q==='light')?q:localStorage.getItem('theme');"
    "if(t==='dark'||t==='light')d.setAttribute('data-theme',t);"
    "if(q==='dark'||q==='light')d.setAttribute('data-theme-preview','');"
    "}catch(e){}})();"
)


def canonical(path: str) -> str:
    return BASE_URL + (path if path.startswith("/") else "/" + path)


def head(title: str, description: str, path: str, og_image: str | None = None,
         jsonld: Any = None, extra_css: Iterable[str] = (), noindex: bool = False) -> str:
    """Inner <head> markup. ``title`` is the page title (site name is appended
    unless the title already contains it)."""
    full = title if SITE_NAME in title else f"{title}｜{SITE_NAME}"
    desc = description or DEFAULT_DESCRIPTION
    url = canonical(path)
    image = og_image or "/assets/logo.svg"
    image = image if image.startswith("http") else BASE_URL + asset_abs(image)
    parts = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
        f"<title>{esc(full)}</title>",
        f'<meta name="description" content="{esc(desc)}">',
        '<meta name="color-scheme" content="light dark">',
        '<meta name="theme-color" media="(prefers-color-scheme: light)" content="#FAFAFC">',
        '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#000000">',
        f"<script>{THEME_SCRIPT}</script>",
        f'<link rel="canonical" href="{esc(url)}">',
        '<meta name="robots" content="noindex,follow">' if noindex else "",
        f'<meta property="og:type" content="website"><meta property="og:site_name" content="{esc(SITE_NAME)}">',
        f'<meta property="og:locale" content="zh_TW"><meta property="og:title" content="{esc(full)}">',
        f'<meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{esc(url)}">',
        f'<meta property="og:image" content="{esc(image)}"><meta name="twitter:card" content="summary">',
        f'<link rel="icon" href="{asset_url("favicon.svg")}" type="image/svg+xml">',
        '<link rel="alternate" type="application/rss+xml" title="全站更新 RSS" href="/feeds/updates.xml">',
        f'<link rel="stylesheet" href="{asset_url("tokens.css")}">',
        f'<link rel="stylesheet" href="{asset_url("styles.css")}">',
    ]
    parts += [f'<link rel="stylesheet" href="{asset_url(css)}">' for css in extra_css]
    if jsonld:
        blocks = jsonld if isinstance(jsonld, list) else [jsonld]
        for block in blocks:
            text = json_for_script(block)
            parts.append(f'<script type="application/ld+json">{text}</script>')
    return "\n".join(p for p in parts if p)


def _nav_link(item: Mapping[str, Any], current: bool, cls: str = "nav-item") -> str:
    aria = ' aria-current="page"' if current else ""
    return (f'<a class="{cls}" href="{item["href"]}" data-nav="{item["id"]}"{aria}>{icon(item["icon"])}'
            f'<span class="nav-label">{esc(item["label"])}</span>'
            f'<span class="nav-label-short">{esc(item["short"])}</span></a>')


def render_nav(page_id: str) -> str:
    links = []
    for item in nav_items:
        cls = "nav-item" if item["tab"] else "nav-item nav-desktop-only"
        links.append(_nav_link(item, page_id in item["match"], cls))
    extras = "".join(
        f'<a class="nav-mobile-extra" href="{item["href"]}">{icon(item["icon"], "mi")}<span>{esc(item["label"])}</span></a>'
        for item in nav_items if not item["tab"]
    )
    seg = "".join(
        f'<button type="button" data-theme-set="{val}" aria-pressed="{"true" if val == "system" else "false"}">'
        f'{icon(ic)}<span>{label}</span></button>'
        for val, label, ic in (("system", "系統", "system"), ("light", "淺色", "sun"), ("dark", "深色", "moon"))
    )
    menu = (
        f'<div class="nav-more-menu">{extras}'
        f'<p class="nav-more-label">外觀</p><div class="seg seg-theme" role="group" aria-label="外觀主題">{seg}</div>'
        f'<hr class="nav-more-sep">'
        f'<a href="{GITHUB_URL}" target="_blank" rel="noopener">{icon("external", "mi")}<span>GitHub 原始碼</span></a>'
        f'<a href="{REPORT_URL}" target="_blank" rel="noopener">{icon("about", "mi")}<span>資料回報</span></a>'
        f"</div>"
    )
    more = (f'<details class="nav-more"><summary class="nav-item">{icon("more")}'
            f'<span class="nav-label">更多</span><span class="nav-label-short">更多</span></summary>{menu}</details>')
    return f'<nav class="site-nav" aria-label="主要導覽">{"".join(links)}{more}</nav>'


def render_header(page_id: str) -> str:
    return (
        '<header class="site-header">'
        f'<a class="brand" href="/" aria-label="{SITE_NAME} 首頁"><span class="brand-num">2026</span>'
        f'<span class="brand-sub">{SITE_SHORT}</span></a>'
        f'<a class="topbar-search" href="/search/" aria-label="搜尋">{icon("search")}</a>'
        f"{render_nav(page_id)}</header>"
    )


def render_footer() -> str:
    ext = ' target="_blank" rel="noopener"'

    def links(items):
        return "".join(
            f'<a href="{href}"{ext if href.startswith("http") else ""}>{esc(label)}</a>' for label, href in items
        )
    return (
        '<footer class="site-footer">'
        '<div class="footer-about">'
        f'<a class="footer-brand" href="/"><span class="brand-num">2026</span><span>市長官方來源觀測站</span></a>'
        "<p>獨立、非官方的公開資料觀測站。本站彙整六都市長候選人官方帳號的公開發文並連回原文，"
        "與任何候選人、政黨或競選團隊無關；議題與發文動機由 AI 分類，僅供參考。</p>"
        "</div>"
        '<nav class="footer-nav" aria-label="頁尾導覽">'
        f'<section><h2>本站</h2>{links([("關於本站", "/about/"), ("資料狀態", "/status/"), ("RSS 訂閱", "/feeds/")])}</section>'
        f'<section><h2>參與</h2>{links([("GitHub", GITHUB_URL), ("資料回報", REPORT_URL)])}</section>'
        f'<section><h2>觀測站家族</h2>{links([("竹梅活動觀測站", "https://chumei.observe.tw/"), ("Harmonica Observatory", "https://harmonica.observe.tw/"), ("observe.tw", "https://observe.tw/")])}</section>'
        "</nav></footer>"
    )


def layout(page_id: str, title: str, description: str, path: str, body_html: str,
           extra_css: Iterable[str] = (), extra_js: Iterable[str] = (), jsonld: Any = None,
           og_image: str | None = None, noindex: bool = False, body_class: str = "") -> str:
    """Full HTML document. ``extra_css``/``extra_js`` are asset paths such as
    "pages/home.css". ``body_html`` goes inside <main class="page" id="main">."""
    scripts = [asset_url("icons.js"), asset_url("shell.js")] + [asset_url(js) for js in extra_js]
    script_tags = "".join(f'<script src="{src}" defer></script>' for src in scripts)
    cls = " ".join(c for c in (f"page-{page_id}", body_class) if c)
    return (
        '<!DOCTYPE html>\n<html lang="zh-Hant">\n<head>\n'
        f"{head(title, description, path, og_image, jsonld, extra_css, noindex)}\n{script_tags}\n</head>\n"
        f'<body class="{esc(cls)}" data-page="{esc(page_id)}">\n'
        '<a class="skip-link" href="#main">跳到主要內容</a>\n'
        f"{render_header(page_id)}\n"
        f'<main class="page" id="main">\n{body_html}\n</main>\n'
        f"{render_footer()}\n"
        '<div class="toast" role="status" aria-live="polite" hidden></div>\n'
        "</body>\n</html>\n"
    )


def page_head(title: str, lede: str = "", actions_html: str = "", eyebrow: str = "") -> str:
    """Standard `.page-head` block (h1 + lede + right-side actions)."""
    eb = f'<p class="page-eyebrow">{esc(eyebrow)}</p>' if eyebrow else ""
    ld = f'<p class="page-lede">{lede}</p>' if lede else ""
    act = f'<div class="page-actions">{actions_html}</div>' if actions_html else ""
    return f'<header class="page-head"><div class="page-head-text">{eb}<h1>{esc(title)}</h1>{ld}</div>{act}</header>'


def write_redirect(path: str, target: str, title: str = "頁面已搬移") -> Path:
    """meta-refresh stub at route ``path`` pointing to root-absolute ``target``."""
    html = (
        '<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url={esc(target)}">'
        f'<link rel="canonical" href="{esc(canonical(target))}">'
        '<meta name="robots" content="noindex,follow">'
        f"<title>{esc(title)}｜{SITE_NAME}</title></head>"
        f'<body><p>頁面已搬移，請前往 <a href="{esc(target)}">{esc(title)}</a>。</p></body></html>\n'
    )
    return write_page(path, html)
