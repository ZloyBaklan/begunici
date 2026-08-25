import { apiRequest, getCSRFToken, getApiErrorMessage } from "./utils.js";

// Глобальные переменные для ковровой отбивки
let selectedAnimals = new Set(); // Для хранения выбранных животных
let selectedAnimalsData = new Map(); // Для хранения полной информации о выбранных животных
let selectedAnimalsWeights = new Map(); // Для хранения веса при отбивке по бирке
let weightsStepVisible = false;

document.addEventListener('DOMContentLoaded', function () {
    fetchOtbivka();  // Загружаем список отбивки при загрузке страницы
    loadBulkOtbivkaPlaces();

    // Убираем автоматические обработчики для поиска и дат
    // Теперь фильтрация работает только по кнопке "Применить"
    
    // Устанавливаем текущую дату как дату отбивки
    const today = new Date().toISOString().split('T')[0];
    const otbivkaDateInput = document.getElementById('otbivka-date');
    if (otbivkaDateInput) {
        otbivkaDateInput.value = today;
    }
    
    // Обработчики для ковровой отбивки
    const searchAnimalsBtn = document.getElementById('searchAnimalsBtn');
    if (searchAnimalsBtn) {
        searchAnimalsBtn.addEventListener('click', searchAnimals);
    }
    
    const animalsSearchInput = document.getElementById('animalsSearch');
    if (animalsSearchInput) {
        animalsSearchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchAnimals();
            }
        });
    }

    const selectAnimalsModal = document.getElementById('selectAnimalsModal');
    if (selectAnimalsModal) {
        selectAnimalsModal.addEventListener('hidden.bs.modal', function() {
            saveSelectedWeights();
        });
    }
    
    // Добавляем обработчик Enter для поля поиска по бирке
    const searchInput = document.getElementById('otbivka-search');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                performOtbivkaSearch();
            }
        });
    }
});

let currentPage = 1;
const pageSize = 10;

// Функция загрузки списка отбивки
async function fetchOtbivka(page = 1, query = '', dateFrom = '', dateTo = '') {
    try {
        let url = `/animals/api/otbivka/?page=${page}&page_size=${pageSize}&search=${encodeURIComponent(query)}`;
        
        if (dateFrom) {
            url += `&date_from=${encodeURIComponent(dateFrom)}`;
        }
        if (dateTo) {
            url += `&date_to=${encodeURIComponent(dateTo)}`;
        }
        
        const response = await apiRequest(url);
        
        if (response && response.results) {
            renderOtbivka(response.results);
            updatePagination(response);
        } else {
            console.error('Некорректный ответ от API:', response);
            showError('Ошибка: данные отбивки не найдены.');
        }
    } catch (error) {
        console.error('Ошибка при загрузке отбивки:', error);
        showError('Ошибка при загрузке списка отбивки.');
    }
}

// Рендеринг списка отбивки
function renderOtbivka(animals) {
    const otbivkaTable = document.getElementById('otbivka-list');
    otbivkaTable.innerHTML = '';
    
    if (animals.length === 0) {
        otbivkaTable.innerHTML = `
            <tr>
                <td colspan="4" class="text-center py-4">
                    <p class="text-muted">Нет животных с датой отбивки.</p>
                </td>
            </tr>
        `;
        return;
    }
    
    animals.forEach((animal) => {
        const row = `<tr>
            <td>${animal.date_otbivka}</td>
            <td>
                <a href="/animals/${animal.animal_type}/${animal.tag_number}/info/" 
                   class="text-decoration-none">
                    ${animal.display_name || animal.tag_number}
                </a>
            </td>
            <td>
                ${animal.age_at_otbivka || '-'}
            </td>
            <td>
                ${animal.weaning_weight || '-'}
            </td>
        </tr>`;
        otbivkaTable.innerHTML += row;
    });
}

// Функция поиска отбивки с фильтрацией по датам
async function performOtbivkaSearch() {
    const searchTerm = document.getElementById('otbivka-search').value;
    const dateFrom = document.getElementById('otbivka-date-from').value;
    const dateTo = document.getElementById('otbivka-date-to').value;
    
    currentPage = 1;
    fetchOtbivka(currentPage, searchTerm, dateFrom, dateTo);
}

function exportOtbivkaToExcel() {
    const params = new URLSearchParams();
    const searchTerm = document.getElementById('otbivka-search').value.trim();
    const dateFrom = document.getElementById('otbivka-date-from').value;
    const dateTo = document.getElementById('otbivka-date-to').value;

    if (searchTerm) {
        params.set('search', searchTerm);
    }
    if (dateFrom) {
        params.set('date_from', dateFrom);
    }
    if (dateTo) {
        params.set('date_to', dateTo);
    }

    window.location.href = `/animals/api/otbivka/export-excel/?${params.toString()}`;
}

// Обновление пагинации
function updatePagination(response) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';
    
    if (response.total_pages <= 1) {
        return; // Не показываем пагинацию если только одна страница
    }
    
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
            currentPage--;
            const searchTerm = document.getElementById('otbivka-search').value;
            const dateFrom = document.getElementById('otbivka-date-from').value;
            const dateTo = document.getElementById('otbivka-date-to').value;
            fetchOtbivka(currentPage, searchTerm, dateFrom, dateTo);
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
    pageInfo.innerText = `Страница ${response.current_page} из ${response.total_pages}`;
    pageInfo.style.fontWeight = '500';
    pageInfo.style.minWidth = '150px';
    pageInfo.style.textAlign = 'center';
    paginationContainer.appendChild(pageInfo);

    // Кнопка "Следующая" (справа)
    if (response.next) {
        const nextButton = document.createElement('button');
        nextButton.innerText = 'Следующая';
        nextButton.className = 'btn btn-outline-primary btn-sm';
        nextButton.onclick = () => {
            currentPage++;
            const searchTerm = document.getElementById('otbivka-search').value;
            const dateFrom = document.getElementById('otbivka-date-from').value;
            const dateTo = document.getElementById('otbivka-date-to').value;
            fetchOtbivka(currentPage, searchTerm, dateFrom, dateTo);
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

// Показать ошибку
function showError(message) {
    const otbivkaTable = document.getElementById('otbivka-list');
    otbivkaTable.innerHTML = `
        <tr>
            <td colspan="4" class="text-center py-4">
                <p class="text-danger">${message}</p>
            </td>
        </tr>
    `;
}

// Экспортируем функции для глобального доступа
window.fetchOtbivka = fetchOtbivka;
window.performOtbivkaSearch = performOtbivkaSearch;
window.exportOtbivkaToExcel = exportOtbivkaToExcel;

// Функции для ковровой отбивки
window.showSelectAnimalsModal = showSelectAnimalsModal;
window.confirmAnimalsSelection = confirmAnimalsSelection;
window.performBulkOtbivka = performBulkOtbivka;
window.previewOtbivkaImport = previewOtbivkaImport;
window.confirmOtbivkaImport = confirmOtbivkaImport;

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

async function loadBulkOtbivkaPlaces() {
    const placeSelect = document.getElementById('bulk-otbivka-place');
    if (!placeSelect) {
        return;
    }

    try {
        placeSelect.disabled = true;
        const response = await apiRequest('/veterinary/api/place/?page_size=1000');
        const places = Array.isArray(response) ? response : (response.results || []);

        placeSelect.innerHTML = '<option value="">Не перемещать</option>';
        places.forEach(place => {
            const option = document.createElement('option');
            option.value = place.id;
            option.textContent = place.sheepfold;
            placeSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка загрузки овчарен для отбивки:', error);
        placeSelect.innerHTML = '<option value="">Не удалось загрузить овчарни</option>';
    } finally {
        placeSelect.disabled = false;
    }
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
            'X-CSRFToken': getCSRFToken()
        },
        body: formData
    });

    const data = await response.json();
    if (!response.ok) {
        throw new Error(getApiErrorMessage(data));
    }
    return data;
}

function renderImportResult(resultId, data, title) {
    const resultBlock = document.getElementById(resultId);
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
        <div>Готово к импорту: ${data.valid_count || 0}</div>
        ${issueItems ? `<hr><div class="fw-semibold mb-1">Проверка файла:</div><ul class="mb-0">${issueItems}</ul>` : ''}
    `;
}

async function previewOtbivkaImport() {
    const confirmBtn = document.getElementById('otbivka-import-confirm-btn');
    if (confirmBtn) confirmBtn.disabled = true;

    try {
        const data = await uploadImportFile('otbivka', 'preview', 'otbivka-import-file');
        renderImportResult('otbivka-import-result', data, 'Файл отбивки прочитан');
        if (confirmBtn) confirmBtn.disabled = !data.can_confirm;
    } catch (error) {
        renderImportResult('otbivka-import-result', { valid_count: 0, errors: [error.message] }, 'Ошибка чтения файла');
    }
}

async function confirmOtbivkaImport() {
    if (!confirm('Подтвердить импорт отбивки? Ошибочные строки будут пропущены.')) {
        return;
    }

    const confirmBtn = document.getElementById('otbivka-import-confirm-btn');
    if (confirmBtn) confirmBtn.disabled = true;

    try {
        const data = await uploadImportFile('otbivka', 'confirm', 'otbivka-import-file');
        const updatedCount = data.updated_count || 0;
        const weightCount = data.weight_records_count || 0;
        const movedCount = data.moved_count || 0;
        renderImportResult(
            'otbivka-import-result',
            data,
            `Импорт завершен. Отбито: ${updatedCount}; весов: ${weightCount}; перемещено: ${movedCount}`
        );
        fetchOtbivka();
    } catch (error) {
        renderImportResult('otbivka-import-result', { valid_count: 0, errors: [error.message] }, 'Ошибка импорта');
        if (confirmBtn) confirmBtn.disabled = false;
    }
}

// Показать модальное окно выбора животных
async function showSelectAnimalsModal() {
    document.getElementById('animalsSearch').value = '';
    document.getElementById('animals-list').innerHTML = `
        <div class="text-muted text-center py-3">
            Введите бирку или РСХН и нажмите "Поиск" для отображения результатов
        </div>
    `;
    weightsStepVisible = selectedAnimalsData.size > 0;
    renderSelectedAnimalsWeights();
    
    // Показываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('selectAnimalsModal'));
    modal.show();
}

// Поиск животных без отбивки
async function searchAnimals() {
    const search = document.getElementById('animalsSearch').value.trim();
    
    if (!search) {
        document.getElementById('animals-list').innerHTML = `
            <div class="text-muted text-center py-3">
                Введите бирку или РСХН для поиска
            </div>
        `;
        return;
    }
    
    // Сохраняем текущие выбранные чекбоксы
    saveSelectedWeights();
    saveSelectedAnimals();
    
    // Показываем индикатор загрузки
    document.getElementById('animals-list').innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Поиск...</span>
            </div>
            <div class="mt-2">Поиск животных без отбивки...</div>
        </div>
    `;
    
    try {
        const response = await apiRequest(`/animals/api/animals-without-otbivka/?search=${encodeURIComponent(search)}`);
        const animals = response || [];
        
        const animalsList = document.getElementById('animals-list');
        animalsList.innerHTML = '';
        
        if (animals.length === 0) {
            animalsList.innerHTML = '<div class="text-center text-muted">Животные без отбивки не найдены</div>';
        } else {
            animals.forEach(animal => {
                const item = createAnimalItem(animal);
                animalsList.appendChild(item);
            });
            
            // Показываем информацию о количестве результатов
            if (animals.length >= 100) {
                const info = document.createElement('div');
                info.className = 'text-muted text-center mt-2 small';
                info.textContent = `Показано первых 100 результатов`;
                animalsList.appendChild(info);
            }
            
            // Восстанавливаем выбранные чекбоксы
            restoreSelectedAnimals();
            renderSelectedAnimalsWeights();
        }
    } catch (error) {
        console.error('Ошибка поиска животных:', error);
        document.getElementById('animals-list').innerHTML = `
            <div class="text-danger text-center py-3">
                Ошибка поиска
            </div>
        `;
    }
}

// Создание элемента для выбора животного
function createAnimalItem(animal) {
    const item = document.createElement('div');
    item.className = 'form-check mb-2';
    
    item.innerHTML = `
        <input class="form-check-input animal-checkbox" type="checkbox" 
               value="${animal.tag_number}" data-type="${animal.type_code}" data-display="${animal.display_name}">
        <label class="form-check-label">
            ${animal.display_name} (${animal.animal_type}) - ${animal.status}
        </label>
    `;
    
    return item;
}

// Функция для сохранения выбранных животных
function saveSelectedAnimals() {
    const checkboxes = document.querySelectorAll('.animal-checkbox');
    checkboxes.forEach(checkbox => {
        const tagNumber = checkbox.value;
        if (checkbox.checked) {
            selectedAnimals.add(tagNumber);
            selectedAnimalsData.set(tagNumber, {
                tag_number: tagNumber,
                type: checkbox.dataset.type,
                display_name: checkbox.dataset.display
            });
        } else {
            selectedAnimals.delete(tagNumber);
            selectedAnimalsData.delete(tagNumber);
            selectedAnimalsWeights.delete(tagNumber);
        }
    });
}

// Функция для восстановления выбранных животных
function restoreSelectedAnimals() {
    const checkboxes = document.querySelectorAll('.animal-checkbox');
    checkboxes.forEach(checkbox => {
        if (selectedAnimals.has(checkbox.value)) {
            checkbox.checked = true;
        }
    });
}

function saveSelectedWeights() {
    const weightInputs = document.querySelectorAll('.otbivka-weight-input');
    weightInputs.forEach(input => {
        const tagNumber = input.dataset.tag;
        const value = input.value.trim();

        if (!tagNumber) {
            return;
        }

        if (value) {
            selectedAnimalsWeights.set(tagNumber, value);
        } else {
            selectedAnimalsWeights.delete(tagNumber);
        }
    });
}

function updateSelectionModalButton() {
    const button = document.getElementById('confirmAnimalsSelectionBtn');
    if (button) {
        button.textContent = weightsStepVisible ? 'Готово' : 'Выбрать';
    }
}

function renderSelectedAnimalsWeights() {
    const section = document.getElementById('selected-animals-weights-section');
    const list = document.getElementById('selected-animals-weights-list');
    if (!section || !list) {
        return;
    }

    const selectedAnimalsArray = Array.from(selectedAnimalsData.values());
    if (!weightsStepVisible || selectedAnimalsArray.length === 0) {
        section.style.display = 'none';
        list.innerHTML = '';
        updateSelectionModalButton();
        return;
    }

    section.style.display = 'block';
    list.innerHTML = selectedAnimalsArray.map(animal => {
        const tagNumber = animal.tag_number;
        const savedWeight = selectedAnimalsWeights.get(tagNumber) || '';

        return `
            <div class="row g-2 align-items-center">
                <div class="col-md-7">
                    <span class="fw-semibold">${escapeHtml(animal.display_name || tagNumber)}</span>
                </div>
                <div class="col-md-5">
                    <input type="number"
                           class="form-control otbivka-weight-input"
                           data-tag="${escapeHtml(tagNumber)}"
                           min="0"
                           step="0.1"
                           placeholder="Вес, кг"
                           value="${escapeHtml(savedWeight)}">
                </div>
            </div>
        `;
    }).join('');

    list.querySelectorAll('.otbivka-weight-input').forEach(input => {
        input.addEventListener('input', function() {
            const value = this.value.trim();
            if (value) {
                selectedAnimalsWeights.set(this.dataset.tag, value);
            } else {
                selectedAnimalsWeights.delete(this.dataset.tag);
            }
        });
    });

    updateSelectionModalButton();
}

function updateSelectedAnimalsDisplay() {
    const selectedAnimalsArray = Array.from(selectedAnimalsData.values());
    const display = document.getElementById('selected-animals-display');
    const bulkOtbivkaBtn = document.getElementById('bulk-otbivka-btn');

    if (!display || !bulkOtbivkaBtn) {
        window.selectedAnimalsForOtbivka = selectedAnimalsArray;
        return;
    }

    if (selectedAnimalsArray.length === 0) {
        display.textContent = 'Не выбрано';
        display.className = 'mt-2 text-muted';
        bulkOtbivkaBtn.disabled = true;
    } else {
        display.textContent = `Выбрано: ${selectedAnimalsArray.length} животных`;
        display.className = 'mt-2 text-success';
        bulkOtbivkaBtn.disabled = false;
    }

    window.selectedAnimalsForOtbivka = selectedAnimalsArray;
}

// Подтверждение выбора животных
function confirmAnimalsSelection() {
    // Сохраняем текущие выбранные чекбоксы
    saveSelectedWeights();
    saveSelectedAnimals();
    updateSelectedAnimalsDisplay();

    if (selectedAnimalsData.size === 0) {
        weightsStepVisible = false;
        renderSelectedAnimalsWeights();
        const emptyModal = bootstrap.Modal.getInstance(document.getElementById('selectAnimalsModal'));
        emptyModal.hide();
        return;
    }

    if (!weightsStepVisible) {
        weightsStepVisible = true;
        renderSelectedAnimalsWeights();
        return;
    }

    const renderedWeightTags = new Set(
        Array.from(document.querySelectorAll('.otbivka-weight-input')).map(input => input.dataset.tag)
    );
    const hasSelectedAnimalsWithoutWeightRow = Array
        .from(selectedAnimalsData.keys())
        .some(tagNumber => !renderedWeightTags.has(tagNumber));

    if (hasSelectedAnimalsWithoutWeightRow) {
        renderSelectedAnimalsWeights();
        return;
    }

    // Закрываем модальное окно после ввода необязательных весов.
    const modal = bootstrap.Modal.getInstance(document.getElementById('selectAnimalsModal'));
    modal.hide();
}

// Выполнение массовой отбивки
async function performBulkOtbivka() {
    const otbivkaDate = document.getElementById('otbivka-date').value;
    const placeSelect = document.getElementById('bulk-otbivka-place');
    const selectedPlaceId = placeSelect?.value || '';
    const selectedPlaceName = placeSelect?.selectedOptions?.[0]?.textContent || '';
    
    if (!otbivkaDate) {
        alert('Укажите дату отбивки');
        return;
    }
    
    if (!window.selectedAnimalsForOtbivka || window.selectedAnimalsForOtbivka.length === 0) {
        alert('Выберите животных для отбивки');
        return;
    }
    
    // Подтверждение операции
    let confirmMessage = `Выполнить отбивку для ${window.selectedAnimalsForOtbivka.length} животных на дату ${otbivkaDate}?\n\nСтатусы животных автоматически меняться не будут.`;
    if (selectedPlaceId) {
        confirmMessage += `\n\nПосле отбивки животные будут перемещены в: ${selectedPlaceName}.`;
    }
    if (!confirm(confirmMessage)) {
        return;
    }
    
    try {
        const animalTags = window.selectedAnimalsForOtbivka.map(animal => animal.tag_number);
        const animalWeights = {};

        window.selectedAnimalsForOtbivka.forEach(animal => {
            const savedWeight = selectedAnimalsWeights.get(animal.tag_number);
            if (savedWeight) {
                animalWeights[animal.tag_number] = savedWeight;
            }
        });

        const payload = {
            otbivka_date: otbivkaDate,
            animal_tags: animalTags
        };

        if (Object.keys(animalWeights).length > 0) {
            payload.animal_weights = animalWeights;
        }

        if (selectedPlaceId) {
            payload.place_id = selectedPlaceId;
        }

        const response = await apiRequest('/animals/api/bulk-otbivka/', 'POST', payload);

        let message = `Успешно выполнена отбивка для ${response.updated_count} из ${response.total_requested} животных!`;
        if (response.weight_records_count) {
            message += `\nЗаписей веса добавлено/обновлено: ${response.weight_records_count}`;
        }
        if (response.moved_count) {
            message += `\nПеремещено животных: ${response.moved_count}`;
        }
        
        if (response.errors && response.errors.length > 0) {
            message += `\n\nОшибки:\n${response.errors.join('\n')}`;
        }
        
        alert(message);
        
        // Очищаем форму
        resetBulkOtbivkaForm();
        
        // Перезагружаем список отбивки
        fetchOtbivka();
        
    } catch (error) {
        console.error('Ошибка выполнения массовой отбивки:', error);
        alert('Ошибка при выполнении отбивки: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Сброс формы массовой отбивки
function resetBulkOtbivkaForm() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('otbivka-date').value = today;
    
    selectedAnimals.clear();
    selectedAnimalsData.clear();
    selectedAnimalsWeights.clear();
    weightsStepVisible = false;
    window.selectedAnimalsForOtbivka = [];

    const placeSelect = document.getElementById('bulk-otbivka-place');
    if (placeSelect) {
        placeSelect.value = '';
    }

    renderSelectedAnimalsWeights();
    
    document.getElementById('selected-animals-display').textContent = 'Не выбрано';
    document.getElementById('selected-animals-display').className = 'mt-2 text-muted';
    document.getElementById('bulk-otbivka-btn').disabled = true;
}
