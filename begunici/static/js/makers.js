import { apiRequest, formatDateToOutput } from "./utils.js";

// Глобальное хранение выбранных элементов с сохранением в sessionStorage
let selectedMakers = new Set();

// Функции для работы с sessionStorage
function saveSelectedMakers() {
    sessionStorage.setItem('selectedMakers', JSON.stringify(Array.from(selectedMakers)));
}

function loadSelectedMakers() {
    const saved = sessionStorage.getItem('selectedMakers');
    if (saved) {
        selectedMakers = new Set(JSON.parse(saved));
    }
}

// Загружаем сохраненные выбранные элементы при инициализации
loadSelectedMakers();

let currentPage = 1;
let currentFilters = {};
const pageSize = 10;

function toggleMakerAdditionalFilters() {
    const filtersBlock = document.getElementById('maker-advanced-filters');
    if (!filtersBlock) return;
    filtersBlock.style.display = filtersBlock.style.display === 'none' || filtersBlock.style.display === '' ? 'block' : 'none';
}

function getMakerFiltersFromInputs() {
    return {
        search: document.getElementById('maker-search')?.value || '',
        birth_date_from: document.getElementById('maker-birth-date-from')?.value || '',
        birth_date_to: document.getElementById('maker-birth-date-to')?.value || '',
        age_min: document.getElementById('maker-age-min-filter')?.value || '',
        age_max: document.getElementById('maker-age-max-filter')?.value || '',
        father_tag: document.getElementById('maker-father-tag-filter')?.value || '',
        mother_tag: document.getElementById('maker-mother-tag-filter')?.value || ''
    };
}

function initializeMakerFiltersFromUrl() {
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

    const searchInput = document.getElementById('maker-search');
    if (searchInput) searchInput.value = filters.search;
    const birthDateFromInput = document.getElementById('maker-birth-date-from');
    if (birthDateFromInput) birthDateFromInput.value = filters.birth_date_from;
    const birthDateToInput = document.getElementById('maker-birth-date-to');
    if (birthDateToInput) birthDateToInput.value = filters.birth_date_to;
    const ageMinInput = document.getElementById('maker-age-min-filter');
    if (ageMinInput) ageMinInput.value = filters.age_min;
    const ageMaxInput = document.getElementById('maker-age-max-filter');
    if (ageMaxInput) ageMaxInput.value = filters.age_max;
    const fatherTagInput = document.getElementById('maker-father-tag-filter');
    if (fatherTagInput) fatherTagInput.value = filters.father_tag;
    const motherTagInput = document.getElementById('maker-mother-tag-filter');
    if (motherTagInput) motherTagInput.value = filters.mother_tag;

    if (filters.birth_date_from || filters.birth_date_to || filters.age_min || filters.age_max || filters.father_tag || filters.mother_tag) {
        const filtersBlock = document.getElementById('maker-advanced-filters');
        if (filtersBlock) {
            filtersBlock.style.display = 'block';
        }
    }

    return filters;
}

document.addEventListener('DOMContentLoaded', function () {
    const initialFilters = initializeMakerFiltersFromUrl();
    fetchMakers(1, initialFilters);  // Загрузка списка баранов-производителей при загрузке страницы
    loadAnimalStatuses();
    loadPlaces();
    setupArchiveButton(); // Устанавливаем URL для кнопки архива

    const createMakerButton = document.querySelector('#create-maker-button');
    if (createMakerButton) {
        createMakerButton.onclick = saveMaker;  // Привязываем событие к кнопке
    }
});

// Функция для загрузки статусов животных
async function loadAnimalStatuses() {
    try {
        const response = await apiRequest('/veterinary/api/status/?page_size=100');
        // API возвращает пагинированные данные, берем массив из results
        const statuses = response.results || response;
        const statusSelect = document.getElementById('animal_status');
        statusSelect.innerHTML = '';
        statuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.text = status.status_type;
            statusSelect.add(option);
        });
    } catch (error) {
        console.error('Ошибка при загрузке статусов животных:', error);
    }
}

// Функция загрузки статусов
async function loadStatuses() {
    try {
        const response = await apiRequest('/veterinary/api/status/?page_size=100');
        // API возвращает пагинированные данные, берем массив из results
        const statuses = response.results || response;
        const select = document.getElementById('animal_status');
        if (select) {
            select.innerHTML = '<option value="">Выберите статус</option>';
            
            statuses.forEach(status => {
                const option = document.createElement('option');
                option.value = status.id;
                option.textContent = status.status_type;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Ошибка загрузки статусов:', error);
    }
}

// Функция для загрузки мест (овчарня и отсек)
async function loadPlaces() {
    try {
        const response = await apiRequest('/veterinary/api/place/?page_size=100');
        // API возвращает пагинированные данные, берем массив из results
        const places = response.results || response;
        const sheepfoldSelect = document.getElementById('place');
        sheepfoldSelect.innerHTML = '';
        places.forEach(place => {
            const sheepfoldOption = document.createElement('option');
            sheepfoldOption.value = place.id;
            sheepfoldOption.text = place.sheepfold;
            sheepfoldSelect.add(sheepfoldOption);
        });
    } catch (error) {
        console.error('Ошибка при загрузке мест:', error);
    }
}


// Функция для скрытия/показа формы создания барана-производителя
function toggleForm() {
    const form = document.getElementById('create-maker-form');
    const toggleButton = document.getElementById('toggle-create-maker-form');
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
    toggleButton.innerText = form.style.display === 'none' ? '▼ Создать барана-производителя' : '▲ Скрыть форму';
}

// Создание нового барана-производителя
async function saveMaker() {
    const url = '/animals/maker/';
    const method = 'POST';

    const data = {
        tag_number: document.getElementById('tag').value,
        name: document.getElementById('name').value || null,
        animal_status_id: parseInt(document.getElementById('animal_status').value),
        birth_date: document.getElementById('birth_date').value,
        plemstatus: document.getElementById('plemstatus').value,
        working_condition: document.getElementById('working_condition').value,
        rshn_tag: document.getElementById('rshn_tag').value,
        dorper_percentage: document.getElementById('dorper_percentage').value || null,
        is_manual_dorper: document.getElementById('dorper_percentage').value ? true : false,
        note: document.getElementById('note').value,
        place_id: parseInt(document.getElementById('place').value), // Передаём ID места,
    };
    
    console.log('Отправляемые данные:', data); // Логируем данные для отладки

    if (!data.tag_number || !data.animal_status_id || !data.place_id) {
        alert('Пожалуйста, заполните обязательные поля: бирка, статус, место.');
        return;
    }

    try {
        await apiRequest(url, method, data);
        alert('Баран-Производитель успешно создан');
        document.getElementById('create-maker-form').reset();
        fetchMakers();
    } catch (error) {
        console.error('Ошибка при создании барана-производителя:', error);
        alert('Ошибка: Проверьте корректность введенных данных');
    }
}

// Загрузка списка баранов-производителей
async function fetchMakers(page = 1, filters = {}) {
    try {
        if (typeof filters === 'string') {
            filters = { search: filters };
        }

        if (!filters || typeof filters !== 'object') {
            filters = {};
        }

        // Обновляем текущие фильтры
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
        
        // Строим URL с параметрами
        const params = new URLSearchParams();
        
        // Добавляем параметр страницы
        params.append('page', page);
        
        // Добавляем фильтры если они есть
        if (currentFilters.search && currentFilters.search.trim()) {
            params.append('search', currentFilters.search.trim());
        }
        if (currentFilters.animal_status) {
            params.append('animal_status', currentFilters.animal_status);
        }
        if (currentFilters.place) {
            params.append('place', currentFilters.place);
        }
        if (currentFilters.birth_date_from) {
            params.append('birth_date_from', currentFilters.birth_date_from);
        }
        if (currentFilters.birth_date_to) {
            params.append('birth_date_to', currentFilters.birth_date_to);
        }
        if (currentFilters.age_min) {
            params.append('age_min', currentFilters.age_min);
        }
        if (currentFilters.age_max) {
            params.append('age_max', currentFilters.age_max);
        }
        if (currentFilters.father_tag) {
            params.append('father_tag', currentFilters.father_tag);
        }
        if (currentFilters.mother_tag) {
            params.append('mother_tag', currentFilters.mother_tag);
        }
        
        currentPage = page;
        const response = await apiRequest(`/animals/maker/?${params.toString()}`);
        
        // Обрабатываем ответ - может быть массив или объект с results
        const makers = Array.isArray(response) ? response : (response.results || response);

        if (makers) {
            renderMakers(makers);
            // Проверяем, есть ли пагинация в ответе
            if (response.results && (response.next || response.previous)) {
                // Используем полную пагинацию если есть next/previous
                updatePagination(response);
            } else {
                // Для неограниченного списка создаем простую пагинацию
                updateSimpleMakersPagination(makers.length, currentFilters.search);
            }
        } else {
            console.error('Некорректный ответ от API:', response);
            alert('Ошибка: данные баранов-производителей не найдены.');
        }
    } catch (error) {
        console.error('Ошибка при загрузке баранов-производителей:', error);
        alert('Ошибка при загрузке списка баранов-производителей.');
    }
}


// Рендеринг списка баранов-производителей
function renderMakers(makers, startIndex = null) {
    const makerList = document.getElementById('maker-list');
    const rows = [];
    
    makers.forEach((maker, index) => {
        // Если startIndex не передан, используем стандартную пагинацию
        const recordNumber = startIndex !== null ? startIndex + index + 1 : (currentPage - 1) * pageSize + index + 1;
        
        const row = `<tr>
            <td>
                <input type="checkbox" 
                class="select-maker"  
                data-tag="${maker.tag.tag_number}"
                data-animal-id="${maker.id}">
            </td>
            <td>${recordNumber}</td>
            <td><a href="/animals/maker/${maker.tag.tag_number}/info/">${maker.display_name || maker.tag.tag_number}</a></td>
            <td style="background-color:${maker.animal_status ? maker.animal_status.color : '#FFFFFF'}">
                ${maker.animal_status ? maker.animal_status.status_type : 'Нет статуса'}
            </td>
            <td>${maker.age || 'Нет данных'}</td>
            <td>${maker.place ? maker.place.sheepfold : 'Нет данных'}</td>
            <td>${maker.dorper_display || '-'}</td>
            <td>${maker.weight_records && maker.weight_records.length > 0 
                ? `${maker.weight_records[0].weight_date}: ${maker.weight_records[0].weight} кг` 
                : 'Нет записей'}</td>
            <td>${formatLastVetTreatment(maker.veterinary_history)}</td>
            <td>${maker.working_condition || 'Нет данных'}</td>
            <td>${maker.rshn_tag || '-'}</td>
            <td>${maker.note}</td>
        </tr>`;
        rows.push(row);
    });
    
    makerList.innerHTML = rows.join('');
    
    // Добавляем обработчики событий для чекбоксов
    document.querySelectorAll('.select-maker').forEach(cb => {
        cb.addEventListener('click', e => toggleSelectMaker(e.target));
        
        // Восстанавливаем состояние чекбокса
        const tagNumber = cb.getAttribute('data-tag');
        if (selectedMakers.has(tagNumber)) {
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



// Функция поиска баранов-производителей
async function searchMakers() {
    const filters = getMakerFiltersFromInputs();
    const statusFilter = document.getElementById('status-filter') ? document.getElementById('status-filter').value : '';
    const placeFilter = document.getElementById('place-filter') ? document.getElementById('place-filter').value : '';
    
    currentPage = 1;
    await fetchMakers(currentPage, {
        ...filters,
        animal_status: statusFilter,
        place: placeFilter
    });
}

// Алиас для совместимости с шаблоном
async function performMakerSearch() {
    await searchMakers();
}

// Получение цвета для статуса
function getColorForStatus(status) {
    if (!status) return 'black';
    switch (status.status_type) {
        case 'Ветобработка': return 'green';
        case 'Убой': return 'red';
        default: return 'black';
    }
}

// Функция для управления чекбоксами всех записей
function toggleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.select-maker');
    checkboxes.forEach(cb => {
        const tagNumber = cb.dataset.tag;

        cb.checked = checkbox.checked;
        
        if (checkbox.checked) {
            selectedMakers.add(tagNumber);
        } else {
            selectedMakers.delete(tagNumber);
        }
    });
    
    // Сохраняем состояние в sessionStorage
    saveSelectedMakers();
    
    console.log('Текущее состояние selectedMakers после выбора всех:', selectedMakers);
    toggleDeleteButton();
}


// Функция для управления отдельным чекбоксом
function toggleSelectMaker(checkbox) {
    const tagNumber = checkbox.dataset.tag;

    if (checkbox.checked) {
        selectedMakers.add(tagNumber);
    } else {
        selectedMakers.delete(tagNumber);
    }
    
    // Сохраняем состояние в sessionStorage
    saveSelectedMakers();
    
    console.log('Текущее состояние selectedMakers: \n', selectedMakers);
    toggleDeleteButton();
}


// Функция для отображения кнопки удаления
function toggleDeleteButton() {
    const selectedActionsDiv = document.getElementById('selected-actions');
    const hasSelection = selectedMakers.size > 0;

    selectedActionsDiv.style.display = hasSelection ? 'block' : 'none';
}

// Обновление состояния чекбоксов при загрузке страницы
function getTagFromTable(tagNumber) {
    const row = document.querySelector(`.select-maker[data-tag="${tagNumber}"]`);
    if (row) {
        return row.closest('tr').querySelector('td:nth-child(3)').innerText.trim(); // Извлекаем бирку
    }
    return 'Неизвестно';
}

// Функция для удаления выбранных записей
async function deleteSelectedMakers() {
    const selectedTags = Array.from(selectedMakers);

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
                await apiRequest(`/animals/maker/${tag}/`, 'DELETE');
            }
            alert('Выбранные записи успешно удалены');
            
            // Очищаем все выбранные элементы
            selectedMakers.clear();
            saveSelectedMakers(); // Сохраняем очищенное состояние
            
            // Снимаем галочку с "выбрать все"
            const selectAllCheckbox = document.getElementById('select-all');
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = false;
            }
            
            fetchMakers(currentPage); // Обновляем текущую страницу
            toggleDeleteButton(); // Скрываем кнопки
            modal.style.display = 'none'; // Закрываем модальное окно
        } catch (error) {
            console.error('Ошибка при удалении выбранных записей:', error);
            alert('Ошибка при удалении записей');
        }
    };
}


function closeDeleteModal() {
    const modal = document.getElementById('delete-modal');
    modal.style.display = 'none';
}


// Функция для сброса состояния кнопки
function resetButton() {
    const createButton = document.getElementById('create-maker-button');
    createButton.innerText = 'Создать барана-производителя';
    createButton.removeAttribute('data-id');
    createButton.onclick = () => saveMaker();
}

// Функция обновления пагинации для локальной фильтрации
function updateSimpleMakersPagination(totalItems, searchQuery = '') {
    const paginationContainer = document.getElementById('pagination');
    if (!paginationContainer) return;

    // Для неограниченного списка показываем только информацию о количестве
    paginationContainer.innerHTML = `
        <div class="pagination-info">
            <span>Показано: ${totalItems} ${getAnimalWord(totalItems, 'баран-производитель', 'барана-производителя', 'баранов-производителей')}</span>
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

function updateLocalMakersPagination(totalItems, currentPage, searchQuery = '') {
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
            fetchMakers(currentPage - 1, { ...currentFilters, search: searchQuery });
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
            fetchMakers(currentPage + 1, { ...currentFilters, search: searchQuery });
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

function updatePagination(response) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = ''; // Очищаем старую навигацию
    
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
            fetchMakers(currentPage - 1, currentFilters);
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
            fetchMakers(currentPage + 1, currentFilters);
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
    const actNumberInput = document.getElementById('archive-act-number');
    if (actNumberInput) {
        actNumberInput.value = '';
    }
    const actNumberGroup = document.getElementById('archive-act-number-group');
    if (actNumberGroup) {
        actNumberGroup.style.display = 'none';
    }

    loadArchiveStatuses();
}

// Экспортируем функцию для глобального доступа
window.openArchiveModal = openArchiveModal;

function closeArchiveModal() {
    const modal = document.getElementById('archive-modal');
    modal.style.display = 'none';
}

function toggleArchiveActNumberField() {
    const statusSelect = document.getElementById('archive-status-select');
    const actNumberGroup = document.getElementById('archive-act-number-group');
    const actNumberInput = document.getElementById('archive-act-number');
    if (!statusSelect || !actNumberGroup) return;

    const selectedStatusName = statusSelect.options[statusSelect.selectedIndex]?.text?.trim() || '';
    const shouldShow = selectedStatusName === 'Выбытие';
    actNumberGroup.style.display = shouldShow ? 'block' : 'none';
    if (!shouldShow && actNumberInput) {
        actNumberInput.value = '';
    }
}

// Экспортируем функцию для глобального доступа
window.closeArchiveModal = closeArchiveModal;

async function loadArchiveStatuses() {
    try {
        const response = await apiRequest('/veterinary/api/status/?page_size=100');
        // API возвращает пагинированные данные, берем массив из results
        const statuses = response.results || response;
        const archiveStatuses = statuses.filter(status => ['Выбытие', 'Убой', 'Реализация в живом весе', 'Продажа на племя'].includes(status.status_type));

        const statusSelect = document.getElementById('archive-status-select');
        statusSelect.innerHTML = ''; // Очистка существующих опций

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
    const selectedTags = Array.from(selectedMakers);

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
    const selectedStatusName = statusSelect.options[statusSelect.selectedIndex]?.text?.trim() || '';
    const actNumberRaw = document.getElementById('archive-act-number')?.value?.trim() || '';
    let carcassWeight = null;
    if (carcassWeightRaw) {
        carcassWeight = parseFloat(carcassWeightRaw);
        if (Number.isNaN(carcassWeight) || carcassWeight < 0) {
            alert('Вес туши должен быть числом не меньше 0.');
            return;
        }
    }

    try {
        for (const tag of selectedTags) {
            await apiRequest(`/animals/maker/${tag}/`, 'PATCH', { 
                animal_status_id: statusId,
                status_date: statusDate,
                carcass_weight: carcassWeight,
                act_number: selectedStatusName === 'Выбытие' ? actNumberRaw : ''
            });
        }
        alert('Выбранные записи успешно перенесены в архив.');
        
        // Очищаем все выбранные элементы
        selectedMakers.clear();
        saveSelectedMakers(); // Сохраняем очищенное состояние
        
        // Снимаем галочку с "выбрать все"
        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }
        
        closeArchiveModal();
        fetchMakers(currentPage); // Обновляем текущую страницу
        toggleDeleteButton(); // Скрываем кнопки
    } catch (error) {
        console.error('Ошибка при переносе в архив:', error);
        alert('Ошибка при переносе записей.');
    }
}

// Экспортируем функции для глобального доступа
window.applyArchiveStatus = applyArchiveStatus;
window.deleteSelectedMakers = deleteSelectedMakers;
window.toggleSelectAll = toggleSelectAll;
window.toggleSelectMaker = toggleSelectMaker;
window.toggleDeleteButton = toggleDeleteButton;
window.saveMaker = saveMaker;
window.fetchMakers = fetchMakers;
window.searchMakers = searchMakers;
window.performMakerSearch = performMakerSearch;
window.toggleMakerAdditionalFilters = toggleMakerAdditionalFilters;

function setupArchiveButton() {
    // Кнопка архива теперь находится в другом месте, не нужно настраивать href
    console.log('Archive button setup - using direct link in HTML');
}

// Функции экспорта теперь в export-common.js

// Очищаем sessionStorage при переходе на другие страницы (не пагинацию)
window.addEventListener('beforeunload', function() {
    // Проверяем, остаемся ли мы на той же странице (пагинация)
    const currentPath = window.location.pathname;
    if (!currentPath.includes('/animals/makers/')) {
        sessionStorage.removeItem('selectedMakers');
    }
});
// Функция для сброса фильтров и выбранных элементов
function clearFilters() {
    // Очищаем поля фильтров
    const searchInput = document.getElementById('maker-search');
    if (searchInput) searchInput.value = '';
    
    const statusFilter = document.getElementById('status-filter');
    if (statusFilter) statusFilter.value = '';
    
    const placeFilter = document.getElementById('place-filter');
    if (placeFilter) placeFilter.value = '';
    const birthDateFromInput = document.getElementById('maker-birth-date-from');
    if (birthDateFromInput) birthDateFromInput.value = '';
    const birthDateToInput = document.getElementById('maker-birth-date-to');
    if (birthDateToInput) birthDateToInput.value = '';
    const ageMinInput = document.getElementById('maker-age-min-filter');
    if (ageMinInput) ageMinInput.value = '';
    const ageMaxInput = document.getElementById('maker-age-max-filter');
    if (ageMaxInput) ageMaxInput.value = '';
    const fatherTagInput = document.getElementById('maker-father-tag-filter');
    if (fatherTagInput) fatherTagInput.value = '';
    const motherTagInput = document.getElementById('maker-mother-tag-filter');
    if (motherTagInput) motherTagInput.value = '';
    
    // Очищаем выбранные элементы
    selectedMakers.clear();
    saveSelectedMakers(); // Сохраняем очищенное состояние
    
    // Снимаем галочку с "выбрать все"
    const selectAllCheckbox = document.getElementById('select-all');
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = false;
    }
    
    // Обновляем кнопки
    toggleDeleteButton();

    currentFilters = {};
    
    // Перезагружаем данные
    fetchMakers(1);
}

window.clearFilters = clearFilters;

