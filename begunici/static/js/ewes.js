import { apiRequest, formatDateToOutput } from "./utils.js";

// Глобальное хранение выбранных элементов с сохранением в sessionStorage
let selectedEwes = new Set();

// Функции для работы с sessionStorage
function saveSelectedEwes() {
    sessionStorage.setItem('selectedEwes', JSON.stringify(Array.from(selectedEwes)));
}

function loadSelectedEwes() {
    const saved = sessionStorage.getItem('selectedEwes');
    if (saved) {
        selectedEwes = new Set(JSON.parse(saved));
    }
}

// Загружаем сохраненные выбранные элементы при инициализации
loadSelectedEwes();

let currentPage = 1;
const pageSize = 10;

document.addEventListener('DOMContentLoaded', function () {
    fetchEwes();  // Загружаем список ярок при загрузке страницы
    loadStatuses();
    loadPlaces();

    const createEweButton = document.querySelector('#create-ewe-button');
    if (createEweButton) {
        createEweButton.onclick = createEwe;
    }
});

// Функция создания ярки
async function saveEwe() {
    const formData = new FormData(document.getElementById('create-ewe-form'));
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
        await apiRequest('/animals/ewe/', 'POST', data);
        alert('Ярка успешно создана');
        document.getElementById('create-ewe-form').reset();
        fetchEwes();
    } catch (error) {
        console.error('Ошибка создания ярки:', error);
        alert(`Ошибка: ${error.message}`);
    }
}

// Алиас для обратной совместимости
const createEwe = saveEwe;

// Функция загрузки списка ярок
// Функция загрузки списка ярок
async function fetchEwes(page = 1, query = '') {
    try {
        // Сохраняем параметры поиска в URL для сохранения при пагинации
        const urlParams = new URLSearchParams(window.location.search);
        if (query && query.trim()) {
            urlParams.set('search', query);
        } else {
            urlParams.delete('search');
        }
        
        // Обновляем URL без перезагрузки страницы
        const newUrl = `${window.location.pathname}${urlParams.toString() ? '?' + urlParams.toString() : ''}`;
        window.history.replaceState({}, '', newUrl);

        // Формируем параметры запроса
        let apiUrl = '/animals/ewe/';
        const params = new URLSearchParams();
        
        // Добавляем параметр страницы
        params.set('page', page);
        
        if (query && query.trim()) {
            params.set('search', query);
        }
        
        if (params.toString()) {
            apiUrl += '?' + params.toString();
        }

        currentPage = page;
        const response = await apiRequest(apiUrl);
        
        // Обрабатываем ответ - может быть массив или объект с results
        const ewes = Array.isArray(response) ? response : (response.results || response);

        if (ewes) {
            renderEwes(ewes);
            // Проверяем, есть ли пагинация в ответе
            if (response.results && (response.next || response.previous)) {
                // Используем полную пагинацию если есть next/previous
                updatePagination(response);
            } else {
                // Для неограниченного списка создаем простую пагинацию
                updateSimplePagination(ewes.length, query);
            }
        } else {
            console.error('Некорректный ответ от API:', response);
            alert('Ошибка: данные ярок не найдены.');
        }
    } catch (error) {
        console.error('Ошибка при загрузке ярок:', error);
        alert('Ошибка при загрузке списка ярок.');
    }
}


// Рендеринг списка ярок
function renderEwes(ewes) {
    const eweTable = document.getElementById('ewe-list');
    const rows = [];
    
    ewes.forEach((ewe, index) => {
        const recordNumber = (currentPage - 1) * pageSize + index + 1;
        
        const row = `<tr>
            <td>
                <input type="checkbox" 
                class="select-ewe"  
                data-tag="${ewe.tag.tag_number}"
                data-animal-id="${ewe.id}">
            </td>
            <td>${recordNumber}</td>
            <td><a href="/animals/ewe/${ewe.tag.tag_number}/info/">${ewe.tag.tag_number}</a></td>
            <td style="background-color:${ewe.animal_status ? ewe.animal_status.color : '#FFFFFF'}">
                ${ewe.animal_status ? ewe.animal_status.status_type : 'Не указан'}
            </td>
            <td>${ewe.age || 'Не указан'}</td>
            <td>${ewe.place ? ewe.place.sheepfold : 'Не указано'}</td>
            <td>${ewe.weight_records && ewe.weight_records.length > 0 
                ? `${ewe.weight_records[0].weight_date}: ${ewe.weight_records[0].weight} кг` 
                : 'Нет записей'}</td>
            <td>${ewe.veterinary_history && ewe.veterinary_history.length > 0 
                ? `${formatDateToOutput(ewe.veterinary_history[0].date_of_care)}: ${ewe.veterinary_history[0].veterinary_care.care_name}`
                : 'Нет записей'}</td>
            <td>${ewe.rshn_tag || '-'}</td>
            <td>${ewe.dorper_display || '-'}</td>
            <td>${ewe.note || ''}</td>
        </tr>`;
        rows.push(row);
    });
    
    eweTable.innerHTML = rows.join('');
    
    // Добавляем обработчики событий для чекбоксов
    document.querySelectorAll('.select-ewe').forEach(cb => {
        cb.addEventListener('click', e => toggleSelectEwe(e.target));
        
        // Восстанавливаем состояние чекбокса
        const tagNumber = cb.getAttribute('data-tag');
        if (selectedEwes.has(tagNumber)) {
            cb.checked = true;
        }
    });
    
    // Обновляем кнопки действий
    toggleDeleteButton();
}

// Функция загрузки статусов
async function loadStatuses() {
    try {
        const response = await apiRequest('/veterinary/api/status/?page_size=100');
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

// Функция поиска ярок
async function searchEwes() {
    const searchTerm = document.getElementById('ewe-search').value;
    
    // Сохраняем выбранные чекбоксы
    const selectedCheckboxes = Array.from(document.querySelectorAll('input[name="selectedEwes"]:checked'))
        .map(cb => cb.value);
    
    currentPage = 1;
    await fetchEwes(currentPage, searchTerm);
    
    // Восстанавливаем выбранные чекбоксы
    selectedCheckboxes.forEach(tagNumber => {
        const checkbox = document.querySelector(`input[name="selectedEwes"][value="${tagNumber}"]`);
        if (checkbox) {
            checkbox.checked = true;
        }
    });
    
    // Обновляем кнопку удаления
    toggleDeleteButton();
}

// Алиас для совместимости с шаблоном
async function performSearch() {
    await searchEwes();
}

// Остальные функции
function toggleForm() {
    const form = document.getElementById('create-ewe-form');
    const button = document.getElementById('toggle-create-ewe-form');
    
    if (form.style.display === 'none' || form.style.display === '') {
        form.style.display = 'block';
        button.textContent = '▲ Скрыть форму создания ярки';
    } else {
        form.style.display = 'none';
        button.textContent = '▼ Создать ярку';
    }
}

// Функция для управления чекбоксами всех записей
function toggleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.select-ewe');
    checkboxes.forEach(cb => {
        const tagNumber = cb.dataset.tag;

        cb.checked = checkbox.checked;
        
        if (checkbox.checked) {
            selectedEwes.add(tagNumber);
        } else {
            selectedEwes.delete(tagNumber);
        }
    });
    
    // Сохраняем состояние в sessionStorage
    saveSelectedEwes();
    
    console.log('Текущее состояние selectedEwes после выбора всех:', selectedEwes);
    toggleDeleteButton();
}

// Функция для управления отдельным чекбоксом
function toggleSelectEwe(checkbox) {
    const tagNumber = checkbox.dataset.tag;

    if (checkbox.checked) {
        selectedEwes.add(tagNumber);
    } else {
        selectedEwes.delete(tagNumber);
    }
    
    // Сохраняем состояние в sessionStorage
    saveSelectedEwes();
    
    console.log('Текущее состояние selectedEwes: \n', selectedEwes);
    toggleDeleteButton();
}

// Функция для отображения кнопки удаления
function toggleDeleteButton() {
    const selectedActionsDiv = document.getElementById('selected-actions');
    const hasSelection = selectedEwes.size > 0;

    selectedActionsDiv.style.display = hasSelection ? 'block' : 'none';
}

// Функция для удаления выбранных записей
async function deleteSelectedEwes() {
    const selectedTags = Array.from(selectedEwes.entries())
        .filter(([tagNumber, { isSelected }]) => isSelected)
        .map(([tagNumber]) => tagNumber);

    console.log('Выбранные для удаления:', selectedTags);

    if (selectedTags.length === 0) {
        alert('Нет выбранных записей для удаления');
        return;
    }

    const tags = selectedTags.map(item => item.tag);
    const modal = document.getElementById('delete-modal');
    const modalMessage = document.getElementById('delete-modal-message');
    const confirmButton = document.getElementById('delete-confirm-button');

    modalMessage.textContent = `Вы уверены, что хотите удалить следующие бирки: ${tags.join(', ')}?`;
    modal.style.display = 'block';

    confirmButton.onclick = async () => {
        try {
            for (const tag of selectedTags) {
                await apiRequest(`/animals/ewe/${tag}/`, 'DELETE');
                selectedEwes.delete(tag);
            }
            alert('Выбранные записи успешно удалены');
            
            // Очищаем все выбранные элементы
            selectedEwes.clear();
            
            // Снимаем галочку с "выбрать все"
            const selectAllCheckbox = document.getElementById('select-all');
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = false;
            }
            
            fetchEwes(currentPage);
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
    
    loadArchiveStatuses();
}

function closeArchiveModal() {
    const modal = document.getElementById('archive-modal');
    modal.style.display = 'none';
}

async function loadArchiveStatuses() {
    try {
        const response = await apiRequest('/veterinary/api/status/?page_size=100');
        // API возвращает пагинированные данные, берем массив из results
        const statuses = response.results || response;
        const archiveStatuses = statuses.filter(status => ['Убыл', 'Убой', 'Продажа на мясо', 'Продажа на племя'].includes(status.status_type));

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
    } catch (error) {
        console.error('Ошибка при загрузке статусов:', error);
    }
}

async function applyArchiveStatus() {
    const selectedTags = Array.from(selectedEwes.entries())
        .filter(([tagNumber, { isSelected }]) => isSelected)
        .map(([tagNumber]) => tagNumber);

    if (selectedTags.length === 0) {
        alert('Нет выбранных записей для переноса.');
        return;
    }

    const statusId = document.getElementById('archive-status-select').value;
    if (!statusId) {
        alert('Выберите статус.');
        return;
    }

    const statusDate = document.getElementById('archive-status-date').value;
    if (!statusDate) {
        alert('Укажите дату присвоения статуса.');
        return;
    }

    try {
        for (const tag of selectedTags) {
            await apiRequest(`/animals/ewe/${tag}/`, 'PATCH', { 
                animal_status_id: statusId,
                status_date: statusDate
            });
        }
        alert('Выбранные записи успешно перенесены в архив.');
        
        // Очищаем все выбранные элементы
        selectedEwes.clear();
        
        // Снимаем галочку с "выбрать все"
        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }
        
        closeArchiveModal();
        fetchEwes(currentPage);
        toggleDeleteButton(); // Скрываем кнопки
    } catch (error) {
        console.error('Ошибка при переносе в архив:', error);
        alert('Ошибка при переносе записей.');
    }
}

// Функция обновления пагинации для локальной фильтрации
function updateSimplePagination(totalItems, searchQuery = '') {
    const paginationContainer = document.getElementById('pagination');
    if (!paginationContainer) return;

    // Для неограниченного списка показываем только информацию о количестве
    paginationContainer.innerHTML = `
        <div class="pagination-info">
            <span>Показано: ${totalItems} ${getAnimalWord(totalItems, 'ярка', 'ярки', 'ярок')}</span>
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

function updateLocalPagination(totalItems, currentPage, searchQuery = '') {
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
            fetchEwes(currentPage - 1, searchQuery);
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
            fetchEwes(currentPage + 1, searchQuery);
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
            const searchQuery = document.getElementById('ewe-search').value;
            fetchEwes(currentPage - 1, searchQuery);
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
            const searchQuery = document.getElementById('ewe-search').value;
            fetchEwes(currentPage + 1, searchQuery);
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
window.deleteSelectedEwes = deleteSelectedEwes;
window.toggleSelectAll = toggleSelectAll;
window.toggleSelectEwe = toggleSelectEwe;
window.toggleDeleteButton = toggleDeleteButton;
window.saveEwe = saveEwe;
window.fetchEwes = fetchEwes;
window.searchEwes = searchEwes;
window.performSearch = performSearch;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Восстанавливаем поисковый запрос из URL
    const urlParams = new URLSearchParams(window.location.search);
    const searchQuery = urlParams.get('search');
    if (searchQuery) {
        const searchInput = document.getElementById('ewe-search');
        if (searchInput) {
            searchInput.value = searchQuery;
        }
    }
    
    fetchEwes(1, searchQuery || '');
    loadStatuses();
    loadPlaces();
});