(() => {
  const search = document.getElementById('source-search');
  const filter = document.getElementById('source-filter');
  const rows = [...document.querySelectorAll('[data-source-group]')];
  const update = () => {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    rows.forEach(row => {
      const matches = row.dataset.sourceSearch.toLocaleLowerCase().includes(query);
      const group = filter.value === 'all' || row.dataset.sourceGroup === filter.value ||
        (filter.value === 'attention' && row.dataset.sourceAttention === 'true');
      row.hidden = !(matches && group);
      if (!row.hidden) visible++;
    });
    document.getElementById('source-visible-count').textContent = `${visible} / ${rows.length} 個來源`;
  };
  if (search && filter) {
    search.addEventListener('input', update);
    filter.addEventListener('change', update);
    update();
  }
  const checkAge = () => {
    const stamp = Date.parse(document.getElementById('status-generated-at')?.dateTime || '');
    const warning = document.getElementById('status-stale-warning');
    if (warning) warning.hidden = !Number.isFinite(stamp) || Date.now() - stamp <= 8 * 3600000;
  };
  checkAge();
  setInterval(checkAge, 60000);
})();
