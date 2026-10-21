(() => {
    'use strict';

    document.addEventListener('DOMContentLoaded', () => {
        const root = document.getElementById('weight-list-page');
        if (!root) return;

        const form = document.getElementById('weight-filters');
        const rows = document.getElementById('weight-list');
        const pagination = document.getElementById('weight-pagination');
        const loading = document.getElementById('loading');
        const noData = document.getElementById('no-data');
        const errorBox = document.getElementById('weight-error');
        const total = document.getElementById('total-count');
        const dateFrom = form.elements.weight_date_from;
        const dateTo = form.elements.weight_date_to;
        const weightMin = form.elements.weight_min;
        const weightMax = form.elements.weight_max;
        let appliedFilters = new URLSearchParams();
        let requestId = 0;
        let controller = null;

        function readFilters() {
            dateTo.setCustomValidity(dateFrom.value && dateTo.value && dateFrom.value > dateTo.value
                ? 'Дата «по» не может быть раньше даты «с».' : '');
            weightMax.setCustomValidity(weightMin.value && weightMax.value
                && Number(weightMin.value) > Number(weightMax.value)
                ? 'Вес «до» не может быть меньше веса «от».' : '');
            if (!form.reportValidity()) return null;
            const params = new URLSearchParams();
            for (const [key, value] of new FormData(form)) {
                if (value.trim()) params.set(key, value.trim());
            }
            return params;
        }

        function renderRows(records) {
            const fragment = document.createDocumentFragment();
            for (const record of records) {
                const row = document.createElement('tr');
                const tag = document.createElement('td');
                if (record.animal_url) {
                    const link = document.createElement('a');
                    link.href = record.animal_url;
                    link.className = 'text-decoration-none';
                    link.textContent = record.tag_number;
                    tag.appendChild(link);
                } else {
                    tag.textContent = record.tag_number;
                }
                row.appendChild(tag);
                // Date-only values must not shift with the browser's time zone.
                const date = record.weight_date.split('-').reverse().join('.');
                const weight = Number(record.weight).toLocaleString('ru-RU', { maximumFractionDigits: 2 });
                for (const value of [record.animal_type, record.rshn_tag || '-', date, weight]) {
                    const cell = document.createElement('td');
                    cell.textContent = value;
                    row.appendChild(cell);
                }
                fragment.appendChild(row);
            }
            rows.replaceChildren(fragment);
        }

        function renderPagination(data) {
            pagination.replaceChildren();
            if (data.total_pages <= 1) return;
            const list = document.createElement('ul');
            list.className = 'pagination justify-content-center flex-wrap';
            function addPage(label, page, active = false) {
                const item = document.createElement('li');
                item.className = `page-item${active ? ' active' : ''}`;
                const link = document.createElement('a');
                link.href = '#';
                link.className = 'page-link';
                link.textContent = label;
                if (active) link.setAttribute('aria-current', 'page');
                link.addEventListener('click', (event) => {
                    event.preventDefault();
                    loadPage(page);
                });
                item.appendChild(link);
                list.appendChild(item);
            }
            if (data.has_previous) addPage('Предыдущая', data.current_page - 1);
            for (let page = Math.max(1, data.current_page - 2);
                page <= Math.min(data.total_pages, data.current_page + 2); page++) {
                addPage(String(page), page, page === data.current_page);
            }
            if (data.has_next) addPage('Следующая', data.current_page + 1);
            pagination.appendChild(list);
        }

        function errorMessage(data) {
            if (typeof data === 'string') return data;
            if (Array.isArray(data)) return data.map(errorMessage).join(' ');
            if (data && typeof data === 'object') return Object.values(data).map(errorMessage).join(' ');
            return 'Не удалось загрузить взвешивания.';
        }

        async function loadPage(page = 1) {
            const id = ++requestId;
            if (controller) controller.abort();
            controller = new AbortController();
            const params = new URLSearchParams(appliedFilters);
            params.set('page', page);
            params.set('page_size', 10);
            rows.replaceChildren();
            pagination.replaceChildren();
            total.textContent = '0';
            noData.hidden = true;
            errorBox.hidden = true;
            loading.hidden = false;
            document.getElementById('weight-results').setAttribute('aria-busy', 'true');
            try {
                const response = await fetch(`${root.dataset.apiUrl}?${params}`, {
                    signal: controller.signal,
                    headers: { Accept: 'application/json' },
                });
                if (!response.ok || !(response.headers.get('content-type') || '').includes('application/json')) {
                    let message = 'Не удалось загрузить взвешивания. Обновите страницу и повторите попытку.';
                    if ((response.headers.get('content-type') || '').includes('application/json')) {
                        message = errorMessage(await response.json());
                    }
                    throw new Error(message);
                }
                const data = await response.json();
                if (id !== requestId) return;
                renderRows(data.results);
                renderPagination(data);
                total.textContent = data.count;
                noData.hidden = data.results.length > 0;
            } catch (error) {
                if (id !== requestId || error.name === 'AbortError') return;
                errorBox.textContent = error.message;
                errorBox.hidden = false;
            } finally {
                if (id === requestId) {
                    loading.hidden = true;
                    document.getElementById('weight-results').setAttribute('aria-busy', 'false');
                }
            }
        }

        form.addEventListener('submit', (event) => {
            event.preventDefault();
            const params = readFilters();
            if (params) {
                appliedFilters = params;
                loadPage();
            }
        });
        form.addEventListener('input', () => {
            dateTo.setCustomValidity('');
            weightMax.setCustomValidity('');
        });
        form.addEventListener('reset', () => {
            dateTo.setCustomValidity('');
            weightMax.setCustomValidity('');
            appliedFilters = new URLSearchParams();
            loadPage();
        });
        document.getElementById('weight-export').addEventListener('click', () => {
            const params = readFilters();
            if (params) window.location.assign(`${root.dataset.exportUrl}?${params}`);
        });
        loadPage();
    });
})();
