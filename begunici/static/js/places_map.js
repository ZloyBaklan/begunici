import { apiRequest, getApiErrorMessage, getCSRFToken } from "./utils.js";

let currentBarnStats = null;
let showEmptySections = false;
let carpetMoveSelectedAnimalKeys = new Set();
let carpetMoveSelectedAnimalsData = new Map();

document.addEventListener('DOMContentLoaded', function () {
    loadBarnsSelector();
    
    // Обработчик кнопки "Назад к списку"
    document.getElementById('back-to-list').addEventListener('click', function() {
        showBarnsSelector();
    });

    const showEmptySectionsCheckbox = document.getElementById('show-empty-sections-checkbox');
    if (showEmptySectionsCheckbox) {
        showEmptySectionsCheckbox.checked = false;
        showEmptySectionsCheckbox.addEventListener('change', function() {
            showEmptySections = this.checked;
            if (currentBarnStats) {
                displayBarnFromStatistics(currentBarnStats);
            }
        });
    }

    const carpetMovePlaceSelect = document.getElementById('carpet-move-place');
    if (carpetMovePlaceSelect) {
        carpetMovePlaceSelect.addEventListener('change', refreshCarpetMoveWarnings);
    }

    const carpetMoveSearchInput = document.getElementById('carpet-move-animals-search');
    if (carpetMoveSearchInput) {
        carpetMoveSearchInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                searchCarpetMoveAnimals();
            }
        });
    }

    const carpetMoveSearchButton = document.getElementById('carpet-move-animals-search-button');
    if (carpetMoveSearchButton) {
        carpetMoveSearchButton.addEventListener('click', searchCarpetMoveAnimals);
    }
});

function formatSectionMetric(value, unit) {
    if (value === null || value === undefined || value === '') {
        return '-';
    }

    const numberValue = Number(value);
    if (Number.isNaN(numberValue)) {
        return '-';
    }

    const normalized = Number.isInteger(numberValue)
        ? `${numberValue}`
        : numberValue.toFixed(1).replace(/\.0$/, '');

    return unit ? `${normalized} ${unit}` : normalized;
}

function formatSectionCount(value) {
    const numberValue = Number(value);
    if (Number.isNaN(numberValue)) {
        return '0';
    }
    return `${numberValue}`;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function getPlaceSortParts(place) {
    const text = String(place?.sheepfold || '');
    const match = text.match(/Овчарня\s+(\d+)\s+Отсек\s+(\d+)/i);
    if (!match) {
        return [Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER, text];
    }
    return [Number(match[1]), Number(match[2]), text];
}

function sortPlacesBySheepfold(places) {
    return [...places].sort((left, right) => {
        const leftParts = getPlaceSortParts(left);
        const rightParts = getPlaceSortParts(right);
        return (
            leftParts[0] - rightParts[0]
            || leftParts[1] - rightParts[1]
            || leftParts[2].localeCompare(rightParts[2], 'ru')
        );
    });
}

async function populatePlaceSelect(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return;

    select.disabled = true;
    select.innerHTML = '<option value="">Загрузка мест...</option>';

    try {
        const places = await loadAllPages('/veterinary/api/place/?page_size=100');
        select.innerHTML = '<option value="">Выберите место...</option>';
        sortPlacesBySheepfold(places).forEach(place => {
            const option = document.createElement('option');
            option.value = place.id;
            option.textContent = place.sheepfold;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка загрузки мест:', error);
        select.innerHTML = '<option value="">Не удалось загрузить места</option>';
    } finally {
        select.disabled = false;
    }
}

function getCarpetMoveAnimalKey(typeCode, tagNumber) {
    return `${typeCode}:${tagNumber}`;
}

function getCarpetMoveSelectedAnimalsArray() {
    return Array.from(carpetMoveSelectedAnimalsData.values()).map(animal => ({
        animal_type: animal.type_code,
        tag_number: animal.tag_number,
    }));
}

function updateCarpetMoveSelectedDisplay() {
    const display = document.getElementById('carpet-move-selected-display');
    if (!display) return;

    const selectedAnimals = Array.from(carpetMoveSelectedAnimalsData.values());
    if (selectedAnimals.length === 0) {
        display.textContent = 'Не выбрано';
        display.className = 'place-map-selection-display text-muted';
        return;
    }

    const tags = selectedAnimals.map(animal => animal.tag_number);
    const visibleTags = tags.slice(0, 20).join(', ');
    const tail = tags.length > 20 ? `, ... (+${tags.length - 20})` : '';
    display.textContent = `Выбрано: ${selectedAnimals.length} (${visibleTags}${tail})`;
    display.className = 'place-map-selection-display text-success';
}

function renderCarpetMoveResult(data, title, alertClass = null) {
    const resultBlock = document.getElementById('carpet-move-warning-result');
    if (!resultBlock) return;

    const warnings = data.warnings || [];
    const errors = data.errors || [];
    const hasIssues = warnings.length > 0 || errors.length > 0;
    const resultClass = alertClass || (hasIssues ? 'alert-warning' : 'alert-success');
    const issueItems = []
        .concat(errors.map(error => `<li>${escapeHtml(error)}</li>`))
        .concat(warnings.map(warning => `<li>${escapeHtml(warning)}</li>`))
        .join('');

    resultBlock.className = `alert ${resultClass}`;
    resultBlock.style.display = 'block';
    resultBlock.innerHTML = `
        <div class="fw-semibold mb-1">${escapeHtml(title)}</div>
        ${data.movable_count !== undefined ? `<div>К перемещению: ${data.movable_count || 0}</div>` : ''}
        ${data.moved_count !== undefined ? `<div>Перемещено: ${data.moved_count || 0}</div>` : ''}
        ${issueItems ? `<hr><ul class="mb-0">${issueItems}</ul>` : ''}
    `;
}

function setCarpetMoveSubmitEnabled(enabled) {
    const submitButton = document.getElementById('carpet-move-submit');
    if (submitButton) {
        submitButton.disabled = !enabled;
    }
}

async function refreshCarpetMoveWarnings() {
    const placeId = document.getElementById('carpet-move-place')?.value;
    const selectedAnimals = getCarpetMoveSelectedAnimalsArray();
    const resultBlock = document.getElementById('carpet-move-warning-result');

    setCarpetMoveSubmitEnabled(false);

    if (!selectedAnimals.length || !placeId) {
        if (resultBlock) {
            resultBlock.style.display = 'none';
            resultBlock.innerHTML = '';
        }
        return;
    }

    renderCarpetMoveResult({ movable_count: selectedAnimals.length }, 'Проверяем предупреждения...', 'alert-info');

    try {
        const data = await requestBulkPlaceMove(selectedAnimals, placeId, false, true);
        const movableCount = data.movable_count || 0;
        const warnings = data.warnings || [];
        const title = warnings.length
            ? 'Есть предупреждения. Перемещение всё равно можно выполнить.'
            : 'Предупреждений нет';
        renderCarpetMoveResult(data, title);
        setCarpetMoveSubmitEnabled(movableCount > 0);
    } catch (error) {
        renderCarpetMoveResult(
            { errors: [error.message || 'Не удалось проверить перемещение'] },
            'Ошибка проверки',
            'alert-warning'
        );
    }
}

async function toggleCarpetPlaceMoveCard() {
    const card = document.getElementById('carpet-place-move-card');
    const toggleButton = document.getElementById('carpet-place-move-toggle');
    if (!card) return;

    const shouldShow = card.style.display === 'none' || !card.style.display;
    card.style.display = shouldShow ? 'block' : 'none';
    if (toggleButton) {
        toggleButton.setAttribute('aria-expanded', shouldShow ? 'true' : 'false');
    }

    if (shouldShow) {
        await populatePlaceSelect('carpet-move-place');
        updateCarpetMoveSelectedDisplay();
        await refreshCarpetMoveWarnings();
        card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function openCarpetMoveAnimalsModal() {
    const modal = document.getElementById('carpet-move-animals-modal');
    const searchInput = document.getElementById('carpet-move-animals-search');
    const list = document.getElementById('carpet-move-animals-list');

    if (searchInput) searchInput.value = '';
    if (list) {
        list.innerHTML = `
            <div class="text-muted text-center py-3">
                Введите бирку или РСХН и нажмите "Поиск" для отображения результатов
            </div>
        `;
    }
    if (modal) modal.style.display = 'block';
}

function closeCarpetMoveAnimalsModal() {
    const modal = document.getElementById('carpet-move-animals-modal');
    if (modal) modal.style.display = 'none';
}

function createCarpetMoveAnimalItem(animal) {
    const key = getCarpetMoveAnimalKey(animal.type_code, animal.tag_number);
    const item = document.createElement('div');
    item.className = 'form-check mb-2';

    const rshnText = animal.rshn_tag ? `; РСХН: ${escapeHtml(animal.rshn_tag)}` : '';
    item.innerHTML = `
        <input
            class="form-check-input carpet-move-animal-checkbox"
            type="checkbox"
            value="${escapeHtml(key)}"
            data-type="${escapeHtml(animal.type_code)}"
            data-tag="${escapeHtml(animal.tag_number)}"
            data-label="${escapeHtml(animal.animal_type)}"
            data-status="${escapeHtml(animal.status || '')}"
            data-rshn="${escapeHtml(animal.rshn_tag || '')}"
        >
        <label class="form-check-label">
            ${escapeHtml(animal.tag_number)} (${escapeHtml(animal.animal_type)}) - ${escapeHtml(animal.status || '-')}${rshnText}
        </label>
    `;

    return item;
}

function saveCarpetMoveAnimalSelectionFromModal() {
    const checkboxes = document.querySelectorAll('.carpet-move-animal-checkbox');
    checkboxes.forEach(checkbox => {
        const key = checkbox.value;
        if (checkbox.checked) {
            carpetMoveSelectedAnimalKeys.add(key);
            carpetMoveSelectedAnimalsData.set(key, {
                type_code: checkbox.dataset.type,
                tag_number: checkbox.dataset.tag,
                animal_type: checkbox.dataset.label,
                status: checkbox.dataset.status,
                rshn_tag: checkbox.dataset.rshn,
            });
        } else {
            carpetMoveSelectedAnimalKeys.delete(key);
            carpetMoveSelectedAnimalsData.delete(key);
        }
    });
}

function restoreCarpetMoveAnimalSelectionInModal() {
    const checkboxes = document.querySelectorAll('.carpet-move-animal-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = carpetMoveSelectedAnimalKeys.has(checkbox.value);
    });
}

async function searchCarpetMoveAnimals() {
    const searchInput = document.getElementById('carpet-move-animals-search');
    const list = document.getElementById('carpet-move-animals-list');
    const search = (searchInput?.value || '').trim();

    if (!list) return;

    if (!search) {
        list.innerHTML = `
            <div class="text-muted text-center py-3">
                Введите бирку или РСХН для поиска
            </div>
        `;
        return;
    }

    saveCarpetMoveAnimalSelectionFromModal();
    list.innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Поиск...</span>
            </div>
            <div class="mt-2">Поиск животных...</div>
        </div>
    `;

    try {
        const animals = await apiRequest(
            `/animals/api/animals-without-otbivka/?include_with_otbivka=1&search=${encodeURIComponent(search)}`
        );
        const limitedAnimals = (animals || []).slice(0, 100);
        list.innerHTML = '';

        if (limitedAnimals.length === 0) {
            list.innerHTML = '<div class="text-center text-muted">Животные не найдены</div>';
            return;
        }

        const groups = [
            ['maker', 'Бараны-производители'],
            ['ram', 'Баранчики'],
            ['ewe', 'Ярки'],
            ['sheep', 'Овцематки'],
        ];

        groups.forEach(([typeCode, title]) => {
            const groupAnimals = limitedAnimals.filter(animal => animal.type_code === typeCode);
            if (!groupAnimals.length) return;

            const header = document.createElement('h6');
            header.textContent = title;
            header.className = 'mt-3 mb-2 text-primary';
            list.appendChild(header);

            groupAnimals.forEach(animal => {
                list.appendChild(createCarpetMoveAnimalItem(animal));
            });
        });

        if ((animals || []).length > 100) {
            const info = document.createElement('div');
            info.className = 'text-muted text-center mt-2 small';
            info.textContent = `Показано первых 100 из ${animals.length} результатов`;
            list.appendChild(info);
        }

        restoreCarpetMoveAnimalSelectionInModal();
    } catch (error) {
        console.error('Ошибка поиска животных для коврового перемещения:', error);
        list.innerHTML = '<div class="text-danger text-center py-3">Ошибка поиска</div>';
    }
}

async function confirmCarpetMoveAnimalsSelection() {
    saveCarpetMoveAnimalSelectionFromModal();
    updateCarpetMoveSelectedDisplay();
    closeCarpetMoveAnimalsModal();
    await refreshCarpetMoveWarnings();
}

async function clearCarpetMoveSelection() {
    carpetMoveSelectedAnimalKeys.clear();
    carpetMoveSelectedAnimalsData.clear();
    updateCarpetMoveSelectedDisplay();
    await refreshCarpetMoveWarnings();
}

async function refreshVisibleBarnMap() {
    const titleElement = document.getElementById('selected-barn-title');
    const match = titleElement?.textContent?.match(/Овчарня (\d+)/);
    if (match) {
        await loadSpecificBarn(parseInt(match[1]));
    } else {
        await loadBarnsSelector();
    }
}

async function executeCarpetPlaceMove() {
    const placeId = document.getElementById('carpet-move-place')?.value;
    const selectedAnimals = getCarpetMoveSelectedAnimalsArray();

    if (!selectedAnimals.length) {
        alert('Выберите животных для перемещения');
        return;
    }
    if (!placeId) {
        alert('Выберите овчарню и отсек');
        return;
    }

    if (!confirm(`Переместить выбранных животных: ${selectedAnimals.length}?`)) {
        return;
    }

    setCarpetMoveSubmitEnabled(false);
    try {
        const data = await requestBulkPlaceMove(selectedAnimals, placeId, true, false);
        renderCarpetMoveResult(data, `Перемещение завершено. Перемещено: ${data.moved_count || 0}`);
        carpetMoveSelectedAnimalKeys.clear();
        carpetMoveSelectedAnimalsData.clear();
        updateCarpetMoveSelectedDisplay();
        await refreshVisibleBarnMap();
    } catch (error) {
        renderCarpetMoveResult(
            { errors: [error.message || 'Не удалось выполнить перемещение'] },
            'Ошибка перемещения',
            'alert-warning'
        );
        setCarpetMoveSubmitEnabled(true);
    }
}

function renderMonthStatsBlock(title, monthStats) {
    if (!monthStats) {
        return `
            <div class="section-month-block">
                <div class="section-month-title">${title}</div>
                <div class="section-month-line">Нет данных</div>
            </div>
        `;
    }

    const periodText = (monthStats.period_start && monthStats.period_end)
        ? `${monthStats.period_start} - ${monthStats.period_end}`
        : 'Период не задан';

    const avgAgeText = formatSectionMetric(monthStats.avg_age_months, 'мес.');
    const avgWeightLambsText = formatSectionMetric(monthStats.avg_weight_lambs_kg, 'кг');
    const avgWeightOthersText = formatSectionMetric(monthStats.avg_weight_others_kg, 'кг');

    return `
        <div class="section-month-block">
            <div class="section-month-title">${title}</div>
            <div class="section-month-period">${periodText}</div>
            <div class="section-month-line">
                Всего: ${formatSectionCount(monthStats.total)},
                Б-П: ${formatSectionCount(monthStats.makers)},
                Б: ${formatSectionCount(monthStats.rams)},
                Я: ${formatSectionCount(monthStats.ewes)},
                О: ${formatSectionCount(monthStats.sheep)},
                Ягнят: ${formatSectionCount(monthStats.lambs_count)}
            </div>
            <div class="section-month-line">
                Ср. возраст: ${avgAgeText},
                ср. вес ягнят: ${avgWeightLambsText},
                ср. вес остальных животных: ${avgWeightOthersText}
            </div>
        </div>
    `;
}

// Показать селектор овчарен
function showBarnsSelector() {
    document.getElementById('barns-selector').style.display = 'block';
    document.getElementById('selected-barn-container').style.display = 'none';
}

// Показать выбранную овчарню
function showSelectedBarn() {
    document.getElementById('barns-selector').style.display = 'none';
    document.getElementById('selected-barn-container').style.display = 'block';
}

// Загрузка селектора овчарен
async function loadBarnsSelector() {
    const container = document.getElementById('barns-list');
    container.innerHTML = '<div class="loading">Загрузка списка овчарен...</div>';
    
    try {
        // Получаем все места
        const places = await loadAllPages('/veterinary/api/place/?page_size=100');
        
        // Группируем места по овчарням БЕЗ подсчета животных
        const barnGroups = groupPlacesByBarn(places);
        
        // Отображаем список овчарен
        displayBarnsSelector(barnGroups);
        
    } catch (error) {
        console.error('Ошибка при загрузке списка овчарен:', error);
        container.innerHTML = '<div style="color: red;">Ошибка загрузки данных</div>';
    }
}

// Простая группировка мест по овчарням (без статистики)
function groupPlacesByBarn(places) {
    const barnGroups = {};
    
    places.forEach(place => {
        const match = place.sheepfold.match(/Овчарня (\d+) Отсек (\d+)/);
        if (match) {
            const barnNumber = parseInt(match[1]);
            
            if (!barnGroups[barnNumber]) {
                barnGroups[barnNumber] = {
                    barnNumber,
                    sections: {},
                    totalSections: 0
                };
            }
            
            const sectionNumber = parseInt(match[2]);
            barnGroups[barnNumber].sections[sectionNumber] = {
                id: place.id,
                name: place.sheepfold,
                barnNumber,
                sectionNumber
            };
            barnGroups[barnNumber].totalSections++;
        }
    });
    
    return barnGroups;
}

// Отображение селектора овчарен
function displayBarnsSelector(barnGroups) {
    const container = document.getElementById('barns-list');
    container.innerHTML = '';
    
    // Сортируем овчарни по номерам
    const sortedBarns = Object.keys(barnGroups).sort((a, b) => parseInt(a) - parseInt(b));
    
    if (sortedBarns.length === 0) {
        container.innerHTML = '<div class="no-barns">Овчарни не найдены</div>';
        return;
    }
    
    sortedBarns.forEach(barnNumber => {
        const barn = barnGroups[barnNumber];
        const card = createBarnSelectorCard(barn);
        container.appendChild(card);
    });
}

// Создание карточки овчарни для селектора
function createBarnSelectorCard(barn) {
    const card = document.createElement('div');
    card.className = 'barn-selector-card';
    card.onclick = () => loadSpecificBarn(barn.barnNumber);
    
    card.innerHTML = `
        <h3>Овчарня ${barn.barnNumber}</h3>
        <div class="barn-stats">
            <div>Отсеков: ${barn.totalSections}</div>
        </div>
    `;
    
    return card;
}

// Загрузка конкретной овчарни
async function loadSpecificBarn(barnNumber) {
    const container = document.getElementById('barn-content');
    const title = document.getElementById('selected-barn-title');
    const showEmptySectionsCheckbox = document.getElementById('show-empty-sections-checkbox');
    
    title.textContent = `Овчарня ${barnNumber}`;
    container.innerHTML = '<div class="loading">Загрузка овчарни...</div>';
    currentBarnStats = null;
    showEmptySections = false;
    if (showEmptySectionsCheckbox) {
        showEmptySectionsCheckbox.checked = false;
    }
    
    // Показываем контейнер выбранной овчарни
    showSelectedBarn();
    
    try {
        console.log(`Загружаем статистику для овчарни ${barnNumber}`);
        
        // Используем новый быстрый API для получения статистики
        const barnStats = await apiRequest(`/veterinary/api/barn/${barnNumber}/statistics/`);
        
        console.log(`Получена статистика:`, barnStats);
        
        if (barnStats.sections.length === 0) {
            container.innerHTML = '<div class="empty-barn">В этой овчарне нет отсеков</div>';
            return;
        }
        
        // Отображаем овчарню используя полученную статистику
        currentBarnStats = barnStats;
        displayBarnFromStatistics(barnStats);
        
    } catch (error) {
        console.error('Ошибка при загрузке овчарни:', error);
        container.innerHTML = `<div style="color: red;">Ошибка загрузки данных: ${error.message}</div>`;
    }
}

// Отображение овчарни на основе статистики
function getSectionAnimalStats(barnStats, section) {
    return barnStats.animals_by_section?.[section.id] || {
        makers: 0,
        rams: 0,
        ewes: 0,
        sheep: 0,
        total: 0,
        avg_age_months: null,
        avg_weight_kg: null,
        avg_weight_lambs_kg: null,
        avg_weight_others_kg: null,
        lambs_count: 0,
        current_month: null,
        previous_month: null,
    };
}

function isSectionEmpty(barnStats, section) {
    const stats = getSectionAnimalStats(barnStats, section);
    return Number(stats.total || 0) <= 0;
}

function displayBarnFromStatistics(barnStats) {
    const container = document.getElementById('barn-content');
    container.innerHTML = '';
    
    const barnDiv = document.createElement('div');
    barnDiv.className = 'barn-container';
    
    // Создаем таблицу с отсеками
    const table = document.createElement('table');
    table.className = 'barn-table';
    
    const sections = [...barnStats.sections]
        .sort((a, b) => Number(a.section_number) - Number(b.section_number))
        .filter(section => showEmptySections || !isSectionEmpty(barnStats, section));

    if (sections.length === 0) {
        barnDiv.innerHTML = `
            <div class="empty-barn">
                В этой овчарне нет отсеков с животными. Включите «Показать пустые отсеки», чтобы увидеть все отсеки.
            </div>
        `;
        container.appendChild(barnDiv);
        return;
    }

    const rows = Math.ceil(sections.length / 2);
    
    for (let row = 0; row < rows; row++) {
        const tr = document.createElement('tr');
        
        // Левый отсек
        const leftIndex = row * 2;
        if (leftIndex < sections.length) {
            const leftSection = sections[leftIndex];
            const leftCell = createSectionCellFromStats(leftSection, getSectionAnimalStats(barnStats, leftSection));
            tr.appendChild(leftCell);
        }
        
        // Правый отсек (если есть)
        const rightIndex = row * 2 + 1;
        if (rightIndex < sections.length) {
            const rightSection = sections[rightIndex];
            const rightCell = createSectionCellFromStats(rightSection, getSectionAnimalStats(barnStats, rightSection));
            tr.appendChild(rightCell);
        } else {
            // Если правого отсека нет, добавляем пустую ячейку для выравнивания
            const emptyCell = document.createElement('td');
            emptyCell.className = 'section-cell empty-placeholder';
            emptyCell.style.visibility = 'hidden';
            tr.appendChild(emptyCell);
        }
        
        table.appendChild(tr);
    }
    
    barnDiv.appendChild(table);
    container.appendChild(barnDiv);
}

// Создание ячейки отсека на основе статистики
function createSectionCellFromStats(section, animalStats) {
    const cell = document.createElement('td');
    cell.className = 'section-cell';

    const stats = animalStats || {
        makers: 0,
        rams: 0,
        ewes: 0,
        sheep: 0,
        total: 0,
        avg_age_months: null,
        avg_weight_kg: null,
        avg_weight_lambs_kg: null,
        avg_weight_others_kg: null,
        lambs_count: 0,
        current_month: null,
        previous_month: null,
    };
    const currentMonthStats = stats.current_month || null;
    const previousMonthStats = stats.previous_month || null;

    cell.innerHTML = `
        <div class="section-number">
            Отсек ${section.section_number}
        </div>
    `;

    const contentGrid = document.createElement('div');
    contentGrid.className = 'section-content-grid';

    const compositionBlock = document.createElement('div');
    compositionBlock.className = 'section-composition-block';
    compositionBlock.innerHTML = '<div class="section-composition-title">Состав животных</div>';

    if (stats.total > 0) {
        const animalsDiv = document.createElement('div');
        animalsDiv.className = 'animals-info';

        // Отображаем количество каждого типа животных
        if (stats.makers > 0) {
            const makersSpan = document.createElement('span');
            makersSpan.className = 'animal-count makers';
            makersSpan.textContent = `Б-П: ${stats.makers}`;
            makersSpan.onclick = () => loadAndShowAnimalsModal('Бараны-Производители', section.id, section.name);
            animalsDiv.appendChild(makersSpan);
        }

        if (stats.rams > 0) {
            const ramsSpan = document.createElement('span');
            ramsSpan.className = 'animal-count rams';
            ramsSpan.textContent = `Б: ${stats.rams}`;
            ramsSpan.onclick = () => loadAndShowAnimalsModal('Баранчики', section.id, section.name);
            animalsDiv.appendChild(ramsSpan);
        }

        if (stats.ewes > 0) {
            const ewesSpan = document.createElement('span');
            ewesSpan.className = 'animal-count ewes';
            ewesSpan.textContent = `Я: ${stats.ewes}`;
            ewesSpan.onclick = () => loadAndShowAnimalsModal('Ярки', section.id, section.name);
            animalsDiv.appendChild(ewesSpan);
        }

        if (stats.sheep > 0) {
            const sheepSpan = document.createElement('span');
            sheepSpan.className = 'animal-count sheep';
            sheepSpan.textContent = `О: ${stats.sheep}`;
            sheepSpan.onclick = () => loadAndShowAnimalsModal('Овцематки', section.id, section.name);
            animalsDiv.appendChild(sheepSpan);
        }

        compositionBlock.appendChild(animalsDiv);
    } else {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'empty-section';
        emptyDiv.textContent = 'Пусто';
        compositionBlock.appendChild(emptyDiv);
    }

    const monthStatsCol = document.createElement('div');
    monthStatsCol.className = 'section-month-stats';
    monthStatsCol.innerHTML = `
        ${renderMonthStatsBlock('Текущий месяц', currentMonthStats)}
        ${renderMonthStatsBlock('Предыдущий месяц', previousMonthStats)}
    `;

    contentGrid.appendChild(compositionBlock);
    contentGrid.appendChild(monthStatsCol);
    cell.appendChild(contentGrid);
    
    return cell;
}

// Загрузка и показ модального окна с животными
async function loadAndShowAnimalsModal(animalType, placeId, sectionName) {
    try {
        console.log(`Загружаем животных для отсека ${placeId}`);
        
        // Загружаем животных для конкретного отсека
        const animals = await apiRequest(`/veterinary/api/place/${placeId}/animals/`);
        
        // Фильтруем по типу
        const filteredAnimals = animals.filter(animal => {
            const typeMap = {
                'Бараны-Производители': 'Баран-Производитель',
                'Баранчики': 'Баранчик',
                'Ярки': 'Ярка',
                'Овцематки': 'Овцематка'
            };
            return animal.type === typeMap[animalType];
        });
        
        // Преобразуем в формат, ожидаемый старой функцией
        const formattedAnimals = filteredAnimals.map(animal => ({
            id: animal.tag_number, // Используем номер бирки как ID
            tag: { tag_number: animal.tag_number },
            display_name: animal.display_name || animal.tag_number, // Добавляем display_name
            rshn_tag: animal.rshn_tag || ''
        }));
        
        // Показываем модальное окно
        showAnimalsModal(animalType, formattedAnimals, sectionName, placeId);
        
    } catch (error) {
        console.error('Ошибка загрузки животных:', error);
        alert('Ошибка загрузки списка животных');
    }
}

// Отображение одной овчарни (старая функция, больше не используется)
// function displaySingleBarn(barnNumber, sections, animalsByPlace) {
//     const container = document.getElementById('barn-content');
//     container.innerHTML = '';
//     
//     const barnDiv = createBarnTable(barnNumber, sections, animalsByPlace);
//     container.appendChild(barnDiv);
// }

// Функция для загрузки всех данных с пагинацией
async function loadAllPages(url) {
    let allResults = [];
    let nextUrl = url;
    
    console.log(`Загружаем данные с URL: ${url}`);
    
    while (nextUrl) {
        try {
            console.log(`Запрос к: ${nextUrl}`);
            const response = await apiRequest(nextUrl);
            
            if (response.results) {
                // Пагинированный ответ
                allResults = allResults.concat(response.results);
                nextUrl = response.next;
                console.log(`Получено ${response.results.length} записей, всего: ${allResults.length}`);
            } else {
                // Непагинированный ответ
                allResults = response;
                nextUrl = null;
                console.log(`Получено ${response.length} записей (непагинированный ответ)`);
            }
        } catch (error) {
            console.error(`Ошибка при загрузке ${nextUrl}:`, error);
            throw error;
        }
    }
    
    console.log(`Итого загружено: ${allResults.length} записей`);
    return allResults;
}

// Группировка животных по местам
function groupAnimalsByPlace(animals) {
    const animalsByPlace = {};
    
    animals.forEach(animal => {
        if (animal.place && animal.place.id) {
            const placeId = animal.place.id;
            
            if (!animalsByPlace[placeId]) {
                animalsByPlace[placeId] = {
                    makers: [],
                    rams: [],
                    ewes: [],
                    sheep: []
                };
            }
            
            // Определяем тип животного по наличию полей
            if (animal.plemstatus !== undefined) {
                animalsByPlace[placeId].makers.push(animal);
            } else if (animal.tag && animal.tag.animal_type === 'Ram') {
                animalsByPlace[placeId].rams.push(animal);
            } else if (animal.tag && animal.tag.animal_type === 'Ewe') {
                animalsByPlace[placeId].ewes.push(animal);
            } else {
                animalsByPlace[placeId].sheep.push(animal);
            }
        }
    });
    
    return animalsByPlace;
}

// Создание таблицы для овчарни
function createBarnTable(barnNumber, sections, animalsByPlace) {
    const barnDiv = document.createElement('div');
    barnDiv.className = 'barn-container';
    
    // Получаем только существующие номера отсеков и сортируем их
    const sectionNumbers = Object.keys(sections).map(n => parseInt(n)).sort((a, b) => a - b);
    
    if (sectionNumbers.length === 0) {
        // Если нет отсеков, показываем сообщение
        const emptyMessage = document.createElement('div');
        emptyMessage.textContent = 'Нет отсеков в этой овчарне';
        emptyMessage.className = 'empty-barn';
        barnDiv.appendChild(emptyMessage);
        return barnDiv;
    }
    
    // Создаем таблицу с отсеками
    const table = document.createElement('table');
    table.className = 'barn-table';
    
    // Определяем количество строк (по 2 отсека в ряд)
    const rows = Math.ceil(sectionNumbers.length / 2);
    
    for (let row = 0; row < rows; row++) {
        const tr = document.createElement('tr');
        
        // Левый отсек
        const leftIndex = row * 2;
        if (leftIndex < sectionNumbers.length) {
            const leftSectionNum = sectionNumbers[leftIndex];
            const leftCell = createSectionCell(leftSectionNum, sections[leftSectionNum], animalsByPlace);
            tr.appendChild(leftCell);
        }
        
        // Правый отсек (если есть)
        const rightIndex = row * 2 + 1;
        if (rightIndex < sectionNumbers.length) {
            const rightSectionNum = sectionNumbers[rightIndex];
            const rightCell = createSectionCell(rightSectionNum, sections[rightSectionNum], animalsByPlace);
            tr.appendChild(rightCell);
        } else {
            // Если правого отсека нет, добавляем пустую ячейку для выравнивания
            const emptyCell = document.createElement('td');
            emptyCell.className = 'section-cell empty-placeholder';
            emptyCell.style.visibility = 'hidden';
            tr.appendChild(emptyCell);
        }
        
        table.appendChild(tr);
    }
    
    barnDiv.appendChild(table);
    return barnDiv;
}

// Создание ячейки отсека
function createSectionCell(sectionNumber, section, animalsByPlace) {
    const cell = document.createElement('td');
    cell.className = 'section-cell';
    
    // Отсек всегда существует (так как мы передаем только существующие)
    cell.innerHTML = `<div class="section-number">Отсек ${sectionNumber}</div>`;
    
    const animals = animalsByPlace[section.id];
    if (animals) {
        const animalsDiv = document.createElement('div');
        animalsDiv.className = 'animals-info';
        
        // Отображаем количество каждого типа животных
        if (animals.makers.length > 0) {
            const makersSpan = document.createElement('span');
            makersSpan.className = 'animal-count makers';
            makersSpan.textContent = `Бараны-Производители: ${animals.makers.length}`;
            makersSpan.onclick = () => showAnimalsModal('Бараны-Производители', animals.makers, section.name, section.id);
            animalsDiv.appendChild(makersSpan);
        }
        
        if (animals.rams.length > 0) {
            const ramsSpan = document.createElement('span');
            ramsSpan.className = 'animal-count rams';
            ramsSpan.textContent = `Баранчики: ${animals.rams.length}`;
            ramsSpan.onclick = () => showAnimalsModal('Баранчики', animals.rams, section.name, section.id);
            animalsDiv.appendChild(ramsSpan);
        }
        
        if (animals.ewes.length > 0) {
            const ewesSpan = document.createElement('span');
            ewesSpan.className = 'animal-count ewes';
            ewesSpan.textContent = `Ярки: ${animals.ewes.length}`;
            ewesSpan.onclick = () => showAnimalsModal('Ярки', animals.ewes, section.name, section.id);
            animalsDiv.appendChild(ewesSpan);
        }
        
        if (animals.sheep.length > 0) {
            const sheepSpan = document.createElement('span');
            sheepSpan.className = 'animal-count sheep';
            sheepSpan.textContent = `Овцематки: ${animals.sheep.length}`;
            sheepSpan.onclick = () => showAnimalsModal('Овцематки', animals.sheep, section.name, section.id);
            animalsDiv.appendChild(sheepSpan);
        }
        
        cell.appendChild(animalsDiv);
    } else {
        // Отсек пустой
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'empty-section';
        emptyDiv.textContent = 'Пусто';
        cell.appendChild(emptyDiv);
    }
    
    return cell;
}

// Показ модального окна с животными
function showAnimalsModal(animalType, animals, sectionName, placeId) {
    const modal = document.getElementById('animals-modal');
    const title = document.getElementById('modal-title');
    const list = document.getElementById('animals-list');
    const searchInput = document.getElementById('animals-modal-search');
    
    title.textContent = `${animalType} в ${sectionName}`;
    
    list.innerHTML = '';
    if (searchInput) {
        searchInput.value = '';
    }

    animals.forEach((animal, index) => {
        const animalDiv = document.createElement('div');
        animalDiv.className = 'animal-item';
        
        const tagNumber = animal.tag ? animal.tag.tag_number : 'Нет бирки';
        const displayName = animal.display_name || tagNumber;
        const rshnTag = animal.rshn_tag || '';
        animalDiv.dataset.tagNumber = String(tagNumber).toLocaleLowerCase('ru-RU');
        animalDiv.dataset.displayName = String(displayName).toLocaleLowerCase('ru-RU');
        animalDiv.dataset.rshnTag = String(rshnTag).toLocaleLowerCase('ru-RU');
        
        // Создаем чекбокс для каждого животного
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'animal-checkbox';
        checkbox.value = animal.id;
        checkbox.dataset.animalType = getAnimalTypeFromCategory(animalType);
        checkbox.dataset.tagNumber = tagNumber;
        checkbox.dataset.oldPlaceId = placeId || '';
        checkbox.addEventListener('change', updateMoveButtonVisibility);
        
        const label = document.createElement('label');
        label.style.display = 'flex';
        label.style.alignItems = 'center';
        label.style.gap = '8px';
        label.appendChild(checkbox);
        
        if (animal.tag && animal.tag.tag_number) {
            // Определяем тип животного для URL
            const animalTypeRoute = getAnimalTypeFromCategory(animalType);
            
            // Создаем кликабельную ссылку
            const link = document.createElement('a');
            link.href = `/animals/${animalTypeRoute}/${tagNumber}/info/`;
            link.textContent = displayName; // Используем display_name вместо tagNumber
            link.className = 'animal-link';
            label.appendChild(link);
        } else {
            // Если нет бирки, показываем просто текст
            const span = document.createElement('span');
            span.textContent = displayName; // Используем display_name вместо tagNumber
            label.appendChild(span);
        }
        
        animalDiv.appendChild(label);
        list.appendChild(animalDiv);
    });
    
    // Сбрасываем состояние чекбоксов
    document.getElementById('select-all-animals').checked = false;
    updateMoveButtonVisibility();
    
    modal.style.display = 'block';
}

function filterAnimalsModalList() {
    const searchInput = document.getElementById('animals-modal-search');
    const searchValue = (searchInput?.value || '').trim().toLocaleLowerCase('ru-RU');
    const searchTerms = searchValue
        .split(',')
        .map(term => term.trim())
        .filter(Boolean);
    const animalItems = document.querySelectorAll('#animals-list .animal-item');

    animalItems.forEach(item => {
        const tagNumber = item.dataset.tagNumber || '';
        const displayName = item.dataset.displayName || '';
        const rshnTag = item.dataset.rshnTag || '';
        const isVisible = searchTerms.length === 0 || searchTerms.some(term => (
            tagNumber.includes(term) || displayName.includes(term) || rshnTag.includes(term)
        ));

        item.style.display = isVisible ? '' : 'none';

        if (!isVisible) {
            const checkbox = item.querySelector('.animal-checkbox');
            if (checkbox) {
                checkbox.checked = false;
            }
        }
    });

    const selectAllCheckbox = document.getElementById('select-all-animals');
    if (selectAllCheckbox) {
        const visibleCheckboxes = Array.from(document.querySelectorAll('#animals-list .animal-item'))
            .filter(item => item.style.display !== 'none')
            .map(item => item.querySelector('.animal-checkbox'))
            .filter(Boolean);

        selectAllCheckbox.checked = (
            visibleCheckboxes.length > 0 && visibleCheckboxes.every(checkbox => checkbox.checked)
        );
    }

    updateMoveButtonVisibility();
}

// Вспомогательная функция для преобразования категории в тип животного
function getAnimalTypeFromCategory(category) {
    const typeMap = {
        'Бараны-Производители': 'maker',
        'Баранчики': 'ram',
        'Ярки': 'ewe',
        'Овцематки': 'sheep'
    };
    return typeMap[category] || 'sheep';
}

// Закрытие модального окна
function closeAnimalsModal() {
    document.getElementById('animals-modal').style.display = 'none';
}

// Закрытие модального окна перемещения
function closeMoveModal() {
    document.getElementById('move-modal').style.display = 'none';
}

function toggleHousingStandardsCard() {
    const card = document.getElementById('housing-standards-card');
    const toggleButton = document.getElementById('housing-standards-toggle');
    if (!card) {
        return;
    }

    const shouldShow = card.style.display === 'none' || !card.style.display;
    card.style.display = shouldShow ? 'block' : 'none';
    if (toggleButton) {
        toggleButton.textContent = shouldShow ? 'Скрыть нормы содержания' : 'Нормы содержания';
        toggleButton.setAttribute('aria-expanded', shouldShow ? 'true' : 'false');
    }

    if (shouldShow) {
        card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function closeHousingStandardsCard() {
    const card = document.getElementById('housing-standards-card');
    const toggleButton = document.getElementById('housing-standards-toggle');
    if (card) {
        card.style.display = 'none';
    }
    if (toggleButton) {
        toggleButton.textContent = 'Нормы содержания';
        toggleButton.setAttribute('aria-expanded', 'false');
    }
}

// Обновление видимости кнопки перемещения
function updateMoveButtonVisibility() {
    const checkboxes = document.querySelectorAll('.animal-checkbox:checked');
    const moveContainer = document.getElementById('move-animals-container');
    
    if (checkboxes.length > 0) {
        moveContainer.style.display = 'block';
    } else {
        moveContainer.style.display = 'none';
    }
}

// Обработчик чекбокса "Выбрать всех"
document.addEventListener('DOMContentLoaded', function() {
    const selectAllCheckbox = document.getElementById('select-all-animals');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const animalItems = document.querySelectorAll('#animals-list .animal-item');
            animalItems.forEach(item => {
                if (item.style.display === 'none') {
                    return;
                }

                const checkbox = item.querySelector('.animal-checkbox');
                if (checkbox) {
                    checkbox.checked = this.checked;
                }
            });
            updateMoveButtonVisibility();
        });
    }

    const searchInput = document.getElementById('animals-modal-search');
    if (searchInput) {
        searchInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                filterAnimalsModalList();
            }
        });
    }

    const searchButton = document.getElementById('animals-modal-search-button');
    if (searchButton) {
        searchButton.addEventListener('click', filterAnimalsModalList);
    }
});

// Показать диалог выбора места для перемещения
async function showMoveAnimalsDialog() {
    try {
        await populatePlaceSelect('destination-place');

        const downloadActCheckbox = document.getElementById('download-transfer-act');
        if (downloadActCheckbox) {
            downloadActCheckbox.checked = true;
        }
        
        // Показываем модальное окно
        document.getElementById('move-modal').style.display = 'block';
        
    } catch (error) {
        console.error('Ошибка загрузки мест:', error);
        alert('Ошибка загрузки списка мест');
    }
}

function getFilenameFromContentDisposition(contentDisposition) {
    if (!contentDisposition) {
        return '';
    }

    const utfMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utfMatch) {
        return decodeURIComponent(utfMatch[1]);
    }

    const regularMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
    return regularMatch ? regularMatch[1] : '';
}

async function downloadManualTransferAct(animals, oldPlaceId, newPlaceId) {
    const response = await fetch('/animals/api/acts/transfer/manual/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify({
            animals,
            old_place_id: oldPlaceId,
            new_place_id: newPlaceId,
        }),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(getApiErrorMessage(errorData, 'Ошибка скачивания акта перевода'));
    }

    const blob = await response.blob();
    const filename = getFilenameFromContentDisposition(response.headers.get('Content-Disposition'))
        || 'akt_perevoda_bez_nomera.xlsx';
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
}

async function requestBulkPlaceMove(animals, destinationPlaceId, confirmGroupPlaceMove = false, previewOnly = false) {
    return apiRequest('/animals/api/bulk-place-move/', 'POST', {
        animals,
        place_id: parseInt(destinationPlaceId),
        confirm_group_place_move: confirmGroupPlaceMove,
        preview_only: previewOnly,
    });
}

async function uploadPlaceImport(action) {
    const fileInput = document.getElementById('place-import-file');
    const file = fileInput?.files?.[0];
    if (!file) {
        throw new Error('Выберите файл импорта');
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`/animals/api/import/place/${action}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
        },
        body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
        const error = new Error(getApiErrorMessage(data));
        error.data = data;
        error.status = response.status;
        throw error;
    }
    return data;
}

function renderPlaceImportResult(data, title) {
    const resultBlock = document.getElementById('place-import-result');
    if (!resultBlock) return;

    const errors = data.errors || [];
    const warnings = data.warnings || [];
    const hasIssues = errors.length > 0 || warnings.length > 0;
    const issueItems = []
        .concat(errors.map(error => `<li>${escapeHtml(error)}</li>`))
        .concat(warnings.map(warning => `<li>${escapeHtml(warning)}</li>`))
        .join('');

    resultBlock.className = `alert ${hasIssues ? 'alert-warning' : 'alert-success'}`;
    resultBlock.style.display = 'block';
    resultBlock.innerHTML = `
        <div class="fw-semibold mb-1">${escapeHtml(title)}</div>
        <div>Готово к перемещению: ${data.valid_count || 0}</div>
        ${data.moved_count !== undefined ? `<div>Перемещено: ${data.moved_count || 0}</div>` : ''}
        ${issueItems ? `<hr><div class="fw-semibold mb-1">Проверка файла:</div><ul class="mb-0">${issueItems}</ul>` : ''}
    `;
}

function openPlaceImportModal() {
    const modal = document.getElementById('place-import-modal');
    const fileInput = document.getElementById('place-import-file');
    const resultBlock = document.getElementById('place-import-result');
    const confirmBtn = document.getElementById('place-import-confirm-btn');

    if (fileInput) fileInput.value = '';
    if (confirmBtn) confirmBtn.disabled = true;
    if (resultBlock) {
        resultBlock.style.display = 'none';
        resultBlock.innerHTML = '';
    }
    if (modal) modal.style.display = 'block';
}

function closePlaceImportModal() {
    const modal = document.getElementById('place-import-modal');
    if (modal) modal.style.display = 'none';
}

async function previewPlaceImport() {
    const confirmBtn = document.getElementById('place-import-confirm-btn');
    if (confirmBtn) confirmBtn.disabled = true;

    try {
        const data = await uploadPlaceImport('preview');
        renderPlaceImportResult(data, 'Файл перемещений прочитан');
        if (confirmBtn) confirmBtn.disabled = !data.can_confirm;
    } catch (error) {
        renderPlaceImportResult({ valid_count: 0, errors: [error.message] }, 'Ошибка чтения файла');
    }
}

async function confirmPlaceImport() {
    if (!confirm('Подтвердить импорт перемещений? Строки с ошибками будут пропущены, предупреждения не мешают перемещению.')) {
        return;
    }

    const confirmBtn = document.getElementById('place-import-confirm-btn');
    if (confirmBtn) confirmBtn.disabled = true;

    try {
        const data = await uploadPlaceImport('confirm');
        renderPlaceImportResult(data, `Импорт завершен. Перемещено: ${data.moved_count || 0}`);

        const titleElement = document.getElementById('selected-barn-title');
        const match = titleElement?.textContent?.match(/Овчарня (\d+)/);
        if (match) {
            await loadSpecificBarn(parseInt(match[1]));
        } else {
            await loadBarnsSelector();
        }
    } catch (error) {
        renderPlaceImportResult({ valid_count: 0, errors: [error.message] }, 'Ошибка импорта');
        if (confirmBtn) confirmBtn.disabled = false;
    }
}

// Перемещение выбранных животных
async function moveSelectedAnimals() {
    const selectedCheckboxes = document.querySelectorAll('.animal-checkbox:checked');
    const destinationPlaceId = document.getElementById('destination-place').value;
    const shouldDownloadTransferAct = Boolean(document.getElementById('download-transfer-act')?.checked);
    
    if (!destinationPlaceId) {
        alert('Выберите место назначения');
        return;
    }
    
    if (selectedCheckboxes.length === 0) {
        alert('Выберите животных для перемещения');
        return;
    }

    const selectedAnimalsForAct = Array.from(selectedCheckboxes).map((checkbox) => ({
        animal_type: checkbox.dataset.animalType,
        tag_number: checkbox.dataset.tagNumber,
    }));
    const oldPlaceIds = Array.from(
        new Set(Array.from(selectedCheckboxes).map((checkbox) => checkbox.dataset.oldPlaceId).filter(Boolean))
    );

    if (oldPlaceIds.length === 1 && String(oldPlaceIds[0]) === String(destinationPlaceId)) {
        alert('Выбранные животные уже находятся в этом отсеке');
        return;
    }

    if (shouldDownloadTransferAct && oldPlaceIds.length !== 1) {
        alert('Не удалось определить исходный отсек для акта перемещения.');
        return;
    }

    try {
        let moveResult;
        try {
            moveResult = await requestBulkPlaceMove(selectedAnimalsForAct, destinationPlaceId, false);
        } catch (error) {
            if (error?.data?.requires_confirmation) {
                const warnings = error.data.warnings || [];
                const warningText = warnings.length
                    ? warnings.map((warning, index) => `${index + 1}. ${warning}`).join('\n')
                    : error.message;
                if (!confirm(`${warningText}\n\nПродолжить перемещение этих животных?`)) {
                    return;
                }
                moveResult = await requestBulkPlaceMove(selectedAnimalsForAct, destinationPlaceId, true);
            } else {
                throw error;
            }
        }

        const movedCount = moveResult?.moved_count || 0;

        if (shouldDownloadTransferAct && movedCount > 0) {
            try {
                await downloadManualTransferAct(selectedAnimalsForAct, oldPlaceIds[0], destinationPlaceId);
            } catch (downloadError) {
                console.error('Ошибка скачивания акта перемещения:', downloadError);
                alert(`Животные перемещены, но акт не скачался: ${downloadError.message || 'неизвестная ошибка'}`);
            }
        }
        
        const warningText = (moveResult?.warnings || []).length
            ? `\n\nПредупреждения:\n${moveResult.warnings.join('\n')}`
            : '';
        alert(`Животные успешно перемещены: ${movedCount}${warningText}`);
        
        // Закрываем модальные окна
        closeMoveModal();
        closeAnimalsModal();
        
        // Обновляем карту - получаем номер текущей овчарни из заголовка
        const titleElement = document.getElementById('selected-barn-title');
        if (titleElement && titleElement.textContent) {
            const match = titleElement.textContent.match(/Овчарня (\d+)/);
            if (match) {
                const barnNumber = parseInt(match[1]);
                console.log(`Обновляем овчарню ${barnNumber} после перемещения животных`);
                loadSpecificBarn(barnNumber);
            } else {
                console.log('Не удалось определить номер овчарни, перезагружаем селектор');
                loadBarnsSelector();
            }
        } else {
            console.log('Заголовок овчарни не найден, перезагружаем селектор');
            loadBarnsSelector();
        }
        
    } catch (error) {
        console.error('Ошибка при перемещении животных:', error);
        alert('Ошибка при перемещении животных: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Экспортируем функции для глобального доступа
window.closeAnimalsModal = closeAnimalsModal;
window.closeMoveModal = closeMoveModal;
window.toggleHousingStandardsCard = toggleHousingStandardsCard;
window.closeHousingStandardsCard = closeHousingStandardsCard;
window.toggleCarpetPlaceMoveCard = toggleCarpetPlaceMoveCard;
window.openCarpetMoveAnimalsModal = openCarpetMoveAnimalsModal;
window.closeCarpetMoveAnimalsModal = closeCarpetMoveAnimalsModal;
window.confirmCarpetMoveAnimalsSelection = confirmCarpetMoveAnimalsSelection;
window.clearCarpetMoveSelection = clearCarpetMoveSelection;
window.executeCarpetPlaceMove = executeCarpetPlaceMove;
window.openPlaceImportModal = openPlaceImportModal;
window.closePlaceImportModal = closePlaceImportModal;
window.previewPlaceImport = previewPlaceImport;
window.confirmPlaceImport = confirmPlaceImport;
window.showMoveAnimalsDialog = showMoveAnimalsDialog;
window.moveSelectedAnimals = moveSelectedAnimals;
