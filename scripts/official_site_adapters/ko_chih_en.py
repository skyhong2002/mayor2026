"""Adapter placeholder for k100.tw, whose hostname currently has no DNS record.

The request is still performed so DNS/HTTP outages remain hard failures as
required by the adapter contract. If the domain comes back and advertises an
RSS feed, the adapter consumes it; a reachable page without a dated news feed
is treated as genuinely empty.
"""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin

from ._common import attrs_dict, fetch_feed, request_text


class _FeedLink(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.href = ""

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = attrs_dict(attrs_list)
        rel = set(attrs.get("rel", "").lower().split())
        media_type = attrs.get("type", "").lower()
        if tag == "link" and "alternate" in rel and media_type in {
            "application/rss+xml",
            "application/atom+xml",
        }:
            self.href = attrs.get("href", "")


def fetch(url: str) -> list[dict]:
    body, _ = request_text(url)
    parser = _FeedLink()
    parser.feed(body)
    if parser.href:
        return fetch_feed(urljoin(url, parser.href), limit=10)
    return []
