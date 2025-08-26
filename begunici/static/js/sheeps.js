import { apiRequest } from "./utils.js";

document.addEventListener('DOMContentLoaded', function () {
    fetchSheeps();  // Загружаем список овец при загрузке страницы
    loadStatuses();
    loadPlaces();

    const createSheepButton = document.querySelector('#create-sheep-button');
    if (createSheepButton) {
        createSheepButton.onclick = createSheep;
    }

    // Добавляем обработчик для поиска
    const searchInput = document.getElementById('sheep-search');
    if (searchInput) {
        searchInput.addEventListener('input', searchSheeps);
    }
});

// Функция создания овцы
async function createSheep() {
    const formData = new FormData(document.getElementById('create-sheep-form'));
    const data = {
        tag: formData.get('tag'),
        animal_status_id: formData.get('animal_status') || null,
        birth_date: formData.get('birth_date') || null,
        place_id: formData.get('place') || null,
        note: formData.get('note') || ''
    };

    if (!data.tag) {
        alert('Пожалуйста, введите номер бирки');
        return;
    }

    try {
        await apiRequest('/animals/sheep/', 'POST', data);
        alert('Овца успешно создана');
        document.getElementById('create-sheep-form').reset();
        fetchSheeps();
    } catch (error) {
        console.error('Ошибка создания овцы:', error);
        alert(`Ошибка: ${error.message}`);
    }
}

// Функция загрузки списка овец
async function fetchSheeps() {
    try {
        const sheeps = await apiRequest('/animals/sheep/');
        const sheepTable = document.getElementById('sheep-list');
        sheepTable.innerHTML = '';

        sheeps.results.forEach((sheep, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><input type="checkbox" value="${sheep.tag.tag_number}" onchange="updateDeleteButtons()"></td>
                <td>${index + 1}</td>
                <td><a href="/animals/sheep/${sheep.tag.tag_number}/info/">${sheep.tag.tag_number}</a></td>
                <td>${sheep.animal_status ? sheep.animal_status.status_type : 'Не указан'}</td>
                <td>${sheep.age || 'Не указан'}</td>
                <td>${sheep.place ? sheep.place.sheepfold : 'Не указано'}</td>
                <td>${sheep.last_weight || 'Нет данных'}</td>
                <td>${sheep.last_vet_care || 'Нет данных'}</td>
                <td>${sheep.note || ''}</td>
            `;
            sheepTable.appendChild(row);
        });

        // Обновляем пагинацию
        updatePagination(sheeps);
    } catch (error) {
        console.error('Ошибка при загрузке овец:', error);
    }
}

// Функция загрузки статусов
async function loadStatuses() {
    try {
        const statuses = await apiRequest('/veterinary/status/');
        const select = document.getElementById('animal_status');
        select.innerHTML = '<option value="">Выберите статус</option>';
        
        const statusesArray = statuses.results || statuses;
        statusesArray.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.textContent = status.status_type;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка загрузки статусов:', error);
    }
}

// Функция загрузки овчарен
async function loadPlaces() {
    try {
        const places = await apiRequest('/veterinary/place/');
        const select = document.getElementById('place');
        select.innerHTML = '<option value="">Выберите овчарню</option>';
        
        const placesArray = places.results || places;
        placesArray.forEach(place => {
            const option = document.createElement('option');
            option.value = place.id;
            option.textContent = place.sheepfold;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка загрузки овчарен:', error);
    }
}

// Функция поиска овец
function searchSheeps() {
    const input = document.getElementById('sheep-search').value.toLowerCase();
    const table = document.getElementById('sheep-list');
    const rows = table.getElementsByTagName('tr');

    for (let i = 0; i < rows.length; i++) {
        const cells = rows[i].getElementsByTagName('td');
        if (cells.length > 0) {
            const tagNumber = cells[2].innerText.toLowerCase();
            const status = cells[3].innerText.toLowerCase();
            const place = cells[5].innerText.toLowerCase();
            
            if (tagNumber.indexOf(input) > -1 || status.indexOf(input) > -1 || place.indexOf(input) > -1) {
                rows[i].style.display = '';
            } else {
                rows[i].style.display = 'none';
            }
        }
    }
}

// Функция обновления пагинации
function updatePagination(data) {
    const pagination = document.getElementById('pagination');
    if (!data.pagination) return;

    let paginationHTML = '';
    
    if (data.pagination.previous) {
        paginationHTML += `<button onclick="changePage('${data.pagination.previous}')">Предыдущая</button>`;
    }
    
    if (data.pagination.next) {
        paginationHTML += `<button onclick="changePage('${data.pagination.next}')">Следующая</button>`;
    }
    
    pagination.innerHTML = paginationHTML;
}

// Функция смены страницы
async function changePage(url) {
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        const sheepTable = document.getElementById('sheep-list');
        sheepTable.innerHTML = '';

        data.results.forEach((sheep, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><input type="checkbox" value="${sheep.tag.tag_number}" onchange="updateDeleteButtons()"></td>
                <td>${index + 1}</td>
                <td><a href="/animals/sheep/${sheep.tag.tag_number}/info/">${sheep.tag.tag_number}</a></td>
                <td>${sheep.animal_status ? sheep.animal_status.status_type : 'Не указан'}</td>
                <td>${sheep.age || 'Не указан'}</td>
                <td>${sheep.place ? sheep.place.sheepfold : 'Не указано'}</td>
                <td>${sheep.last_weight || 'Нет данных'}</td>
                <td>${sheep.last_vet_care || 'Нет данных'}</td>
                <td>${sheep.note || ''}</td>
            `;
            sheepTable.appendChild(row);
        });

        updatePagination(data);
    } catch (error) {
        console.error('Ошибка при смене страницы:', error);
    }
}

// Функция удаления выбранных овец
async function deleteSelectedSheeps() {
    const selectedCheckboxes = document.querySelectorAll('input[type="checkbox"]:checked:not(#select-all)');
    const selectedIds = Array.from(selectedCheckboxes).map(cb => cb.value);
    
    if (selectedIds.length === 0) {
        alert('Выберите овец для удаления');
        return;
    }
    
    const confirmDelete = confirm(`Вы уверены, что хотите удалить ${selectedIds.length} овец?`);
    if (!confirmDelete) return;

    try {
        for (const id of selectedIds) {
            await apiRequest(`/animals/sheep/${id}/`, 'DELETE');
        }
        alert('Овцы успешно удалены');
        fetchSheeps();
    } catch (error) {
        console.error('Ошибка при удалении овец:', error);
        alert('Ошибка при удалении овец');
    }
}

// Функция архивирования выбранных овец
async function archiveSelectedSheeps(statusId) {
    const selectedCheckboxes = document.querySelectorAll('input[type="checkbox"]:checked:not(#select-all)');
    const selectedIds = Array.from(selectedCheckboxes).map(cb => cb.value);
    
    if (selectedIds.length === 0) {
        alert('Выберите овец для архивирования');
        return;
    }

    try {
        for (const id of selectedIds) {
            await apiRequest(`/animals/sheep/${id}/`, 'PATCH', { animal_status_id: statusId });
        }
        alert('Овцы успешно перенесены в архив');
        fetchSheeps();
    } catch (error) {
        console.error('Ошибка при архивировании овец:', error);
        alert('Ошибка при архивировании овец');
    }
}

// Экспортируем функцию для глобального доступа
window.archiveSelectedSheeps = archiveSelectedSheeps;

