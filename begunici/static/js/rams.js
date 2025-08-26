import { apiRequest } from "./utils.js";

document.addEventListener('DOMContentLoaded', function () {
    fetchRams();  // Загружаем список баранов при загрузке страницы
    loadStatuses();
    loadPlaces();

    const createRamButton = document.querySelector('#create-ram-button');
    if (createRamButton) {
        createRamButton.onclick = createRam;
    }

    // Добавляем обработчик для поиска
    const searchInput = document.getElementById('ram-search');
    if (searchInput) {
        searchInput.addEventListener('input', searchRams);
    }
});

// Функция создания барана
async function createRam() {
    const formData = new FormData(document.getElementById('create-ram-form'));
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
        await apiRequest('/animals/ram/', 'POST', data);
        alert('Баран успешно создан');
        document.getElementById('create-ram-form').reset();
        fetchRams();
    } catch (error) {
        console.error('Ошибка создания барана:', error);
        alert(`Ошибка: ${error.message}`);
    }
}

// Функция загрузки списка баранов
async function fetchRams() {
    try {
        const rams = await apiRequest('/animals/ram/');
        const ramTable = document.getElementById('ram-list');
        ramTable.innerHTML = '';

        rams.results.forEach((ram, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><input type="checkbox" value="${ram.tag.tag_number}" onchange="updateDeleteButtons()"></td>
                <td>${index + 1}</td>
                <td><a href="/animals/ram/${ram.tag.tag_number}/info/">${ram.tag.tag_number}</a></td>
                <td>${ram.animal_status ? ram.animal_status.status_type : 'Не указан'}</td>
                <td>${ram.age || 'Не указан'}</td>
                <td>${ram.place ? ram.place.sheepfold : 'Не указано'}</td>
                <td>${ram.last_weight || 'Нет данных'}</td>
                <td>${ram.last_vet_care || 'Нет данных'}</td>
                <td>${ram.note || ''}</td>
            `;
            ramTable.appendChild(row);
        });

        // Обновляем пагинацию
        updatePagination(rams);
    } catch (error) {
        console.error('Ошибка при загрузке баранов:', error);
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

// Функция поиска баранов
function searchRams() {
    const input = document.getElementById('ram-search').value.toLowerCase();
    const table = document.getElementById('ram-list');
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
        
        const ramTable = document.getElementById('ram-list');
        ramTable.innerHTML = '';

        data.results.forEach((ram, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><input type="checkbox" value="${ram.tag.tag_number}" onchange="updateDeleteButtons()"></td>
                <td>${index + 1}</td>
                <td><a href="/animals/ram/${ram.tag.tag_number}/info/">${ram.tag.tag_number}</a></td>
                <td>${ram.animal_status ? ram.animal_status.status_type : 'Не указан'}</td>
                <td>${ram.age || 'Не указан'}</td>
                <td>${ram.place ? ram.place.sheepfold : 'Не указано'}</td>
                <td>${ram.last_weight || 'Нет данных'}</td>
                <td>${ram.last_vet_care || 'Нет данных'}</td>
                <td>${ram.note || ''}</td>
            `;
            ramTable.appendChild(row);
        });

        updatePagination(data);
    } catch (error) {
        console.error('Ошибка при смене страницы:', error);
    }
}

// Функция удаления выбранных баранов
async function deleteSelectedRams() {
    const selectedCheckboxes = document.querySelectorAll('input[type="checkbox"]:checked:not(#select-all)');
    const selectedIds = Array.from(selectedCheckboxes).map(cb => cb.value);
    
    if (selectedIds.length === 0) {
        alert('Выберите баранов для удаления');
        return;
    }
    
    const confirmDelete = confirm(`Вы уверены, что хотите удалить ${selectedIds.length} баранов?`);
    if (!confirmDelete) return;

    try {
        for (const id of selectedIds) {
            await apiRequest(`/animals/ram/${id}/`, 'DELETE');
        }
        alert('Бараны успешно удалены');
        fetchRams();
    } catch (error) {
        console.error('Ошибка при удалении баранов:', error);
        alert('Ошибка при удалении баранов');
    }
}

// Функция архивирования выбранных баранов
async function archiveSelectedRams(statusId) {
    const selectedCheckboxes = document.querySelectorAll('input[type="checkbox"]:checked:not(#select-all)');
    const selectedIds = Array.from(selectedCheckboxes).map(cb => cb.value);
    
    if (selectedIds.length === 0) {
        alert('Выберите баранов для архивирования');
        return;
    }

    try {
        for (const id of selectedIds) {
            await apiRequest(`/animals/ram/${id}/`, 'PATCH', { animal_status_id: statusId });
        }
        alert('Бараны успешно перенесены в архив');
        fetchRams();
    } catch (error) {
        console.error('Ошибка при архивировании баранов:', error);
        alert('Ошибка при архивировании баранов');
    }
}

// Экспортируем функцию для глобального доступа
window.archiveSelectedRams = archiveSelectedRams;

