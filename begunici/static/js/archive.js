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
    
    fetchArchive();  // Загружаем архив при загрузке страницы
});

// Функция загрузки архива
async function fetchArchive(page = 1) {
    try {
        currentPage = page;
        
        // Получаем начальный тип животного из URL или глобальной переменной
        const initialType = window.initialAnimalType || '';
        let url = `/animals/archive/?page=${page}&page_size=${pageSize}`;
        
        // Добавляем параметр type если он есть
        if (initialType) {
            url += `&type=${encodeURIComponent(initialType)}`;
        }
        
        const response = await apiRequest(url);
        allArchiveData = response.results || response;
        displayArchive(allArchiveData);
        updatePagination(response);
    } catch (error) {
        console.error('Ошибка при загрузке архива:', error);
    }
}

// Функция отображения архива
function displayArchive(data) {
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
        const age = animal.age ? `${animal.age} мес.` : 'Не указан';
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
        
        row.innerHTML = `
            <td>${(currentPage - 1) * pageSize + index + 1}</td>
            <td>${animalType}</td>
            <td><a href="${detailUrl}">${tagNumber}</a></td>
            <td style="background-color:${statusColor}">${status}</td>
            <td>${archivedDate}</td>
            <td>${age}</td>
            <td>${place}</td>
            <td>${actionsHtml}</td>
        `;
        archiveTable.appendChild(row);
    });
}

// Функция фильтрации архива
async function filterArchiveData(animalType, status, search) {
    try {
        currentPage = 1; // Сбрасываем на первую страницу при фильтрации
        
        // Строим URL с параметрами фильтрации
        let url = `/animals/archive/?page=${currentPage}&page_size=${pageSize}`;
        
        if (animalType) {
            url += `&type=${encodeURIComponent(animalType)}`;
        }
        if (search) {
            url += `&search=${encodeURIComponent(search)}`;
        }
        
        // Делаем новый запрос с фильтрами
        const response = await apiRequest(url);
        allArchiveData = response.results || response;
        
        // Дополнительная фильтрация по статусу (если API не поддерживает)
        let filteredData = allArchiveData;
        if (status) {
            filteredData = filteredData.filter(animal => 
                animal.status && animal.status === status
            );
        }
        
        displayArchive(filteredData);
        updatePagination(response);
    } catch (error) {
        console.error('Ошибка при фильтрации архива:', error);
        // Fallback к локальной фильтрации
        let filteredData = allArchiveData;
        
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
        const statuses = await apiRequest('/veterinary/api/status/');
        // Исключаем архивные статусы
        const activeStatuses = statuses.filter(status => 
            !['Убыл', 'Убой', 'Продажа'].includes(status.status_type)
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

// Функция обновления пагинации
function updatePagination(response) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = ''; // Очищаем старую навигацию

    if (response.previous) {
        const prevButton = document.createElement('button');
        prevButton.className = 'btn btn-outline-secondary';
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
        nextButton.className = 'btn btn-outline-secondary';
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
