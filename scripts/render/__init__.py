"""Server-side renderers for mayor2026.observe.tw (standard library only).

shell.py  — shared HTML shell, icons, formatting helpers, render_post().
data.py   — cached loader for site/api/*.json.
<page>.py — one module per page family; each exposes ``render(data) -> None``.
"""
