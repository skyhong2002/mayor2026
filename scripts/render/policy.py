"""/policy-match/ — step-by-step policy questionnaire (DESIGN.md §7.5).

SSR renders the full question bank (every step and choice) plus the
methodology, so crawlers and no-JS readers see everything. pages/policy.js
turns it into a one-question-at-a-time flow and computes the results in the
browser from a slim inline scoring blob; evidence excerpts are fetched from
/api/policy-match.json. Choices are shared through ``#c=<choice ids>``.
"""

from __future__ import annotations

import json
import shutil
from typing import Any

from . import shell as S

ROUTE = "/policy-match/"
OUT_DIR = S.SITE_ROOT / "policy-match"

LEDE = "依序回答四題，選出你在意的市政方向，再看各城市候選人的主動政策發文和這些方向有多少重合。"
DESCRIPTION = ("先選市政優先方向，再看六都市長候選人主動發起的政策倡議貼文與你的選擇有多少議題重合；"
               "每項結果都附原文證據，資料不足者不推定立場。")

# Shown before JS runs: marks the document as enhanced (hides later steps via
# CSS, no flash) and, for shared links, hides the quiz until results render.
BOOT_SCRIPT = (
    "<script>(function(){var d=document.documentElement;d.classList.add('pm-js');"
    "if(/(^#|&)c=[^&]/.test(location.hash))d.classList.add('pm-hash');})();</script>"
)


def _json_script(element_id: str, payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" id="{element_id}">{text}</script>'


def _scoring_blob(data: Any, pm: dict[str, Any]) -> dict[str, Any]:
    """Everything policy.js needs to rank candidates without the 300 KB API file."""
    rows = {r.get("candidateId"): r for r in pm.get("candidates") or []}
    candidates = []
    for cand in data.candidates:  # roster only; missing rows → eligible 0 (資料不足)
        row = rows.get(cand["id"]) or {}
        candidates.append({
            "id": cand["id"],
            "name": cand.get("name") or row.get("candidateName") or cand["id"],
            "city": cand.get("city") or row.get("city") or "",
            "party": cand.get("party") or "",
            "avatarUrl": S.asset_abs(cand.get("avatarUrl")),
            "eligible": int(row.get("eligiblePostCount") or 0),
            "weights": {k: v for k, v in (row.get("topicWeights") or {}).items() if v},
        })
    questions = [
        {"id": q.get("id"), "max": int(q.get("maxChoices") or 1),
         "choices": [{"id": c.get("id"), "label": c.get("label"), "topics": c.get("topics") or []}
                     for c in q.get("choices") or []]}
        for q in pm.get("questions") or []
    ]
    return {
        "questions": questions,
        "candidates": candidates,
        "cities": [{"id": c["id"], "label": S.city_label(c["id"], short=False)} for c in data.cities],
        "topicSlugs": S.TOPIC_SLUGS,
    }


def _choice(choice: dict[str, Any]) -> str:
    topics = "、".join(choice.get("topics") or [])
    return (
        f'<button type="button" class="policy-choice" data-choice="{S.esc(choice.get("id"))}" aria-pressed="false">'
        '<span class="policy-check" aria-hidden="true"></span>'
        f'<span class="policy-choice-text"><span class="policy-choice-label">{S.esc(choice.get("label"))}</span>'
        f'<span class="policy-choice-topics">對應議題：{S.esc(topics)}</span></span></button>'
    )


def _step(index: int, total: int, question: dict[str, Any]) -> str:
    qid = S.esc(question.get("id"))
    max_choices = int(question.get("maxChoices") or 1)
    rule = f"可複選，最多 {max_choices} 項" if max_choices > 1 else "單選"
    choices = "".join(_choice(c) for c in question.get("choices") or [])
    current = " is-current" if index == 0 else ""
    return (
        f'<li class="policy-step{current}" data-step="{index}" data-question="{qid}" data-max="{max_choices}">'
        f'<p class="policy-step-kicker">第 {index + 1} 題<span aria-hidden="true"> · </span>'
        f'<span class="policy-rule">{rule}</span></p>'
        f'<h2 class="policy-prompt" id="pq-{qid}" tabindex="-1">{S.esc(question.get("prompt"))}</h2>'
        f'<div class="policy-choices" role="group" aria-labelledby="pq-{qid}">{choices}</div>'
        f'<p class="policy-hint" data-hint aria-live="polite">{rule}；沒有想法也可以略過。</p>'
        "</li>"
    )


def _quiz(questions: list[dict[str, Any]]) -> str:
    total = len(questions)
    steps = "".join(_step(i, total, q) for i, q in enumerate(questions))
    first = 1 / total if total else 0
    return (
        '<section class="policy-quiz card" id="policy-quiz" aria-label="問卷">'
        '<div class="policy-progress">'
        f'<p class="policy-progress-label"><span data-progress-text>第 1 / {total} 題</span>'
        '<span class="policy-picked-count" data-picked-count></span></p>'
        f'<div class="meter" role="progressbar" aria-label="作答進度" aria-valuemin="1" aria-valuemax="{total}" '
        f'aria-valuenow="1" data-progress><span class="meter-fill" style="--v:{first:.4f}"></span></div>'
        "</div>"
        f'<ol class="policy-steps">{steps}</ol>'
        '<div class="policy-nav">'
        f'<button type="button" class="btn" data-act="prev">{S.icon("chevron", "icon policy-prev-icon")}上一題</button>'
        '<button type="button" class="btn btn-primary" data-act="next"><span data-label>下一題</span>'
        f'{S.icon("chevron", "icon policy-next-icon")}</button>'
        '<button type="button" class="btn btn-primary" data-act="result" hidden>看結果</button>'
        "</div>"
        "</section>"
    )


def _results_shell() -> str:
    return (
        '<section class="policy-results" id="policy-results" aria-labelledby="policy-results-title" hidden>'
        '<div class="policy-results-head card">'
        '<div class="policy-results-title-row">'
        '<h2 id="policy-results-title" tabindex="-1">你選的方向</h2>'
        f'<button type="button" class="btn btn-sm" data-act="share">{S.icon("share")}分享結果</button>'
        "</div>"
        '<div class="policy-picked" data-picked></div>'
        '<p class="policy-results-note">重合度只計算候選人<strong>主動發文</strong>中含政策倡議的貼文'
        "（不含回應他方觀點的貼文），比較議題分布，不代表候選人對政策的立場或支持程度；"
        "貼文較少或未提及某議題，不等於反對。</p>"
        "</div>"
        '<div class="policy-cities" data-results></div>'
        '<div class="policy-again">'
        '<button type="button" class="btn" data-act="edit">修改選擇</button>'
        '<button type="button" class="btn btn-primary" data-act="restart">重新選擇</button>'
        "</div>"
        "</section>"
    )


def _methodology(pm: dict[str, Any], data: Any) -> str:
    method = pm.get("methodology") or ""
    maxes = sorted({int(q.get("maxChoices") or 1) for q in pm.get("questions") or []})
    rule = f"每題最多選 {maxes[0]} 項，可略過" if len(maxes) == 1 else "每題有選擇上限，可略過"
    stamp = S.fmt_time_tpe(data.generated_at, with_year=True)
    return (
        '<section class="policy-method" aria-labelledby="policy-method-title">'
        '<h2 id="policy-method-title">計算方式</h2>'
        f'<p>{S.esc(method)}</p>'
        '<ul class="policy-method-list">'
        "<li>只納入候選人<strong>主動發文</strong>、且 AI 判定含政策倡議的貼文；回應他方觀點的貼文與「生活」類不計入。</li>"
        f"<li>你的選擇會展開成對應議題（{rule}），各議題權重相同；"
        "與每位候選人的議題分布計算餘弦相似度，顯示為「議題重合」百分比。</li>"
        "<li>候選人依城市分組，同城市內依重合度排序，同分時依候選人代碼排序；不以政黨排序或配色。</li>"
        "<li>每個議題最多列出 3 則證據貼文摘錄，一律連回原文。沒有可計算貼文的候選人標示「資料不足，不推定立場」。</li>"
        "<li>選擇只存在網址的 <code>#</code> 片段，不會送到伺服器；本頁不使用 cookie 或追蹤。</li>"
        "</ul>"
        f'<p class="snapshot">資料快照：{S.esc(stamp)}（GMT+8）・'
        '<a href="/api/policy-match.json">policy-match.json</a>・<a href="/about/">關於分類方式</a></p>'
        "</section>"
    )


def render(data: Any) -> None:
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    pm = data.policy_match or {}
    title = pm.get("title") or "你的市政優先順序"
    questions = pm.get("questions") or []

    if questions:
        main = _quiz(questions) + _results_shell()
    else:
        main = S.render_empty("尚無資料", "政策題庫尚未產生，請稍後再來。")

    body = (
        BOOT_SCRIPT
        + S.page_head(title, S.esc(LEDE), eyebrow="議題選擇器")
        + '<noscript><p class="notice policy-noscript">逐題作答與結果計算需要啟用 JavaScript；'
          "以下仍列出完整題目與計算方式。</p></noscript>"
        + '<div class="policy-app" id="policy-app">' + main + "</div>"
        + _methodology(pm, data)
        + _json_script("policy-data", _scoring_blob(data, pm))
    )
    jsonld = {
        "@context": "https://schema.org", "@type": "WebPage", "name": f"{title}｜{S.SITE_NAME}",
        "url": S.canonical(ROUTE), "description": DESCRIPTION, "inLanguage": "zh-Hant",
    }
    html = S.layout("policy", title, DESCRIPTION, ROUTE, body,
                    extra_css=["pages/policy.css"], extra_js=["pages/policy.js"], jsonld=jsonld)
    S.write_page(ROUTE, html)
