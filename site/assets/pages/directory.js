/* directory: /source/ filters + sorting, /feeds/ copy buttons. Depends on window.MO. */
(function () {
  "use strict";
  var MO = window.MO || {};
  var doc = document;
  function qsa(sel, root) { return Array.prototype.slice.call((root || doc).querySelectorAll(sel)); }

  /* ---------- copy-to-clipboard (feeds / api) ---------- */
  doc.addEventListener("click", function (ev) {
    var btn = ev.target.closest && ev.target.closest("[data-copy]");
    if (!btn) return;
    var url = new URL(btn.getAttribute("data-copy"), location.href).href;
    var copy = MO.copyText ? MO.copyText(url) : Promise.reject();
    copy.then(function () { MO.toast && MO.toast("已複製：" + url); },
      function () { MO.toast && MO.toast("無法複製，請手動複製網址"); });
  });

  /* ---------- /source/ directory ---------- */
  var table = doc.querySelector(".directory-table");
  if (!table) return;
  var tbody = table.tBodies[0];
  var rows = qsa("tr", tbody);
  var input = doc.getElementById("dir-q");
  var countEl = doc.querySelector("[data-count]");
  var empty = doc.querySelector(".dir-empty");
  var segBtns = qsa("[data-sort-key]");
  var ths = qsa("th[data-sort]", table);
  var filters = { city: "", party: "", platform: "" };
  var DEFAULT_DIR = { latest: "desc", posts: "desc", name: "asc", city: "asc" };
  var sortKey, sortDir;
  var collator = window.Intl && Intl.Collator ? new Intl.Collator("zh-Hant-TW-u-co-stroke") : null;

  function cmp(a, b) {
    var d = 0;
    if (sortKey === "name") d = collator ? collator.compare(a.dataset.name, b.dataset.name) : (a.dataset.name < b.dataset.name ? -1 : 1);
    else if (sortKey === "city") d = (+a.dataset.cityIndex) - (+b.dataset.cityIndex);
    else if (sortKey === "posts") d = (+a.dataset.posts) - (+b.dataset.posts);
    else d = (+a.dataset.ts) - (+b.dataset.ts);
    if (sortDir === "desc") d = -d;
    if (!d) d = (+b.dataset.ts) - (+a.dataset.ts); // stable, neutral tie-break
    return d;
  }

  function applySort(key, dir) {
    sortKey = key; sortDir = dir || DEFAULT_DIR[key];
    rows.slice().sort(cmp).forEach(function (tr) { tbody.appendChild(tr); });
    segBtns.forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.sortKey === key ? "true" : "false"); });
    ths.forEach(function (th) {
      if (th.dataset.sort === key) th.setAttribute("aria-sort", sortDir === "asc" ? "ascending" : "descending");
      else th.removeAttribute("aria-sort");
    });
  }

  function applyFilter() {
    var q = (input && input.value || "").trim().toLowerCase();
    var terms = q ? q.split(/\s+/) : [];
    var shown = 0;
    rows.forEach(function (tr) {
      var ok = (!filters.city || tr.dataset.city === filters.city) &&
        (!filters.party || tr.dataset.party === filters.party) &&
        (!filters.platform || (" " + tr.dataset.platforms + " ").indexOf(" " + filters.platform + " ") >= 0) &&
        terms.every(function (t) { return tr.dataset.search.indexOf(t) >= 0; });
      tr.hidden = !ok;
      if (ok) shown++;
    });
    if (countEl) {
      countEl.textContent = shown === rows.length ? String(rows.length) : shown + " / " + rows.length;
    }
    if (empty) empty.hidden = shown > 0;
    table.parentNode.hidden = shown === 0;
  }

  qsa("[data-filter]").forEach(function (chip) {
    chip.addEventListener("click", function () {
      var key = chip.dataset.filter;
      filters[key] = chip.dataset.value;
      qsa('[data-filter="' + key + '"]').forEach(function (c) {
        c.setAttribute("aria-pressed", c === chip ? "true" : "false");
      });
      applyFilter();
    });
  });
  if (input) input.addEventListener("input", applyFilter);
  var reset = doc.querySelector("[data-reset]");
  if (reset) reset.addEventListener("click", function () {
    filters = { city: "", party: "", platform: "" };
    if (input) input.value = "";
    qsa("[data-filter]").forEach(function (c) { c.setAttribute("aria-pressed", c.dataset.value ? "false" : "true"); });
    applyFilter();
  });

  segBtns.forEach(function (b) { b.addEventListener("click", function () { applySort(b.dataset.sortKey); }); });
  ths.forEach(function (th) {
    function go() {
      var key = th.dataset.sort;
      var dir = key === sortKey ? (sortDir === "asc" ? "desc" : "asc") : DEFAULT_DIR[key];
      applySort(key, dir);
    }
    th.addEventListener("click", go);
    th.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); go(); }
    });
  });

  // Neutral default: random between 最新更新 / 貼文數 on every load (the build also picked one at random).
  var params = new URLSearchParams(location.search);
  var qp = params.get("q");
  if (qp && input) input.value = qp;
  ["city", "party", "platform"].forEach(function (k) {
    var v = params.get(k);
    var chip = v && doc.querySelector('[data-filter="' + k + '"][data-value="' + CSS.escape(v) + '"]');
    if (chip) chip.click();
  });
  var initial = params.get("sort");
  applySort(DEFAULT_DIR[initial] ? initial : (Math.random() < 0.5 ? "latest" : "posts"));
  applyFilter();
})();
