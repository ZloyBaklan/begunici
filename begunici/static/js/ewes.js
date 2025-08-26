import { apiRequest } from "./utils.js";

document.addEventListener('DOMContentLoaded', function () {
    fetchEwes();  // Загружаем список ярок при загрузке страницы
    loadStatuses();
    loadPlaces();

    const createEweButton = document.querySelector('#create-ewe-button');
    if (createEweButton) {
        createEweButton.onclick = createEwe;
    }

    // Добавляем обработчик для поиска
    const searchInput = document.getElementById('ewe-search');
    if (searchInput) {
        searchInput.addEventListener('input', searchEwes);
    }
});

// Функция создания ярки
async function createEwe() {
    const formData = new FormData(document.getElementById('create-ewe-form'));
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
        await apiRequest('/animals/ewe/', 'POST', data);
        alert('Ярка успешно создана');
        document.getElementById('create-ewe-form').reset();
        fetchEwes();
    } catch (error) {
        console.error('Ошибка создания ярки:', error);
        alert(`Ошибка: ${error.message}`);
    }
}

// Функция загрузки списка ярок
async function fetchEwes() {
    try {
        const ewes = await apiRequest('/animals/ewe/');
        const eweTable = document.getElementById('ewe-list');
        eweTable.innerHTML = '';

        ewes.results.forEach((ewe, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><input type="checkbox" value="${ewe.tag.tag_number}" onchange="updateDeleteButtons()"></td>
                <td>${index + 1}</td>
                <td><a href="/animals/ewe/${ewe.tag.tag_number}/info/">${ewe.tag.tag_number}</a></td>
                <td>${ewe.animal_status ? ewe.animal_status.status_type : 'Не указан'}</td>
                <td>${ewe.age || 'Не указан'}</td>
                <td>${ewe.place ? ewe.place.sheepfold : 'Не указано'}</td>
                <td>${ewe.last_weight || 'Нет данных'}</td>
                <td>${ewe.last_vet_care || 'Нет данных'}</td>
                <td>${ewe.note || ''}</td>
            `;
            eweTable.appendChild(row);
        });

        // Обновляем пагинацию
        updatePagination(ewes);
    } catch (error) {
        console.error('Ошибка при загрузке ярок:', error);
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

// Функция поиска ярок
function searchEwes() {
    const input = document.getElementById('ewe-search').value.toLowerCase();
    const table = document.getElementById('ewe-list');
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
        
        const eweTable = document.getElementById('ewe-list');
        eweTable.innerHTML = '';

        data.results.forEach((ewe, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><input type="checkbox" value="${ewe.tag.tag_number}" onchange="updateDeleteButtons()"></td>
                <td>${index + 1}</td>
                <td><a href="/animals/ewe/${ewe.tag.tag_number}/info/">${ewe.tag.tag_number}</a></td>
                <td>${ewe.animal_status ? ewe.animal_status.status_type : 'Не указан'}</td>
                <td>${ewe.age || 'Не указан'}</td>
                <td>${ewe.place ? ewe.place.sheepfold : 'Не указано'}</td>
                <td>${ewe.last_weight || 'Нет данных'}</td>
                <td>${ewe.last_vet_care || 'Нет данных'}</td>
                <td>${ewe.note || ''}</td>
            `;
            eweTable.appendChild(row);
        });

        updatePagination(data);
    } catch (error) {
        console.error('Ошибка при смене страницы:', error);
    }
}

// Функция удаления выбранных ярок
async function deleteSelectedEwes() {
    const selectedCheckboxes = document.querySelectorAll('input[type="checkbox"]:checked:not(#select-all)');
    const selectedIds = Array.from(selectedCheckboxes).map(cb => cb.value);
    
    if (selectedIds.length === 0) {
        alert('Выберите ярок для удаления');
        return;
    }
    
    const confirmDelete = confirm(`Вы уверены, что хотите удалить ${selectedIds.length} ярок?`);
    if (!confirmDelete) return;

    try {
        for (const id of selectedIds) {
            await apiRequest(`/animals/ewe/${id}/`, 'DELETE');
        }
        alert('Ярки успешно удалены');
        fetchEwes();
    } catch (error) {
        console.error('Ошибка при удалении ярок:', error);
        alert('Ошибка при удалении ярок');
    }
}

// Функция архивирования выбранных ярок
async function archiveSelectedEwes(statusId) {
    const selectedCheckboxes = document.querySelectorAll('input[type="checkbox"]:checked:not(#select-all)');
    const selectedIds = Array.from(selectedCheckboxes).map(cb => cb.value);
    
    if (selectedIds.length === 0) {
        alert('Выберите ярок для архивирования');
        return;
    }

    try {
        for (const id of selectedIds) {
            await apiRequest(`/animals/ewe/${id}/`, 'PATCH', { animal_status_id: statusId });
        }
        alert('Ярки успешно перенесены в архив');
        fetchEwes();
    } catch (error) {
        console.error('Ошибка при архивировании ярок:', error);
        alert('Ошибка при архивировании ярок');
    }
}

// Экспортируем функцию для глобального доступа
window.archiveSelectedEwes = archiveSelectedEwes;

