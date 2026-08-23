"""Adapters for 謝龍介's legacy official site and affiliated news site."""

from __future__ import annotations

from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit

from ._common import attrs_dict, clean_parts, fetch_feed, parse_date, request_text


class _LegacyNews(HTMLParser):
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pending_date = ""
        self.href = ""
        self.link_depth = 0
        self.parts: list[str] = []
        self.rows: list[dict] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = attrs_dict(attrs_list)
        if tag == "a" and "action=item_article" in attrs.get("href", ""):
            self.href = attrs["href"]
            self.link_depth = 1
            self.parts = []
        elif self.link_depth and tag not in self._VOID:
            self.link_depth += 1

    def handle_data(self, data: str) -> None:
        date_match = re.search(r"\b20\d{2}/\d{1,2}/\d{1,2}\b", data)
        if date_match and not self.link_depth:
            self.pending_date = date_match.group(0)
        if self.link_depth:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.link_depth:
            return
        self.link_depth -= 1
        if self.link_depth == 0:
            title = clean_parts(self.parts)
            if title and self.href:
                self.rows.append(
                    {
                        "href": self.href,
                        "date": self.pending_date,
                        "text": title,
                    }
                )
                self.pending_date = ""
            self.href = ""
            self.parts = []


def _fetch_legacy(url: str) -> list[dict]:
    listing_url = urljoin(url, "index.php?action=news")
    body, _ = request_text(listing_url)
    parser = _LegacyNews()
    parser.feed(body)
    rows = []
    seen: set[str] = set()
    for item in parser.rows:
        article_url = urljoin(listing_url, item["href"])
        post_id_match = re.search(r"[?&]wpicon_uid=(\d+)", article_url)
        post_id = post_id_match.group(1) if post_id_match else article_url
        if post_id in seen:
            continue
        seen.add(post_id)
        rows.append(
            {
                "post_id": post_id,
                "url": article_url,
                "posted_at": parse_date(item["date"]),
                "text": item["text"],
                "media": [],
            }
        )
    rows.sort(key=lambda row: row["posted_at"], reverse=True)
    return rows[:10]


def fetch(url: str) -> list[dict]:
    host = (urlsplit(url).hostname or "").lower()
    if host == "inewslong.com" or host.endswith(".inewslong.com"):
        return fetch_feed(urljoin(url, "/feed/"), limit=10)
    if host == "joo.com.tw" or host.endswith(".joo.com.tw"):
        return _fetch_legacy(url)
    raise ValueError(f"unsupported 謝龍介 official-site domain: {host or url!r}")
