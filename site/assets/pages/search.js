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

  function syncChips() {
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

  function run() {
    state.q = input.value.trim().slice(0, 100);
    writeURL();
    if (!state.q && !filtersOn()) { idle(); return; }
    if (!index) {
      results.setAttribute("aria-busy", "true");
      countEl.textContent = "正在讀取搜尋索引…";
      results.innerHTML = "";
      load().then(function () { results.removeAttribute("aria-busy"); run(); }, function () {
        results.removeAttribute("aria-busy");
        countEl.textContent = "";
        results.innerHTML = '<div class="empty"><p class="empty-title">無法讀取搜尋索引</p><p class="empty-body">網路連線可能中斷，或資料正在更新。請稍後再試。</p>' +
          '<button class="btn btn-sm" type="button" data-retry>重試</button></div>';
        var r = results.querySelector("[data-retry]");
        if (r) r.addEventListener("click", run);
      });
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

  function idle() {
    hits = []; shown = 0;
    countEl.textContent = "";
    if (moreWrap) moreWrap.hidden = true;
    results.innerHTML = '<div class="empty"><p class="empty-title">輸入關鍵字開始搜尋</p>' +
      '<p class="empty-body">可以輸入多個關鍵字（以空白分隔），也可以只用城市、平台篩選瀏覽最新貼文。</p></div>';
  }

  if (state.q || filtersOn()) run();
  else setTimeout(function () { load().catch(function () {}); }, 400); // warm the index
  if (document.activeElement !== input) { try { input.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }
})();
