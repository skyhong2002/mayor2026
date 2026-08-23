"""Adapter for a-chun.tw's native WordPress RSS feed."""

from __future__ import annotations

from urllib.parse import urljoin

from ._common import fetch_feed


def fetch(url: str) -> list[dict]:
    return fetch_feed(urljoin(url, "/feed"), limit=10)
