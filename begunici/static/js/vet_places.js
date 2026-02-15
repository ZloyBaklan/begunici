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
    fetchPlaces();  // Загружаем список овчарен при загрузке страницы
    
    const createPlaceButton = document.querySelector('#add-place-button');
    if (createPlaceButton) {
        // Назначаем событие для создания/обновления овчарни
        createPlaceButton.onclick = handleCreateOrUpdatePlace;
    }

    // Добавляем обработчик для мгновенного поиска
    const searchInput = document.getElementById('place-search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const query = this.value;
            currentPage = 1; // Сбрасываем на первую страницу при поиске
            fetchPlaces(1, query);
        });
    }
});

// Функция, которая переключается между созданием и обновлением
function handleCreateOrUpdatePlace() {
    const createPlaceButton = document.getElementById('add-place-button');
    const placeId = createPlaceButton.getAttribute('data-id');
    if (placeId) {
        updatePlace(placeId);  // Если есть data-id, выполняем обновление
    } else {
        createPlace();  // Иначе создаем новую овчарню
    }
}

// Функция отмены редактирования
function cancelEdit() {
    document.getElementById('create-place-form').reset();
    resetButton();
    document.getElementById('form-title').textContent = 'Создать овчарню';
    document.getElementById('cancel-edit-button').style.display = 'none';
}
window.cancelEdit = cancelEdit; // Делаем функцию глобальной

// Функция создания овчарни через API
async function createPlace() {
    const barnNumber = document.getElementById('place-sheepfold-barn').value;
    const sectionNumber = document.getElementById('place-sheepfold-section').value;
    const dateOfTransfer = document.getElementById('place-date').value;

    if (!barnNumber || !sectionNumber) {
        alert('Пожалуйста, введите номер овчарни и отсека');
        return;
    }

    // Формируем название в формате "Овчарня X Отсек Y"
    const placeSheepfold = `Овчарня ${barnNumber} Отсек ${sectionNumber}`;

    const data = {
        sheepfold: placeSheepfold,
        date_of_transfer: dateOfTransfer || null
    };

    console.log('Creating place with data:', data);

    try {
        await apiRequest('/veterinary/api/place/', 'POST', data);
        showMessage('Овчарня успешно создана', 'success');
        
        // Очищаем поля формы
        document.getElementById('place-sheepfold-barn').value = '';
        document.getElementById('place-sheepfold-section').value = '';
        document.getElementById('place-date').value = '';
        
        fetchPlaces(currentPage);  // Обновляем текущую страницу
        resetButton();  // Сбрасываем состояние кнопки на "Создать"
    } catch (error) {
        console.error('Ошибка:', error);
        showMessage(`Произошла ошибка при создании овчарни: ${error.message}`, 'danger');
    }
}

// Функция для загрузки списка овчарен
async function fetchPlaces(page = 1, searchQuery = '') {
    try {
        console.log('Fetching places...');
        let url = `/veterinary/api/place/?page=${page}&page_size=${pageSize}`;
        if (searchQuery) {
            url += `&search=${encodeURIComponent(searchQuery)}`;
        }
        const response = await apiRequest(url);
        console.log('Places response:', response);

        // Обрабатываем пагинированный ответ
        const places = Array.isArray(response) ? response : response.results;
        currentPage = page;

        const placeTable = document.getElementById('place-list');
        placeTable.innerHTML = '';  // Очищаем старый список

        if (places && places.length > 0) {
            places.forEach((place, index) => {
                const row = document.createElement('tr');
                
                // Создаем кнопки действий с проверкой прав
                const permissions = getUserPermissions();
                let actionsHtml = `
                    <div class="btn-group btn-group-sm" role="group">
                        <button class="btn btn-outline-primary edit-place-btn" data-id="${place.id}">Редактировать</button>`;
                
                if (permissions.can_delete_vet_data) {
                    actionsHtml += `
                        <button class="btn btn-outline-danger delete-place-btn" data-id="${place.id}">Удалить</button>`;
                }
                
                actionsHtml += `</div>`;
                
                // Вычисляем номер записи с учетом пагинации
                const recordNumber = (page - 1) * pageSize + index + 1;
                
                row.innerHTML = `
                    <td>${recordNumber}</td>
                    <td>${place.sheepfold}</td>
                    <td>${formatDateToOutput(place.date_of_transfer) || 'Нет даты'}</td>
                    <td>${actionsHtml}</td>
                `;
                
                // Добавляем обработчики событий
                row.querySelector('.edit-place-btn').addEventListener('click', () => editPlace(place.id));
                
                const deleteBtn = row.querySelector('.delete-place-btn');
                if (deleteBtn) {
                    deleteBtn.addEventListener('click', () => deletePlace(place.id));
                }
                
                placeTable.appendChild(row);
            });
        } else {
            placeTable.innerHTML = '<tr><td colspan="4" class="text-center">Овчарни не найдены</td></tr>';
        }
        
        // Обновляем пагинацию
        if (!Array.isArray(response)) {
            updatePagination(response);
        }
    } catch (error) {
        console.error('Ошибка при загрузке овчарен:', error);
        const placeTable = document.getElementById('place-list');
        placeTable.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Ошибка загрузки данных</td></tr>';
    }
}

// Функция удаления овчарни
async function deletePlace(placeId) {
        const confirmDelete = confirm('Вы уверены, что хотите удалить эту овчарню?');
    if (!confirmDelete) return;

    try {
        await apiRequest(`/veterinary/api/place/${placeId}/`, 'DELETE');
        showMessage('Овчарня успешно удалена', 'success');
        fetchPlaces(currentPage);  // Обновляем текущую страницу
    } catch (error) {
        console.error('Ошибка при удалении овчарни:', error);
        showMessage(`Ошибка при удалении овчарни: ${error.message}`, 'danger');
    }
}

// Функция для редактирования овчарни
async function editPlace(placeId) {
    try {
        const place = await apiRequest(`/veterinary/api/place/${placeId}/`);

        // Парсим название овчарни для извлечения номеров
        const match = place.sheepfold.match(/Овчарня (\d+) Отсек (\d+)/);
        if (match) {
            document.getElementById('place-sheepfold-barn').value = match[1];
            document.getElementById('place-sheepfold-section').value = match[2];
        } else {
            // Если формат не соответствует, показываем как есть
            document.getElementById('place-sheepfold-barn').value = '';
            document.getElementById('place-sheepfold-section').value = '';
            alert('Неизвестный формат названия овчарни. Введите номера заново.');
        }
        
        document.getElementById('place-date').value = formatDateToInput(place.date_of_transfer);

        const createPlaceButton = document.getElementById('add-place-button');
        createPlaceButton.innerText = 'Сохранить изменения';
        createPlaceButton.setAttribute('data-id', placeId);
        
        document.getElementById('form-title').textContent = 'Редактировать овчарню';
        document.getElementById('cancel-edit-button').style.display = 'block';
    } catch (error) {
        console.error('Ошибка при редактировании овчарни:', error);
        showMessage(`Ошибка при загрузке данных овчарни: ${error.message}`, 'danger');
    }
}

// Функция для обновления овчарни
async function updatePlace(placeId) {
    const barnNumber = document.getElementById('place-sheepfold-barn').value;
    const sectionNumber = document.getElementById('place-sheepfold-section').value;
    const dateOfTransfer = document.getElementById('place-date').value;

    if (!barnNumber || !sectionNumber) {
        alert('Пожалуйста, введите номер овчарни и отсека');
        return;
    }

    // Формируем название в формате "Овчарня X Отсек Y"
    const placeSheepfold = `Овчарня ${barnNumber} Отсек ${sectionNumber}`;

    const data = {
        sheepfold: placeSheepfold,
        date_of_transfer: dateOfTransfer ? dateOfTransfer : null
    };

    try {
        await apiRequest(`/veterinary/api/place/${placeId}/`, 'PUT', data);
        showMessage('Овчарня успешно обновлена', 'success');
        resetButton();  // Сбрасываем состояние кнопки на "Создать"
        cancelEdit();
        fetchPlaces(currentPage);  // Обновляем текущую страницу
    } catch (error) {
        console.error('Ошибка при обновлении овчарни:', error);
        showMessage(`Произошла ошибка при обновлении овчарни: ${error.message}`, 'danger');
    }
}

// Функция для поиска овчарен
function searchPlaces(query = null) {
    if (query === null) {
        query = document.getElementById('place-search').value;
    }
    currentPage = 1; // Сбрасываем на первую страницу при поиске
    fetchPlaces(1, query);
}
window.searchPlaces = searchPlaces; // Делаем функцию глобальной

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
            const searchQuery = document.getElementById('place-search').value;
            fetchPlaces(currentPage, searchQuery);
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
            const searchQuery = document.getElementById('place-search').value;
            fetchPlaces(currentPage, searchQuery);
        };
        rightContainer.appendChild(nextButton);
    }
    
    paginationElement.appendChild(leftContainer);
    paginationElement.appendChild(pageInfo);
    paginationElement.appendChild(rightContainer);
}

// Функция для сброса кнопки в режим создания
function resetButton() {
    const createPlaceButton = document.getElementById('add-place-button');
    createPlaceButton.innerText = 'Создать овчарню';
    createPlaceButton.removeAttribute('data-id');
    createPlaceButton.onclick = handleCreateOrUpdatePlace;  // Назначаем обработчик для создания/обновления
    
    // Очищаем поля формы
    document.getElementById('place-sheepfold-barn').value = '';
    document.getElementById('place-sheepfold-section').value = '';
    document.getElementById('place-date').value = '';
}

// Функция для отображения сообщений
function showMessage(message, type) {
    const messageDiv = document.getElementById('place-message');
    messageDiv.className = `alert alert-${type}`;
    messageDiv.textContent = message;
    messageDiv.style.display = 'block';
    
    // Автоматически скрываем сообщение через 5 секунд
    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 5000);
}

// Делаем функцию глобальной для использования в HTML
window.handleCreateOrUpdatePlace = handleCreateOrUpdatePlace;