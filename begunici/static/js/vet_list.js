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
        throw new Error(`HTTP error! status: ${response.status}`);
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

// Загрузка опций для фильтров
async function loadFilterOptions() {
    try {
        const response = await apiRequest('/animals/api/vet-filter-options/');
        
        // Заполняем селект названий обработок
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
            sort_by: 'id',
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
    
    // Заполняем селект обработок
    loadVaccinationCares();
});

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
    selectedAnimalsForVaccination.clear();
    selectedAnimalsForVaccinationData.clear();
    document.getElementById('animalsVaccinationSearch').value = '';
    document.getElementById('animals-vaccination-list').innerHTML = `
        <div class="text-muted text-center py-3">
            Введите номер бирки и нажмите "Поиск" для отображения результатов
        </div>
    `;
    
    const modal = new bootstrap.Modal(document.getElementById('selectAnimalsVaccinationModal'));
    modal.show();
}

// Поиск животных для вакцинации
async function searchAnimalsForVaccination() {
    const search = document.getElementById('animalsVaccinationSearch').value.trim();
    
    if (!search) {
        document.getElementById('animals-vaccination-list').innerHTML = `
            <div class="text-muted text-center py-3">
                Введите номер бирки для поиска
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
        const response = await apiRequest(`/animals/api/animals-without-otbivka/?search=${encodeURIComponent(search)}&include_with_otbivka=1`);
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

// Очищение формы ковровой вакцинации
function resetBulkVaccinationForm() {
    selectedAnimalsForVaccination.clear();
    selectedAnimalsForVaccinationData.clear();
    
    const today = getCurrentLocalDateString();
    document.getElementById('vaccination-date').value = today;
    document.getElementById('vaccination-care').value = '';
    document.getElementById('selected-animals-vaccination-display').textContent = 'Не выбрано';
    document.getElementById('selected-animals-vaccination-display').className = 'mt-2 text-muted';
    document.getElementById('bulk-vaccination-btn').disabled = true;
}

// Смена страницы
function changePage(page) {
    currentPage = page;
    loadVetList();
}

// Экспортируем функции для глобального доступа
window.changePage = changePage;
