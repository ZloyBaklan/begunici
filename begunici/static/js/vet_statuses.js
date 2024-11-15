// Функция для получения CSRF-токена из cookies
function getCSRFToken() {
    let cookieValue = null;
    const name = 'csrftoken';
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

// Функция для выполнения API-запросов
async function apiRequest(url, method = 'GET', body = null) {
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken(),
    };
    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            const errorData = await response.json();
            console.error(`Ошибка API [${response.status}]:`, errorData);
            throw new Error(errorData.detail || 'Ошибка API');
        }
        return await response.json();
    } catch (error) {
        console.error('Ошибка сети:', error);
        throw error; // Пробрасываем ошибку для обработки в вызывающем коде
    }
}


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
    const data = {
        status_type: document.getElementById('status-type').value,
        date_of_status: document.getElementById('status-date').value || null,
        color: document.getElementById('status-color').value
    };

    try {
        await apiRequest('/veterinary/status/', 'POST', data);
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
async function fetchStatuses() {
    try {
        const statuses = await apiRequest('/veterinary/status/');
        const statusTable = document.getElementById('status-list');
        statusTable.innerHTML = '';

        statuses.forEach((status, index) => {
            const row = `<tr>
                <td>${index + 1}</td>
                <td>${status.status_type}</td>
                <td>${status.date_of_status || 'Нет даты'}</td>
                <td><input type="color" value="${status.color}" disabled></td>
                <td>
                    <button onclick="editStatus(${status.id})">Редактировать</button>
                    <button onclick="deleteStatus(${status.id})">Удалить</button>
                </td>
            </tr>`;
            statusTable.innerHTML += row;
        });
    } catch (error) {
        console.error('Ошибка при загрузке статусов:', error);
    }
}


async function editStatus(statusId) {
    try {
        const status = await apiRequest(`/veterinary/status/${statusId}/`);

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
    if (!confirm('Вы уверены, что хотите удалить статус?')) return;

    try {
        await apiRequest(`/veterinary/status/${statusId}/`, 'DELETE');
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
        await apiRequest(`/veterinary/status/${statusId}/`, 'PUT', data);
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
    const input = document.getElementById('status-search').value.toLowerCase();
    const table = document.getElementById('status-list');
    const rows = table.getElementsByTagName('tr');

    for (let i = 0; i < rows.length; i++) {
        const cells = rows[i].getElementsByTagName('td');
        if (cells.length > 0) {
            const statusName = cells[1].innerText.toLowerCase();
            if (statusName.indexOf(input) > -1) {
                rows[i].style.display = '';
            } else {
                rows[i].style.display = 'none';
            }
        }
    }
}

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

