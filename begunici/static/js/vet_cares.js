import { getCSRFToken } from "./utils.js";

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
        const response = await fetch('/veterinary/care/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify(data),
        });

        const result = await response.json();
        if (response.ok) {
            alert('Ветобработка успешно создана');
            document.getElementById('create-care-form').reset();  // Очистка формы
            fetchCares();  // Обновляем список ветобработок
            resetButton();
        } else {
            alert('Ошибка создания: ' + result.detail);
        }
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Произошла ошибка при создании ветобработки');
    }
}

// Получение списка ветобработок
async function fetchCares() {
    try {
        const response = await fetch('/veterinary/care/');
        if (!response.ok) {
            throw new Error('Ошибка при загрузке ветобработок');
        }
        const cares = await response.json();

        const careTable = document.getElementById('care-list');
        careTable.innerHTML = '';  // Очищаем таблицу

        cares.forEach((care, index) => {
            const row = `<tr>
                <td>${index + 1}</td>
                <td>${care.care_type}</td>
                <td>${care.care_name}</td>
                <td>${care.medication || 'Нет препарата'}</td>
                <td>${care.purpose || 'Нет цели'}</td>
                <td>
                    <button onclick="editCare(${care.id})">Редактировать</button>
                    <button onclick="deleteCare(${care.id})">Удалить</button>
                </td>
            </tr>`;
            careTable.innerHTML += row;
        });
    } catch (error) {
        console.error('Ошибка при загрузке ветобработок:', error);
    }
}

// Редактирование ветобработки
async function editCare(careId) {
    try {
        const response = await fetch(`/veterinary/care/${careId}/`);
        if (!response.ok) {
            throw new Error('Ошибка при получении данных обработки');
        }
        const care = await response.json();

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
        const response = await fetch(`/veterinary/care/${careId}/`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify(data),
        });

        if (response.ok) {
            alert('Ветобработка успешно обновлена');
            fetchCares();  // Обновляем список ветобработок
            resetButton();
        } else {
            alert('Ошибка обновления');
        }
    } catch (error) {
        console.error('Ошибка при обновлении:', error);
        alert('Ошибка при обновлении обработки');
    }
}

// Удаление ветобработки
async function deleteCare(careId) {
    try {
        const response = await fetch(`/veterinary/care/${careId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCSRFToken(),
            }
        });

        if (response.ok) {
            alert('Ветобработка успешно удалена');
            fetchCares();  // Обновляем список
        } else {
            alert('Ошибка при удалении обработки');
        }
    } catch (error) {
        console.error('Ошибка при удалении обработки:', error);
    }
}

// Поиск по ветобработкам
function searchCares() {
    const input = document.getElementById('care-search').value.toLowerCase();
    const table = document.getElementById('care-list');
    const rows = table.getElementsByTagName('tr');

    for (let i = 0; i < rows.length; i++) {
        const cells = rows[i].getElementsByTagName('td');
        if (cells.length > 0) {
            const careName = cells[1].innerText.toLowerCase();
            if (careName.indexOf(input) > -1) {
                rows[i].style.display = '';
            } else {
                rows[i].style.display = 'none';
            }
        }
    }
}

// Сброс кнопки на "Создать"
function resetButton() {
    const createCareButton = document.getElementById('create-care-button');
    createCareButton.innerText = 'Создать обработку';
    createCareButton.removeAttribute('data-id');
}
