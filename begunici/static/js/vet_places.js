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
    fetchPlaces();  // Загружаем список овчарен при загрузке страницы
    
    const createPlaceButton = document.querySelector('#add-place-button');
    if (createPlaceButton) {
        // Назначаем событие для создания/обновления овчарни
        createPlaceButton.onclick = handleCreateOrUpdatePlace;
    }
});

// Функция, которая переключается между созданием и обновлением
function handleCreateOrUpdatePlace() {
    const placeId = this.getAttribute('data-id');
    if (placeId) {
        updatePlace(placeId);  // Если есть data-id, выполняем обновление
    } else {
        createPlace();  // Иначе создаем новую овчарню
    }
}

// Функция создания овчарни через API
async function createPlace() {
    const placeSheepfold = document.getElementById('place-sheepfold').value;
    const placeCompartment = document.getElementById('place-compartment').value;
    const dateOfTransfer = document.getElementById('place-date').value;

    const data = {
        sheepfold: placeSheepfold,
        compartment: placeCompartment,
        date_of_transfer: dateOfTransfer || null
    };

    try {
        const response = await fetch('/veterinary/place/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify(data),
        });

        const result = await response.json();
        console.log('Ответ от сервера:', result);

        if (response.ok) {
            alert('Овчарня успешно создана');
            document.getElementById('create-place-form').reset();  // Очистка формы
            fetchPlaces();  // Обновляем список овчарен
            resetButton();  // Сбрасываем состояние кнопки на "Создать"
        } else {
            alert('Ошибка создания овчарни: ' + result.detail);
        }
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Произошла ошибка при создании овчарни');
    }
}

// Функция для загрузки списка овчарен
async function fetchPlaces() {
    try {
        const response = await fetch('/veterinary/place/');
        if (!response.ok) {
            throw new Error('Ошибка при загрузке овчарен');
        }
        const places = await response.json();

        const placeTable = document.getElementById('place-list');
        placeTable.innerHTML = '';  // Очищаем старый список

        places.forEach((place, index) => {
            const row = `<tr>
                <td>${index + 1}</td>
                <td>${place.sheepfold}</td>
                <td>${place.compartment}</td>
                <td>${place.date_of_transfer || 'Нет даты'}</td>
                <td>
                    <button onclick="editPlace(${place.id})">Редактировать</button>
                    <button onclick="deletePlace(${place.id})">Удалить</button>
                </td>
            </tr>`;
            placeTable.innerHTML += row;
        });
    } catch (error) {
        console.error('Ошибка при загрузке овчарен:', error);
    }
}

// Функция удаления овчарни
async function deletePlace(placeId) {
    const csrfToken = getCSRFToken();
    try {
        const response = await fetch(`/veterinary/place/${placeId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': csrfToken,
            }
        });

        if (response.ok) {
            alert('Овчарня успешно удалена');
            fetchPlaces();  // Обновляем список овчарен
        } else {
            alert('Ошибка при удалении овчарни');
        }
    } catch (error) {
        console.error('Ошибка при удалении овчарни:', error);
    }
}

// Функция для редактирования овчарни
async function editPlace(placeId) {
    try {
        // Загружаем данные овчарни для редактирования
        const response = await fetch(`/veterinary/place/${placeId}/`);
        if (!response.ok) {
            throw new Error('Ошибка при получении данных овчарни');
        }
        const place = await response.json();

        // Заполняем форму редактирования данными овчарни
        document.getElementById('place-sheepfold').value = place.sheepfold;
        document.getElementById('place-compartment').value = place.compartment;
        document.getElementById('place-date').value = place.date_of_transfer || '';

        const createPlaceButton = document.getElementById('add-place-button');
        createPlaceButton.innerText = 'Сохранить изменения';
        createPlaceButton.setAttribute('data-id', placeId);
    } catch (error) {
        console.error('Ошибка при редактировании овчарни:', error);
    }
}

// Функция для обновления овчарни
async function updatePlace(placeId) {
    const placeSheepfold = document.getElementById('place-sheepfold').value;
    const placeCompartment = document.getElementById('place-compartment').value;
    const dateOfTransfer = document.getElementById('place-date').value;

    const data = {
        sheepfold: placeSheepfold,
        compartment: placeCompartment,
        date_of_transfer: dateOfTransfer ? dateOfTransfer : null
    };

    try {
        const response = await fetch(`/veterinary/place/${placeId}/`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify(data),
        });

        if (response.ok) {
            alert('Овчарня успешно обновлена');
            resetButton();  // Сбрасываем состояние кнопки на "Создать"
            fetchPlaces();  // Обновляем список овчарен
            
        } else {
            const errorData = await response.json();
            alert('Ошибка обновления овчарни: ' + errorData.detail);
        }
    } catch (error) {
        console.error('Ошибка при обновлении овчарни:', error);
        alert('Произошла ошибка при обновлении овчарни');
    }
}

// Функция для поиска овчарен
function searchPlaces() {
    const input = document.getElementById('place-search').value.toLowerCase();
    const table = document.getElementById('place-list');
    const rows = table.getElementsByTagName('tr');

    for (let i = 0; i < rows.length; i++) {
        const cells = rows[i].getElementsByTagName('td');
        if (cells.length > 0) {
            const sheepfoldName = cells[1].innerText.toLowerCase();
            const compartmentName = cells[2].innerText.toLowerCase();
            if (sheepfoldName.indexOf(input) > -1 || compartmentName.indexOf(input) > -1) {
                rows[i].style.display = '';
            } else {
                rows[i].style.display = 'none';
            }
        }
    }
}

// Функция для сброса кнопки в режим создания
function resetButton() {
    const createPlaceButton = document.getElementById('add-place-button');
    createPlaceButton.innerText = 'Создать овчарню';
    createPlaceButton.removeAttribute('data-id');
    createPlaceButton.onclick =  handleCreateOrUpdatePlace;  // Назначаем обработчик для создания/обновления
}