"""Keep shared questionnaire URLs working in the unified comparison interface."""
from __future__ import annotations
from typing import Any
from . import shell as S


def render(data: Any) -> None:
    choices = {
        c['id']: [S.TOPIC_SLUGS[t] for t in c.get('topics', []) if t in S.TOPIC_SLUGS]
        for q in (data.policy_match or {}).get('questions', []) for c in q.get('choices', [])
    }
    target = '/compare/taipei/'
    mapping = S.json_for_script(choices, separators=(',', ':'))
    html = (
        '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,follow">'
        f'<link rel="canonical" href="{S.canonical(target)}"><title>政見比較</title>'
        f'<script id="policy-comparison-redirect">const choices={mapping};'
        "const to=new URL('/compare/taipei/',location.origin);to.search=location.search;"
        "const ids=new URLSearchParams(location.hash.slice(1)).get('c');"
        "if(ids){const topics=[...new Set(ids.split(',').flatMap(id=>choices[id]||[]))];"
        "if(topics.length){to.searchParams.delete('topic');to.searchParams.set('topics',topics.join(','));}}"
        "else{to.hash=location.hash;}location.replace(to.href);</script>"
        f'<noscript><meta http-equiv="refresh" content="0;url={target}"></noscript></head>'
        f'<body><p>議題選擇已整合至<a href="{target}">政見比較</a>。</p></body></html>'
    )
    S.write_page('/policy-match/', html)
