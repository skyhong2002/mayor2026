/* /policy-match/ — step-by-step questionnaire + results (DESIGN.md §7.5).
   SSR ships every question; this script shows one step at a time, scores
   candidates from the inline #policy-data blob and fetches evidence excerpts
   from /api/policy-match.json. State lives only in the URL hash (#c=ids). */
(function () {
  "use strict";
  var MO = window.MO;
  var root = document.documentElement;
  var app = document.getElementById("policy-app");
  var dataEl = document.getElementById("policy-data");
  if (!MO || !app || !dataEl) { root.classList.remove("pm-js", "pm-hash"); return; }

  var D;
  try { D = JSON.parse(dataEl.textContent); } catch (e) { root.classList.remove("pm-js", "pm-hash"); return; }
  var esc = MO.esc, qs = MO.qs, qsa = MO.qsa;

  var quiz = qs("#policy-quiz", app);
  var results = qs("#policy-results", app);
  var steps = qsa(".policy-step", quiz);
  var total = steps.length;
  if (!quiz || !results || !total || !Array.isArray(D.questions) || !D.questions.length) {
    root.classList.remove("pm-js", "pm-hash"); return;
  }
  var btnPrev = qs('[data-act="prev"]', quiz);
  var btnNext = qs('[data-act="next"]', quiz);
  var btnResult = qs('[data-act="result"]', quiz);
  var progressText = qs("[data-progress-text]", quiz);
  var progressBar = qs("[data-progress]", quiz);
  var pickedCount = qs("[data-picked-count]", quiz);

  var choiceById = {};
  var questionOf = {};
  D.questions.forEach(function (q) {
    q.choices.forEach(function (c) { choiceById[c.id] = c; questionOf[c.id] = q; });
  });

  /* selection: question id → ordered array of choice ids */
  var sel = {};
  var current = 0;

  function selectedIds() {
    var out = [];
    D.questions.forEach(function (q) { (sel[q.id] || []).forEach(function (id) { out.push(id); }); });
    return out;
  }

  /* ---------------- quiz ---------------- */
  function syncStep(i) {
    var step = steps[i];
    var q = D.questions[i];
    var picked = sel[q.id] || [];
    var full = picked.length >= q.max;
    qsa(".policy-choice", step).forEach(function (b) {
      var on = picked.indexOf(b.getAttribute("data-choice")) !== -1;
      b.setAttribute("aria-pressed", on ? "true" : "false");
      if (!on && full && q.max > 1) b.setAttribute("aria-disabled", "true");
      else b.removeAttribute("aria-disabled");
    });
  }

  function hint(i, text) {
    var el = qs("[data-hint]", steps[i]);
    var q = D.questions[i];
    if (text) { el.textContent = text; el.classList.add("is-alert"); return; }
    el.classList.remove("is-alert");
    var n = (sel[q.id] || []).length;
    var rule = q.max > 1 ? "可複選，最多 " + q.max + " 項" : "單選";
    el.textContent = n ? "已選 " + n + " / " + q.max + " 項" + (n >= q.max && q.max > 1 ? "；要換選項請先取消一項。" : "。")
                       : rule + "；沒有想法也可以略過。";
  }

  function show(i, focus) {
    current = Math.max(0, Math.min(total - 1, i));
    steps.forEach(function (s, k) { s.classList.toggle("is-current", k === current); });
    var last = current === total - 1;
    var n = selectedIds().length;
    btnPrev.disabled = current === 0;
    btnNext.hidden = last;
    btnResult.hidden = !last;
    btnResult.disabled = n === 0;
    var q = D.questions[current];
    var has = (sel[q.id] || []).length > 0;
    qs("[data-label]", btnNext).textContent = has ? "下一題" : "略過這題";
    btnNext.classList.toggle("btn-primary", has);
    progressText.textContent = "第 " + (current + 1) + " / " + total + " 題";
    progressBar.setAttribute("aria-valuenow", String(current + 1));
    qs(".meter-fill", progressBar).style.setProperty("--v", ((current + 1) / total).toFixed(4));
    pickedCount.textContent = n ? "已選 " + n + " 項" : "";
    syncStep(current);
    hint(current, last && n === 0 ? "還沒有選任何方向；至少選一項才能看結果。" : "");
    if (focus) {
      var h = qs(".policy-prompt", steps[current]);
      if (h) h.focus({ preventScroll: true });
      quiz.scrollIntoView({ block: "nearest" });
    }
  }

  function toggle(btn) {
    var id = btn.getAttribute("data-choice");
    var q = questionOf[id];
    if (!q) return;
    var arr = (sel[q.id] = sel[q.id] || []);
    var at = arr.indexOf(id);
    if (at !== -1) arr.splice(at, 1);
    else if (q.max === 1) arr.splice(0, arr.length, id);
    else if (arr.length >= q.max) {
      syncStep(current);
      hint(current, "這題最多選 " + q.max + " 項，請先取消已選的一項。");
      return;
    } else arr.push(id);
    show(current, false);
  }

  quiz.addEventListener("click", function (ev) {
    var choice = ev.target.closest(".policy-choice");
    if (choice) { toggle(choice); return; }
    var act = ev.target.closest("[data-act]");
    if (!act || act.disabled) return;
    var a = act.getAttribute("data-act");
    if (a === "prev") show(current - 1, true);
    else if (a === "next") show(current + 1, true);
    else if (a === "result") showResults(true);
  });
  /* ← / → move between choices inside a step (buttons stay in Tab order too) */
  quiz.addEventListener("keydown", function (ev) {
    if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft" && ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
    var choice = ev.target.closest && ev.target.closest(".policy-choice");
    if (!choice) return;
    var list = qsa(".policy-choice", steps[current]);
    var k = list.indexOf(choice) + (ev.key === "ArrowRight" || ev.key === "ArrowDown" ? 1 : -1);
    if (k < 0 || k >= list.length) return;
    ev.preventDefault();
    list[k].focus();
  });

  /* ---------------- hash ---------------- */
  function readHash() {
    var m = /(?:^#|&)c=([^&]*)/.exec(location.hash);
    if (!m) return null;
    var ids;
    try { ids = decodeURIComponent(m[1]).split(","); } catch (e) { return null; }
    var next = {};
    ids.forEach(function (id) {
      id = id.trim();
      var q = questionOf[id];
      if (!q) return;
      var arr = (next[q.id] = next[q.id] || []);
      if (arr.indexOf(id) === -1 && arr.length < q.max) arr.push(id);
    });
    return next;
  }
  function writeHash(ids) {
    var url = location.pathname + location.search + (ids.length ? "#c=" + ids.join(",") : "");
    try { history.replaceState(null, "", url); } catch (e) { location.hash = ids.length ? "c=" + ids.join(",") : ""; }
  }

  /* ---------------- scoring ---------------- */
  function unionTopics(ids) {
    var seen = {}, out = [];
    ids.forEach(function (id) {
      (choiceById[id].topics || []).forEach(function (t) { if (!seen[t]) { seen[t] = 1; out.push(t); } });
    });
    return out;
  }
  /* cosine between the user's uniform topic vector and the candidate's weights */
  function score(c, topics) {
    if (!c.eligible || !topics.length) return null;
    var w = c.weights || {};
    var norm = Math.sqrt(Object.keys(w).reduce(function (s, k) { return s + w[k] * w[k]; }, 0));
    if (!norm) return 0;
    var dot = topics.reduce(function (s, t) { return s + (w[t] || 0); }, 0);
    return dot / (Math.sqrt(topics.length) * norm);
  }

  /* ---------------- evidence (lazy) ---------------- */
  var evidence = null;       // candidateId → {topic: [items]}
  var evidenceFailed = false;
  function loadEvidence() {
    return MO.fetchJSON("/api/policy-match.json").then(function (pm) {
      evidence = {};
      (pm.candidates || []).forEach(function (r) { evidence[r.candidateId] = r.evidence || {}; });
    }, function () { evidenceFailed = true; });
  }
  var evidenceReady = loadEvidence();

  function platformOf(item) {
    var p = String(item.postId || "").split(":")[0];
    return MO.PLATFORM_LABELS && MO.PLATFORM_LABELS[p] ? p : "website";
  }
  function evidenceHTML(cid, topic) {
    if (evidenceFailed) return '<p class="policy-ev-empty">證據貼文暫時無法取得，請重新整理頁面。</p>';
    if (!evidence) return "";
    var items = ((evidence[cid] || {})[topic] || []).slice(0, 3);
    if (!items.length) return '<p class="policy-ev-empty">這個議題沒有可列出的證據貼文。</p>';
    return '<ul class="policy-ev-list">' + items.map(function (it) {
      var plat = platformOf(it);
      var label = (MO.PLATFORM_LABELS && MO.PLATFORM_LABELS[plat]) || "原文";
      var text = String(it.text || "").replace(/\s+/g, " ").trim();
      var more = text.length >= 180 ? "…" : "";
      var href = MO.safeUrl(it.url, true);
      return '<li class="policy-ev"><p class="policy-ev-text">' + esc(text) + more + "</p>" +
        (href ? '<a class="feed-action policy-ev-link" href="' + esc(href) + '" target="_blank" rel="noopener" ' +
        'aria-label="在 ' + esc(label) + ' 開啟原文：' + esc(text.slice(0, 24)) + '">' +
        MO.icon(plat) + "<span>" + esc(label) + " 原文</span>" + MO.icon("external") + "</a>" : "") + "</li>";
    }).join("") + "</ul>";
  }

  /* ---------------- results ---------------- */
  var lastTopics = [];

  function pct(v) { return Math.round(v * 100); }

  function candidateHTML(c, topics) {
    var href = "/" + c.city + "/" + c.id + "/";
    var s = c.score;
    var head = '<header class="policy-cand-head">' +
      MO.avatarHTML(c, "md", href, "policy-cand-avatar") +
      '<div class="policy-cand-id"><a class="policy-cand-name" href="' + esc(href) + '">' + esc(c.name) + "</a>" +
      '<span class="chip-soft chip-party" data-party="' + MO.partySlug(c.party) + '"><span>' + esc(c.party || "無黨籍") + "</span></span></div>";
    if (s === null) {
      return '<article class="policy-cand card is-insufficient" data-candidate="' + esc(c.id) + '">' + head +
        '<p class="policy-score policy-score-na">資料不足</p></header>' +
        '<p class="policy-insufficient">資料不足，不推定立場。目前沒有可計算的主動政策倡議貼文。</p></article>';
    }
    head += '<p class="policy-score"><span class="policy-score-num">' + pct(s) + '<span class="policy-score-unit">%</span></span>' +
      '<span class="policy-score-label">議題重合</span></p></header>';
    var meter = '<div class="meter meter-lg" role="img" aria-label="議題重合 ' + pct(s) + '%"><span class="meter-fill" style="--v:' +
      Math.max(0, Math.min(1, s)).toFixed(4) + '"></span></div>' +
      '<p class="policy-basis">依 ' + c.eligible + " 則主動政策倡議貼文計算</p>";
    var w = c.weights || {};
    var matched = topics.filter(function (t) { return w[t]; }).sort(function (a, b) { return (w[b] - w[a]) || (a < b ? -1 : 1); });
    var missing = topics.filter(function (t) { return !w[t]; });
    var body = "";
    if (matched.length) {
      body += '<div class="policy-topics" role="group" aria-label="' + esc(c.name) + ' 的相符議題（選擇以查看證據）">' +
        matched.map(function (t, k) {
          return '<button type="button" class="chip policy-topic" data-topic="' + esc(t) + '" aria-pressed="' + (k === 0 ? "true" : "false") + '">' +
            "<span>" + esc(t) + '</span><span class="chip-count">' + pct(w[t]) + "%</span></button>";
        }).join("") + "</div>" +
        '<p class="policy-topics-hint">百分比＝該議題佔其政策貼文的比例</p>' +
        '<div class="policy-ev-wrap" data-ev>' + evidenceHTML(c.id, matched[0]) + "</div>";
    } else {
      body += '<p class="policy-ev-empty">所選方向的議題，在其主動政策貼文中都沒有出現。這不代表反對。</p>';
    }
    if (missing.length && matched.length) {
      body += '<p class="policy-missing">未見相關貼文：' + missing.map(esc).join("、") + "</p>";
    }
    return '<article class="policy-cand card" data-candidate="' + esc(c.id) + '">' + head + meter + body + "</article>";
  }

  function renderResults(ids) {
    var topics = unionTopics(ids);
    lastTopics = topics;
    qs("[data-picked]", results).innerHTML =
      '<ul class="policy-picked-list">' + ids.map(function (id) {
        return '<li class="chip-soft policy-picked-chip"><span>' + esc(choiceById[id].label) + "</span></li>";
      }).join("") + "</ul>" +
      '<p class="policy-picked-topics">對應議題：' + topics.map(function (t) {
        return '<a href="/spectrum/' + esc((D.topicSlugs || {})[t] || "") + '/">' + esc(t) + "</a>";
      }).join("、") + "</p>";

    var byCity = {};
    D.candidates.forEach(function (c) {
      var row = { id: c.id, name: c.name, city: c.city, party: c.party, avatarUrl: c.avatarUrl,
                  eligible: c.eligible, weights: c.weights, score: score(c, topics) };
      (byCity[c.city] = byCity[c.city] || []).push(row);
    });
    var html = D.cities.map(function (city) {
      var rows = byCity[city.id] || [];
      if (!rows.length) return "";
      rows.sort(function (a, b) {
        var sa = a.score === null ? -1 : a.score, sb = b.score === null ? -1 : b.score;
        return (sb - sa) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
      });
      return '<section class="policy-city" data-city="' + esc(city.id) + '" aria-labelledby="pc-' + esc(city.id) + '">' +
        '<h3 class="policy-city-title" id="pc-' + esc(city.id) + '"><span class="policy-city-dot" aria-hidden="true"></span>' +
        esc(city.label) + '<span class="policy-city-count">' + rows.length + " 位候選人</span></h3>" +
        '<div class="policy-cands">' + rows.map(function (r) { return candidateHTML(r, topics); }).join("") + "</div></section>";
    }).join("");
    qs("[data-results]", results).innerHTML = html;
  }

  function fillEvidence() {
    qsa(".policy-cand", results).forEach(function (card) {
      var on = qs('.policy-topic[aria-pressed="true"]', card);
      var wrap = qs("[data-ev]", card);
      if (on && wrap) wrap.innerHTML = evidenceHTML(card.getAttribute("data-candidate"), on.getAttribute("data-topic"));
    });
  }

  function showResults(focus) {
    var ids = selectedIds();
    if (!ids.length) { show(total - 1, true); return; }
    writeHash(ids);
    renderResults(ids);
    quiz.hidden = true;
    results.hidden = false;
    root.classList.remove("pm-hash");
    if (!evidence && !evidenceFailed) evidenceReady.then(fillEvidence);
    if (focus) {
      window.scrollTo(0, 0);
      qs("#policy-results-title", results).focus({ preventScroll: true });
    }
  }

  function backToQuiz(clear) {
    if (clear) sel = {};
    writeHash([]);
    results.hidden = true;
    quiz.hidden = false;
    root.classList.remove("pm-hash");
    show(0, true);
    window.scrollTo(0, 0);
  }

  results.addEventListener("click", function (ev) {
    var topicBtn = ev.target.closest(".policy-topic");
    if (topicBtn) {
      var card = topicBtn.closest(".policy-cand");
      qsa(".policy-topic", card).forEach(function (b) { b.setAttribute("aria-pressed", b === topicBtn ? "true" : "false"); });
      qs("[data-ev]", card).innerHTML = evidenceHTML(card.getAttribute("data-candidate"), topicBtn.getAttribute("data-topic"));
      return;
    }
    var act = ev.target.closest("[data-act]");
    if (!act) return;
    var a = act.getAttribute("data-act");
    if (a === "share") MO.share(location.href, document.title);
    else if (a === "edit") backToQuiz(false);
    else if (a === "restart") backToQuiz(true);
  });

  function fromHash(focus) {
    var next = readHash();
    if (next && Object.keys(next).length) { sel = next; showResults(focus); return true; }
    return false;
  }
  window.addEventListener("hashchange", function () { fromHash(true); });

  if (!fromHash(false)) { root.classList.remove("pm-hash"); show(0, false); }
})();
