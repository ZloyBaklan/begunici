import { apiRequest, formatDateToOutput, formatDateToInput } from "./utils.js";

// Переменные для пагинации
let currentPage = 1;
const pageSize = 10;

// Получаем права пользователя из глобальной переменной
function getUserPermissions() {
    return window.userPermissions || {
        can_delete_vet_data: true
    };
}

document.addEventListener('DOMContentLoaded', function () {
    fetchStatuses();  // Загружаем список статусов при загрузке страницы

    const createStatusButton = document.querySelector('#create-status-button');
    if (createStatusButton) {
        createStatusButton.onclick = handleCreateOrUpdateStatus;
    }

    // Добавляем обработчик для мгновенного поиска
    const searchInput = document.getElementById('status-search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const query = this.value;
            currentPage = 1; // Сбрасываем на первую страницу при поиске
            fetchStatuses(1, query);
        });
    }
});

// Функция, которая переключается между созданием и обновлением
function handleCreateOrUpdateStatus() {
    const createStatusButton = document.getElementById('create-status-button');
    const statusId = createStatusButton.getAttribute('data-id');
    if (statusId) {
        updateStatus(statusId);  // Если есть data-id, выполняем обновление
    } else {
        createStatus();  // Иначе создаем новый статус
    }
}

// Функция отмены редактирования
function cancelEdit() {
    document.getElementById('create-status-form').reset();
    document.getElementById('status-color').value = '#FFFFFF'; // Сброс цвета по умолчанию
    resetButton();
    document.getElementById('form-title').textContent = 'Создать статус';
    document.getElementById('cancel-edit-button').style.display = 'none';
}
window.cancelEdit = cancelEdit; // Делаем функцию глобальной

/// Функция создания нового статуса
async function createStatus() {
    const statusType = document.getElementById('status-type').value;
    const statusDate = document.getElementById('status-date').value;
    const statusColor = document.getElementById('status-color').value;

    if (!statusType.trim()) {
        showMessage('Пожалуйста, введите название статуса', 'warning');
        return;
    }

    const data = {
        status_type: statusType,
        date_of_status: statusDate || null, // Отправляем как есть из input[type="date"]
        color: statusColor
    };

    console.log('Creating status with data:', data);

    try {
        await apiRequest('/veterinary/api/status/', 'POST', data);
        showMessage('Статус успешно создан', 'success');
        document.getElementById('create-status-form').reset();
        document.getElementById('status-color').value = '#FFFFFF'; // Сброс цвета
        fetchStatuses(currentPage); // Обновляем текущую страницу
        resetButton();
    } catch (error) {
        console.error('Ошибка создания статуса:', error);
        showMessage(`Ошибка: ${error.message}`, 'danger');
    }
}

// Функция загрузки списка статусов
async function fetchStatuses(page = 1, searchQuery = '') {
    try {
        console.log('Fetching statuses...');
        let url = `/veterinary/api/status/?page=${page}&page_size=${pageSize}`;
        if (searchQuery) {
            url += `&search=${encodeURIComponent(searchQuery)}`;
        }
        const response = await apiRequest(url);
        console.log('Statuses response:', response);
        
        // Обрабатываем пагинированный ответ
        const statuses = Array.isArray(response) ? response : response.results;
        currentPage = page;
        
        const statusTable = document.getElementById('status-list');
        statusTable.innerHTML = '';

        if (statuses && statuses.length > 0) {
            statuses.forEach((status, index) => {
                const row = document.createElement('tr');
                
                // Создаем кнопки действий с проверкой прав
                const permissions = getUserPermissions();
                let actionsHtml = `
                    <div class="btn-group btn-group-sm" role="group">
                        <button class="btn btn-outline-primary edit-status-btn" data-id="${status.id}">
                            Редактировать
                        </button>`;
                
                if (permissions.can_delete_vet_data) {
                    actionsHtml += `
                        <button class="btn btn-outline-danger delete-status-btn" data-id="${status.id}">
                            Удалить
                        </button>`;
                }
                
                actionsHtml += `</div>`;
                
                // Вычисляем номер записи с учетом пагинации
                const recordNumber = (page - 1) * pageSize + index + 1;
                
                row.innerHTML = `
                    <td>${recordNumber}</td>
                    <td>${status.status_type}</td>
                    <td>${formatDateToOutput(status.date_of_status) || 'Нет даты'}</td>
                    <td>
                        <div style="width: 30px; height: 20px; background-color: ${status.color}; border: 1px solid #ccc; border-radius: 3px;"></div>
                    </td>
                    <td>${actionsHtml}</td>
                `;
                
                // Добавляем обработчики событий
                row.querySelector('.edit-status-btn').addEventListener('click', () => editStatus(status.id));
                
                const deleteBtn = row.querySelector('.delete-status-btn');
                if (deleteBtn) {
                    deleteBtn.addEventListener('click', () => deleteStatus(status.id));
                }
                
                statusTable.appendChild(row);
            });
        } else {
            statusTable.innerHTML = '<tr><td colspan="5" class="text-center">Статусы не найдены</td></tr>';
        }
        
        // Обновляем пагинацию
        if (!Array.isArray(response)) {
            updatePagination(response);
        }
    } catch (error) {
        console.error('Ошибка при загрузке статусов:', error);
        const statusTable = document.getElementById('status-list');
        statusTable.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Ошибка загрузки данных</td></tr>';
    }
}


async function editStatus(statusId) {
    try {
        const status = await apiRequest(`/veterinary/api/status/${statusId}/`);

        // Заполняем поля формы данными статуса для редактирования
        document.getElementById('status-type').value = status.status_type;
        document.getElementById('status-date').value = formatDateToInput(status.date_of_status);
        document.getElementById('status-color').value = status.color || '#FFFFFF';

        // Меняем текст кнопки на "Сохранить изменения" и привязываем действие
        const createStatusButton = document.getElementById('create-status-button');
        createStatusButton.innerText = 'Сохранить изменения';
        createStatusButton.setAttribute('data-id', statusId);
        
        document.getElementById('form-title').textContent = 'Редактировать статус';
        document.getElementById('cancel-edit-button').style.display = 'block';
    } catch (error) {
        console.error('Ошибка при редактировании статуса:', error);
        showMessage('Произошла ошибка при попытке редактирования статуса.', 'danger');
    }
}

// Функция удаления статуса
async function deleteStatus(statusId) {
    const confirmDelete = confirm('Вы уверены, что хотите удалить статус?')
    if (!confirmDelete) return;

    try {
        await apiRequest(`/veterinary/api/status/${statusId}/`, 'DELETE');
        showMessage('Статус успешно удален', 'success');
        fetchStatuses(currentPage); // Обновляем текущую страницу
    } catch (error) {
        console.error('Ошибка при удалении статуса:', error);
        showMessage('Ошибка при удалении статуса', 'danger');
    }
}




// Функция для обновления статуса
async function updateStatus(statusId) {
    const statusDate = document.getElementById('status-date').value;
    
    const data = {
        status_type: document.getElementById('status-type').value,
        date_of_status: statusDate || null, // Отправляем как есть из input[type="date"]
        color: document.getElementById('status-color').value
    };
    
    console.log('Отправляемые данные:', data); // Логируем данные
    try {
        await apiRequest(`/veterinary/api/status/${statusId}/`, 'PUT', data);
        showMessage('Статус успешно обновлен', 'success');
        
        fetchStatuses(currentPage); // Обновляем текущую страницу
        resetButton();
        cancelEdit();
        
    } catch (error) {
        console.error('Ошибка при обновлении статуса:', error);
        showMessage(`Ошибка: ${error.message}`, 'danger');
    }
}

// Функция для поиска статусов
function searchStatuses(query = null) {
    if (query === null) {
        query = document.getElementById('status-search').value;
    }
    currentPage = 1; // Сбрасываем на первую страницу при поиске
    fetchStatuses(1, query);
}
window.searchStatuses = searchStatuses; // Делаем функцию глобальной

// Функция обновления пагинации
function updatePagination(response) {
    const pagination = document.getElementById('pagination');
    if (!pagination) {
        // Создаем элемент пагинации если его нет
        const paginationDiv = document.createElement('div');
        paginationDiv.id = 'pagination';
        paginationDiv.className = 'mt-3 d-flex justify-content-between align-items-center';
        document.querySelector('.card-body').appendChild(paginationDiv);
    }
    
    const paginationElement = document.getElementById('pagination');
    paginationElement.innerHTML = '';

    // Левая часть - кнопка "Предыдущая"
    const leftContainer = document.createElement('div');
    if (response.previous) {
        const prevButton = document.createElement('button');
        prevButton.className = 'btn btn-outline-primary btn-sm';
        prevButton.innerText = 'Предыдущая';
        prevButton.onclick = () => {
            currentPage--;
            const searchQuery = document.getElementById('status-search').value;
            fetchStatuses(currentPage, searchQuery);
        };
        leftContainer.appendChild(prevButton);
    }

    // Центральная часть - номер страницы
    const pageInfo = document.createElement('span');
    pageInfo.className = 'text-muted';
    pageInfo.innerText = `Страница ${currentPage}`;

    // Правая часть - кнопка "Следующая"
    const rightContainer = document.createElement('div');
    if (response.next) {
        const nextButton = document.createElement('button');
        nextButton.className = 'btn btn-outline-primary btn-sm';
        nextButton.innerText = 'Следующая';
        nextButton.onclick = () => {
            currentPage++;
            const searchQuery = document.getElementById('status-search').value;
            fetchStatuses(currentPage, searchQuery);
        };
        rightContainer.appendChild(nextButton);
    }
    
    paginationElement.appendChild(leftContainer);
    paginationElement.appendChild(pageInfo);
    paginationElement.appendChild(rightContainer);
}

// Функция для сброса кнопки в режим создания
function resetButton() {
    const createStatusButton = document.getElementById('create-status-button');
    createStatusButton.innerText = 'Создать статус';
    createStatusButton.removeAttribute('data-id');
    createStatusButton.onclick = handleCreateOrUpdateStatus;  // Назначаем обработчик для создания/обновления
}

// Функция для отображения сообщений
function showMessage(message, type) {
    const messageDiv = document.getElementById('status-message');
    messageDiv.className = `alert alert-${type}`;
    messageDiv.textContent = message;
    messageDiv.style.display = 'block';
    
    // Автоматически скрываем сообщение через 5 секунд
    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 5000);
}

// Делаем функцию глобальной для использования в HTML
window.handleCreateOrUpdateStatus = handleCreateOrUpdateStatus;

