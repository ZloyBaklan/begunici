/* Feed UI stays scoped: no handlers or state in the existing animal module. */
(() => {
    'use strict';
    const card = document.getElementById('feed-plan');
    if (card && !card.dataset.bound) {
        card.dataset.bound = 'yes';
        const content = card.querySelector('#feed-plan-content');
        const toggle = card.querySelector('[data-feed-toggle]');
        const expand = show => { content.hidden = !show; toggle.textContent = show ? 'Свернуть' : 'Развернуть'; toggle.setAttribute('aria-expanded', String(show)); };
        toggle.addEventListener('click', () => expand(content.hidden));
        if (window.location.hash === '#feed-plan' || !content.hidden) expand(true);
        window.addEventListener('hashchange', () => { if (window.location.hash === '#feed-plan') expand(true); });
        const form = card.querySelector('[data-feed-norms]');
        const modeLabels = {norm: 'На одну голову в день', daily: 'На всё поголовье за сутки', monthly: 'На всё поголовье за месяц', yearly: form.dataset.yearExplanation};
        const exportLink = card.querySelector('[data-feed-export]');
        const periodLabel = card.querySelector('[data-feed-period-label]');
        const setMode = mode => {
            form.querySelectorAll('[data-feed-mode]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.feedMode === mode)));
            form.querySelectorAll('[data-feed-metric]').forEach(value => { value.hidden = value.dataset.feedMetric !== mode || form.dataset.editing === 'true'; });
            form.querySelector('[data-feed-view-explanation]').textContent = modeLabels[mode];
            form.querySelectorAll('[data-feed-total]').forEach(row => { row.hidden = row.dataset.feedTotal !== (mode === 'yearly' ? 'yearly' : 'monthly'); });
            exportLink.href = mode === 'yearly' ? exportLink.dataset.yearUrl : exportLink.dataset.monthUrl;
            exportLink.textContent = mode === 'yearly' ? 'Скачать Excel до конца года' : 'Скачать Excel за месяц';
            periodLabel.textContent = mode === 'yearly' ? periodLabel.dataset.yearCaption : periodLabel.dataset.monthCaption;
        };
        form.querySelectorAll('[data-feed-mode]').forEach(button => button.addEventListener('click', () => setMode(button.dataset.feedMode)));
        const editing = enabled => {
            form.dataset.editing = String(enabled);
            form.querySelectorAll('.feed-norm').forEach(input => { input.disabled = !enabled; input.hidden = !enabled; });
            form.querySelectorAll('[data-feed-mode]').forEach(button => { button.disabled = enabled; });
            if (form.querySelector('[data-feed-edit]')) {
                form.querySelector('[data-feed-edit]').hidden = enabled;
                form.querySelector('[data-feed-save]').hidden = !enabled;
                form.querySelector('[data-feed-cancel]').hidden = !enabled;
            }
            form.querySelector('[data-feed-norm-hint]').hidden = !enabled;
            setMode('norm');
        };
        editing(form.dataset.editing === 'true');
        form.querySelector('[data-feed-edit]')?.addEventListener('click', () => editing(true));
        form.querySelector('[data-feed-cancel]')?.addEventListener('click', () => { form.reset(); editing(false); });
    }
    document.querySelectorAll('.feeds nav a').forEach(link => {
        if (window.location.pathname === new URL(link.href).pathname) {
            link.classList.replace('btn-outline-secondary', 'btn-secondary');
            link.setAttribute('aria-current', 'page');
        }
    });
    document.querySelectorAll('.feeds form').forEach(form => {
        if (form.dataset.feedBound) return;
        form.dataset.feedBound = 'yes';
        form.addEventListener('submit', event => {
            if (form.dataset.feedAsk && !window.confirm(form.dataset.feedAsk)) { event.preventDefault(); return; }
            // A separate confirmation must not post an unsaved edit underneath it.
            if (form.hasAttribute('data-feed-confirm') && document.querySelector('[data-feed-draft][data-dirty]')) {
                event.preventDefault(); window.alert('Сначала сохраните исправления черновика или обновите страницу, чтобы их отменить.'); return;
            }
            if (form.dataset.submitting) { event.preventDefault(); return; }
            form.dataset.submitting = 'yes';
        });
        if (form.hasAttribute('data-feed-draft')) form.addEventListener('input', () => { form.dataset.dirty = 'yes'; });
    });
})();
