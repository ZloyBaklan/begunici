import { apiRequest, formatDateToOutput } from "./utils.js";

// Глобальное хранение выбранных элементов с сохранением в sessionStorage
let selectedSheeps = new Set();

// Функции для работы с sessionStorage
function saveSelectedSheeps() {
    sessionStorage.setItem('selectedSheeps', JSON.stringify(Array.from(selectedSheeps)));
}

function loadSelectedSheeps() {
    const saved = sessionStorage.getItem('selectedSheeps');
    if (saved) {
        selectedSheeps = new Set(
            JSON.parse(saved)
                .map(tag => String(tag || '').trim())
                .filter(tag => tag && tag !== 'undefined' && tag !== 'null')
        );
    }
}

// Загружаем сохраненные выбранные элементы при инициализации
loadSelectedSheeps();

let currentPage = 1;
let currentFilters = {};
const pageSize = 10;
let searchTimeout;

function toggleSheepAdditionalFilters() {
    const filtersBlock = document.getElementById('sheep-advanced-filters');
    if (!filtersBlock) return;
    filtersBlock.style.display = filtersBlock.style.display === 'none' || filtersBlock.style.display === '' ? 'block' : 'none';
}

function getSheepFiltersFromInputs() {
    return {
        search: document.getElementById('sheep-search')?.value || '',
        birth_date_from: document.getElementById('sheep-birth-date-from')?.value || '',
        birth_date_to: document.getElementById('sheep-birth-date-to')?.value || '',
        age_min: document.getElementById('sheep-age-min-filter')?.value || '',
        age_max: document.getElementById('sheep-age-max-filter')?.value || '',
        father_tag: document.getElementById('sheep-father-tag-filter')?.value || '',
        mother_tag: document.getElementById('sheep-mother-tag-filter')?.value || ''
    };
}

function initializeSheepFiltersFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    const filters = {
        search: urlParams.get('search') || '',
        birth_date_from: urlParams.get('birth_date_from') || '',
        birth_date_to: urlParams.get('birth_date_to') || '',
        age_min: urlParams.get('age_min') || '',
        age_max: urlParams.get('age_max') || '',
        father_tag: urlParams.get('father_tag') || '',
        mother_tag: urlParams.get('mother_tag') || ''
    };

    const searchInput = document.getElementById('sheep-search');
    if (searchInput) searchInput.value = filters.search;
    const birthDateFromInput = document.getElementById('sheep-birth-date-from');
    if (birthDateFromInput) birthDateFromInput.value = filters.birth_date_from;
    const birthDateToInput = document.getElementById('sheep-birth-date-to');
    if (birthDateToInput) birthDateToInput.value = filters.birth_date_to;
    const ageMinInput = document.getElementById('sheep-age-min-filter');
    if (ageMinInput) ageMinInput.value = filters.age_min;
    const ageMaxInput = document.getElementById('sheep-age-max-filter');
    if (ageMaxInput) ageMaxInput.value = filters.age_max;
    const fatherTagInput = document.getElementById('sheep-father-tag-filter');
    if (fatherTagInput) fatherTagInput.value = filters.father_tag;
    const motherTagInput = document.getElementById('sheep-mother-tag-filter');
    if (motherTagInput) motherTagInput.value = filters.mother_tag;

    if (filters.birth_date_from || filters.birth_date_to || filters.age_min || filters.age_max || filters.father_tag || filters.mother_tag) {
        const filtersBlock = document.getElementById('sheep-advanced-filters');
        if (filtersBlock) {
            filtersBlock.style.display = 'block';
        }
    }

    return filters;
}

document.addEventListener('DOMContentLoaded', function () {
    const initialFilters = initializeSheepFiltersFromUrl();
    fetchSheeps(1, initialFilters);  // Загружаем список овцематок при загрузке страницы
    loadStatuses();
    loadPlaces();

    const createSheepButton = document.querySelector('#create-sheep-button');
    if (createSheepButton) {
        createSheepButton.onclick = createSheep;
    }

    // Добавляем обработчик для поиска по Enter
    const searchInput = document.getElementById('sheep-search');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                performSheepSearch();
            }
        });
    }
});

// Функция создания овцематки
async function saveSheep() {
    const formData = new FormData(document.getElementById('create-sheep-form'));
    const data = {
        tag_number: formData.get('tag'),
        animal_status_id: formData.get('animal_status') ? parseInt(formData.get('animal_status')) : null,
        birth_date: formData.get('birth_date') || null,
        place_id: formData.get('place') ? parseInt(formData.get('place')) : null,
        rshn_tag: formData.get('rshn_tag') || null,
        dorper_percentage: formData.get('dorper_percentage') || null,
        is_manual_dorper: formData.get('dorper_percentage') ? true : false,
        note: formData.get('note') || ''
    };

    if (!data.tag_number) {
        alert('Пожалуйста, введите номер бирки');
        return;
    }

    try {
        await apiRequest('/animals/sheep/', 'POST', data);
        alert('Овцематка успешно создана');
        document.getElementById('create-sheep-form').reset();
        fetchSheeps();
    } catch (error) {
        console.error('Ошибка создания овцематки:', error);
        alert(`Ошибка: ${error.message}`);
    }
}

// Алиас для обратной совместимости
const createSheep = saveSheep;

// Функция загрузки списка овцематок
async function fetchSheeps(page = 1, filters = {}) {
    try {
        if (typeof filters === 'string') {
            filters = { search: filters };
        }

        if (!filters || typeof filters !== 'object') {
            filters = {};
        }

        currentFilters = { ...currentFilters, ...filters };

        // Сохраняем параметры поиска в URL для сохранения при пагинации
        const urlParams = new URLSearchParams(window.location.search);
        const filterKeys = ['search', 'birth_date_from', 'birth_date_to', 'age_min', 'age_max', 'father_tag', 'mother_tag'];
        filterKeys.forEach(key => {
            const value = (currentFilters[key] || '').toString().trim();
            currentFilters[key] = value;
            if (value) {
                urlParams.set(key, value);
            } else {
                urlParams.delete(key);
            }
        });
        
        // Обновляем URL без перезагрузки страницы
        const newUrl = `${window.location.pathname}${urlParams.toString() ? '?' + urlParams.toString() : ''}`;
        window.history.replaceState({}, '', newUrl);

        // Формируем параметры запроса
        let apiUrl = '/animals/sheep/';
        const params = new URLSearchParams();
        
        // Добавляем параметр страницы
        params.set('page', page);
        
        if (currentFilters.search) {
            params.set('search', currentFilters.search);
        }
        if (currentFilters.birth_date_from) {
            params.set('birth_date_from', currentFilters.birth_date_from);
        }
        if (currentFilters.birth_date_to) {
            params.set('birth_date_to', currentFilters.birth_date_to);
        }
        if (currentFilters.age_min) {
            params.set('age_min', currentFilters.age_min);
        }
        if (currentFilters.age_max) {
            params.set('age_max', currentFilters.age_max);
        }
        if (currentFilters.father_tag) {
            params.set('father_tag', currentFilters.father_tag);
        }
        if (currentFilters.mother_tag) {
            params.set('mother_tag', currentFilters.mother_tag);
        }
        
        if (params.toString()) {
            apiUrl += '?' + params.toString();
        }

        currentPage = page;
        const response = await apiRequest(apiUrl);
        
        // Обрабатываем ответ - может быть массив или объект с results
        const sheeps = Array.isArray(response) ? response : (response.results || response);

        if (sheeps) {
            renderSheeps(sheeps);
            // Проверяем, есть ли пагинация в ответе
            if (response.results && (response.next || response.previous)) {
                // Используем полную пагинацию если есть next/previous
                updatePagination(response);
            } else {
                // Для неограниченного списка создаем простую пагинацию
                updateSimpleSheepsPagination(sheeps.length, currentFilters.search);
            }
        } else {
            console.error('Некорректный ответ от API:', response);
            alert('Ошибка: данные овцематок не найдены.');
        }
    } catch (error) {
        console.error('Ошибка при загрузке овцематок:', error);
        alert('Ошибка при загрузке списка овцематок.');
    }
}

// Рендеринг списка овцематок
function renderSheeps(sheeps, startIndex = null) {
    const sheepTable = document.getElementById('sheep-list');
    const rows = [];
    
    sheeps.forEach((sheep, index) => {
        // Если startIndex не передан, используем стандартную пагинацию
        const recordNumber = startIndex !== null ? startIndex + index + 1 : (currentPage - 1) * pageSize + index + 1;
        
        const row = `<tr>
            <td>
                <input type="checkbox" 
                class="select-sheep"  
                data-tag="${sheep.tag.tag_number}"
                data-animal-id="${sheep.id}">
            </td>
            <td>${recordNumber}</td>
            <td><a href="/animals/sheep/${sheep.tag.tag_number}/info/">${sheep.tag.tag_number}</a></td>
            <td style="background-color:${sheep.animal_status ? sheep.animal_status.color : '#FFFFFF'}">
                ${sheep.animal_status ? sheep.animal_status.status_type : 'Не указан'}
            </td>
            <td>${sheep.age || 'Не указан'}</td>
            <td>${sheep.place ? sheep.place.sheepfold : 'Не указано'}</td>
            <td>${sheep.dorper_display || '-'}</td>
            <td>${sheep.weight_records && sheep.weight_records.length > 0 
                ? `${sheep.weight_records[0].weight_date}: ${sheep.weight_records[0].weight} кг` 
                : 'Нет записей'}</td>
            <td>${formatLastVetTreatment(sheep.veterinary_history)}</td>
            <td>${sheep.rshn_tag || '-'}</td>
            <td>${sheep.note || ''}</td>
        </tr>`;
        rows.push(row);
    });
    
    sheepTable.innerHTML = rows.join('');
    
    // Добавляем обработчики событий для чекбоксов
    document.querySelectorAll('.select-sheep').forEach(cb => {
        cb.addEventListener('click', e => toggleSelectSheep(e.target));
        
        // Восстанавливаем состояние чекбокса
        const tagNumber = cb.getAttribute('data-tag');
        if (selectedSheeps.has(tagNumber)) {
            cb.checked = true;
        }
    });
    
    // Обновляем кнопки действий
    toggleDeleteButton();
}

function formatLastVetTreatment(veterinaryHistory) {
    if (!Array.isArray(veterinaryHistory) || veterinaryHistory.length === 0) {
        return 'Нет записей';
    }

    const lastVet = veterinaryHistory[0];
    const care = lastVet?.veterinary_care;
    const careType = care?.care_name || 'Не указан тип';
    const medication = care?.medication || 'без препарата';
    const careDate = lastVet?.date_of_care ? formatDateToOutput(lastVet.date_of_care) : '-';

    return `${careDate}: ${careType} (${medication})`;
}

// Функция загрузки статусов
async function loadStatuses() {
    try {
        const response = await apiRequest('/veterinary/api/status/?exclude_archive=1&page_size=100');
        // API возвращает пагинированные данные, берем массив из results
        const statuses = response.results || response;
        const select = document.getElementById('animal_status');
        select.innerHTML = '<option value="">Выберите статус</option>';
        
        statuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.textContent = status.status_type;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка загрузки статусов:', error);
    }
}

// Функция загрузки мест
async function loadPlaces() {
    try {
        const response = await apiRequest('/veterinary/api/place/?page_size=100');
        // API возвращает пагинированные данные, берем массив из results
        const places = response.results || response;
        const select = document.getElementById('place');
        select.innerHTML = '<option value="">Выберите место</option>';
        
        places.forEach(place => {
            const option = document.createElement('option');
            option.value = place.id;
            option.textContent = place.sheepfold;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка загрузки мест:', error);
    }
}

// Функция поиска овцематок
async function searchSheeps() {
    const filters = getSheepFiltersFromInputs();
    
    // Сохраняем выбранные чекбоксы
    const selectedCheckboxes = Array.from(document.querySelectorAll('input[name="selectedSheeps"]:checked'))
        .map(cb => cb.value);
    
    currentPage = 1;
    await fetchSheeps(currentPage, filters);
    
    // Восстанавливаем выбранные чекбоксы
    selectedCheckboxes.forEach(tagNumber => {
        const checkbox = document.querySelector(`input[name="selectedSheeps"][value="${tagNumber}"]`);
        if (checkbox) {
            checkbox.checked = true;
        }
    });
    
    // Обновляем кнопку удаления
    toggleDeleteButton();
}

// Алиас для совместимости с шаблоном
async function performSheepSearch() {
    await searchSheeps();
}

// Функция обновления пагинации для локальной фильтрации
function updateSimpleSheepsPagination(totalItems, searchQuery = '') {
    const paginationContainer = document.getElementById('pagination');
    if (!paginationContainer) return;

    // Для неограниченного списка показываем только информацию о количестве
    paginationContainer.innerHTML = `
        <div class="pagination-info">
            <span>Показано: ${totalItems} ${getAnimalWord(totalItems, 'овцематка', 'овцематки', 'овцематок')}</span>
            ${searchQuery ? `<span class="search-info">Поиск: "${searchQuery}"</span>` : ''}
        </div>
    `;
}

function getAnimalWord(count, one, few, many) {
    const lastDigit = count % 10;
    const lastTwoDigits = count % 100;
    
    if (lastTwoDigits >= 11 && lastTwoDigits <= 19) {
        return many;
    }
    
    if (lastDigit === 1) {
        return one;
    } else if (lastDigit >= 2 && lastDigit <= 4) {
        return few;
    } else {
        return many;
    }
}

function updateLocalSheepsPagination(totalItems, currentPage, searchQuery = '') {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = ''; // Очищаем старую навигацию
    
    const totalPages = Math.ceil(totalItems / pageSize);
    
    // Создаем контейнер для пагинации с центрированием
    const paginationContainer = document.createElement('div');
    paginationContainer.style.display = 'flex';
    paginationContainer.style.alignItems = 'center';
    paginationContainer.style.justifyContent = 'center';
    paginationContainer.style.gap = '15px';

    // Кнопка "Предыдущая" (слева)
    if (currentPage > 1) {
        const prevButton = document.createElement('button');
        prevButton.innerText = 'Предыдущая';
        prevButton.className = 'btn btn-outline-primary btn-sm';
        prevButton.onclick = () => {
            fetchSheeps(currentPage - 1, { ...currentFilters, search: searchQuery });
        };
        paginationContainer.appendChild(prevButton);
    } else {
        // Пустой элемент для сохранения симметрии
        const emptyDiv = document.createElement('div');
        emptyDiv.style.width = '80px';
        paginationContainer.appendChild(emptyDiv);
    }

    // Информация о странице (по центру)
    const pageInfo = document.createElement('span');
    pageInfo.innerText = `Страница ${currentPage} из ${totalPages} (всего: ${totalItems})`;
    pageInfo.style.fontWeight = '500';
    pageInfo.style.minWidth = '200px';
    pageInfo.style.textAlign = 'center';
    paginationContainer.appendChild(pageInfo);

    // Кнопка "Следующая" (справа)
    if (currentPage < totalPages) {
        const nextButton = document.createElement('button');
        nextButton.innerText = 'Следующая';
        nextButton.className = 'btn btn-outline-primary btn-sm';
        nextButton.onclick = () => {
            fetchSheeps(currentPage + 1, { ...currentFilters, search: searchQuery });
        };
        paginationContainer.appendChild(nextButton);
    } else {
        // Пустой элемент для сохранения симметрии
        const emptyDiv = document.createElement('div');
        emptyDiv.style.width = '80px';
        paginationContainer.appendChild(emptyDiv);
    }

    pagination.appendChild(paginationContainer);
}

// Остальные функции (toggleForm, updateDeleteButtons, updatePagination) остаются без изменений
function toggleForm() {
    const form = document.getElementById('create-sheep-form');
    const button = document.getElementById('toggle-create-sheep-form');
    
    if (form.style.display === 'none' || form.style.display === '') {
        form.style.display = 'block';
        button.textContent = '▲ Скрыть форму создания овцематки';
    } else {
        form.style.display = 'none';
        button.textContent = '▼ Создать овцематку';
    }
}

// Функция для управления чекбоксами всех записей
function toggleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.select-sheep');
    checkboxes.forEach(cb => {
        const tagNumber = cb.dataset.tag;

        cb.checked = checkbox.checked;
        
        if (checkbox.checked) {
            selectedSheeps.add(tagNumber);
        } else {
            selectedSheeps.delete(tagNumber);
        }
    });
    
    // Сохраняем состояние в sessionStorage
    saveSelectedSheeps();
    
    console.log('Текущее состояние selectedSheeps после выбора всех:', selectedSheeps);
    toggleDeleteButton();
}

// Функция для управления отдельным чекбоксом
function toggleSelectSheep(checkbox) {
    const tagNumber = checkbox.dataset.tag;

    if (checkbox.checked) {
        selectedSheeps.add(tagNumber);
    } else {
        selectedSheeps.delete(tagNumber);
    }
    
    // Сохраняем состояние в sessionStorage
    saveSelectedSheeps();
    
    console.log('Текущее состояние selectedSheeps: \n', selectedSheeps);
    toggleDeleteButton();
}

// Функция для отображения кнопки удаления
function toggleDeleteButton() {
    const selectedActionsDiv = document.getElementById('selected-actions');
    const hasSelection = selectedSheeps.size > 0;

    selectedActionsDiv.style.display = hasSelection ? 'block' : 'none';
}

// Функция для удаления выбранных записей
async function deleteSelectedSheeps() {
    const selectedTags = Array.from(selectedSheeps);

    console.log('Выбранные для удаления:', selectedTags);

    if (selectedTags.length === 0) {
        alert('Нет выбранных записей для удаления');
        return;
    }

    const modal = document.getElementById('delete-modal');
    const modalMessage = document.getElementById('delete-modal-message');
    const confirmButton = document.getElementById('delete-confirm-button');

    modalMessage.textContent = `Вы уверены, что хотите удалить следующие бирки: ${selectedTags.join(', ')}?`;
    modal.style.display = 'block';

    confirmButton.onclick = async () => {
        try {
            for (const tag of selectedTags) {
                await apiRequest(`/animals/sheep/${tag}/`, 'DELETE');
                selectedSheeps.delete(tag);
            }
            alert('Выбранные записи успешно удалены');
            
            // Очищаем все выбранные элементы
            selectedSheeps.clear();
            
            // Снимаем галочку с "выбрать все"
            const selectAllCheckbox = document.getElementById('select-all');
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = false;
            }
            
            fetchSheeps(currentPage);
            toggleDeleteButton();
            modal.style.display = 'none';
        } catch (error) {
            console.error('Ошибка при удалении выбранных записей:', error);
            alert('Ошибка при удалении записей');
        }
    };
}

function openArchiveModal() {
    const modal = document.getElementById('archive-modal');
    modal.style.display = 'block';
    
    // Устанавливаем текущую дату
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('archive-status-date').value = today;
    const carcassWeightInput = document.getElementById('archive-carcass-weight');
    if (carcassWeightInput) {
        carcassWeightInput.value = '';
    }
    window.archiveActModal?.reset();
    window.archiveActModal?.setSelectedAnimals(
        Array.from(selectedSheeps)
            .filter(tag => tag && String(tag).trim())
            .map(tag => ({ animalType: 'sheep', tagNumber: String(tag).trim() }))
    );
    
    loadArchiveStatuses();
}

function closeArchiveModal() {
    const modal = document.getElementById('archive-modal');
    modal.style.display = 'none';
}

function toggleArchiveActNumberField() {
    window.archiveActModal?.toggle();
}

async function loadArchiveStatuses() {
    try {
        const response = await apiRequest('/veterinary/api/status/?page_size=100');
        // API возвращает пагинированные данные, берем массив из results
        const statuses = response.results || response;
        const archiveStatuses = statuses.filter(status => ['Падеж', 'Вынужденная прирезка', 'Реализация в живом весе', 'Продажа на племя'].includes(status.status_type));

        const statusSelect = document.getElementById('archive-status-select');
        statusSelect.innerHTML = '';

        if (archiveStatuses.length === 0) {
            alert('Нет статусов для переноса в архив. Создайте необходимые статусы.');
            closeArchiveModal();
            return;
        }

        archiveStatuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.text = status.status_type;
            statusSelect.add(option);
        });
        statusSelect.onchange = toggleArchiveActNumberField;
        toggleArchiveActNumberField();
    } catch (error) {
        console.error('Ошибка при загрузке статусов:', error);
    }
}

async function applyArchiveStatus() {
    const selectedTags = Array.from(selectedSheeps).filter(tag => tag && String(tag).trim()).map(tag => String(tag).trim());

    if (selectedTags.length === 0) {
        alert('Нет выбранных записей для переноса.');
        return;
    }

    const statusSelect = document.getElementById('archive-status-select');
    const statusId = statusSelect.value;
    if (!statusId) {
        alert('Выберите статус.');
        return;
    }

    const statusDate = document.getElementById('archive-status-date').value;
    if (!statusDate) {
        alert('Укажите дату присвоения статуса.');
        return;
    }

    const carcassWeightRaw = document.getElementById('archive-carcass-weight')?.value?.trim();
    let carcassWeight = null;
    if (carcassWeightRaw) {
        carcassWeight = parseFloat(carcassWeightRaw);
        if (Number.isNaN(carcassWeight) || carcassWeight < 0) {
            alert('Вес туши должен быть неотрицательным числом.');
            return;
        }
    }
    const archiveActPayload = window.archiveActModal?.collectPayload?.() || {};

    try {
        for (const tag of selectedTags) {
            await apiRequest(`/animals/sheep/${tag}/`, 'PATCH', { 
                animal_status_id: statusId,
                status_date: statusDate,
                carcass_weight: carcassWeight,
                ...archiveActPayload
            });
            if (archiveActPayload.archive_act_download) {
                window.archiveActModal?.downloadArchiveAct('sheep', tag);
            }
        }
        alert('Выбранные записи успешно перенесены в архив.');
        
        // Очищаем все выбранные элементы
        selectedSheeps.clear();
        
        // Снимаем галочку с "выбрать все"
        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }
        
        closeArchiveModal();
        fetchSheeps(currentPage);
        toggleDeleteButton(); // Скрываем кнопки
    } catch (error) {
        console.error('Ошибка при переносе в архив:', error);
        alert('Ошибка при переносе записей.');
    }
}

function updatePagination(response) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';
    
    // Создаем контейнер для пагинации с центрированием
    const paginationContainer = document.createElement('div');
    paginationContainer.style.display = 'flex';
    paginationContainer.style.alignItems = 'center';
    paginationContainer.style.justifyContent = 'center';
    paginationContainer.style.gap = '15px';

    // Кнопка "Предыдущая" (слева)
    if (response.previous) {
        const prevButton = document.createElement('button');
        prevButton.innerText = 'Предыдущая';
        prevButton.className = 'btn btn-outline-primary btn-sm';
        prevButton.onclick = () => {
            fetchSheeps(currentPage - 1, currentFilters);
        };
        paginationContainer.appendChild(prevButton);
    } else {
        // Пустой элемент для сохранения симметрии
        const emptyDiv = document.createElement('div');
        emptyDiv.style.width = '80px'; // Примерная ширина кнопки
        paginationContainer.appendChild(emptyDiv);
    }

    // Информация о странице (по центру)
    const pageInfo = document.createElement('span');
    pageInfo.innerText = `Страница ${currentPage}`;
    pageInfo.style.fontWeight = '500';
    pageInfo.style.minWidth = '100px';
    pageInfo.style.textAlign = 'center';
    paginationContainer.appendChild(pageInfo);

    // Кнопка "Следующая" (справа)
    if (response.next) {
        const nextButton = document.createElement('button');
        nextButton.innerText = 'Следующая';
        nextButton.className = 'btn btn-outline-primary btn-sm';
        nextButton.onclick = () => {
            fetchSheeps(currentPage + 1, currentFilters);
        };
        paginationContainer.appendChild(nextButton);
    } else {
        // Пустой элемент для сохранения симметрии
        const emptyDiv = document.createElement('div');
        emptyDiv.style.width = '80px'; // Примерная ширина кнопки
        paginationContainer.appendChild(emptyDiv);
    }

    pagination.appendChild(paginationContainer);
}

function closeDeleteModal() {
    const modal = document.getElementById('delete-modal');
    modal.style.display = 'none';
}

// Экспортируем функции для глобального доступа
window.toggleForm = toggleForm;
window.openArchiveModal = openArchiveModal;
window.closeArchiveModal = closeArchiveModal;
window.closeDeleteModal = closeDeleteModal;
window.applyArchiveStatus = applyArchiveStatus;
window.deleteSelectedSheeps = deleteSelectedSheeps;
window.toggleSelectAll = toggleSelectAll;
window.toggleSelectSheep = toggleSelectSheep;
window.toggleDeleteButton = toggleDeleteButton;
window.saveSheep = saveSheep;
window.fetchSheeps = fetchSheeps;
window.searchSheeps = searchSheeps;
window.performSheepSearch = performSheepSearch;
window.toggleSheepAdditionalFilters = toggleSheepAdditionalFilters;

