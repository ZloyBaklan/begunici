import { apiRequest } from './utils.js';

function getScannerApp() {
    return document.getElementById('scanner-app');
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function setBlockText(element, text, visible = true) {
    if (!element) return;
    element.textContent = text || '';
    element.style.display = visible && text ? 'block' : 'none';
}

function renderWarnings(warnings) {
    const warningsBlock = document.getElementById('scanner-warnings');
    if (!warningsBlock) return;

    const cleanWarnings = Array.isArray(warnings)
        ? warnings.map((item) => String(item || '').trim()).filter(Boolean)
        : [];

    if (!cleanWarnings.length) {
        warningsBlock.innerHTML = '';
        warningsBlock.style.display = 'none';
        return;
    }

    warningsBlock.innerHTML = cleanWarnings
        .map((warning) => `<div>${escapeHtml(warning)}</div>`)
        .join('');
    warningsBlock.style.display = 'block';
}

function renderAnimalLinks(animals) {
    if (!Array.isArray(animals) || !animals.length) {
        return '<span class="text-muted">-</span>';
    }

    return animals
        .map((animal) => {
            const tag = escapeHtml(animal.display_name || animal.tag_number || '-');
            const url = animal.url ? escapeHtml(animal.url) : '';
            const archived = animal.is_archived ? ' <span class="text-muted">(архив)</span>' : '';
            if (!url) {
                return `${tag}${archived}`;
            }
            return `<a href="${url}" class="text-decoration-none">${tag}</a>${archived}`;
        })
        .join(', ');
}

function renderTable(rows) {
    const tableBody = document.querySelector('#scanner-results-table tbody');
    if (!tableBody) return;

    if (!Array.isArray(rows) || !rows.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="2" class="text-center text-muted py-4">
                    Сканер не вернул записей.
                </td>
            </tr>
        `;
        return;
    }

    tableBody.innerHTML = rows
        .map((row) => `
            <tr>
                <td>${escapeHtml(row.chip || '')}</td>
                <td>${renderAnimalLinks(row.animals)}</td>
            </tr>
        `)
        .join('');
}

async function readScannerData() {
    const app = getScannerApp();
    if (!app) return;

    const readButton = document.getElementById('scanner-read-btn');
    const exportButton = document.getElementById('scanner-export-btn');
    const statusBlock = document.getElementById('scanner-status');
    const errorBlock = document.getElementById('scanner-error');
    const readUrl = app.dataset.readUrl;

    setBlockText(errorBlock, '', false);
    renderWarnings([]);
    if (exportButton) exportButton.disabled = true;
    if (readButton) {
        readButton.disabled = true;
        readButton.textContent = 'Читаю...';
    }
    if (statusBlock) {
        statusBlock.textContent = 'Читаю историю со сканера. Это может занять несколько секунд...';
        statusBlock.className = 'text-muted mb-3';
    }

    try {
        const response = await apiRequest(readUrl, 'POST', {});
        const rows = response.results || [];

        renderTable(rows);
        renderWarnings(response.warnings || []);

        if (exportButton) exportButton.disabled = rows.length === 0;
        if (statusBlock) {
            statusBlock.textContent = `Прочитано записей: ${response.count || rows.length}.`;
            statusBlock.className = 'text-success mb-3';
        }
    } catch (error) {
        renderTable([]);
        setBlockText(
            errorBlock,
            error.message || 'Не удалось прочитать данные со сканера.',
            true
        );
        if (statusBlock) {
            statusBlock.textContent = 'Чтение не выполнено.';
            statusBlock.className = 'text-danger mb-3';
        }
    } finally {
        if (readButton) {
            readButton.disabled = false;
            readButton.textContent = 'Прочитать данные';
        }
    }
}

function exportScannerData() {
    const app = getScannerApp();
    if (!app?.dataset.exportUrl) return;
    window.location.href = app.dataset.exportUrl;
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('scanner-read-btn')?.addEventListener('click', readScannerData);
    document.getElementById('scanner-export-btn')?.addEventListener('click', exportScannerData);
});
