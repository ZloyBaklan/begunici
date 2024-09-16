// Получение CSRF-токена для запросов
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


document.addEventListener('DOMContentLoaded', function () {
    fetchStatuses();  // Загружаем список статусов при загрузке страницы

    // Проверяем наличие формы статуса и привязываем кнопку создания к функции создания статуса
    const createStatusButton = document.querySelector('#create-status-button');
    if (createStatusButton) {
        // Назначаем событие для создания/обновления статуса
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

// Функция создания нового статуса
// Создание нового статуса
// Функция создания статуса через API
async function createStatus() {
    const statusType = document.getElementById('status-type').value;
    const statusDate = document.getElementById('status-date').value;
    const statusColor = document.getElementById('status-color').value;

    const data = {
        status_type: statusType,
        date_of_status: statusDate || null,  // Если дата не указана, оставляем null
        color: statusColor
    };

    try {
        const response = await fetch('/veterinary/status/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),  // Добавляем CSRF токен
            },
            body: JSON.stringify(data),
        });

        const result = await response.json();
        console.log('Ответ от сервера:', result);  // Выводим ответ сервера в консоль для дебага

        if (response.ok) {
            alert('Статус успешно создан');
            document.getElementById('create-status-form').reset();  // Очистка формы
            fetchStatuses();  // Обновляем список статусов
            resetButton();  // Сбрасываем состояние кнопки на "Создать"
        } else {
            alert('Ошибка создания статуса: ' + result.detail);
        }
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Произошла ошибка при создании статуса');
    }
}


async function fetchStatuses() {
    try {
        // Запрашиваем список статусов с API
        const response = await fetch('/veterinary/status/');
        if (!response.ok) {
            throw new Error('Ошибка при загрузке статусов');
        }
        const statuses = await response.json();
        
        // Выводим статусы в таблицу
        const statusTable = document.getElementById('status-list');
        statusTable.innerHTML = '';  // Очищаем старую таблицу

        statuses.forEach((status, index) => {
            // Создаем строку для каждого статуса
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
            // Добавляем строку в таблицу
            statusTable.innerHTML += row;
        });
    } catch (error) {
        console.error('Ошибка при загрузке статусов:', error);
    }
}




// Функция удаления статуса
async function deleteStatus(statusId) {
    const csrfToken = getCSRFToken();
    try {
        const response = await fetch(`/veterinary/status/${statusId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': csrfToken,
            }
        });

        if (response.ok) {
            alert('Статус успешно удален');
            fetchStatuses();  // Обновляем список статусов
        } else {
            alert('Ошибка при удалении статуса');
        }
    } catch (error) {
        console.error('Ошибка при удалении статуса:', error);
    }
}


// Функция для редактирования статуса
async function editStatus(statusId) {
    try {
        // Загружаем данные статуса для редактирования
        const response = await fetch(`/veterinary/status/${statusId}/`);
        if (!response.ok) {
            throw new Error('Ошибка при получении данных статуса');
        }
        const status = await response.json();

        // Заполняем форму редактирования данными статуса
        document.getElementById('status-type').value = status.status_type;
        document.getElementById('status-date').value = status.date_of_status || '';
        document.getElementById('status-color').value = status.color || '#FFFFFF';

        const createStatusButton = document.getElementById('create-status-button');
        createStatusButton.innerText = 'Сохранить изменения';
        createStatusButton.setAttribute('data-id', statusId);

    } catch (error) {
        console.error('Ошибка при редактировании статуса:', error);
    }
}

// Функция для обновления статуса
async function updateStatus(statusId) {
    const statusType = document.getElementById('status-type').value;
    const statusDate = document.getElementById('status-date').value;
    const statusColor = document.getElementById('status-color').value;

    const data = {
        status_type: statusType,
        date_of_status: statusDate ? statusDate : null,
        color: statusColor
    };

    try {
        const response = await fetch(`/veterinary/status/${statusId}/`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify(data),
        });

        if (response.ok) {
            alert('Статус успешно обновлен');
            fetchStatuses();  // Обновляем список статусов
            resetButton();  // Сбрасываем состояние кнопки на "Создать"
        } else {
            const errorData = await response.json();
            alert('Ошибка обновления статуса: ' + errorData.detail);
        }
    } catch (error) {
        console.error('Ошибка при обновлении статуса:', error);
        alert('Произошла ошибка при обновлении статуса');
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
