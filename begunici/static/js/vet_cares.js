import { apiRequest } from "./utils.js";

document.addEventListener('DOMContentLoaded', function () {
    fetchCares();  // Загружаем список ветобработок при загрузке страницы

    const createCareButton = document.querySelector('#create-care-button');
    if (createCareButton) {
        createCareButton.onclick = handleCreateOrUpdateCare;
    }
});

// Функция для создания/обновления ветобработки
function handleCreateOrUpdateCare() {
    const careId = this.getAttribute('data-id');
    if (careId) {
        updateCare(careId);  // Если есть data-id, выполняем обновление
    } else {
        createCare();  // Иначе создаем новую обработку
    }
}

// Создание новой ветобработки
async function createCare() {
    const careType = document.getElementById('care-type').value;
    const careName = document.getElementById('care-name').value;
    const medication = document.getElementById('medication').value;
    const purpose = document.getElementById('purpose').value;

    const data = {
        care_type: careType,
        care_name: careName,
        medication: medication || null,
        purpose: purpose || null
    };

    try {
        await apiRequest('/veterinary/api/care/', 'POST', data);
        alert('Ветобработка успешно создана');
        document.getElementById('create-care-form').reset();  // Очистка формы
        fetchCares();  // Обновляем список ветобработок
        resetButton();
    } catch (error) {
        console.error('Ошибка:', error);
        alert(`Произошла ошибка при создании ветобработки: ${error.message}`);
    }
}

// Получение списка ветобработок
async function fetchCares(searchQuery = '') {
    try {
        let url = '/veterinary/api/care/';
        if (searchQuery) {
            url += `?search=${searchQuery}`;
        }
        const cares = await apiRequest(url);
        const careTable = document.getElementById('care-list');
        careTable.innerHTML = '';  // Очищаем таблицу

        cares.forEach((care, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${care.care_type}</td>
                <td>${care.care_name}</td>
                <td>${care.medication || 'Нет препарата'}</td>
                <td>${care.purpose || 'Нет цели'}</td>
                <td>
                    <button class="edit-care-btn" data-id="${care.id}">Редактировать</button>
                    <button class="delete-care-btn" data-id="${care.id}">Удалить</button>
                </td>
            `;
            row.querySelector('.edit-care-btn').addEventListener('click', () => editCare(care.id));
            row.querySelector('.delete-care-btn').addEventListener('click', () => deleteCare(care.id));
            careTable.appendChild(row);
        });
    } catch (error) {
        console.error('Ошибка при загрузке ветобработок:', error);
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

        const createCareButton = document.getElementById('create-care-button');
        createCareButton.innerText = 'Сохранить изменения';
        createCareButton.setAttribute('data-id', careId);
    } catch (error) {
        console.error('Ошибка при редактировании обработки:', error);
    }
}

// Обновление ветобработки
async function updateCare(careId) {
    const careType = document.getElementById('care-type').value;
    const careName = document.getElementById('care-name').value;
    const medication = document.getElementById('medication').value;
    const purpose = document.getElementById('purpose').value;

    const data = {
        care_type: careType,
        care_name: careName,
        medication: medication || null,
        purpose: purpose || null
    };

    try {
        await apiRequest(`/veterinary/api/care/${careId}/`, 'PUT', data);
        alert('Ветобработка успешно обновлена');
        fetchCares();  // Обновляем список ветобработок
        resetButton();
    } catch (error) {
        console.error('Ошибка при обновлении:', error);
        alert(`Ошибка при обновлении обработки: ${error.message}`);
    }
}

// Удаление ветобработки
async function deleteCare(careId) {
    const confirmDelete = confirm('Вы уверены, что хотите удалить эту обработку?');
    if (!confirmDelete) return;

    try {
        await apiRequest(`/veterinary/api/care/${careId}/`, 'DELETE');
        alert('Ветобработка успешно удалена');
        fetchCares();  // Обновляем список
    } catch (error) {
        console.error('Ошибка при удалении обработки:', error);
        alert(`Ошибка при удалении обработки: ${error.message}`);
    }
}

// Поиск по ветобработкам
function searchCares() {
    const query = document.getElementById('care-search').value;
    fetchCares(query);
}
window.searchCares = searchCares; // Делаем функцию глобальной

// Сброс кнопки на "Создать"
function resetButton() {
    const createCareButton = document.getElementById('create-care-button');
    createCareButton.innerText = 'Создать обработку';
    createCareButton.removeAttribute('data-id');
}
