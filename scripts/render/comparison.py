"""Evidence-first policy comparison review, rendered from a verified snapshot."""
from __future__ import annotations

from collections import Counter
import copy
import datetime as dt
import gzip
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit

from . import shell as S


def link(url: str, label: str) -> str:
    if urlsplit(url).scheme not in ("https", "http"):
        return S.esc(label)
    return f'<a href="{S.esc(url)}" target="_blank" rel="noopener noreferrer">{S.esc(label)} ↗</a>'


def day(value: str) -> str:
    if not value:
        return "發布日期不詳"
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone(dt.timezone(dt.timedelta(hours=8)))
        return parsed.date().isoformat()
    except ValueError:
        return "發布日期不詳"


def evidence(claim: dict, source: dict) -> str:
    date = day(source["postedAt"])
    kind = "正式政策頁" if source["kind"] == "policy" else source["platform"]
    heading = f'<span>原頁小標：{S.esc(claim["sourceHeading"])}</span>' if claim["sourceHeading"] and re.sub(r"\s+", "", claim["sourceHeading"]) in re.sub(r"\s+", "", source["text"]) else ""
    return (f'<article class="claim-evidence" id="claim-{claim["id"]}">'
            f'<div class="evidence-meta"><span class="chip-soft">{S.esc(claim["assertionType"])}</span><span>{S.esc(date)}</span><span>{S.esc(kind)}</span></div>'
            f'<blockquote>{S.esc(claim["quote"])}</blockquote>'
            f'<p class="evidence-meta">{heading}{link(source["url"], "查看原始來源")}'
            f'<a href="#source-{source["id"]}" data-source-link="{source["id"]}">查看完整收錄文本</a></p></article>')


def position_copy(value: str) -> str:
    """Delete editorial qualifications; retain policy requirements and numbers.

    This changes presentation only. Direct quotations and private analysis stay
    intact, and tentative verbs such as 研議 are never converted into promises.
    """
    editorial = re.compile(
        r"(?:需|須|待)(?:再|進一步)?(?:核對|釐清)"
        r"|不能(?:直接|逕)?(?:視為|當成|等同|據此|由此|互相|與.+比)"
        r"|不宜(?:直接|改寫|將|視為)|不代表"
        r"|(?:無法|不足以)(?:直接)?(?:認定|判定|比較|證明)"
        r"|(?:本題|同題)(?:該則|完整)?引(?:文|句)"
        r"|(?:相關|兩段|這兩段|所附|該段)?引(?:文|句).*(?:未提|未交代|未明|不足)"
        r"|(?:收錄|統計|比較).*(?:口徑|期間|範圍).*(?:不同|不明)"
        r"|(?:並非|不是|非)(?:新增政策承諾|已完成(?:改善)?的?成果|其他人的直接陳述)"
        r"|^(?:這些|此處|此段|這|此|上述).*(?:屬|是|為).*(?:成果自述|問題診斷|監督說法|陳述|批評|願景|供給預估)"
    )
    sentences = []
    for sentence in re.split(r"[。！？]", value):
        clauses = []
        for clause in re.split(r"[，；]", sentence):
            clause = clause.strip()
            if clause and not editorial.search(clause):
                clauses.append(clause)
        if clauses:
            sentences.append("，".join(clauses))
    return "。".join(sentences) + ("。" if sentences else "")


def render_question(q: dict, candidates: list[dict], claims: dict, sources: dict, source_counts: Counter) -> str:
    by_candidate = {r["candidateId"]: r for r in q["rows"]}
    cards = []
    search = [q["title"]]
    for candidate in candidates:
        cid = candidate["id"]
        row = by_candidate.get(cid)
        if row:
            rows = [claims[i] for i in row["claimIds"]]
            kinds = "、".join(dict.fromkeys(c["assertionType"] for c in rows))
            summary = position_copy(row["summary"]) if row["verified"] else ""
            search.extend([candidate["name"], summary] + [c["quote"] + c["subtopic"] + c["sourceHeading"] for c in rows])
            body = (f'<p class="position-kind">{S.esc(kinds)}</p>'
                    + (f'<p class="position-summary">{S.esc(summary)}</p>' if summary else '')
                    + f'<details class="row-evidence"><summary>原文 · {len(rows)}</summary>'
                    + "".join(evidence(c, sources[c["sourceId"]]) for c in rows) + '</details>')
            cls = "has-claims"
        elif not source_counts[cid]:
            body = '<span class="empty-position">來源尚未取得</span>'
            cls = "no-source"
        else:
            body = '<span class="empty-position">—</span><span class="sr-only">本題無收錄主張</span>'
            cls = "no-position"
        hidden = '' if source_counts[cid] else ' hidden'
        cards.append(f'<td class="position {cls}" data-candidate="{cid}" headers="candidate-{cid} {q["id"]}-title"{hidden}>{body}</td>')
    comparable = "true" if len(by_candidate) > 1 else "false"
    return (f'<tr class="mobile-question-heading"><th colspan="7" data-table-span><a href="#{q["id"]}">{S.esc(q["title"])}</a></th></tr>'
            f'<tr class="comparison-question" id="{q["id"]}" data-comparable="{comparable}" data-search="{S.esc(" ".join(search).lower())}">'
            f'<th scope="row" class="question-label" id="{q["id"]}-title"><a href="#{q["id"]}">{S.esc(q["title"])}</a></th>'
            + "".join(cards) + '</tr>')


def render_review(data: dict, out: Path, *, review: bool = True) -> None:
    # Rejected prose belongs to the private diagnostic snapshot, never the
    # public HTML, search attributes or downloadable JSON.
    data = copy.deepcopy(data)
    text_scope = "本次先分析可取得的文字內容；圖片內文字、影片語音及未取得的選舉公報尚未納入。"
    if text_scope not in data["limitations"]:
        data["limitations"].append(text_scope)
    for topic in data["topics"]:
        topic["briefFindings"] = [{"text": finding["text"], "claimIds": finding["claimIds"], "verified": True}
                                  for finding in topic.get("briefFindings", []) if finding["verified"]]
        for question in topic["questions"]:
            if not question["summaryVerified"]:
                question["summary"] = "比較摘要未通過完整檢核，請核對各候選人原文。"
                question["relation"] = "尚無法比較"
            for row in question["rows"]:
                if not row["verified"]:
                    row["summary"] = "摘要未通過語意檢核，請直接核對原文。"
            question.pop("verification", None)
            for row in question["rows"]:
                row.pop("verificationReason", None)
        # Prioritise questions with a verified comparison, keeping every
        # remaining heading accessible.
        topic["questions"].sort(key=lambda q: (not (q["summaryVerified"] and q["relation"] != "尚無法比較"), q["title"]))
    sources = {s["id"]: s for s in data["sources"]}
    claims = {c["id"]: c for c in data["claims"]}
    source_counts = Counter(s["candidateId"] for s in sources.values())
    post_counts = Counter(s["candidateId"] for s in sources.values() if s["kind"] == "post")
    candidates = sorted(data["candidates"], key=lambda c: (-post_counts[c["id"]], c["number"]))
    data["candidates"] = candidates
    selected_count = sum(bool(source_counts[c["id"]]) for c in candidates)
    names = {c["id"]: c["name"] for c in candidates}
    policies = sorted((s for s in sources.values() if s["kind"] == "policy"), key=lambda s: (s["postedAt"], s["title"]))
    all_headings = sum(len(s["headings"]) for s in policies)
    question_count = sum(len(t["questions"]) for t in data["topics"])
    topic_options, topic_sections = [], []
    for topic in data["topics"]:
        tid, title, questions = topic["id"], topic["name"], topic["questions"]
        topic_options.append(f'<label><input type="checkbox" data-topic-filter="{tid}"><span>{S.esc(title)}</span><small>{len(questions)}</small></label>')
        empty = '<tr class="empty-topic"><th scope="row">目前無收錄主張</th>' + ''.join(f'<td data-candidate="{c["id"]}"' + ('' if source_counts[c['id']] else ' hidden') + '>—</td>' for c in candidates) + '</tr>' if not questions else ''
        topic_sections.append(f'<tbody class="comparison-topic" id="topic-{tid}" data-topic="{tid}">'
                              f'<tr class="topic-divider"><th colspan="{selected_count + 1}" data-table-span><h2>{S.esc(title)}</h2><span>{len(questions)} 個政策問題</span></th></tr>'
                              + empty + "".join(render_question(q, candidates, claims, sources, source_counts) for q in questions) + '</tbody>')
    candidate_headers = []
    for c in candidates:
        count = source_counts[c["id"]]
        policy_count = count - post_counts[c["id"]]
        state = f'{post_counts[c["id"]]:,} 則貼文' if count else "來源尚未取得"
        if policy_count:
            state += f' · {policy_count} 篇政見'
        avatar = S.ASSETS_DIR / "comparison-avatars" / (c["id"] + ".webp")
        if not avatar.is_file():
            avatar = S.PROJECT_ROOT / "private/comparison-taipei/inputs/avatars" / (c["id"] + ".webp")
        if avatar.is_file():
            avatar_out = out / "assets/comparison-avatars" / avatar.name
            avatar_out.parent.mkdir(parents=True, exist_ok=True)
            if avatar.resolve() != avatar_out.resolve():
                shutil.copy2(avatar, avatar_out)
            c["avatarUrl"] = "assets/comparison-avatars/" + avatar.name
            portrait = f'<img class="candidate-portrait" src="/assets/comparison-avatars/{S.esc(avatar.name)}" alt="{S.esc(c["name"])}頭貼" width="56" height="56" decoding="async">'
        else:
            portrait = f'<span class="candidate-portrait portrait-initial" aria-hidden="true">{S.esc(c["name"][:1])}</span>'
        hidden = '' if count else ' hidden'
        candidate_headers.append(f'<th scope="col" id="candidate-{c["id"]}" data-candidate="{c["id"]}"{hidden}>'
                                 f'<div class="candidate-photo">{portrait}<span class="ballot-number">{c["number"]}</span></div><strong>{S.esc(c["name"])}</strong>'
                                 f'<span class="candidate-party">{S.esc(c["party"])}</span><small>{state}</small></th>')
    documents = []
    for source in policies:
        headings = "".join(f'<li class="outline-{h["level"]}">{S.esc(h["text"])}</li>' for h in source["headings"])
        documents.append(f'<details class="policy-outline" data-outline-search="{S.esc((source["title"] + source["text"]).lower())}">'
                         f'<summary>{S.esc(source["title"])}<span>{len(source["headings"])} 個標題</span></summary>'
                         f'<p class="meta">{S.esc(names[source["candidateId"]])} · {day(source["postedAt"])}</p><ol>{headings}</ol>'
                         f'<p>{link(source["url"], "原始政策專頁")} · <a href="#source-{source["id"]}" data-source-link="{source["id"]}">完整收錄文本</a></p></details>')
    library = []
    for source in sorted(sources.values(), key=lambda s: (s["candidateId"], s["postedAt"]), reverse=True):
        library.append(f'<details class="library-source" id="source-{source["id"]}"><summary>{S.esc(names[source["candidateId"]])} · {S.esc(source["title"][:65])}</summary>'
                       f'<p class="meta">{S.esc(day(source["postedAt"]))} · {S.esc(source["platform"])} · {len(source["alternatives"])} 個收錄來源版本</p>'
                       f'<p>{link(source["url"], "開啟原文")}</p><div class="source-fulltext">{S.esc(source["text"])}</div>'
                       + ("<p class=\"meta\">同文其他來源：" + " · ".join(link(s["url"], s["platform"]) for s in source["alternatives"] if s["url"] != source["url"]) + "</p>" if len(source["alternatives"]) > 1 else "")
                       + '</details>')
    last_post = max(s["postedAt"] for s in sources.values() if s["kind"] == "post" and s["postedAt"])
    failures = data.get("policyFailures", [])
    if failures:
        raise ValueError("cannot call all policy pages complete with fetch failures")
    candidate_controls = "".join(f'<label><input type="checkbox" data-candidate-filter="{c["id"]}"' + (' checked' if source_counts[c['id']] else '') + f'><span>{c["number"]} {S.esc(c["name"])}</span>' + ('' if source_counts[c['id']] else '<small>尚無來源</small>') + '</label>' for c in candidates)
    candidate_cols = ''.join(f'<col data-candidate="{c["id"]}"' + ('' if source_counts[c['id']] else ' hidden') + '>' for c in candidates)
    body = f'''<div class="container comparison-app">
      <header class="comparison-intro"><p class="eyebrow">2026 臺北市長選舉</p><h1>比較候選人的政見。</h1>
      <p class="snapshot-line">{len(data["topics"])} 類議題 · {question_count} 個政策問題 · 貼文更新至 {S.esc(day(last_post))}</p></header>
      <div class="comparison-toolbar">
        <details class="candidate-menu topic-menu"><summary><span id="selected-topic-label">所有議題</span><span aria-hidden="true">⌄</span></summary><fieldset><legend class="sr-only">選擇要比較的議題，可複選</legend><div class="topic-menu-heading"><strong>選擇議題 · 可複選</strong><button type="button" id="all-topics" class="text-button">顯示全部</button></div>{''.join(topic_options)}</fieldset></details>
        <details class="candidate-menu"><summary>比較對象 <span id="selected-candidate-count">{selected_count}</span><span aria-hidden="true">⌄</span></summary><fieldset><legend class="sr-only">選擇比較對象</legend>{candidate_controls}</fieldset></details>
        <label class="search-control" for="comparison-search"><span class="sr-only">搜尋議題或原文</span><input id="comparison-search" type="search" placeholder="搜尋議題或原文" autocomplete="off"></label>
        <button type="button" id="clear-search" class="text-button">清除</button>
      </div>
      <div class="topic-selection" id="topic-selection" hidden aria-label="已選議題"></div>
      <div class="table-status"><span id="result-count" role="status" aria-live="polite">{question_count} 個政策問題</span><label><input type="checkbox" id="only-comparable">只看多人有主張</label><span class="table-hint">左右滑動比較 →</span></div>
      <div class="comparison-table-scroll" style="--candidate-count:{selected_count}" tabindex="0" role="region" aria-label="候選人政見比較表">
        <table class="comparison-table"><caption class="sr-only">臺北市長候選人政見比較，依議題及政策問題排列</caption>
          <colgroup><col class="question-column">{candidate_cols}</colgroup>
          <thead><tr><th scope="col" class="corner-cell"><span>政策問題</span><small>— 本題無收錄主張</small></th>{''.join(candidate_headers)}</tr></thead>
          {''.join(topic_sections)}
        </table>
        <div id="comparison-no-results" class="empty" hidden>沒有符合的政策問題 <button type="button" id="reset-comparison" class="text-button">重設篩選</button></div>
      </div>
      <details class="comparison-documents" id="policy-outlines"><summary>政策原頁與全部小標 <span>{len(policies)} 篇 · {all_headings} 個標題</span></summary><div class="outlines-grid">{''.join(documents)}</div></details>
      <details id="source-library" class="source-library"><summary>完整來源庫 <span>{len(sources):,} 份文本</span></summary>{''.join(library)}</details>
      <details class="comparison-methods" id="methods"><summary>資料資訊</summary><p>文字來源自 2026-01-01 起。貼文最新發布 {S.esc(day(last_post))}；政策頁抓取 {S.esc(day(data["generatedAt"]))}。目前收錄 {selected_count} 位候選人的來源。</p>
      <p>政策專頁來自沈伯洋官網；蔣萬安、蕭文乾依已收錄貼文整理。圖片、影片語音與選舉公報尚未納入。</p>
      <p>{link(candidates[0]['rosterSource'], '官方候選人公告')} · <a href="/api/comparison.json" download>下載比較資料</a> · {link(S.REPORT_URL, "資料回報")}</p></details>
      </div>'''
    title = "臺北市長政見比較" + ("・Review" if review else "")
    html = S.layout("comparison", title, "臺北市6位市長候選人，全議題與政策小標的公開主張比較，逐項附原文證據。", "/compare/taipei/", body,
                    extra_css=("pages/comparison.css",), extra_js=("pages/comparison.js",), noindex=review)
    # This isolated review contains only its own route. Existing site navigation
    # opens the production pages instead of leading reviewers to broken links.
    if review:
        html = re.sub(r'href="(/(?!assets/|api/comparison\.json)[^"#]*)"', lambda m: 'href="' + S.BASE_URL + m.group(1) + '"', html)
    route = out / "compare/taipei"
    route.mkdir(parents=True, exist_ok=True)
    (route / "index.html").write_text(html, encoding="utf-8")
    if review:
        (out / "index.html").write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=/compare/taipei/"><a href="/compare/taipei/">臺北市政見比較</a>', encoding="utf-8")
        asset_out = out / "assets"
        asset_out.mkdir(parents=True, exist_ok=True)
        for path in S.ASSETS_DIR.rglob("*"):
            if path.is_file() and path.suffix in (".css", ".js", ".svg"):
                dest = asset_out / path.relative_to(S.ASSETS_DIR)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
    (out / "api").mkdir(exist_ok=True)
    (out / "api/comparison.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if review:
        (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    print(f"comparison rendered: {route / 'index.html'}; {question_count} questions, {all_headings} source headings")


def render(_data) -> None:
    """Publish the reviewed, sanitized snapshot on every ordinary site build.

    No inference or production feed mutation takes place during rendering.
    Missing or invalid snapshots fail the build instead of deleting this route.
    """
    from build_issue_comparisons import validate_snapshot

    path = S.PROJECT_ROOT / "data/comparisons/taipei.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        snapshot = json.load(stream)
    validate_snapshot(snapshot)
    render_review(snapshot, S.SITE_ROOT, review=False)
