import { apiRequest } from "./utils.js";

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
    fetchCares();  // Загружаем список ветобработок при загрузке страницы

    const createCareButton = document.querySelector('#create-care-button');
    if (createCareButton) {
        createCareButton.onclick = handleCreateOrUpdateCare;
    }

    // Добавляем обработчик для мгновенного поиска
    const searchInput = document.getElementById('care-search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const query = this.value;
            currentPage = 1; // Сбрасываем на первую страницу при поиске
            fetchCares(1, query);
        });
    }
});

// Функция для создания/обновления ветобработки
function handleCreateOrUpdateCare() {
    const createCareButton = document.getElementById('create-care-button');
    const careId = createCareButton.getAttribute('data-id');
    if (careId) {
        updateCare(careId);  // Если есть data-id, выполняем обновление
    } else {
        createCare();  // Иначе создаем новую обработку
    }
}

// Функция отмены редактирования
function cancelEdit() {
    document.getElementById('create-care-form').reset();
    resetButton();
    document.getElementById('form-title').textContent = 'Создать обработку';
    document.getElementById('cancel-edit-button').style.display = 'none';
}
window.cancelEdit = cancelEdit; // Делаем функцию глобальной

// Создание новой ветобработки
async function createCare() {
    const careType = document.getElementById('care-type').value;
    const careName = document.getElementById('care-name').value;
    const medication = document.getElementById('medication').value;
    const purpose = document.getElementById('purpose').value;
    const defaultDurationDays = document.getElementById('default-duration-days').value;

    const data = {
        care_type: careType,
        care_name: careName,
        medication: medication || null,
        purpose: purpose || null,
        default_duration_days: parseInt(defaultDurationDays) || 0
    };

    try {
        await apiRequest('/veterinary/api/care/', 'POST', data);
        showMessage('Ветобработка успешно создана', 'success');
        document.getElementById('create-care-form').reset();  // Очистка формы
        fetchCares(currentPage);  // Обновляем текущую страницу
        resetButton();
    } catch (error) {
        console.error('Ошибка:', error);
        showMessage(`Произошла ошибка при создании ветобработки: ${error.message}`, 'danger');
    }
}

// Получение списка ветобработок
async function fetchCares(page = 1, searchQuery = '') {
    try {
        let url = `/veterinary/api/care/?page=${page}&page_size=${pageSize}`;
        if (searchQuery) {
            url += `&search=${encodeURIComponent(searchQuery)}`;
        }
        const response = await apiRequest(url);
        
        // Обрабатываем пагинированный ответ
        const cares = Array.isArray(response) ? response : response.results;
        currentPage = page;
        
        const careTable = document.getElementById('care-list');
        careTable.innerHTML = '';  // Очищаем таблицу

        if (cares && cares.length > 0) {
            cares.forEach((care, index) => {
                const row = document.createElement('tr');
                
                // Создаем кнопки действий с проверкой прав
                const permissions = getUserPermissions();
                let actionsHtml = `
                    <div class="btn-group btn-group-sm" role="group">
                        <button class="btn btn-outline-primary edit-care-btn" data-id="${care.id}">Редактировать</button>`;
                
                if (permissions.can_delete_vet_data) {
                    actionsHtml += `
                        <button class="btn btn-outline-danger delete-care-btn" data-id="${care.id}">Удалить</button>`;
                }
                
                actionsHtml += `</div>`;
                
                // Вычисляем номер записи с учетом пагинации
                const recordNumber = (page - 1) * pageSize + index + 1;
                
                row.innerHTML = `
                    <td>${recordNumber}</td>
                    <td>${care.care_type}</td>
                    <td>${care.care_name}</td>
                    <td>${care.medication || 'Нет препарата'}</td>
                    <td>${care.purpose || 'Нет цели'}</td>
                    <td>${care.default_duration_days === 0 ? 'Бессрочно' : care.default_duration_days + ' дней'}</td>
                    <td>${actionsHtml}</td>
                `;
                
                row.querySelector('.edit-care-btn').addEventListener('click', () => editCare(care.id));
                
                const deleteBtn = row.querySelector('.delete-care-btn');
                if (deleteBtn) {
                    deleteBtn.addEventListener('click', () => deleteCare(care.id));
                }
                
                careTable.appendChild(row);
            });
        } else {
            careTable.innerHTML = '<tr><td colspan="7" class="text-center">Ветобработки не найдены</td></tr>';
        }
        
        // Обновляем пагинацию
        if (!Array.isArray(response)) {
            updatePagination(response);
        }
    } catch (error) {
        console.error('Ошибка при загрузке ветобработок:', error);
        const careTable = document.getElementById('care-list');
        careTable.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Ошибка загрузки данных</td></tr>';
    }
}

// Редактирование ветобработки
async function editCare(careId) {
    try {
        const care = await apiRequest(`/veterinary/api/care/${careId}/`);

        document.getElementById('care-type').value = care.care_type;
        document.getElementById('care-name').value = care.care_name;
        document.getElementById('medication').value = care.medication || '';
        document.getElementById('purpose').value = care.purpose || '';
        document.getElementById('default-duration-days').value = care.default_duration_days || 0;

        const createCareButton = document.getElementById('create-care-button');
        createCareButton.innerText = 'Сохранить изменения';
        createCareButton.setAttribute('data-id', careId);
        
        document.getElementById('form-title').textContent = 'Редактировать обработку';
        document.getElementById('cancel-edit-button').style.display = 'block';
    } catch (error) {
        console.error('Ошибка при редактировании обработки:', error);
        showMessage(`Ошибка при загрузке данных обработки: ${error.message}`, 'danger');
    }
}

// Обновление ветобработки
async function updateCare(careId) {
    const careType = document.getElementById('care-type').value;
    const careName = document.getElementById('care-name').value;
    const medication = document.getElementById('medication').value;
    const purpose = document.getElementById('purpose').value;
    const defaultDurationDays = document.getElementById('default-duration-days').value;

    const data = {
        care_type: careType,
        care_name: careName,
        medication: medication || null,
        purpose: purpose || null,
        default_duration_days: parseInt(defaultDurationDays) || 0
    };

    try {
        await apiRequest(`/veterinary/api/care/${careId}/`, 'PUT', data);
        showMessage('Ветобработка успешно обновлена', 'success');
        fetchCares(currentPage);  // Обновляем текущую страницу
        resetButton();
        cancelEdit();
    } catch (error) {
        console.error('Ошибка при обновлении:', error);
        showMessage(`Ошибка при обновлении обработки: ${error.message}`, 'danger');
    }
}

// Удаление ветобработки
async function deleteCare(careId) {
    const confirmDelete = confirm('Вы уверены, что хотите удалить эту обработку?');
    if (!confirmDelete) return;

    try {
        await apiRequest(`/veterinary/api/care/${careId}/`, 'DELETE');
        showMessage('Ветобработка успешно удалена', 'success');
        fetchCares(currentPage);  // Обновляем текущую страницу
    } catch (error) {
        console.error('Ошибка при удалении обработки:', error);
        showMessage(`Ошибка при удалении обработки: ${error.message}`, 'danger');
    }
}

// Поиск по ветобработкам
function searchCares(query = null) {
    if (query === null) {
        query = document.getElementById('care-search').value;
    }
    currentPage = 1; // Сбрасываем на первую страницу при поиске
    fetchCares(1, query);
}
window.searchCares = searchCares; // Делаем функцию глобальной

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
            const searchQuery = document.getElementById('care-search').value;
            fetchCares(currentPage, searchQuery);
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
            const searchQuery = document.getElementById('care-search').value;
            fetchCares(currentPage, searchQuery);
        };
        rightContainer.appendChild(nextButton);
    }
    
    paginationElement.appendChild(leftContainer);
    paginationElement.appendChild(pageInfo);
    paginationElement.appendChild(rightContainer);
}

// Сброс кнопки на "Создать"
function resetButton() {
    const createCareButton = document.getElementById('create-care-button');
    createCareButton.innerText = 'Создать обработку';
    createCareButton.removeAttribute('data-id');
}

// Функция для отображения сообщений
function showMessage(message, type) {
    const messageDiv = document.getElementById('care-message');
    messageDiv.className = `alert alert-${type}`;
    messageDiv.textContent = message;
    messageDiv.style.display = 'block';
    
    // Автоматически скрываем сообщение через 5 секунд
    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 5000);
}

// Делаем функцию глобальной для использования в HTML
window.handleCreateOrUpdateCare = handleCreateOrUpdateCare;
