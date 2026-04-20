import { apiRequest, formatDateToOutput } from "./utils.js";

// Получаем права пользователя из глобальной переменной
function getUserPermissions() {
    return window.userPermissions || {
        can_restore_from_archive: true
    };
}

let allArchiveData = []; // Храним все данные архива
let currentPage = 1; // Текущая страница
const pageSize = 10; // Количество записей на странице

document.addEventListener('DOMContentLoaded', function () {
    // Устанавливаем начальный фильтр по типу животного, если он передан
    const initialType = window.initialAnimalType || '';
    if (initialType) {
        const typeFilter = document.getElementById('animal-type-filter');
        if (typeFilter) {
            typeFilter.value = initialType;
        }
    }
    
    loadArchiveStatuses();  // Загружаем статусы для фильтра
    fetchArchive();  // Загружаем архив при загрузке страницы
});

// Функция загрузки статусов для фильтра
async function loadArchiveStatuses() {
    try {
        const response = await apiRequest('/veterinary/api/status/?page_size=100');
        const statuses = response.results || response;
        
        // Оставляем только архивные статусы (как было в оригинале)
        const archiveStatuses = statuses.filter(status => 
            ['Убой', 'Убыл', 'Продажа на мясо', 'Продажа на племя'].includes(status.status_type)
        );
        
        const statusSelect = document.getElementById('status-filter');
        statusSelect.innerHTML = '<option value="">Все статусы</option>';
        
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

// Функция загрузки архива
async function fetchArchive(page = 1) {
    try {
        // Сохраняем параметры поиска в URL для сохранения при пагинации
        const urlParams = new URLSearchParams(window.location.search);
        const searchQuery = urlParams.get('search') || '';
        const animalType = urlParams.get('type') || window.initialAnimalType || '';
        const statusFilter = urlParams.get('animal_status') || '';
        const placeFilter = urlParams.get('place') || '';
        const archiveDateFrom = urlParams.get('archive_date_from') || '';
        const archiveDateTo = urlParams.get('archive_date_to') || '';
        
        // Формируем параметры запроса
        let apiUrl = '/animals/archive/';
        const params = new URLSearchParams();
        
        // Добавляем параметр страницы
        params.set('page', page);
        
        if (searchQuery && searchQuery.trim()) {
            params.set('search', searchQuery);
        }
        if (animalType) {
            params.set('type', animalType);
        }
        if (statusFilter) {
            params.set('animal_status', statusFilter);
        }
        if (placeFilter) {
            params.set('place', placeFilter);
        }
        if (archiveDateFrom) {
            params.set('archive_date_from', archiveDateFrom);
        }
        if (archiveDateTo) {
            params.set('archive_date_to', archiveDateTo);
        }
        
        apiUrl += '?' + params.toString();

        currentPage = page;
        const response = await apiRequest(apiUrl);
        
        // Обрабатываем пагинированный ответ
        if (response && response.results) {
            // Пагинированный ответ
            displayArchive(response.results);
            updateArchivePagination(response);
        } else if (Array.isArray(response)) {
            // Массив (для обратной совместимости)
            displayArchive(response);
            updateSimpleArchivePagination(response.length, searchQuery, animalType);
        } else {
            console.error('Неожиданный формат ответа:', response);
        }
    } catch (error) {
        console.error('Ошибка при загрузке архива:', error);
    }
}

// Функция отображения архива
function displayArchive(data, startIndex = null) {
    const archiveTable = document.getElementById('archive-list');
    
    archiveTable.innerHTML = '';

    data.forEach((animal, index) => {
        const row = document.createElement('tr');
        
        // Получаем данные с учетом формата ArchiveAnimalSerializer
        const tagNumber = animal.tag_number;
        const animalTypeCode = animal.animal_type;
        const status = animal.status || 'Не указан';
        const statusColor = animal.status_color || '#FFFFFF';
        const archivedDate = formatDateToOutput(animal.archived_date) || 'Не указана';
        const age = animal.age || 'Не указан';
        const place = animal.place || 'Не указано';
        
        // Определяем тип животного и URL
        let animalType = 'Неизвестно';
        let detailUrl = '';
        
        if (animalTypeCode === 'Maker') {
            animalType = 'Производитель';
            detailUrl = `/animals/maker/${tagNumber}/info/`;
        } else if (animalTypeCode === 'Ram') {
            animalType = 'Баран';
            detailUrl = `/animals/ram/${tagNumber}/info/`;
        } else if (animalTypeCode === 'Ewe') {
            animalType = 'Ярка';
            detailUrl = `/animals/ewe/${tagNumber}/info/`;
        } else if (animalTypeCode === 'Sheep') {
            animalType = 'Овца';
            detailUrl = `/animals/sheep/${tagNumber}/info/`;
        }
        
        // Создаем кнопку восстановления только если есть права
        const permissions = getUserPermissions();
        let actionsHtml = '';
        
        if (permissions.can_restore_from_archive) {
            actionsHtml = `
                <button class="btn btn-outline-success btn-sm" onclick="restoreAnimal('${animalTypeCode}', '${tagNumber}')">
                    Восстановить
                </button>
            `;
        } else {
            actionsHtml = '<span class="text-muted">Нет прав</span>';
        }
        
        // Если startIndex не передан, используем стандартную пагинацию
        const recordNumber = startIndex !== null ? startIndex + index + 1 : (currentPage - 1) * pageSize + index + 1;
        
        row.innerHTML = `
            <td>${recordNumber}</td>
            <td>${animalType}</td>
            <td><a href="${detailUrl}">${animal.display_name || tagNumber}</a></td>
            <td style="background-color:${statusColor}">${status}</td>
            <td>${archivedDate}</td>
            <td>${age}</td>
            <td>${place}</td>
            <td>${actionsHtml}</td>
        `;
        archiveTable.appendChild(row);
    });
}

// Функция фильтрации архива (алиас для обратной совместимости)
async function filterArchiveData(animalType, status, search) {
    // Перенаправляем на новую функцию с полной загрузкой данных
    return filterArchiveDataWithSearch(animalType, status, search);
}

// Функция восстановления животного из архива
async function restoreAnimal(animalType, tagNumber) {
    // Открываем модальное окно для выбора статуса
    openRestoreModal(animalType, tagNumber);
}

// Функция открытия модального окна восстановления
async function openRestoreModal(animalType, tagNumber) {
    const modal = document.getElementById('restore-modal');
    const confirmButton = document.getElementById('restore-confirm-button');
    
    // Загружаем статусы
    await loadRestoreStatuses();
    
    // Показываем модальное окно
    modal.style.display = 'block';
    
    // Настраиваем обработчик подтверждения
    confirmButton.onclick = () => performRestore(animalType, tagNumber);
}

// Функция загрузки статусов для восстановления
async function loadRestoreStatuses() {
    try {
        const response = await apiRequest('/veterinary/api/status/');
        // API возвращает пагинированные данные, нужно взять results
        const statuses = response.results || response;
        
        // Исключаем архивные статусы
        const activeStatuses = statuses.filter(status => 
            !['Убыл', 'Убой', 'Продажа на мясо', 'Продажа на племя'].includes(status.status_type)
        );

        const statusSelect = document.getElementById('restore-status-select');
        statusSelect.innerHTML = '<option value="">Выберите статус</option>';

        if (activeStatuses.length === 0) {
            statusSelect.innerHTML = '<option value="">Нет доступных статусов</option>';
            return;
        }

        activeStatuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.textContent = status.status_type;
            statusSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка при загрузке статусов:', error);
        const statusSelect = document.getElementById('restore-status-select');
        statusSelect.innerHTML = '<option value="">Ошибка загрузки статусов</option>';
    }
}

// Функция выполнения восстановления с выбранным статусом
async function performRestore(animalType, tagNumber) {
    const statusId = document.getElementById('restore-status-select').value;
    
    if (!statusId) {
        alert('Пожалуйста, выберите статус для животного');
        return;
    }

    try {
        // Определяем URL для восстановления в зависимости от типа животного
        let restoreUrl = '';
        switch (animalType) {
            case 'Maker':
                restoreUrl = `/animals/maker/${tagNumber}/restore/`;
                break;
            case 'Ram':
                restoreUrl = `/animals/ram/${tagNumber}/restore/`;
                break;
            case 'Ewe':
                restoreUrl = `/animals/ewe/${tagNumber}/restore/`;
                break;
            case 'Sheep':
                restoreUrl = `/animals/sheep/${tagNumber}/restore/`;
                break;
            default:
                throw new Error('Неизвестный тип животного');
        }
        
        // Отправляем запрос с выбранным статусом
        await apiRequest(restoreUrl, 'POST', { status_id: statusId });
        alert('Животное успешно восстановлено из архива');
        closeRestoreModal();
        fetchArchive(currentPage); // Обновляем текущую страницу архива
    } catch (error) {
        console.error('Ошибка при восстановлении животного:', error);
        alert('Ошибка при восстановлении животного');
    }
}

// Функция закрытия модального окна восстановления
function closeRestoreModal() {
    const modal = document.getElementById('restore-modal');
    modal.style.display = 'none';
}

// Функция поиска в архиве
function performArchiveSearch() {
    const animalType = document.getElementById('animal-type-filter').value;
    const status = document.getElementById('status-filter').value;
    const place = document.getElementById('place-filter') ? document.getElementById('place-filter').value : '';
    const search = document.getElementById('archive-search').value;
    const archiveDateFrom = document.getElementById('archive-date-from').value;
    const archiveDateTo = document.getElementById('archive-date-to').value;
    
    // Сохраняем параметры поиска в URL
    const urlParams = new URLSearchParams(window.location.search);
    if (search && search.trim()) {
        urlParams.set('search', search);
    } else {
        urlParams.delete('search');
    }
    if (animalType) {
        urlParams.set('type', animalType);
    } else {
        urlParams.delete('type');
    }
    if (status) {
        urlParams.set('animal_status', status);
    } else {
        urlParams.delete('animal_status');
    }
    if (place) {
        urlParams.set('place', place);
    } else {
        urlParams.delete('place');
    }
    if (archiveDateFrom) {
        urlParams.set('archive_date_from', archiveDateFrom);
    } else {
        urlParams.delete('archive_date_from');
    }
    if (archiveDateTo) {
        urlParams.set('archive_date_to', archiveDateTo);
    } else {
        urlParams.delete('archive_date_to');
    }
    
    // Обновляем URL без перезагрузки страницы
    const newUrl = `${window.location.pathname}${urlParams.toString() ? '?' + urlParams.toString() : ''}`;
    window.history.replaceState({}, '', newUrl);
    
    // Выполняем поиск
    fetchArchive(1);
}
window.performArchiveSearch = performArchiveSearch; // Делаем функцию глобальной

// Функция фильтрации с загрузкой всех данных
async function filterArchiveDataWithSearch(animalType, status, search) {
    try {
        currentPage = 1; // Сбрасываем на первую страницу при фильтрации
        
        // Всегда загружаем больше данных для корректной фильтрации
        let url = `/animals/archive/?page=1&page_size=500`;
        
        // Добавляем тип животного в запрос если указан
        if (animalType) {
            url += `&type=${encodeURIComponent(animalType)}`;
        }
        
        // Добавляем даты архивирования если указаны
        const archiveDateFrom = document.getElementById('archive-date-from').value;
        const archiveDateTo = document.getElementById('archive-date-to').value;
        
        if (archiveDateFrom) {
            url += `&archive_date_from=${encodeURIComponent(archiveDateFrom)}`;
        }
        if (archiveDateTo) {
            url += `&archive_date_to=${encodeURIComponent(archiveDateTo)}`;
        }
        
        const response = await apiRequest(url);
        let allData = response.results || response;
        
        // Применяем локальную фильтрацию
        let filteredData = allData;
        
        // Фильтрация по статусу
        if (status) {
            filteredData = filteredData.filter(animal => 
                animal.status && animal.status === status
            );
        }
        
        // Фильтрация по поиску (case-insensitive)
        if (search && search.trim()) {
            const searchLower = search.toLowerCase();
            filteredData = filteredData.filter(animal => 
                animal.tag_number && animal.tag_number.toLowerCase().includes(searchLower)
            );
        }
        
        // Применяем пагинацию к отфильтрованным данным
        const startIndex = (currentPage - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        const paginatedData = filteredData.slice(startIndex, endIndex);
        
        displayArchive(paginatedData, startIndex);
        updateLocalArchivePagination(filteredData.length, currentPage, animalType, status, search);
    } catch (error) {
        console.error('Ошибка при фильтрации архива:', error);
        // Fallback к локальной фильтрации существующих данных
        let filteredData = allArchiveData || [];
        
        if (animalType) {
            filteredData = filteredData.filter(animal => animal.animal_type === animalType);
        }
        if (status) {
            filteredData = filteredData.filter(animal => 
                animal.status && animal.status === status
            );
        }
        if (search) {
            const searchLower = search.toLowerCase();
            filteredData = filteredData.filter(animal => 
                animal.tag_number && animal.tag_number.toLowerCase().includes(searchLower)
            );
        }
        
        displayArchive(filteredData);
    }
}

// Функция обновления пагинации для локальной фильтрации
function updateSimpleArchivePagination(totalItems, searchQuery = '', animalType = '') {
    const paginationContainer = document.getElementById('pagination');
    if (!paginationContainer) return;

    // Определяем название животного для отображения
    let animalName = 'животных';
    if (animalType === 'Maker') animalName = 'производителей';
    else if (animalType === 'Sheep') animalName = 'овец';
    else if (animalType === 'Ewe') animalName = 'ярок';
    else if (animalType === 'Ram') animalName = 'баранов';

    // Для неограниченного списка показываем только информацию о количестве
    paginationContainer.innerHTML = `
        <div class="pagination-info">
            <span>Показано: ${totalItems} ${animalName} в архиве</span>
            ${searchQuery ? `<span class="search-info">Поиск: "${searchQuery}"</span>` : ''}
            ${animalType ? `<span class="filter-info">Тип: ${animalType}</span>` : ''}
        </div>
    `;
}

// Функция обновления пагинации для API с пагинацией
function updateArchivePagination(response) {
    const pagination = document.getElementById('pagination');
    if (!pagination) return;
    
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
            fetchArchive(currentPage - 1);
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
    pageInfo.innerText = `Страница ${currentPage} (всего: ${response.count})`;
    pageInfo.style.fontWeight = '500';
    pageInfo.style.minWidth = '200px';
    pageInfo.style.textAlign = 'center';
    paginationContainer.appendChild(pageInfo);

    // Кнопка "Следующая" (справа)
    if (response.next) {
        const nextButton = document.createElement('button');
        nextButton.innerText = 'Следующая';
        nextButton.className = 'btn btn-outline-primary btn-sm';
        nextButton.onclick = () => {
            fetchArchive(currentPage + 1);
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

function updateLocalArchivePagination(totalItems, currentPage, animalType = '', status = '', search = '') {
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
            fetchArchiveWithFilters(currentPage - 1, animalType, status, search);
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
            fetchArchiveWithFilters(currentPage + 1, animalType, status, search);
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

// Функция для загрузки архива с фильтрами (для пагинации)
async function fetchArchiveWithFilters(page, animalType, status, search) {
    try {
        // Всегда загружаем больше данных для корректной фильтрации
        let url = `/animals/archive/?page=1&page_size=500`;
        
        if (animalType) {
            url += `&type=${encodeURIComponent(animalType)}`;
        }
        
        // Добавляем даты архивирования если указаны
        const archiveDateFrom = document.getElementById('archive-date-from').value;
        const archiveDateTo = document.getElementById('archive-date-to').value;
        
        if (archiveDateFrom) {
            url += `&archive_date_from=${encodeURIComponent(archiveDateFrom)}`;
        }
        if (archiveDateTo) {
            url += `&archive_date_to=${encodeURIComponent(archiveDateTo)}`;
        }
        
        const response = await apiRequest(url);
        let allData = response.results || response;
        
        // Применяем локальную фильтрацию
        let filteredData = allData;
        
        // Фильтрация по статусу
        if (status) {
            filteredData = filteredData.filter(animal => 
                animal.status && animal.status === status
            );
        }
        
        // Фильтрация по поиску (case-insensitive)
        if (search && search.trim()) {
            const searchLower = search.toLowerCase();
            filteredData = filteredData.filter(animal => 
                animal.tag_number && animal.tag_number.toLowerCase().includes(searchLower)
            );
        }
        
        // Применяем пагинацию к отфильтрованным данным
        const startIndex = (page - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        const paginatedData = filteredData.slice(startIndex, endIndex);
        
        currentPage = page;
        displayArchive(paginatedData, startIndex);
        updateLocalArchivePagination(filteredData.length, page, animalType, status, search);
    } catch (error) {
        console.error('Ошибка при загрузке архива с фильтрами:', error);
    }
}

// Функция обновления пагинации
function updatePagination(response) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = ''; // Очищаем старую навигацию

    if (response.previous) {
        const prevButton = document.createElement('button');
        prevButton.className = 'btn btn-outline-primary btn-sm';
        prevButton.innerText = 'Предыдущая';
        prevButton.onclick = () => {
            currentPage--;
            fetchArchive(currentPage);
        };
        pagination.appendChild(prevButton);
    }

    const pageInfo = document.createElement('span');
    pageInfo.className = 'mx-2';
    pageInfo.innerText = `Страница ${currentPage}`;
    pagination.appendChild(pageInfo);

    if (response.next) {
        const nextButton = document.createElement('button');
        nextButton.className = 'btn btn-outline-primary btn-sm';
        nextButton.innerText = 'Следующая';
        nextButton.onclick = () => {
            currentPage++;
            fetchArchive(currentPage);
        };
        pagination.appendChild(nextButton);
    }
}

// Экспортируем функции для использования в HTML
window.filterArchiveData = filterArchiveData;
window.restoreAnimal = restoreAnimal;
window.closeRestoreModal = closeRestoreModal;
window.performArchiveSearch = performArchiveSearch;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Восстанавливаем параметры из URL
    const urlParams = new URLSearchParams(window.location.search);
    const searchQuery = urlParams.get('search');
    const animalType = urlParams.get('type');
    const archiveDateFrom = urlParams.get('archive_date_from');
    const archiveDateTo = urlParams.get('archive_date_to');
    
    if (searchQuery) {
        const searchInput = document.getElementById('archive-search');
        if (searchInput) {
            searchInput.value = searchQuery;
        }
    }
    
    if (animalType) {
        const typeFilter = document.getElementById('animal-type-filter');
        if (typeFilter) {
            typeFilter.value = animalType;
        }
        // Устанавливаем глобальную переменную для совместимости
        window.initialAnimalType = animalType;
    }
    
    if (archiveDateFrom) {
        const dateFromInput = document.getElementById('archive-date-from');
        if (dateFromInput) {
            dateFromInput.value = archiveDateFrom;
        }
    }
    
    if (archiveDateTo) {
        const dateToInput = document.getElementById('archive-date-to');
        if (dateToInput) {
            dateToInput.value = archiveDateTo;
        }
    }
    
    fetchArchive(1);
});
