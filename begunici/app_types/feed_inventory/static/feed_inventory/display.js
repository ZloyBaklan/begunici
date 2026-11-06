(() => {
    'use strict';
    document.querySelectorAll('[data-feed-month-form]').forEach(form => {
        if (form.dataset.bound) return;
        form.dataset.bound = '1';
        const month = form.querySelector('input[type="month"]');
        month.addEventListener('change', () => { if (month.value && month.checkValidity()) form.requestSubmit(); });
    });
    const card = document.getElementById('feed-actual');
    if (!card || card.dataset.bound) return;
    card.dataset.bound = '1';
    const content = card.querySelector('#feed-actual-content');
    const toggle = card.querySelector('[data-feed-actual-toggle]');
    const expand = show => { content.hidden = !show; toggle.textContent = show ? 'Свернуть' : 'Развернуть'; toggle.setAttribute('aria-expanded', String(show)); };
    toggle.addEventListener('click', () => expand(content.hidden));
    if (location.hash === '#feed-actual') expand(true);
    window.addEventListener('hashchange', () => { if (location.hash === '#feed-actual') expand(true); });
})();
