import { apiRequest, formatDateToOutput } from "./utils.js";

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
        await apiRequest('/animals/ewe/', 'POST', data);
        alert('Ярка успешно создана');
        document.getElementById('create-ewe-form').reset();
        fetchEwes();
    } catch (error) {
        console.error('Ошибка создания ярки:', error);
        alert(`Ошибка: ${error.message}`);
    }
}

let currentPage = 1;
const pageSize = 10;

// Функция загрузки списка ярок
async function fetchEwes(page = 1, query = '') {
    try {
        const response = await apiRequest(`/animals/ewe/?page=${page}&page_size=${pageSize}&search=${encodeURIComponent(query)}`);
        const ewes = Array.isArray(response) ? response : response.results;

        if (ewes) {
            renderEwes(ewes);
            updatePagination(response);
        } else {
            console.error('Некорректный ответ от API:', response);
            alert('Ошибка: данные ярок не найдены.');
        }
    } catch (error) {
        console.error('Ошибка при загрузке ярок:', error);
        alert('Ошибка при загрузке списка ярок.');
    }
}

// Рендеринг списка ярок
function renderEwes(ewes) {
    const eweTable = document.getElementById('ewe-list');
    eweTable.innerHTML = '';
    ewes.forEach((ewe, index) => {
        const row = `<tr>
            <td>
                <input type="checkbox" 
                class="select-ewe"  
                data-tag="${ewe.tag.tag_number}">
            </td>
            <td>${(currentPage - 1) * pageSize + index + 1}</td>
            <td><a href="/animals/ewe/${ewe.tag.tag_number}/info/">${ewe.tag.tag_number}</a></td>
            <td style="background-color:${ewe.animal_status ? ewe.animal_status.color : '#FFFFFF'}">
                ${ewe.animal_status ? ewe.animal_status.status_type : 'Не указан'}
            </td>
            <td>${ewe.age || 'Не указан'}</td>
            <td>${ewe.place ? ewe.place.sheepfold : 'Не указано'}</td>
            <td>${ewe.weight_records && ewe.weight_records.length > 0 
                ? `${ewe.weight_records[0].weight_date}: ${ewe.weight_records[0].weight} кг` 
                : 'Нет записей'}</td>
            <td>${ewe.veterinary_history && ewe.veterinary_history.length > 0 
                ? `${formatDateToOutput(ewe.veterinary_history[0].date_of_care)}: ${ewe.veterinary_history[0].veterinary_care.care_name}` 
                : 'Нет записей'}</td>
            <td>${ewe.note || ''}</td>
        </tr>`;
        eweTable.innerHTML += row;
    });
    
    document.querySelectorAll('.select-ewe').forEach(cb => cb.addEventListener('click', e => toggleSelectEwe(e.target)))
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

// Функция поиска ярок
async function searchEwes() {
    const searchTerm = document.getElementById('ewe-search').value;
    currentPage = 1;
    fetchEwes(currentPage, searchTerm);
}

// Остальные функции
function toggleForm() {
    const form = document.getElementById('create-ewe-form');
    const button = document.getElementById('toggle-create-ewe-form');
    
    if (form.style.display === 'none' || form.style.display === '') {
        form.style.display = 'block';
        button.textContent = '▲ Скрыть форму создания ярки';
    } else {
        form.style.display = 'none';
        button.textContent = '▼ Создать ярку';
    }
}

let selectedEwes = new Map(); // Хранение {id: true/false}

// Функция для управления чекбоксами всех записей
function toggleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.select-ewe');
    checkboxes.forEach(cb => {
        const tagNumber= cb.dataset.tag;

        cb.checked = checkbox.checked;
        selectedEwes.set(tagNumber, { tag: tagNumber, isSelected: checkbox.checked });
    });
    console.log('Текущее состояние selectedEwes после выбора всех:', selectedEwes);
    toggleDeleteButton();
}

// Функция для управления отдельным чекбоксом
function toggleSelectEwe(checkbox) {
    const tagNumber = checkbox.dataset.tag;

    selectedEwes.set(tagNumber, { tag: tagNumber, isSelected: checkbox.checked });
    console.log('Текущее состояние selectedEwes: \n', selectedEwes);
    toggleDeleteButton();
}

// Функция для отображения кнопки удаления
function toggleDeleteButton() {
    const deleteButton = document.getElementById('delete-selected-button');
    const archiveButton = document.getElementById('archive-selected-button');
    const hasSelection = Array.from(selectedEwes.values()).some(value => value.isSelected);

    deleteButton.style.display = hasSelection ? 'block' : 'none';
    archiveButton.style.display = hasSelection ? 'block' : 'none';
}

// Функция для удаления выбранных записей
async function deleteSelectedEwes() {
    const selectedTags = Array.from(selectedEwes.entries())
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
                await apiRequest(`/animals/ewe/${tag}/`, 'DELETE');
                selectedEwes.delete(tag);
            }
            alert('Выбранные записи успешно удалены');
            fetchEwes(currentPage);
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
    const selectedTags = Array.from(selectedEwes.entries())
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
            await apiRequest(`/animals/ewe/${tag}/`, 'PATCH', { animal_status_id: statusId });
        }
        alert('Выбранные записи успешно перенесены в архив.');
        closeArchiveModal();
        fetchEwes(currentPage);
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
            fetchEwes(currentPage);
        };
        pagination.appendChild(prevButton);
    }

    if (response.next) {
        const nextButton = document.createElement('button');
        nextButton.innerText = 'Следующая';
        nextButton.onclick = () => {
            currentPage++;
            fetchEwes(currentPage);
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
window.deleteSelectedEwes = deleteSelectedEwes;
window.toggleSelectAll = toggleSelectAll;
window.toggleSelectEwe = toggleSelectEwe;
window.toggleDeleteButton = toggleDeleteButton;