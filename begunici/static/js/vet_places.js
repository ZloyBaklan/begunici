import { apiRequest, formatDateToOutput } from "./utils.js";

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
    const dateOfTransfer = document.getElementById('place-date').value;

    if (!placeSheepfold.trim()) {
        alert('Пожалуйста, введите название овчарни');
        return;
    }

    const data = {
        sheepfold: placeSheepfold,
        date_of_transfer: dateOfTransfer || null
    };

    console.log('Creating place with data:', data);

        try {
        await apiRequest('/veterinary/api/place/', 'POST', data);
        alert('Овчарня успешно создана');
        document.getElementById('create-place-form').reset();  // Очистка формы
        fetchPlaces();  // Обновляем список овчарен
        resetButton();  // Сбрасываем состояние кнопки на "Создать"
    } catch (error) {
        console.error('Ошибка:', error);
        alert(`Произошла ошибка при создании овчарни: ${error.message}`);
    }
}

// Функция для загрузки списка овчарен
async function fetchPlaces(searchQuery = '') {
    try {
        console.log('Fetching places...');
        let url = '/veterinary/api/place/';
        if (searchQuery) {
            url += `?search=${searchQuery}`;
        }
        const places = await apiRequest(url);
        console.log('Places data:', places);

        const placeTable = document.getElementById('place-list');
        placeTable.innerHTML = '';  // Очищаем старый список

        places.forEach((place, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${place.sheepfold}</td>
                <td>${formatDateToOutput(place.date_of_transfer) || 'Нет даты'}</td>
                <td>
                    <button class="edit-place-btn" data-id="${place.id}">Редактировать</button>
                    <button class="delete-place-btn" data-id="${place.id}">Удалить</button>
                </td>
            `;
            
            // Добавляем обработчики событий
            row.querySelector('.edit-place-btn').addEventListener('click', () => editPlace(place.id));
            row.querySelector('.delete-place-btn').addEventListener('click', () => deletePlace(place.id));
            
            placeTable.appendChild(row);
        });
    } catch (error) {
        console.error('Ошибка при загрузке овчарен:', error);
    }
}

// Функция удаления овчарни
async function deletePlace(placeId) {
        const confirmDelete = confirm('Вы уверены, что хотите удалить эту овчарню?');
    if (!confirmDelete) return;

    try {
        await apiRequest(`/veterinary/api/place/${placeId}/`, 'DELETE');
        alert('Овчарня успешно удалена');
        fetchPlaces();  // Обновляем список овчарен
    } catch (error) {
        console.error('Ошибка при удалении овчарни:', error);
        alert(`Ошибка при удалении овчарни: ${error.message}`);
    }
}

// Функция для редактирования овчарни
async function editPlace(placeId) {
        try {
        const place = await apiRequest(`/veterinary/api/place/${placeId}/`);

        // Заполняем форму редактирования данными овчарни
        document.getElementById('place-sheepfold').value = place.sheepfold;
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
    const dateOfTransfer = document.getElementById('place-date').value;

    const data = {
        sheepfold: placeSheepfold,
        date_of_transfer: dateOfTransfer ? dateOfTransfer : null
    };

        try {
        await apiRequest(`/veterinary/api/place/${placeId}/`, 'PUT', data);
        alert('Овчарня успешно обновлена');
        resetButton();  // Сбрасываем состояние кнопки на "Создать"
        fetchPlaces();  // Обновляем список овчарен
    } catch (error) {
        console.error('Ошибка при обновлении овчарни:', error);
        alert(`Произошла ошибка при обновлении овчарни: ${error.message}`);
    }
}

// Функция для поиска овчарен
function searchPlaces() {
    const query = document.getElementById('place-search').value;
    fetchPlaces(query);
}
window.searchPlaces = searchPlaces; // Делаем функцию глобальной

// Функция для сброса кнопки в режим создания
function resetButton() {
    const createPlaceButton = document.getElementById('add-place-button');
    createPlaceButton.innerText = 'Создать овчарню';
    createPlaceButton.removeAttribute('data-id');
    createPlaceButton.onclick =  handleCreateOrUpdatePlace;  // Назначаем обработчик для создания/обновления
}