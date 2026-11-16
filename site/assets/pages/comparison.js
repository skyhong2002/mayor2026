/* The complete comparison stays in the document; controls filter table rows and columns. */
(() => {
  'use strict';
  const app = document.querySelector('.comparison-app');
  if (!app) return;
  const input = document.getElementById('comparison-search');
  const topicFilters = Array.from(document.querySelectorAll('[data-topic-filter]'));
  const topicLabel = document.getElementById('selected-topic-label');
  const topicSelection = document.getElementById('topic-selection');
  const comparable = document.getElementById('only-comparable');
  const scroller = document.querySelector('.comparison-table-scroll');
  const sections = Array.from(document.querySelectorAll('.comparison-topic'));
  const filters = Array.from(document.querySelectorAll('[data-candidate-filter]'));
  const columns = Array.from(document.querySelectorAll('[data-candidate]'));
  const mobile = window.matchMedia('(max-width: 699px)');
  const params = new URLSearchParams(location.search);
  const selected = params.get('candidates')?.split(',').filter(id => filters.some(f => f.dataset.candidateFilter === id));
  if (selected?.length) filters.forEach(f => { f.checked = selected.includes(f.dataset.candidateFilter); });
  const initialTopics = (params.get('topics') || params.get('topic') || '').split(',');
  topicFilters.forEach(f => { f.checked = initialTopics.includes(f.dataset.topicFilter); });
  comparable.checked = params.get('compare') === '1';
  input.value = params.get('q') || '';

  function updateColumns() {
    const shown = new Set(filters.filter(f => f.checked).map(f => f.dataset.candidateFilter));
    columns.forEach(c => { c.hidden = !shown.has(c.dataset.candidate); });
    document.querySelectorAll('[data-table-span]').forEach(c => { c.colSpan = shown.size + (mobile.matches ? 0 : 1); });
    document.getElementById('selected-candidate-count').textContent = shown.size;
    scroller.style.setProperty('--candidate-count', shown.size);
  }

  function openForSearch(detail) {
    if (detail && !detail.open) { detail.open = true; detail.dataset.searchOpened = 'true'; }
  }
  function restoreSearchOpen(detail) {
    if (detail?.dataset.searchOpened) { detail.open = false; delete detail.dataset.searchOpened; }
  }

  function update(writeURL = true) {
    const query = input.value.trim().toLocaleLowerCase();
    const chosenTopics = topicFilters.filter(f => f.checked).map(f => f.dataset.topicFilter);
    const allTopics = !chosenTopics.length || chosenTopics.length === topicFilters.length;
    topicLabel.textContent = allTopics ? '所有議題' : (chosenTopics.length === 1 ? topicFilters.find(f => f.checked).nextElementSibling.textContent : `已選 ${chosenTopics.length} 個議題`);
    topicSelection.replaceChildren();
    topicSelection.hidden = allTopics;
    if (!allTopics) topicFilters.filter(f => f.checked).forEach(f => {
      const chip = document.createElement('button'); chip.type = 'button';
      chip.textContent = f.nextElementSibling.textContent + ' ×';
      chip.setAttribute('aria-label', '移除議題：' + f.nextElementSibling.textContent);
      chip.addEventListener('click', () => { f.checked = false; update(); });
      topicSelection.append(chip);
    });
    const shownCandidates = new Set(filters.filter(f => f.checked).map(f => f.dataset.candidateFilter));
    let count = 0;
    sections.forEach(section => {
      const matchesTopic = allTopics || chosenTopics.includes(section.dataset.topic);
      const questions = Array.from(section.querySelectorAll('.comparison-question'));
      let matches = 0;
      questions.forEach(q => {
        const candidateCount = q.dataset.claimCandidates ? q.dataset.claimCandidates.split(',').filter(id => shownCandidates.has(id)).length : (q.dataset.comparable === 'true' ? 2 : 1);
        q.hidden = (!!query && !q.dataset.search.includes(query)) || (comparable.checked && candidateCount < 2);
        q.querySelectorAll('.facet-detail').forEach(detail => {
          const titleMatches = q.querySelector('.question-label a').textContent.toLocaleLowerCase().includes(query);
          detail.hidden = !!query && !titleMatches && !detail.dataset.detailSearch.includes(query);
          const quotes = detail.querySelector('.detail-quotes');
          if (query && !detail.hidden && detail.querySelector('blockquote') && Array.from(detail.querySelectorAll('blockquote')).some(b => b.textContent.toLocaleLowerCase().includes(query))) {
            openForSearch(quotes);
          } else restoreSearchOpen(quotes);
        });
        const detailList = q.querySelectorAll('.facet-evidence');
        detailList.forEach(list => {
          if (query && Array.from(list.querySelectorAll('.facet-detail')).some(d => !d.hidden)) openForSearch(list);
          else restoreSearchOpen(list);
        });
        q.previousElementSibling.hidden = q.hidden;
        if (!q.hidden) matches++;
      });
      section.hidden = !matchesTopic || !matches;
      if (!section.hidden) count += matches;
    });
    document.getElementById('result-count').textContent = `${count} 個比較項目`;
    document.getElementById('comparison-no-results').hidden = count !== 0;
    if (writeURL) {
      const url = new URL(location.href);
      url.searchParams.delete('topic');
      allTopics ? url.searchParams.delete('topics') : url.searchParams.set('topics', chosenTopics.join(','));
      query ? url.searchParams.set('q', input.value.trim()) : url.searchParams.delete('q');
      comparable.checked ? url.searchParams.set('compare', '1') : url.searchParams.delete('compare');
      const selected = filters.filter(f => f.checked).map(f => f.dataset.candidateFilter);
      selected.length === filters.length ? url.searchParams.delete('candidates') : url.searchParams.set('candidates', selected.join(','));
      history.replaceState(null, '', url);
    }
  }
  topicFilters.forEach(f => f.addEventListener('change', () => { update(); scroller.scrollTop = 0; }));
  document.getElementById('all-topics').addEventListener('click', () => { topicFilters.forEach(f => { f.checked = false; }); update(); scroller.scrollTop = 0; });
  document.getElementById('reset-comparison').addEventListener('click', () => { topicFilters.forEach(f => { f.checked = false; }); input.value = ''; comparable.checked = false; update(); });
  input.addEventListener('input', () => { update(); scroller.scrollTop = 0; });
  comparable.addEventListener('change', () => { update(); scroller.scrollTop = 0; });
  document.getElementById('clear-search').addEventListener('click', () => { input.value = ''; update(); input.focus(); });
  filters.forEach(filter => filter.addEventListener('change', () => {
    if (!filters.some(f => f.checked)) filter.checked = true;
    updateColumns();
    update();
  }));
  mobile.addEventListener('change', updateColumns);
  const menus = Array.from(document.querySelectorAll('.candidate-menu'));
  document.addEventListener('click', event => { menus.forEach(menu => { if (!menu.contains(event.target)) menu.open = false; }); });
  menus.forEach(menu => {
    menu.addEventListener('toggle', () => { if (menu.open) menus.forEach(other => { if (other !== menu) other.open = false; }); });
    menu.addEventListener('keydown', event => { if (event.key === 'Escape') { menu.open = false; menu.querySelector('summary').focus(); } });
  });

  function revealHash() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    const target = document.getElementById(id) || (id.startsWith('source-') ? document.querySelector('[data-source-id="' + CSS.escape(id.slice(7)) + '"]') : null);
    if (!target) return;
    const topic = target.closest('.comparison-topic');
    if (topic) {
      topicFilters.forEach(f => { f.checked = f.dataset.topicFilter === topic.dataset.topic; });
      input.value = '';
      comparable.checked = false;
      const cell = target.closest('[data-candidate]');
      if (cell) {
        const filter = filters.find(f => f.dataset.candidateFilter === cell.dataset.candidate);
        if (filter) filter.checked = true;
        updateColumns();
      }
      update();
    }
    for (let element = target; element; element = element.parentElement) {
      if (element.tagName === 'DETAILS') element.open = true;
    }
    requestAnimationFrame(() => {
      if (topic) {
        scroller.scrollIntoView({ block: 'start' });
        const row = target.closest('.comparison-question');
        const scrollTarget = mobile.matches && target === row ? row.previousElementSibling : target;
        const bounds = scrollTarget.getBoundingClientRect();
        const viewport = scroller.getBoundingClientRect();
        const headerHeight = scroller.querySelector('thead').getBoundingClientRect().height;
        scroller.scrollTop += bounds.top - viewport.top - headerHeight - 12;
        const cell = target.closest('td');
        if (cell) {
          const labelWidth = scroller.querySelector('.corner-cell').getBoundingClientRect().width;
          scroller.scrollLeft += cell.getBoundingClientRect().left - viewport.left - labelWidth;
        }
      } else target.scrollIntoView({ block: 'start' });
    });
  }
  document.querySelectorAll('a[href^="#"]').forEach(a => a.addEventListener('click', () => requestAnimationFrame(revealHash)));
  window.addEventListener('hashchange', revealHash);
  updateColumns();
  update(false);
  if (location.hash) revealHash();
})();
