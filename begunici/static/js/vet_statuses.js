import { apiRequest } from "./utils.js";

document.addEventListener('DOMContentLoaded', function () {
    fetchStatuses();  // Загружаем список статусов при загрузке страницы

    const createStatusButton = document.querySelector('#create-status-button');
    if (createStatusButton) {
        createStatusButton.onclick = handleCreateOrUpdateStatus;
    }
});

// Функция, которая переключается между созданием и обновлением
function handleCreateOrUpdateStatus() {
    const statusId = this.getAttribute('data-id');
    if (statusId) {
        updateStatus(statusId);  // Если есть data-id, выполняем обновление
    } else {
        createStatus();  // Иначе создаем новый статус
    }
}

/// Функция создания нового статуса
async function createStatus() {
    const statusType = document.getElementById('status-type').value;
    const statusDate = document.getElementById('status-date').value;
    const statusColor = document.getElementById('status-color').value;

    if (!statusType.trim()) {
        alert('Пожалуйста, введите название статуса');
        return;
    }

    const data = {
        status_type: statusType,
        date_of_status: statusDate || null,
        color: statusColor
    };

    console.log('Creating status with data:', data);

    try {
                await apiRequest('/veterinary/api/status/', 'POST', data);
        alert('Статус успешно создан');
        document.getElementById('create-status-form').reset();
        fetchStatuses();
        resetButton();
    } catch (error) {
        console.error('Ошибка создания статуса:', error);
        alert(`Ошибка: ${error.message}`);
    }
}

// Функция загрузки списка статусов
async function fetchStatuses(searchQuery = '') {
    try {
        console.log('Fetching statuses...');
        let url = '/veterinary/api/status/';
        if (searchQuery) {
            url += `?search=${searchQuery}`;
        }
        const statuses = await apiRequest(url);
        console.log('Statuses data:', statuses);
        
        const statusTable = document.getElementById('status-list');
        statusTable.innerHTML = '';

        statuses.forEach((status, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${status.status_type}</td>
                <td>${status.date_of_status || 'Нет даты'}</td>
                <td><input type="color" value="${status.color}" disabled></td>
                <td>
                    <button class="edit-status-btn" data-id="${status.id}">
                        Редактировать
                    </button>
                    <button class="delete-status-btn" data-id="${status.id}">
                        Удалить
                    </button>
                </td>
            `;
            
            // Добавляем обработчики событий
            row.querySelector('.edit-status-btn').addEventListener('click', () => editStatus(status.id));
            row.querySelector('.delete-status-btn').addEventListener('click', () => deleteStatus(status.id));
            
            statusTable.appendChild(row);
        });
    } catch (error) {
        console.error('Ошибка при загрузке статусов:', error);
    }
}


async function editStatus(statusId) {
    try {
                const status = await apiRequest(`/veterinary/api/status/${statusId}/`);

        // Заполняем поля формы данными статуса для редактирования
        document.getElementById('status-type').value = status.status_type;
        document.getElementById('status-date').value = status.date_of_status || '';
        document.getElementById('status-color').value = status.color || '#FFFFFF';

        // Меняем текст кнопки на "Сохранить изменения" и привязываем действие
        const createStatusButton = document.getElementById('create-status-button');
        createStatusButton.innerText = 'Сохранить изменения';
        createStatusButton.setAttribute('data-id', statusId);
        createStatusButton.onclick = () => updateStatus(statusId); // Привязываем функцию обновления
    } catch (error) {
        console.error('Ошибка при редактировании статуса:', error);
        alert('Произошла ошибка при попытке редактирования статуса.');
    }
}

// Функция удаления статуса
async function deleteStatus(statusId) {
    const confirmDelete = confirm('Вы уверены, что хотите удалить статус?')
    if (!confirmDelete) return;

    try {
                await apiRequest(`/veterinary/api/status/${statusId}/`, 'DELETE');
        alert('Статус успешно удален');
        fetchStatuses();
    } catch (error) {
        console.error('Ошибка при удалении статуса:', error);
        alert('Ошибка при удалении статуса');
    }
}




// Функция для обновления статуса
async function updateStatus(statusId) {
    const data = {
        status_type: document.getElementById('status-type').value,
        date_of_status: document.getElementById('status-date').value || null,
        color: document.getElementById('status-color').value
    };
    console.log('Отправляемые данные:', data); // Логируем данные
    try {
                await apiRequest(`/veterinary/api/status/${statusId}/`, 'PUT', data);
        alert('Статус успешно обновлен');
        
        fetchStatuses();
        resetButton();
        document.getElementById('create-status-form').reset();
        
    } catch (error) {
        console.error('Ошибка при обновлении статуса:', error);
        alert(`Ошибка: ${error.message}`);
    }
}

// Функция для поиска статусов
function searchStatuses() {
    const query = document.getElementById('status-search').value;
    fetchStatuses(query);
}
window.searchStatuses = searchStatuses; // Делаем функцию глобальной

// Функция для сброса кнопки в режим создания
function resetButton() {
    const createStatusButton = document.getElementById('create-status-button');
    createStatusButton.innerText = 'Создать статус';
    createStatusButton.removeAttribute('data-id');
    createStatusButton.onclick = handleCreateOrUpdateStatus;  // Назначаем обработчик для создания/обновления
}

// not working
function clearForm() {
    document.getElementById('status-type').value = '';
    document.getElementById('status-date').value = '';
    document.getElementById('status-color').value = '#FFFFFF'; // Устанавливаем цвет по умолчанию (например, белый)
}

