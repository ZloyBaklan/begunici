document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('genealogyModal');
    if (!modal) return;

    const searchForm = document.getElementById('genealogy-search-form');
    const searchInput = document.getElementById('genealogy-search');
    const list = document.getElementById('genealogy-list');
    const errorBox = document.getElementById('genealogy-error');
    const downloadButton = document.getElementById('genealogy-download');
    const selected = new Set();
    let downloading = false;
    let searchController;
    const typeLabels = {
        maker: 'Бараны-производители',
        ram: 'Баранчики',
        ewe: 'Ярки',
        sheep: 'Овцематки',
    };

    function updateSelection() {
        downloadButton.disabled = selected.size === 0 || downloading;
        list.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = selected.has(Number(checkbox.value));
            checkbox.disabled = downloading;
        });
    }

    function showError(message) {
        errorBox.textContent = message;
        errorBox.hidden = !message;
    }

    function showPrompt(message) {
        list.replaceChildren();
        const prompt = document.createElement('div');
        prompt.className = 'text-muted text-center py-3';
        prompt.textContent = message;
        list.appendChild(prompt);
        updateSelection();
    }

    function renderResults(results, count) {
        list.replaceChildren();
        if (!results.length) {
            const empty = document.createElement('div');
            empty.className = 'text-muted text-center py-3';
            empty.textContent = 'Животные не найдены';
            list.appendChild(empty);
        }
        let currentType;
        results.forEach(animal => {
            if (animal.animal_type !== currentType) {
                currentType = animal.animal_type;
                const heading = document.createElement('h6');
                heading.className = 'text-primary mt-3 mb-2';
                heading.textContent = typeLabels[animal.animal_type] || animal.animal_type_label;
                list.appendChild(heading);
            }
            const item = document.createElement('div');
            item.className = 'form-check mb-2';
            const checkbox = document.createElement('input');
            checkbox.className = 'form-check-input';
            checkbox.type = 'checkbox';
            checkbox.id = `genealogy-animal-${animal.tag_id}`;
            checkbox.value = animal.tag_id;
            checkbox.addEventListener('change', () => {
                if (checkbox.checked) selected.add(animal.tag_id);
                else selected.delete(animal.tag_id);
                updateSelection();
            });
            const label = document.createElement('label');
            label.className = 'form-check-label';
            label.htmlFor = checkbox.id;
            label.textContent = `${animal.display_name} (${animal.animal_type_label}) - ${animal.status}`;
            item.append(checkbox, label);
            list.appendChild(item);
        });
        if (count > results.length) {
            const info = document.createElement('div');
            info.className = 'text-muted text-center mt-2 small';
            info.textContent = `Показано первых ${results.length} из ${count} результатов`;
            list.appendChild(info);
        }
        updateSelection();
    }

    async function searchAnimals() {
        if (downloading) return;
        if (searchController) searchController.abort();
        const search = searchInput.value.trim();
        showError('');
        if (!search) {
            showPrompt('Введите бирку или РСХН для поиска');
            return;
        }
        const controller = new AbortController();
        searchController = controller;
        list.innerHTML = `
            <div class="text-center py-3">
                <div class="spinner-border spinner-border-sm" role="status">
                    <span class="visually-hidden">Поиск...</span>
                </div>
                <div class="mt-2">Поиск животных...</div>
            </div>
        `;
        updateSelection();
        const params = new URLSearchParams({ search });
        try {
            const response = await fetch(`${modal.dataset.searchUrl}?${params}`, { signal: controller.signal });
            if (!response.ok) throw new Error('Не удалось загрузить список животных');
            const data = await response.json();
            if (controller.signal.aborted) return;
            renderResults(data.results, data.count);
        } catch (error) {
            if (error.name === 'AbortError') return;
            list.replaceChildren();
            showError(error.message || 'Ошибка поиска животных');
        } finally {
            if (searchController === controller) {
                updateSelection();
            }
        }
    }

    searchForm.addEventListener('submit', event => {
        event.preventDefault();
        searchAnimals();
    });
    modal.addEventListener('show.bs.modal', () => {
        if (searchController) searchController.abort();
        searchInput.value = '';
        showError('');
        showPrompt('Введите бирку или РСХН и нажмите "Поиск" для отображения результатов');
    });

    downloadButton.addEventListener('click', async () => {
        if (!selected.size || downloading) return;
        downloading = true;
        showError('');
        downloadButton.textContent = 'Подготовка...';
        updateSelection();
        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
            const response = await fetch(modal.dataset.exportUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ tag_ids: Array.from(selected) }),
            });
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.error || 'Не удалось скачать таблицу генеалогии');
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            const disposition = response.headers.get('Content-Disposition') || '';
            const utf8Name = disposition.match(/filename\*=UTF-8''([^;]+)/i);
            const plainName = disposition.match(/filename="?([^";]+)"?/i);
            link.download = utf8Name ? decodeURIComponent(utf8Name[1]) : plainName?.[1] || 'genealogy.xlsx';
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (error) {
            showError(error.message || 'Ошибка экспорта');
        } finally {
            downloading = false;
            downloadButton.textContent = 'Скачать';
            updateSelection();
        }
    });
});
