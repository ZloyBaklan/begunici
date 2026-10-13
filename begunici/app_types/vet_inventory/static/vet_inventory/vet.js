(() => {
    'use strict';
    document.querySelectorAll('.vet-stock nav a').forEach(link => {
        if (window.location.pathname === new URL(link.href).pathname) {
            link.classList.replace('btn-outline-secondary', 'btn-secondary');
            link.setAttribute('aria-current', 'page');
        }
    });
    document.querySelectorAll('.vet-stock form').forEach(form => {
        form.addEventListener('submit', event => {
            if (form.dataset.vetAsk && !window.confirm(form.dataset.vetAsk)) { event.preventDefault(); return; }
            if (form.hasAttribute('data-vet-confirm') && document.querySelector('[data-vet-draft][data-dirty]')) {
                event.preventDefault(); window.alert('Сначала сохраните исправления черновика.'); return;
            }
            if (form.dataset.submitting) { event.preventDefault(); return; }
            form.dataset.submitting = 'yes';
        });
        if (form.hasAttribute('data-vet-draft')) form.addEventListener('input', () => { form.dataset.dirty = 'yes'; });
    });
    const form = document.querySelector('[data-vet-rule]');
    if (!form) return;
    const mode = form.querySelector('[data-vet-rule-mode]');
    const rows = form.querySelector('[data-vet-band-rows]');
    const showMode = () => {
        const bands = mode.value === 'bands';
        form.querySelector('[data-vet-bands]').hidden = !bands;
        form.querySelectorAll('[data-vet-bands] input').forEach(input => { input.disabled = !bands; });
        form.querySelector('[data-vet-rate]').hidden = bands;
        form.querySelector('[name=rate]').disabled = bands;
        form.querySelector('[name=rate]').required = !bands;
    };
    mode.addEventListener('change', showMode);
    form.querySelector('[data-vet-add-band]').addEventListener('click', () => {
        if (rows.children.length >= 20) return;
        const row = rows.firstElementChild.cloneNode(true);
        row.querySelectorAll('input').forEach(input => { input.value = ''; });
        rows.append(row);
    });
    rows.addEventListener('click', event => {
        if (event.target.closest('[data-vet-remove-band]') && rows.children.length > 1) event.target.closest('tr').remove();
    });
    showMode();
})();
