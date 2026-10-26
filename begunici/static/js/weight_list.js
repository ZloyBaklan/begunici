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
        const importFile = document.getElementById('weight-import-file');
        const previewImport = document.getElementById('weight-import-preview-btn');
        const confirmImport = document.getElementById('weight-import-confirm-btn');
        const importResult = document.getElementById('weight-import-result');
        if (root.dataset.importPreviewUrl && importFile && previewImport && confirmImport && importResult) {
            let approvedFile = null;
            let importing = false;

            function setImportBusy(value) {
                importing = value;
                importFile.disabled = value;
                previewImport.disabled = value;
                confirmImport.disabled = value || !approvedFile;
                importResult.setAttribute('aria-busy', String(value));
            }

            function renderImport(data, title, fatal = false) {
                const issues = [...(data.errors || []), ...(data.warnings || [])];
                importResult.replaceChildren();
                importResult.className = `mt-3 alert alert-${fatal ? 'danger' : issues.length ? 'warning' : 'success'}`;
                importResult.style.display = 'block';
                const heading = document.createElement('div');
                heading.className = 'fw-semibold mb-1';
                heading.textContent = title;
                importResult.appendChild(heading);
                if (!fatal && data.created_count === undefined) {
                    const count = document.createElement('div');
                    count.textContent = `Готово к импорту: ${data.valid_count || 0}`;
                    importResult.appendChild(count);
                }
                if (issues.length) {
                    const label = document.createElement('div');
                    label.className = 'fw-semibold mt-2 mb-1';
                    label.textContent = 'Проверка файла:';
                    importResult.appendChild(label);
                    const list = document.createElement('ul');
                    list.className = 'mb-0';
                    issues.forEach(message => {
                        const item = document.createElement('li');
                        item.textContent = message;
                        list.appendChild(item);
                    });
                    importResult.appendChild(list);
                }
            }

            async function uploadImport(url, file) {
                const body = new FormData();
                body.append('file', file);
                const response = await fetch(url, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '' },
                    body,
                });
                if (!(response.headers.get('content-type') || '').includes('application/json')) {
                    throw new Error('Не удалось выполнить импорт. Обновите страницу и повторите попытку.');
                }
                const data = await response.json();
                if (!response.ok) throw new Error(errorMessage(data));
                return data;
            }

            importFile.addEventListener('change', () => {
                approvedFile = null;
                confirmImport.disabled = true;
                importResult.style.display = 'none';
                importResult.replaceChildren();
            });
            previewImport.addEventListener('click', async () => {
                if (importing) return;
                approvedFile = null;
                const file = importFile.files?.[0];
                setImportBusy(true);
                try {
                    if (!file) throw new Error('Выберите файл импорта');
                    const data = await uploadImport(root.dataset.importPreviewUrl, file);
                    renderImport(data, 'Файл взвешиваний прочитан');
                    if (data.can_confirm && importFile.files?.[0] === file) approvedFile = file;
                } catch (error) {
                    renderImport({ errors: [error.message] }, 'Ошибка чтения файла', true);
                } finally {
                    setImportBusy(false);
                }
            });
            confirmImport.addEventListener('click', async () => {
                if (importing || !approvedFile || approvedFile !== importFile.files?.[0]) return;
                if (!window.confirm('Подтвердить импорт взвешиваний? Ошибочные строки будут пропущены.')) return;
                const file = approvedFile;
                approvedFile = null;
                setImportBusy(true);
                try {
                    const data = await uploadImport(root.dataset.importConfirmUrl, file);
                    renderImport(data, `Импорт завершен. Создано взвешиваний: ${data.created_count || 0}`);
                    loadPage();
                } catch (error) {
                    renderImport({ errors: [error.message] }, 'Ошибка импорта', true);
                } finally {
                    setImportBusy(false);
                }
            });
        }
        loadPage();
    });
})();
