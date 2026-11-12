/* `/search/` — client-side search over /data/search-index.json. Depends on window.MO. */
(function () {
  "use strict";
  var MO = window.MO;
  var input = document.getElementById("search-q");
  var results = document.getElementById("search-results");
  var countEl = document.getElementById("search-count");
  var moreWrap = document.getElementById("search-more");
  if (!MO || !input || !results) return;
  var qsa = MO.qsa, esc = MO.esc;
  var MAX = 200, STEP = 50;
  var params = new URLSearchParams(location.search);
  var state = {
    q: (params.get("q") || "").trim(),
    city: split(params.get("city")),
    platform: split(params.get("platform")),
    intent: params.get("intent") === "responsive" || params.get("intent") === "self_initiated" ? params.get("intent") : ""
  };
  var index = null, byId = {}, hits = [], shown = 0, timer = null;

  function split(v) { return (v || "").split(",").map(function (s) { return s.trim(); }).filter(Boolean); }

  input.value = state.q;
  syncChips();
  var form = input.form;
  if (form) form.addEventListener("submit", function (ev) { ev.preventDefault(); clearTimeout(timer); run(); input.blur(); });
  input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(run, 150); });

  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest(".search-filters [data-fk]");
    if (!b) return;
    var k = b.getAttribute("data-fk"), v = b.getAttribute("data-fv");
    if (k === "intent") state.intent = v;
    else { var arr = state[k], i = arr.indexOf(v); if (i === -1) arr.push(v); else arr.splice(i, 1); }
    syncChips();
    run();
  });
  if (moreWrap) moreWrap.querySelector("button").addEventListener("click", function () { renderMore(STEP); });

  // Phones: once there is a query, fold the filters into a "篩選（已選 n）" bar so results lead.
  var side = document.querySelector(".search-side");
  var wideMQ = window.matchMedia ? matchMedia("(min-width: 1080px)") : { matches: true };
  function syncDrawer() {
    if (!side) return;
    if (wideMQ.matches) side.open = true;
  }
  if (side) {
    if (!wideMQ.matches && (state.q || state.city.length || state.platform.length || state.intent)) side.open = false;
    side.addEventListener("toggle", syncDrawer);
    if (wideMQ.addEventListener) wideMQ.addEventListener("change", syncDrawer);
  }

  function syncChips() {
    var n = state.city.length + state.platform.length + (state.intent ? 1 : 0);
    var countBadge = document.querySelector("[data-filter-count]");
    if (countBadge) { countBadge.textContent = n ? "已選 " + n : ""; countBadge.hidden = !n; }
    qsa(".search-filters [data-fk]").forEach(function (b) {
      var k = b.getAttribute("data-fk"), v = b.getAttribute("data-fv");
      var on = k === "intent" ? state.intent === v : state[k].indexOf(v) !== -1;
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function load() {
    return MO.fetchJSON("/data/search-index.json").then(function (d) {
      (d.candidates || []).forEach(function (c) { byId[c.id] = c; });
      index = (d.posts || []).map(function (r) {
        var c = byId[r.c] || {};
        r._h = ((r.x || "") + " " + (c.name || "")).toLowerCase();
        r._city = c.city || "";
        return r;
      });
      return index;
    });
  }

  function expand(r) {
    return {
      id: r.id, candidateId: r.c, platform: r.p, url: r.u,
      postedAt: r.t ? new Date(r.t * 1000).toISOString() : null,
      text: r.x, imageUrl: r.i, imageAspect: r.a, topics: r.o || [],
      postingIntent: r.n ? { type: r.n, label: MO.INTENT_LABELS[r.n], confidence: r.r } : null
    };
  }

  function writeURL() {
    var p = new URLSearchParams();
    if (state.q) p.set("q", state.q);
    if (state.city.length) p.set("city", state.city.join(","));
    if (state.platform.length) p.set("platform", state.platform.join(","));
    if (state.intent) p.set("intent", state.intent);
    var s = p.toString();
    history.replaceState(null, "", location.pathname + (s ? "?" + s : ""));
  }

  function filtersOn() { return !!(state.city.length || state.platform.length || state.intent); }

  /* 2026 地方選舉候選人名單：姓名、選舉區、村里（/data/elections/search-2026.json，首次輸入才下載） */
  var candsEl = document.getElementById("search-cands");
  var elIndex = null, elLoading = null;
  function elNorm(s) { return String(s || "").replace(/[\s\u3000]/g, "").replace(/台/g, "臺").toLowerCase(); }
  function runCands(q) {
    if (!candsEl) return;
    var terms = q.split(/\s+/).map(elNorm).filter(Boolean);
    if (!terms.length) { candsEl.hidden = true; return; }
    if (!elLoading) {
      elLoading = MO.fetchJSON("/data/elections/search-2026.json").then(function (d) {
        elIndex = { d: d, rows: d.rows.map(function (r) { return { r: r, hay: elNorm(d.counties[r[3]] + r[4] + r[5] + r[0]) }; }) };
      });
    }
    elLoading.then(function () {
      if (elNorm(input.value) !== elNorm(q)) return;
      var d = elIndex.d, hits = [], total = 0;
      elIndex.rows.forEach(function (row) {
        for (var t = 0; t < terms.length; t++) { if (row.hay.indexOf(terms[t]) < 0) return; }
        total++; if (hits.length < 6) hits.push(row.r);
      });
      if (!total) { candsEl.hidden = true; return; }
      candsEl.querySelector(".search-cands-body").innerHTML = hits.map(function (r) {
        var where = d.counties[r[3]] + (r[4] || "") + (r[5] && r[5] !== r[4] && r[5] !== d.counties[r[3]] ? r[5] : "");
        return '<a class="search-cand" href="' + esc(r[6]) + '"><span class="search-cand-no">' + r[1] + '</span><span><b>' + esc(r[0]) +
          '</b> <span class="muted small">' + esc(d.categories[r[2]]) + "・" + esc(where) + "・" + esc(r[7]) + "</span></span></a>";
      }).join("");
      var more = candsEl.querySelector(".search-cands-more");
      more.href = "/elections/?q=" + encodeURIComponent(q);
      more.textContent = total > hits.length ? "查看全部 " + total.toLocaleString("zh-TW") + " 位候選人" : "在候選人名單查看";
      candsEl.hidden = false;
    }).catch(function () { candsEl.hidden = true; });
  }

  function run() {
    countEl.removeAttribute("data-tone");
    state.q = input.value.trim().slice(0, 100);
    writeURL();
    runCands(state.q);
    if (!state.q && !filtersOn()) { idle(); return; }
    if (!index) {
      results.setAttribute("aria-busy", "true");
      countEl.textContent = "";
      var sk = '<div class="skeleton-post" aria-hidden="true"><span></span><div class="skeleton-lines"><span></span><span></span><span></span><span></span></div></div>';
      results.innerHTML = '<p class="feed-status" data-kind="loading" role="status"><span class="spinner" aria-hidden="true"></span>' +
        "正在讀取搜尋索引…第一次搜尋需要下載整份索引，通常幾秒內完成。</p>" + sk + sk + sk;
      load().then(function () { results.removeAttribute("aria-busy"); run(); }, function () {
        results.removeAttribute("aria-busy");
        countEl.textContent = "";
        results.innerHTML = '<div class="empty" data-tone="error"><p class="empty-title">無法讀取搜尋索引</p><p class="empty-body">網路連線可能中斷，或資料正在更新。請稍後再試。</p>' +
          '<button class="btn btn-sm" type="button" data-retry>重試</button></div>';
        var r = results.querySelector("[data-retry]");
        if (r) r.addEventListener("click", run);
      });
      return;
    }
    if (!index.length) {
      hits = []; shown = 0;
      renderDist();
      countEl.textContent = "";
      if (moreWrap) moreWrap.hidden = true;
      results.innerHTML = '<div class="empty"><p class="empty-title">目前還沒有可以搜尋的貼文</p>' +
        '<p class="empty-body">搜尋索引是空的：資料可能正在重建，或候選人尚未發文。這不是你的關鍵字的問題，請稍後再回來。</p>' +
        '<a class="btn btn-sm" href="/status/">查看資料狀態</a></div>';
      return;
    }
    var terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
    hits = [];
    for (var i = 0; i < index.length; i++) {
      var r = index[i];
      if (state.city.length && state.city.indexOf(r._city) === -1) continue;
      if (state.platform.length && state.platform.indexOf(r.p) === -1) continue;
      if (state.intent && r.n !== state.intent) continue;
      var ok = true;
      for (var j = 0; j < terms.length; j++) if (r._h.indexOf(terms[j]) === -1) { ok = false; break; }
      if (ok) hits.push(r);
    }
    shown = 0;
    results.innerHTML = "";
    renderDist();
    if (!hits.length) {
      countEl.textContent = "找不到符合的貼文";
      results.innerHTML = '<div class="empty"><p class="empty-title">沒有符合「' + esc(state.q || "目前篩選") + '」的貼文</p>' +
        '<p class="empty-body">試試較短或不同的關鍵字，或移除部分城市、平台篩選。搜尋只比對每則貼文的前 300 字。</p></div>';
      if (moreWrap) moreWrap.hidden = true;
      return;
    }
    countEl.textContent = "共 " + hits.length.toLocaleString("zh-TW") + " 則" + (hits.length > MAX ? "，先顯示最新 " + MAX + " 則" : "") + "・依時間由新到舊";
    renderMore(Math.min(MAX, hits.length));
  }

  function renderMore(n) {
    var end = Math.min(hits.length, shown + n);
    var html = "";
    var ctx = { byId: byId, showCity: true };
    for (var i = shown; i < end; i++) html += MO.postHTML(expand(hits[i]), ctx);
    var tmp = document.createElement("div");
    tmp.innerHTML = html;
    while (tmp.firstChild) results.appendChild(tmp.firstChild);
    shown = end;
    MO.bindPostBehaviors(results);
    if (moreWrap) moreWrap.hidden = shown >= hits.length;
  }

  // Right-hand overview: how the hits split by candidate and platform.
  var distEl = document.getElementById("search-dist");
  function renderDist() {
    if (!distEl) return;
    if (!hits.length) { distEl.hidden = true; return; }
    var byC = {}, byP = {};
    hits.forEach(function (r) { byC[r.c] = (byC[r.c] || 0) + 1; byP[r.p] = (byP[r.p] || 0) + 1; });
    function rows(map, label) {
      var keys = Object.keys(map).sort(function (a, b) { return map[b] - map[a]; });
      var top = map[keys[0]] || 1;
      return keys.slice(0, 8).map(function (k) {
        return '<div class="meter-row"><span class="meter-label">' + label(k) + "</span>" +
          '<span class="meter"><span class="meter-fill" style="--v:' + (map[k] / top).toFixed(3) + '"></span></span>' +
          '<span class="meter-value">' + map[k] + "</span></div>";
      }).join("");
    }
    var cityShort = MO.CITY_SHORT || {};
    distEl.querySelector(".search-dist-body").innerHTML =
      "<h3>依候選人</h3>" + rows(byC, function (id) {
        var c = byId[id] || {};
        return '<span class="ellipsis">' + esc(c.name || id) + '</span><span class="xs muted">' + esc(cityShort[c.city] || "") + "</span>";
      }) +
      "<h3>依平台</h3>" + rows(byP, function (p) { return esc((MO.PLATFORM_LABELS || {})[p] || p); });
    document.getElementById("search-dist-note").textContent = "共 " + hits.length.toLocaleString("zh-TW") + " 則符合";
    distEl.hidden = false;
  }

  function idle() {
    hits = []; shown = 0;
    renderDist();
    countEl.textContent = "";
    if (moreWrap) moreWrap.hidden = true;
    results.innerHTML = '<div class="empty"><p class="empty-title">輸入關鍵字開始搜尋</p>' +
      '<p class="empty-body">可以輸入多個關鍵字（以空白分隔），也可以只用城市、平台篩選瀏覽最新貼文。</p></div>';
  }

  if (state.q || filtersOn()) run();
  else setTimeout(warm, 400);

  // Warm the index in the background. A failure is not fatal (run() fetches
  // again, since MO.fetchJSON drops failed promises), but it must be visible:
  // say so next to the box instead of failing silently on the first search.
  function warm() {
    load().catch(function (err) {
      if (window.console) console.warn("search: index warm-up failed", err);
      if (state.q || filtersOn()) return; // a real search already reports its own error
      countEl.textContent = "搜尋索引暫時無法預先讀取，開始搜尋時會自動再試一次。";
      countEl.setAttribute("data-tone", "warn");
    });
  }
  if (document.activeElement !== input) { try { input.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }
})();
