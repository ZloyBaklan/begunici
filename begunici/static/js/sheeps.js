import { apiRequest, formatDateToOutput } from "./utils.js";

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
        tag_number: formData.get('tag'),
        animal_status_id: formData.get('animal_status') ? parseInt(formData.get('animal_status')) : null,
        birth_date: formData.get('birth_date') || null,
        place_id: formData.get('place') ? parseInt(formData.get('place')) : null,
        note: formData.get('note') || ''
    };

    if (!data.tag_number) {
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

let currentPage = 1;
const pageSize = 10;

// Функция загрузки списка овец
async function fetchSheeps(page = 1, query = '') {
    try {
        const response = await apiRequest(`/animals/sheep/?page=${page}&page_size=${pageSize}&search=${encodeURIComponent(query)}`);
        const sheeps = Array.isArray(response) ? response : response.results;

        if (sheeps) {
            renderSheeps(sheeps);
            updatePagination(response);
        } else {
            console.error('Некорректный ответ от API:', response);
            alert('Ошибка: данные овец не найдены.');
        }
    } catch (error) {
        console.error('Ошибка при загрузке овец:', error);
        alert('Ошибка при загрузке списка овец.');
    }
}

// Рендеринг списка овец
function renderSheeps(sheeps) {
    const sheepTable = document.getElementById('sheep-list');
    sheepTable.innerHTML = '';
    sheeps.forEach((sheep, index) => {
        const row = `<tr>
            <td>
                <input type="checkbox" 
                class="select-sheep"  
                data-tag="${sheep.tag.tag_number}">
            </td>
            <td>${(currentPage - 1) * pageSize + index + 1}</td>
            <td><a href="/animals/sheep/${sheep.tag.tag_number}/info/">${sheep.tag.tag_number}</a></td>
            <td style="background-color:${sheep.animal_status ? sheep.animal_status.color : '#FFFFFF'}">
                ${sheep.animal_status ? sheep.animal_status.status_type : 'Не указан'}
            </td>
            <td>${sheep.age ? `${sheep.age} мес.` : 'Не указан'}</td>
            <td>${sheep.place ? sheep.place.sheepfold : 'Не указано'}</td>
            <td>${sheep.weight_records && sheep.weight_records.length > 0 
                ? `${sheep.weight_records[0].weight_date}: ${sheep.weight_records[0].weight} кг` 
                : 'Нет записей'}</td>
            <td>${sheep.veterinary_history && sheep.veterinary_history.length > 0 
                ? `${formatDateToOutput(sheep.veterinary_history[0].date_of_care)}: ${sheep.veterinary_history[0].veterinary_care.care_name}` 
                : 'Нет записей'}</td>
            <td>${sheep.note || ''}</td>
        </tr>`;
        sheepTable.innerHTML += row;
    });
    
    document.querySelectorAll('.select-sheep').forEach(cb => cb.addEventListener('click', e => toggleSelectSheep(e.target)))
}

// Функция загрузки статусов
async function loadStatuses() {
    try {
        const statuses = await apiRequest('/veterinary/api/status/');
        const select = document.getElementById('animal_status');
        select.innerHTML = '<option value="">Выберите статус</option>';
        
        statuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.textContent = status.status_type;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка загрузки статусов:', error);
    }
}

// Функция загрузки мест
async function loadPlaces() {
    try {
        const places = await apiRequest('/veterinary/api/place/');
        const select = document.getElementById('place');
        select.innerHTML = '<option value="">Выберите место</option>';
        
        places.forEach(place => {
            const option = document.createElement('option');
            option.value = place.id;
            option.textContent = place.sheepfold;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка загрузки мест:', error);
    }
}

// Функция поиска овец
async function searchSheeps() {
    const searchTerm = document.getElementById('sheep-search').value;
    currentPage = 1;
    fetchSheeps(currentPage, searchTerm);
}

// Остальные функции (toggleForm, updateDeleteButtons, updatePagination) остаются без изменений
function toggleForm() {
    const form = document.getElementById('create-sheep-form');
    const button = document.getElementById('toggle-create-sheep-form');
    
    if (form.style.display === 'none' || form.style.display === '') {
        form.style.display = 'block';
        button.textContent = '▲ Скрыть форму создания овцы';
    } else {
        form.style.display = 'none';
        button.textContent = '▼ Создать овцу';
    }
}

let selectedSheeps = new Map(); // Хранение {id: true/false}

// Функция для управления чекбоксами всех записей
function toggleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.select-sheep');
    checkboxes.forEach(cb => {
        const tagNumber= cb.dataset.tag;

        cb.checked = checkbox.checked;
        selectedSheeps.set(tagNumber, { tag: tagNumber, isSelected: checkbox.checked });
    });
    console.log('Текущее состояние selectedSheeps после выбора всех:', selectedSheeps);
    toggleDeleteButton();
}

// Функция для управления отдельным чекбоксом
function toggleSelectSheep(checkbox) {
    const tagNumber = checkbox.dataset.tag;

    selectedSheeps.set(tagNumber, { tag: tagNumber, isSelected: checkbox.checked });
    console.log('Текущее состояние selectedSheeps: \n', selectedSheeps);
    toggleDeleteButton();
}

// Функция для отображения кнопки удаления
function toggleDeleteButton() {
    const deleteButton = document.getElementById('delete-selected-button');
    const archiveButton = document.getElementById('archive-selected-button');
    const hasSelection = Array.from(selectedSheeps.values()).some(value => value.isSelected);

    deleteButton.style.display = hasSelection ? 'block' : 'none';
    archiveButton.style.display = hasSelection ? 'block' : 'none';
}

// Функция для удаления выбранных записей
async function deleteSelectedSheeps() {
    const selectedTags = Array.from(selectedSheeps.entries())
        .filter(([tagNumber, { isSelected }]) => isSelected)
        .map(([tagNumber]) => tagNumber);

    console.log('Выбранные для удаления:', selectedTags);

    if (selectedTags.length === 0) {
        alert('Нет выбранных записей для удаления');
        return;
    }

    const tags = selectedTags.map(item => item.tag);
    const modal = document.getElementById('delete-modal');
    const modalMessage = document.getElementById('delete-modal-message');
    const confirmButton = document.getElementById('delete-confirm-button');

    modalMessage.textContent = `Вы уверены, что хотите удалить следующие бирки: ${tags.join(', ')}?`;
    modal.style.display = 'block';

    confirmButton.onclick = async () => {
        try {
            for (const tag of selectedTags) {
                await apiRequest(`/animals/sheep/${tag}/`, 'DELETE');
                selectedSheeps.delete(tag);
            }
            alert('Выбранные записи успешно удалены');
            fetchSheeps(currentPage);
            toggleDeleteButton();
            modal.style.display = 'none';
        } catch (error) {
            console.error('Ошибка при удалении выбранных записей:', error);
            alert('Ошибка при удалении записей');
        }
    };
}

function openArchiveModal() {
    const modal = document.getElementById('archive-modal');
    modal.style.display = 'block';
    loadArchiveStatuses();
}

function closeArchiveModal() {
    const modal = document.getElementById('archive-modal');
    modal.style.display = 'none';
}

async function loadArchiveStatuses() {
    try {
        const statuses = await apiRequest('/veterinary/api/status/');
        const archiveStatuses = statuses.filter(status => ['Убыл', 'Убой', 'Продажа'].includes(status.status_type));

        const statusSelect = document.getElementById('archive-status-select');
        statusSelect.innerHTML = '';

        if (archiveStatuses.length === 0) {
            alert('Нет статусов для переноса в архив. Создайте необходимые статусы.');
            closeArchiveModal();
            return;
        }

        archiveStatuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.text = status.status_type;
            statusSelect.add(option);
        });
    } catch (error) {
        console.error('Ошибка при загрузке статусов:', error);
    }
}

async function applyArchiveStatus() {
    const selectedTags = Array.from(selectedSheeps.entries())
        .filter(([tagNumber, { isSelected }]) => isSelected)
        .map(([tagNumber]) => tagNumber);

    if (selectedTags.length === 0) {
        alert('Нет выбранных записей для переноса.');
        return;
    }

    const statusId = document.getElementById('archive-status-select').value;
    if (!statusId) {
        alert('Выберите статус.');
        return;
    }

    try {
        for (const tag of selectedTags) {
            await apiRequest(`/animals/sheep/${tag}/`, 'PATCH', { animal_status_id: statusId });
        }
        alert('Выбранные записи успешно перенесены в архив.');
        closeArchiveModal();
        fetchSheeps(currentPage);
    } catch (error) {
        console.error('Ошибка при переносе в архив:', error);
        alert('Ошибка при переносе записей.');
    }
}

function updatePagination(response) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';

    if (response.previous) {
        const prevButton = document.createElement('button');
        prevButton.innerText = 'Предыдущая';
        prevButton.onclick = () => {
            currentPage--;
            fetchSheeps(currentPage);
        };
        pagination.appendChild(prevButton);
    }

    if (response.next) {
        const nextButton = document.createElement('button');
        nextButton.innerText = 'Следующая';
        nextButton.onclick = () => {
            currentPage++;
            fetchSheeps(currentPage);
        };
        pagination.appendChild(nextButton);
    }

    const pageInfo = document.createElement('span');
    pageInfo.innerText = ` Страница ${currentPage}`;
    pagination.appendChild(pageInfo);
}

function closeDeleteModal() {
    const modal = document.getElementById('delete-modal');
    modal.style.display = 'none';
}

// Экспортируем функции для глобального доступа
window.toggleForm = toggleForm;
window.openArchiveModal = openArchiveModal;
window.closeArchiveModal = closeArchiveModal;
window.closeDeleteModal = closeDeleteModal;
window.applyArchiveStatus = applyArchiveStatus;
window.deleteSelectedSheeps = deleteSelectedSheeps;
window.toggleSelectAll = toggleSelectAll;
window.toggleSelectSheep = toggleSelectSheep;
window.toggleDeleteButton = toggleDeleteButton;