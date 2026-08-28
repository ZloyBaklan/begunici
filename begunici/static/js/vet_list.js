// Глобальные переменные
let currentPage = 1;
const pageSize = 10;

function getCurrentLocalDateString() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

const API_ERROR_FIELD_LABELS = {
    animal_ids: 'Животные',
    animal_type: 'Тип животного',
    date: 'Дата',
    medication: 'Препарат',
    non_field_errors: 'Общая ошибка',
    purpose: 'Цель',
    tag_number: 'Бирка',
    veterinary_care: 'Ветобработка',
    veterinary_care_id: 'Ветобработка',
};

function getApiErrorFieldLabel(field) {
    return API_ERROR_FIELD_LABELS[field] || String(field).replaceAll('_', ' ');
}

function translateApiErrorText(message) {
    const text = String(message || '').trim();
    const translations = {
        'This field is required.': 'Это поле обязательно для заполнения.',
        'This field may not be blank.': 'Это поле не может быть пустым.',
        'This field may not be null.': 'Это поле не может быть пустым.',
        'A valid integer is required.': 'Нужно указать целое число.',
        'A valid number is required.': 'Нужно указать число.',
        'Enter a valid date.': 'Укажите корректную дату.',
        'Date has wrong format. Use one of these formats instead: YYYY-MM-DD.': 'Неверный формат даты. Используйте формат ДД.ММ.ГГГГ.',
        'Enter a valid date/time.': 'Укажите корректные дату и время.',
        'This field must be unique.': 'Такое значение уже используется.',
    };
    if (translations[text]) return translations[text];
    if (text.includes('Ensure this value is greater than or equal to 0')) return 'Значение не может быть меньше 0.';
    if (text.includes('Invalid pk')) return 'Выбранное значение не найдено в базе.';
    return text;
}

function parseApiErrorString(message) {
    const text = String(message || '').trim();
    if (!text) return '';

    const cleaned = text.replace(
        /ErrorDetail\(string=(['"])(.*?)\1,\s*code=(['"]).*?\3\)/g,
        (_, quote, errorMessage) => `'${String(errorMessage).replaceAll("'", "\\'")}'`
    );

    const fieldMessages = [];
    const fieldRegex = /['"]([^'"]+)['"]\s*:\s*(\[[\s\S]*?\]|['"][\s\S]*?['"])/g;
    let fieldMatch;
    while ((fieldMatch = fieldRegex.exec(cleaned)) !== null) {
        const field = fieldMatch[1];
        const rawValue = fieldMatch[2];
        const values = [];
        const valueRegex = /['"]([^'"]+)['"]/g;
        let valueMatch;
        while ((valueMatch = valueRegex.exec(rawValue)) !== null) {
            values.push(translateApiErrorText(valueMatch[1]));
        }

        if (values.length) {
            fieldMessages.push(`${getApiErrorFieldLabel(field)}: ${values.join(', ')}`);
        }
    }

    if (fieldMessages.length) return fieldMessages.join('\n');

    const detailMessages = [];
    const detailRegex = /ErrorDetail\(string=(['"])(.*?)\1,\s*code=(['"]).*?\3\)/g;
    let detailMatch;
    while ((detailMatch = detailRegex.exec(text)) !== null) {
        detailMessages.push(translateApiErrorText(detailMatch[2]));
    }

    return detailMessages.length ? detailMessages.join('\n') : translateApiErrorText(text);
}

function stringifyApiErrorValue(value) {
    if (value === undefined || value === null || value === '') return '';
    if (typeof value === 'string') return parseApiErrorString(value);
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value)) {
        return value.map(stringifyApiErrorValue).filter(Boolean).join(', ');
    }
    if (typeof value === 'object') {
        return Object.entries(value).map(([field, nestedValue]) => {
            const message = stringifyApiErrorValue(nestedValue);
            if (!message) return '';
            if (['detail', 'error', 'non_field_errors'].includes(field)) return message;
            return `${getApiErrorFieldLabel(field)}: ${message}`;
        }).filter(Boolean).join('\n');
    }
    return String(value);
}

function getApiErrorMessage(errorData, fallback = 'Не удалось выполнить действие. Проверьте введенные данные.') {
    if (!errorData) return fallback;
    if (typeof errorData === 'string') return parseApiErrorString(errorData);
    if (typeof errorData !== 'object') return fallback;
    if (typeof errorData.detail === 'string') return parseApiErrorString(errorData.detail);
    if (typeof errorData.error === 'string') return parseApiErrorString(errorData.error);

    const messages = Object.entries(errorData).map(([field, value]) => {
        const message = stringifyApiErrorValue(value);
        if (!message) return '';
        if (['detail', 'error', 'non_field_errors'].includes(field)) return message;
        return `${getApiErrorFieldLabel(field)}: ${message}`;
    }).filter(Boolean);

    return messages.length ? messages.join('\n') : fallback;
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    loadFilterOptions();
    loadVetList();
    
    // Обработчик кнопки поиска
    document.getElementById('search-btn').addEventListener('click', function() {
        currentPage = 1;
        loadVetList();
    });
    
    // Обработчики Enter в полях ввода
    document.getElementById('tag-search').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            currentPage = 1;
            loadVetList();
        }
    });
});

// Функция для API запросов
async function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    const response = await fetch(url, options);
    
    if (!response.ok) {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            const errorData = await response.json();
            throw new Error(getApiErrorMessage(errorData));
        }

        const errorText = await response.text();
        throw new Error(errorText || `Ошибка сервера: ${response.status}`);
    }
    
    return await response.json();
}

// Получение CSRF токена
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

async function uploadImportFile(importType, action, fileInputId) {
    const fileInput = document.getElementById(fileInputId);
    const file = fileInput?.files?.[0];
    if (!file) {
        throw new Error('Выберите файл импорта');
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`/animals/api/import/${importType}/${action}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData
    });

    const data = await response.json();
    if (!response.ok) {
        throw new Error(getApiErrorMessage(data));
    }
    return data;
}

function renderImportResult(resultId, data, fallbackSuccessText = 'Файл прочитан') {
    const resultBlock = document.getElementById(resultId);
    if (!resultBlock) return;

    const errors = data.errors || [];
    const warnings = data.warnings || [];
    const hasIssues = errors.length > 0 || warnings.length > 0;
    const alertClass = hasIssues ? 'alert-warning' : 'alert-success';

    const issueItems = []
        .concat(errors.map(error => `<li>${escapeHtml(error)}</li>`))
        .concat(warnings.map(warning => `<li>${escapeHtml(warning)}</li>`))
        .join('');

    resultBlock.className = `alert ${alertClass}`;
    resultBlock.style.display = 'block';
    resultBlock.innerHTML = `
        <div class="fw-semibold mb-1">${escapeHtml(fallbackSuccessText)}</div>
        <div>Готово к импорту: ${data.valid_count || 0}</div>
        ${issueItems ? `<hr><div class="fw-semibold mb-1">Проверка файла:</div><ul class="mb-0">${issueItems}</ul>` : ''}
    `;
}

async function previewVetImport() {
    const confirmBtn = document.getElementById('vet-import-confirm-btn');
    if (confirmBtn) confirmBtn.disabled = true;

    try {
        const data = await uploadImportFile('vet', 'preview', 'vet-import-file');
        renderImportResult('vet-import-result', data, 'Файл ветобработок прочитан');
        if (confirmBtn) confirmBtn.disabled = !data.can_confirm;
    } catch (error) {
        renderImportResult('vet-import-result', { valid_count: 0, errors: [error.message] }, 'Ошибка чтения файла');
    }
}

async function confirmVetImport() {
    if (!confirm('Подтвердить импорт ветобработок? Ошибочные строки будут пропущены.')) {
        return;
    }

    const confirmBtn = document.getElementById('vet-import-confirm-btn');
    if (confirmBtn) confirmBtn.disabled = true;

    try {
        const data = await uploadImportFile('vet', 'confirm', 'vet-import-file');
        const createdCount = data.created_count || 0;
        renderImportResult('vet-import-result', data, `Импорт завершен. Создано ветобработок: ${createdCount}`);
        loadVetList();
    } catch (error) {
        renderImportResult('vet-import-result', { valid_count: 0, errors: [error.message] }, 'Ошибка импорта');
        if (confirmBtn) confirmBtn.disabled = false;
    }
}

// Загрузка опций для фильтров
async function loadFilterOptions() {
    try {
        const response = await apiRequest('/animals/api/vet-filter-options/');
        
        // Заполняем селект типов обработок
        const careNameSelect = document.getElementById('care-name-filter');
        careNameSelect.innerHTML = '<option value="">Все</option>';
        response.care_names.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            careNameSelect.appendChild(option);
        });
        
        // Заполняем селект препаратов
        const medicationSelect = document.getElementById('medication-filter');
        medicationSelect.innerHTML = '<option value="">Все</option>';
        response.medications.forEach(medication => {
            const option = document.createElement('option');
            option.value = medication;
            option.textContent = medication;
            medicationSelect.appendChild(option);
        });
        
    } catch (error) {
        console.error('Ошибка загрузки опций фильтров:', error);
    }
}

// Загрузка списка ветобработок
async function loadVetList() {
    const loading = document.getElementById('loading');
    const noData = document.getElementById('no-data');
    const vetList = document.getElementById('vet-list');
    
    // Показываем индикатор загрузки
    loading.style.display = 'block';
    noData.style.display = 'none';
    vetList.innerHTML = '';
    
    try {
        // Собираем параметры фильтрации
        const params = new URLSearchParams({
            page: currentPage,
            page_size: pageSize,
            tag_search: document.getElementById('tag-search').value.trim(),
            care_name: document.getElementById('care-name-filter').value,
            medication: document.getElementById('medication-filter').value,
            care_date_from: document.getElementById('care-date-from').value,
            care_date_to: document.getElementById('care-date-to').value,
            expiry_date_from: document.getElementById('expiry-date-from').value,
            expiry_date_to: document.getElementById('expiry-date-to').value,
            is_hidden: document.getElementById('is-hidden-filter').value,
            sort_by: 'date_of_care',
            sort_order: 'desc'
        });
        
        const response = await apiRequest(`/animals/api/vet-list/?${params}`);
        
        loading.style.display = 'none';
        
        if (response.results && response.results.length > 0) {
            renderVetList(response.results);
            renderPagination(response);
            document.getElementById('total-count').textContent = response.count;
        } else {
            noData.style.display = 'block';
            document.getElementById('total-count').textContent = '0';
        }
        
    } catch (error) {
        console.error('Ошибка загрузки списка ветобработок:', error);
        loading.style.display = 'none';
        noData.style.display = 'block';
        document.getElementById('total-count').textContent = '0';
    }
}

function exportVetListToExcel() {
    const params = new URLSearchParams({
        tag_search: document.getElementById('tag-search').value.trim(),
        care_name: document.getElementById('care-name-filter').value,
        medication: document.getElementById('medication-filter').value,
        care_date_from: document.getElementById('care-date-from').value,
        care_date_to: document.getElementById('care-date-to').value,
        expiry_date_from: document.getElementById('expiry-date-from').value,
        expiry_date_to: document.getElementById('expiry-date-to').value,
        is_hidden: document.getElementById('is-hidden-filter').value,
        sort_by: 'date_of_care',
        sort_order: 'desc'
    });

    window.location.href = `/animals/api/vet-list/export-excel/?${params.toString()}`;
}

// Отображение списка ветобработок
function renderVetList(vetRecords) {
    const vetList = document.getElementById('vet-list');
    const rows = [];
    
    vetRecords.forEach(vet => {
        // Форматируем срок действия
        let durationText = '';
        if (vet.duration_days === 0) {
            durationText = 'Бессрочно';
        } else {
            durationText = `${vet.duration_days} дней`;
        }
        
        // Форматируем дату окончания
        let expiryText = '';
        if (vet.expiry_date) {
            const expiryDate = new Date(vet.expiry_date);
            expiryText = expiryDate.toLocaleDateString('ru-RU');
        } else {
            expiryText = 'Бессрочно';
        }
        
        // Форматируем дату обработки
        const careDate = new Date(vet.care_date);
        const careDateText = careDate.toLocaleDateString('ru-RU');
        
        // Текст завершенного статуса
        const completedText = vet.is_hidden ? 'Да' : 'Нет';
        
        const row = `<tr>
            <td>
                <a href="${vet.animal_url}" class="text-decoration-none">
                    ${vet.display_name || vet.tag_number}
                </a>
            </td>
            <td>${vet.care_name}</td>
            <td>${vet.medication}</td>
            <td>${vet.purpose}</td>
            <td>${durationText}</td>
            <td>${careDateText}</td>
            <td>${expiryText}</td>
            <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" 
                title="${vet.comments}">
                ${vet.comments}
            </td>
            <td class="text-center">${completedText}</td>
        </tr>`;
        
        rows.push(row);
    });
    
    vetList.innerHTML = rows.join('');
}

// Отображение пагинации
function renderPagination(response) {
    const paginationContainer = document.getElementById('pagination');
    paginationContainer.innerHTML = '';
    
    if (response.total_pages <= 1) {
        return;
    }
    
    const pagination = document.createElement('nav');
    const ul = document.createElement('ul');
    ul.className = 'pagination justify-content-center';
    
    // Кнопка "Предыдущая"
    if (response.has_previous) {
        const prevLi = document.createElement('li');
        prevLi.className = 'page-item';
        prevLi.innerHTML = `<a class="page-link" href="#" onclick="changePage(${currentPage - 1})">Предыдущая</a>`;
        ul.appendChild(prevLi);
    }
    
    // Номера страниц
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(response.total_pages, currentPage + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        const li = document.createElement('li');
        li.className = `page-item ${i === currentPage ? 'active' : ''}`;
        li.innerHTML = `<a class="page-link" href="#" onclick="changePage(${i})">${i}</a>`;
        ul.appendChild(li);
    }
    
    // Кнопка "Следующая"
    if (response.has_next) {
        const nextLi = document.createElement('li');
        nextLi.className = 'page-item';
        nextLi.innerHTML = `<a class="page-link" href="#" onclick="changePage(${currentPage + 1})">Следующая</a>`;
        ul.appendChild(nextLi);
    }
    
    pagination.appendChild(ul);
    paginationContainer.appendChild(pagination);
}

// ========== Функции для ковровой вакцинации ==========

// Глобальные переменные для ковровой вакцинации
let selectedAnimalsForVaccination = new Set();
let selectedAnimalsForVaccinationData = new Map();
let vaccinationPlacesLoaded = false;

// Инициализация элементов ковровой вакцинации
document.addEventListener('DOMContentLoaded', function() {
    // Устанавливаем текущую дату как дату вакцинации
    const today = getCurrentLocalDateString();
    const vaccinationDateInput = document.getElementById('vaccination-date');
    if (vaccinationDateInput) {
        vaccinationDateInput.value = today;
    }
    
    // Обработчики для ковровой вакцинации
    const searchAnimalsVaccinationBtn = document.getElementById('searchAnimalsVaccinationBtn');
    if (searchAnimalsVaccinationBtn) {
        searchAnimalsVaccinationBtn.addEventListener('click', searchAnimalsForVaccination);
    }
    
    const animalsVaccinationSearchInput = document.getElementById('animalsVaccinationSearch');
    if (animalsVaccinationSearchInput) {
        animalsVaccinationSearchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchAnimalsForVaccination();
            }
        });
    }

    const toggleAdditionalFiltersBtn = document.getElementById('toggleVaccinationAdditionalFiltersBtn');
    if (toggleAdditionalFiltersBtn) {
        toggleAdditionalFiltersBtn.addEventListener('click', toggleVaccinationAdditionalFilters);
    }
    
    // Заполняем селект обработок
    loadVaccinationCares();
});

async function loadVaccinationPlacesFilter() {
    if (vaccinationPlacesLoaded) {
        return;
    }

    try {
        const places = await apiRequest('/veterinary/api/all-places/');
        const placeSelect = document.getElementById('vaccination-place-filter');
        if (!placeSelect) return;

        placeSelect.innerHTML = '<option value="">Все овчарни</option>';
        (places || []).forEach((place) => {
            const option = document.createElement('option');
            option.value = String(place.id);
            option.textContent = place.sheepfold;
            placeSelect.appendChild(option);
        });

        vaccinationPlacesLoaded = true;
    } catch (error) {
        console.error('Ошибка загрузки овчарен для фильтра:', error);
    }
}

function toggleVaccinationAdditionalFilters() {
    const filtersBlock = document.getElementById('vaccination-additional-filters');
    if (!filtersBlock) return;

    const shouldShow = filtersBlock.style.display === 'none' || filtersBlock.style.display === '';
    filtersBlock.style.display = shouldShow ? 'block' : 'none';

    if (shouldShow) {
        loadVaccinationPlacesFilter();
    }
}

// Загрузка доступных обработок для вакцинации
async function loadVaccinationCares() {
    try {
        const response = await apiRequest('/animals/api/vet-filter-options/');
        
        const careSelect = document.getElementById('vaccination-care');
        if (careSelect) {
            careSelect.innerHTML = '<option value="">Выберите обработку</option>';
            (response.care_options || []).forEach(careOption => {
                const option = document.createElement('option');
                option.value = String(careOption.id);
                option.textContent = careOption.label;
                careSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Ошибка загрузки обработок:', error);
    }
}

// Показать модальное окно выбора животных для вакцинации
function showSelectAnimalsForVaccinationModal() {
    document.getElementById('animalsVaccinationSearch').value = '';
    const placeFilter = document.getElementById('vaccination-place-filter');
    if (placeFilter) {
        placeFilter.value = '';
    }
    const additionalFiltersBlock = document.getElementById('vaccination-additional-filters');
    if (additionalFiltersBlock) {
        additionalFiltersBlock.style.display = 'none';
    }
    document.getElementById('animals-vaccination-list').innerHTML = `
        <div class="text-muted text-center py-3">
            Введите бирку, РСХН или выберите овчарню и нажмите "Поиск"
        </div>
    `;
    
    const modal = new bootstrap.Modal(document.getElementById('selectAnimalsVaccinationModal'));
    modal.show();
}

// Поиск животных для вакцинации
async function searchAnimalsForVaccination() {
    const search = document.getElementById('animalsVaccinationSearch').value.trim();
    const placeId = document.getElementById('vaccination-place-filter')?.value || '';
    
    if (!search && !placeId) {
        document.getElementById('animals-vaccination-list').innerHTML = `
            <div class="text-muted text-center py-3">
                Введите бирку, РСХН или выберите овчарню
            </div>
        `;
        return;
    }
    
    saveSelectedAnimalsForVaccination();
    
    document.getElementById('animals-vaccination-list').innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Поиск...</span>
            </div>
            <div class="mt-2">Поиск животных...</div>
        </div>
    `;
    
    try {
        const params = new URLSearchParams({
            include_with_otbivka: '1'
        });
        if (search) {
            params.set('search', search);
        }
        if (placeId) {
            params.set('place_id', placeId);
        }

        const response = await apiRequest(`/animals/api/animals-without-otbivka/?${params.toString()}`);
        const animals = response || [];
        
        const animalsList = document.getElementById('animals-vaccination-list');
        animalsList.innerHTML = '';
        
        if (animals.length === 0) {
            animalsList.innerHTML = '<div class="text-center text-muted">Животные не найдены</div>';
        } else {
            animals.forEach(animal => {
                const item = createAnimalItemForVaccination(animal);
                animalsList.appendChild(item);
            });
            
            if (animals.length >= 100) {
                const info = document.createElement('div');
                info.className = 'text-muted text-center mt-2 small';
                info.textContent = `Показано первых 100 результатов`;
                animalsList.appendChild(info);
            }
            
            restoreSelectedAnimalsForVaccination();
        }
    } catch (error) {
        console.error('Ошибка поиска животных:', error);
        document.getElementById('animals-vaccination-list').innerHTML = `
            <div class="text-danger text-center py-3">
                Ошибка поиска
            </div>
        `;
    }
}

// Создание элемента для выбора животного
function createAnimalItemForVaccination(animal) {
    const item = document.createElement('div');
    item.className = 'form-check mb-2';
    
    const displayName = animal.display_name || animal.tag_number;
    const animalType = animal.animal_type || animal.type_display || '-';
    
    item.innerHTML = `
        <input class="form-check-input animal-vaccination-checkbox" type="checkbox" 
               value="${animal.tag_number}" data-display="${displayName}">
        <label class="form-check-label">
            ${displayName} (${animalType})
        </label>
    `;
    
    return item;
}

// Сохранение выбранных животных
function saveSelectedAnimalsForVaccination() {
    const checkboxes = document.querySelectorAll('.animal-vaccination-checkbox');
    checkboxes.forEach(checkbox => {
        const tagNumber = checkbox.value;
        if (checkbox.checked) {
            selectedAnimalsForVaccination.add(tagNumber);
            selectedAnimalsForVaccinationData.set(tagNumber, {
                tag_number: tagNumber,
                display_name: checkbox.dataset.display
            });
        } else {
            selectedAnimalsForVaccination.delete(tagNumber);
            selectedAnimalsForVaccinationData.delete(tagNumber);
        }
    });
}

// Восстановление выбранных животных
function restoreSelectedAnimalsForVaccination() {
    const checkboxes = document.querySelectorAll('.animal-vaccination-checkbox');
    checkboxes.forEach(checkbox => {
        if (selectedAnimalsForVaccination.has(checkbox.value)) {
            checkbox.checked = true;
        }
    });
}

// Подтверждение выбора животных для вакцинации
function confirmAnimalsSelectionForVaccination() {
    saveSelectedAnimalsForVaccination();
    
    const selectedAnimalsArray = Array.from(selectedAnimalsForVaccinationData.values());
    
    const display = document.getElementById('selected-animals-vaccination-display');
    const vaccinationBtn = document.getElementById('bulk-vaccination-btn');
    
    if (selectedAnimalsArray.length === 0) {
        display.textContent = 'Не выбрано';
        display.className = 'mt-2 text-muted';
        vaccinationBtn.disabled = true;
    } else {
        display.textContent = `Выбрано: ${selectedAnimalsArray.length} животных`;
        display.className = 'mt-2 text-success';
        vaccinationBtn.disabled = false;
    }
    
    window.selectedAnimalsForVaccinationArray = selectedAnimalsArray;
    
    const modal = bootstrap.Modal.getInstance(document.getElementById('selectAnimalsVaccinationModal'));
    modal.hide();
}

// Выполнение ковровой вакцинации
async function performBulkVaccination() {
    const vaccinationDate = document.getElementById('vaccination-date').value;
    const careSelect = document.getElementById('vaccination-care');
    const veterinaryCareId = careSelect.value;
    
    if (!vaccinationDate) {
        alert('Укажите дату вакцинации');
        return;
    }
    
    if (!veterinaryCareId) {
        alert('Выберите обработку');
        return;
    }
    
    if (!window.selectedAnimalsForVaccinationArray || window.selectedAnimalsForVaccinationArray.length === 0) {
        alert('Выберите животных для вакцинации');
        return;
    }
    
    const selectedCareLabel = careSelect.options[careSelect.selectedIndex]?.textContent || 'выбранная обработка';
    const confirmMessage = `Выполнить вакцинацию "${selectedCareLabel}" для ${window.selectedAnimalsForVaccinationArray.length} животных на дату ${vaccinationDate}?`;
    if (!confirm(confirmMessage)) {
        return;
    }
    
    try {
        const animalTags = window.selectedAnimalsForVaccinationArray.map(animal => animal.tag_number);
        
        const response = await apiRequest('/animals/api/bulk-vaccination/', 'POST', {
            vaccination_date: vaccinationDate,
            veterinary_care_id: parseInt(veterinaryCareId, 10),
            animal_tags: animalTags
        });
        
        let message = `Успешно выполнена вакцинация для ${response.updated_count} из ${response.total_requested} животных!`;
        
        if (response.errors && response.errors.length > 0) {
            message += `\n\nОшибки:\n${response.errors.join('\n')}`;
        }
        
        alert(message);
        
        resetBulkVaccinationForm();
        
        // Перезагружаем список ветобработок
        loadVetList();
        
    } catch (error) {
        console.error('Ошибка при выполнении вакцинации:', error);
        alert('Ошибка при выполнении вакцинации: ' + error.message);
    }
}

// Экспортируем функции в глобальный объект для доступа из HTML
window.showSelectAnimalsForVaccinationModal = showSelectAnimalsForVaccinationModal;
window.searchAnimalsForVaccination = searchAnimalsForVaccination;
window.confirmAnimalsSelectionForVaccination = confirmAnimalsSelectionForVaccination;
window.performBulkVaccination = performBulkVaccination;
window.changePage = changePage;
window.exportVetListToExcel = exportVetListToExcel;

// Очищение формы ковровой вакцинации
function resetBulkVaccinationForm() {
    selectedAnimalsForVaccination.clear();
    selectedAnimalsForVaccinationData.clear();
    window.selectedAnimalsForVaccinationArray = [];
    
    const today = getCurrentLocalDateString();
    document.getElementById('vaccination-date').value = today;
    document.getElementById('vaccination-care').value = '';
    document.getElementById('selected-animals-vaccination-display').textContent = 'Не выбрано';
    document.getElementById('selected-animals-vaccination-display').className = 'mt-2 text-muted';
    document.getElementById('bulk-vaccination-btn').disabled = true;

    const placeFilter = document.getElementById('vaccination-place-filter');
    if (placeFilter) {
        placeFilter.value = '';
    }
    const additionalFiltersBlock = document.getElementById('vaccination-additional-filters');
    if (additionalFiltersBlock) {
        additionalFiltersBlock.style.display = 'none';
    }
}

// Смена страницы
function changePage(page) {
    currentPage = page;
    loadVetList();
}

// Экспортируем функции для глобального доступа
window.changePage = changePage;


