import { apiRequest } from "./utils.js";

let currentBarnStats = null;
let showEmptySections = false;

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
            display_name: animal.display_name || animal.tag_number // Добавляем display_name
        }));
        
        // Показываем модальное окно
        showAnimalsModal(animalType, formattedAnimals, sectionName);
        
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
            makersSpan.onclick = () => showAnimalsModal('Бараны-Производители', animals.makers, section.name);
            animalsDiv.appendChild(makersSpan);
        }
        
        if (animals.rams.length > 0) {
            const ramsSpan = document.createElement('span');
            ramsSpan.className = 'animal-count rams';
            ramsSpan.textContent = `Баранчики: ${animals.rams.length}`;
            ramsSpan.onclick = () => showAnimalsModal('Баранчики', animals.rams, section.name);
            animalsDiv.appendChild(ramsSpan);
        }
        
        if (animals.ewes.length > 0) {
            const ewesSpan = document.createElement('span');
            ewesSpan.className = 'animal-count ewes';
            ewesSpan.textContent = `Ярки: ${animals.ewes.length}`;
            ewesSpan.onclick = () => showAnimalsModal('Ярки', animals.ewes, section.name);
            animalsDiv.appendChild(ewesSpan);
        }
        
        if (animals.sheep.length > 0) {
            const sheepSpan = document.createElement('span');
            sheepSpan.className = 'animal-count sheep';
            sheepSpan.textContent = `Овцематки: ${animals.sheep.length}`;
            sheepSpan.onclick = () => showAnimalsModal('Овцематки', animals.sheep, section.name);
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
function showAnimalsModal(animalType, animals, sectionName) {
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
        animalDiv.dataset.tagNumber = String(tagNumber).toLocaleLowerCase('ru-RU');
        animalDiv.dataset.displayName = String(displayName).toLocaleLowerCase('ru-RU');
        
        // Создаем чекбокс для каждого животного
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'animal-checkbox';
        checkbox.value = animal.id;
        checkbox.dataset.animalType = getAnimalTypeFromCategory(animalType);
        checkbox.dataset.tagNumber = tagNumber;
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
        const isVisible = searchTerms.length === 0 || searchTerms.some(term => (
            tagNumber.includes(term) || displayName.includes(term)
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
        // Загружаем список доступных мест с page_size=100 для получения всех мест
        const response = await apiRequest('/veterinary/api/place/?page_size=100');
        const select = document.getElementById('destination-place');
        
        // Обрабатываем пагинированный ответ
        const places = response.results || response;
        
        if (!Array.isArray(places)) {
            console.error('Ожидался массив мест, получено:', places);
            alert('Ошибка: неверный формат данных мест');
            return;
        }
        
        // Очищаем и заполняем список мест
        select.innerHTML = '<option value="">Выберите место...</option>';
        places.forEach(place => {
            const option = document.createElement('option');
            option.value = place.id;
            option.textContent = place.sheepfold;
            select.appendChild(option);
        });
        
        // Показываем модальное окно
        document.getElementById('move-modal').style.display = 'block';
        
    } catch (error) {
        console.error('Ошибка загрузки мест:', error);
        alert('Ошибка загрузки списка мест');
    }
}

// Перемещение выбранных животных
async function moveSelectedAnimals() {
    const selectedCheckboxes = document.querySelectorAll('.animal-checkbox:checked');
    const destinationPlaceId = document.getElementById('destination-place').value;
    
    if (!destinationPlaceId) {
        alert('Выберите место назначения');
        return;
    }
    
    if (selectedCheckboxes.length === 0) {
        alert('Выберите животных для перемещения');
        return;
    }
    

    
    try {
        // Перемещаем каждое животное
        const movePromises = Array.from(selectedCheckboxes).map(async (checkbox) => {
            const animalType = checkbox.dataset.animalType;
            const tagNumber = checkbox.dataset.tagNumber;
            
            return apiRequest(`/animals/${animalType}/${tagNumber}/`, 'PATCH', {
                place_id: parseInt(destinationPlaceId)
            });
        });
        
        // Ждем завершения всех операций
        await Promise.all(movePromises);
        
        alert('Животные успешно перемещены!');
        
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
window.showMoveAnimalsDialog = showMoveAnimalsDialog;
window.moveSelectedAnimals = moveSelectedAnimals;
