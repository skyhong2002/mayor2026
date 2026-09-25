/* /status/ — 來源表的前端篩選（狀態／平台 chips ＋ 搜尋）與排序。
   SSR 已輸出完整表格；本檔只做增強。支援 ?status=&platform=&q= 參數。 */
(function () {
  "use strict";
  var MO = window.MO;
  var qs = MO.qs, qsa = MO.qsa;

  function init() {
    var table = qs("#src-table");
    if (!table) return;
    var tbody = table.tBodies[0];
    var rows = qsa("tr", tbody);
    var shown = qs("[data-shown]");
    var empty = qs(".src-empty");
    var input = qs("#src-q");
    var state = { status: "", platform: "", q: "", sort: "status", dir: 1 };

    function setPressed(group, value) {
      qsa('[data-filter="' + group + '"] .chip', document).forEach(function (chip) {
        chip.setAttribute("aria-pressed", chip.getAttribute("data-value") === value ? "true" : "false");
      });
    }

    function apply() {
      var terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      var n = 0;
      rows.forEach(function (tr) {
        var hay = tr.getAttribute("data-q") || "";
        var ok = (!state.status || tr.getAttribute("data-status") === state.status) &&
          (!state.platform || tr.getAttribute("data-platform") === state.platform) &&
          terms.every(function (t) { return hay.indexOf(t) !== -1; });
        tr.hidden = !ok;
        if (ok) n++;
      });
      if (shown) shown.textContent = String(n);
      if (empty) empty.hidden = n !== 0;
      syncURL();
    }

    function num(tr, key) { return +tr.getAttribute("data-" + key) || 0; }
    function sort() {
      var key = state.sort, dir = state.dir;
      var sorted = rows.slice().sort(function (a, b) {
        var d;
        if (key === "status") d = (num(a, "rank") - num(b, "rank")) * dir;
        else {
          var av = num(a, key), bv = num(b, key);
          if (!av !== !bv) return av ? -1 : 1; // missing times always last
          d = (av - bv) * dir;
        }
        return d || num(a, "order") - num(b, "order");
      });
      sorted.forEach(function (tr) { tbody.appendChild(tr); });
      qsa("th[data-sort]", table).forEach(function (th) {
        if (th.getAttribute("data-sort") === key) th.setAttribute("aria-sort", dir > 0 ? "ascending" : "descending");
        else th.removeAttribute("aria-sort");
      });
    }

    function syncURL() {
      if (!window.history || !history.replaceState) return;
      var p = new URLSearchParams(location.search);
      [["status", state.status], ["platform", state.platform], ["q", state.q]].forEach(function (kv) {
        if (kv[1]) p.set(kv[0], kv[1]); else p.delete(kv[0]);
      });
      var s = p.toString();
      history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + location.hash);
    }

    qsa("[data-filter]", document).forEach(function (row) {
      var group = row.getAttribute("data-filter");
      row.addEventListener("click", function (ev) {
        var chip = ev.target.closest(".chip");
        if (!chip || chip.disabled) return;
        state[group] = chip.getAttribute("data-value") || "";
        setPressed(group, state[group]);
        apply();
      });
    });

    var timer;
    if (input) input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { state.q = input.value.trim(); apply(); }, 120);
    });

    qsa("th[data-sort]", table).forEach(function (th) {
      th.tabIndex = 0;
      function go() {
        var key = th.getAttribute("data-sort");
        if (state.sort === key) state.dir = -state.dir;
        else { state.sort = key; state.dir = key === "status" ? 1 : -1; } // times: newest first
        sort();
      }
      th.addEventListener("click", go);
      th.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); go(); } });
    });

    var reset = qs("[data-reset]");
    if (reset) reset.addEventListener("click", function () {
      state.status = state.platform = state.q = "";
      if (input) input.value = "";
      setPressed("status", ""); setPressed("platform", "");
      apply();
    });

    // URL → state (only values that exist as chips)
    var params = new URLSearchParams(location.search);
    ["status", "platform"].forEach(function (g) {
      var v = params.get(g) || "";
      if (v && qs('[data-filter="' + g + '"] .chip[data-value="' + CSS.escape(v) + '"]')) { state[g] = v; setPressed(g, v); }
    });
    if (params.get("q") && input) { input.value = params.get("q"); state.q = input.value.trim(); }
    if (state.status || state.platform || state.q) apply();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
