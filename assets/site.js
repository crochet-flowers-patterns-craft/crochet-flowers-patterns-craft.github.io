(() => {
  'use strict';
  const cards = [...document.querySelectorAll('.journal .pattern-card')];
  const input = document.getElementById('search');
  const buttons = [...document.querySelectorAll('[data-filter]')];
  let category = 'All patterns';
  function filter() {
    const query = input.value.trim().toLocaleLowerCase();
    let visible = 0;
    for (const card of cards) {
      const matches = (category === 'All patterns' || card.dataset.category === category) && card.dataset.search.includes(query);
      card.hidden = !matches;
      visible += Number(matches);
    }
    document.getElementById('result-count').textContent = `${visible} ${visible === 1 ? 'pattern' : 'patterns'}${query || category !== 'All patterns' ? ' found' : ' to inspire you'}`;
    document.getElementById('empty-state').hidden = visible !== 0;
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === category)));
  }
  if (input) {
    input.addEventListener('input', filter);
    buttons.forEach(button => button.addEventListener('click', () => { category = button.dataset.filter; filter(); }));
    document.getElementById('clear-search').addEventListener('click', () => { category = 'All patterns'; input.value = ''; filter(); input.focus(); });
    // Keep links from the previous static design usable.
    const routes = {about:'about.html',privacy:'privacy.html',terms:'terms.html',contact:'contact.html'};
    const old = location.hash.slice(1);
    if (routes[old]) location.replace(routes[old]);
    else if (old === 'patterns') document.getElementById('journal').scrollIntoView();
  }
  document.querySelectorAll('[data-print]').forEach(button => button.addEventListener('click', () => window.print()));
})();
