import { apiRequest, formatDateToOutput } from "./utils.js";

document.addEventListener('DOMContentLoaded', function () {
    fetchMakers();  // Загрузка списка производителей при загрузке страницы
    loadAnimalStatuses();
    loadPlaces();
    setupArchiveButton(); // Устанавливаем URL для кнопки архива

    const createMakerButton = document.querySelector('#create-maker-button');
    if (createMakerButton) {
        createMakerButton.onclick = saveMaker;  // Привязываем событие к кнопке
    }
});

// Функция для загрузки статусов животных
async function loadAnimalStatuses() {
    try {
        const statuses = await apiRequest('/veterinary/api/status/');
        const statusSelect = document.getElementById('animal_status');
        statusSelect.innerHTML = '';
        statuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.text = status.status_type;
            statusSelect.add(option);
        });
    } catch (error) {
        console.error('Ошибка при загрузке статусов животных:', error);
    }
}

// Функция для загрузки мест (овчарня и отсек)
async function loadPlaces() {
    try {
        const places = await apiRequest('/veterinary/api/place/');
        const sheepfoldSelect = document.getElementById('place');
        sheepfoldSelect.innerHTML = '';
        places.forEach(place => {
            const sheepfoldOption = document.createElement('option');
            sheepfoldOption.value = place.id;
            sheepfoldOption.text = place.sheepfold;
            sheepfoldSelect.add(sheepfoldOption);
        });
    } catch (error) {
        console.error('Ошибка при загрузке мест:', error);
    }
}


// Функция для скрытия/показа формы создания производителя
function toggleForm() {
    const form = document.getElementById('create-maker-form');
    const toggleButton = document.getElementById('toggle-create-maker-form');
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
    toggleButton.innerText = form.style.display === 'none' ? '▼ Создать производителя' : '▲ Скрыть форму';
}

// Создание нового производителя
async function saveMaker() {
    const url = '/animals/maker/';
    const method = 'POST';

    const data = {
        tag_number: document.getElementById('tag').value,
        animal_status_id: parseInt(document.getElementById('animal_status').value),
        birth_date: document.getElementById('birth_date').value,
        plemstatus: document.getElementById('plemstatus').value,
        working_condition: document.getElementById('working_condition').value,
        note: document.getElementById('note').value,
        place_id: parseInt(document.getElementById('place').value), // Передаём ID места,
    };
    
    console.log('Отправляемые данные:', data); // Логируем данные для отладки

    if (!data.tag_number || !data.animal_status_id || !data.place_id) {
        alert('Пожалуйста, заполните обязательные поля: бирка, статус, место.');
        return;
    }

    try {
        await apiRequest(url, method, data);
        alert('Производитель успешно создан');
        document.getElementById('create-maker-form').reset();
        fetchMakers();
    } catch (error) {
        console.error('Ошибка при создании производителя:', error);
        alert('Ошибка: Проверьте корректность введенных данных');
    }
}


let currentPage = 1; // Текущая страница
const pageSize = 10; // Количество записей на странице

// Загрузка списка производителей
async function fetchMakers(page = 1, query = '') {
    try {
        const response = await apiRequest(`/animals/maker/?page=${page}&page_size=${pageSize}&search=${encodeURIComponent(query)}`);

        // Проверка структуры ответа
        const makers = Array.isArray(response) ? response : response.results;

        if (makers) {
            renderMakers(makers);
            updatePagination(response);
        } else {
            console.error('Некорректный ответ от API:', response);
            alert('Ошибка: данные производителей не найдены.');
        }
    } catch (error) {
        console.error('Ошибка при загрузке производителей:', error);
        alert('Ошибка при загрузке списка производителей.');
    }
}


// Рендеринг списка производителей
function renderMakers(makers) {
    const makerList = document.getElementById('maker-list');
    makerList.innerHTML = '';
    makers.forEach((maker, index) => {
        const row = `<tr>
            <td>
                <input type="checkbox" 
                class="select-maker"  
                data-tag="${maker.tag.tag_number}">
            </td>
            <td>${(currentPage - 1) * pageSize + index + 1}</td>
            <td><a href="/animals/maker/${maker.tag.tag_number}/info/">${maker.tag.tag_number}</a></td>
            <td style="background-color:${maker.animal_status ? maker.animal_status.color : '#FFFFFF'}">
                ${maker.animal_status ? maker.animal_status.status_type : 'Нет статуса'}
            </td>
            <td>${maker.age ? `${maker.age} мес.` : 'Нет данных'}</td>
            <td>${maker.place ? maker.place.sheepfold : 'Нет данных'}</td>
            <td>${maker.weight_records && maker.weight_records.length > 0 
                ? `${maker.weight_records[0].weight_date}: ${maker.weight_records[0].weight} кг` 
                : 'Нет записей'}</td>
            <td>${maker.veterinary_history && maker.veterinary_history.length > 0 
                ? (() => {
                    const lastVet = maker.veterinary_history[0];
                    let displayText = `${formatDateToOutput(lastVet.date_of_care)}: ${lastVet.veterinary_care.care_name}`;
                    
                    // Добавляем информацию о сроке действия
                    if (lastVet.duration_days !== undefined && lastVet.duration_days !== null) {
                        if (lastVet.duration_days === 0) {
                            displayText += ' (Бессрочно)';
                        } else {
                            // Вычисляем оставшиеся дни
                            const careDate = new Date(lastVet.date_of_care);
                            const expiryDate = new Date(careDate);
                            expiryDate.setDate(careDate.getDate() + lastVet.duration_days);
                            
                            // Получаем текущую дату в московском времени
                            const today = new Date();
                            const moscowOffset = 3 * 60; // 3 часа в минутах
                            const utc = today.getTime() + (today.getTimezoneOffset() * 60000);
                            const moscowTime = new Date(utc + (moscowOffset * 60000));
                            
                            const remainingDays = Math.ceil((expiryDate - moscowTime) / (1000 * 60 * 60 * 24));
                            
                            // Убираем все дополнительные сообщения о статусе
                        }
                    }
                    
                    return displayText;
                })()
                : 'Нет записей'}</td>
            <td>${maker.working_condition || 'Нет данных'}</td>
            <td>${maker.note}</td>
        </tr>`;
        makerList.innerHTML += row;
    });
    
    document.querySelectorAll('.select-maker').forEach(cb => cb.addEventListener('click', e => toggleSelectMaker(e.target)))
}



// Получение цвета для статуса
function getColorForStatus(status) {
    if (!status) return 'black';
    switch (status.status_type) {
        case 'Ветобработка': return 'green';
        case 'Убой': return 'red';
        default: return 'black';
    }
}

let selectedMakers = new Map(); // Хранение {id: true/false}

// Функция для управления чекбоксами всех записей
function toggleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.select-maker');
    checkboxes.forEach(cb => {
        const tagNumber= cb.dataset.tag;

        cb.checked = checkbox.checked;
        selectedMakers.set(tagNumber, { tag: tagNumber, isSelected: checkbox.checked });
    });
    console.log('Текущее состояние selectedMakers после выбора всех:', selectedMakers); // Отладочный вывод
    toggleDeleteButton();
}


// Функция для управления отдельным чекбоксом
function toggleSelectMaker(checkbox) {
    const tagNumber = checkbox.dataset.tag;

    selectedMakers.set(tagNumber, { tag: tagNumber, isSelected: checkbox.checked });
    console.log('Текущее состояние selectedMakers: \n', selectedMakers); // Отладочный вывод
    toggleDeleteButton();
}


// Функция для отображения кнопки удаления
function toggleDeleteButton() {
    const selectedActionsDiv = document.getElementById('selected-actions');
    const hasSelection = Array.from(selectedMakers.values()).some(value => value.isSelected);

    selectedActionsDiv.style.display = hasSelection ? 'block' : 'none';
}

// Обновление состояния чекбоксов при загрузке страницы
function updateCheckboxStates() {
    const checkboxes = document.querySelectorAll('.select-maker');
    checkboxes.forEach(cb => {
        const tagNumber = cb.dataset.tag;
        if (selectedMakers.has(tagNumber)) {
            cb.checked = selectedMakers.get(tagNumber).isSelected; // Устанавливаем состояние из selectedMakers
        }
    });
}


function getTagFromTable(tagNumber) {
    const row = document.querySelector(`.select-maker[data-tag="${tagNumber}"]`);
    if (row) {
        return row.closest('tr').querySelector('td:nth-child(3)').innerText.trim(); // Извлекаем бирку
    }
    return 'Неизвестно';
}

// Функция для удаления выбранных записей
async function deleteSelectedMakers() {
    const selectedTags = Array.from(selectedMakers.entries())
        .filter(([tagNumber, { isSelected }]) => isSelected)
        .map(([tagNumber]) => tagNumber);


    console.log('Выбранные для удаления:', selectedTags); // Отладочный вывод

    if (selectedTags.length === 0) {
        alert('Нет выбранных записей для удаления');
        return;
    }

    // Подготавливаем список бирок для отображения
    const tags = selectedTags.map(item => item.tag);
    const modal = document.getElementById('delete-modal');
    const modalMessage = document.getElementById('delete-modal-message');
    const confirmButton = document.getElementById('delete-confirm-button');

    modalMessage.textContent = `Вы уверены, что хотите удалить следующие бирки: ${tags.join(', ')}?`;
    modal.style.display = 'block';

    confirmButton.onclick = async () => {
        try {
            for (const tag of selectedTags) {
                await apiRequest(`/animals/maker/${tag}/`, 'DELETE');
                selectedMakers.delete(tag); // Удаляем из состояния
            }
            alert('Выбранные записи успешно удалены');
            
            // Очищаем все выбранные элементы
            selectedMakers.clear();
            
            // Снимаем галочку с "выбрать все"
            const selectAllCheckbox = document.getElementById('select-all');
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = false;
            }
            
            fetchMakers(currentPage); // Обновляем текущую страницу
            toggleDeleteButton(); // Скрываем кнопки
            modal.style.display = 'none'; // Закрываем модальное окно
        } catch (error) {
            console.error('Ошибка при удалении выбранных записей:', error);
            alert('Ошибка при удалении записей');
        }
    };
}


function closeDeleteModal() {
    const modal = document.getElementById('delete-modal');
    modal.style.display = 'none';
}


// Функция для сброса состояния кнопки
function resetButton() {
    const createButton = document.getElementById('create-maker-button');
    createButton.innerText = 'Создать производителя';
    createButton.removeAttribute('data-id');
    createButton.onclick = () => saveMaker();
}

function updatePagination(response) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = ''; // Очищаем старую навигацию

    if (response.previous) {
        const prevButton = document.createElement('button');
        prevButton.innerText = 'Предыдущая';
        prevButton.onclick = () => {
            currentPage--;
            fetchMakers(currentPage);
        };
        pagination.appendChild(prevButton);
    }

    if (response.next) {
        const nextButton = document.createElement('button');
        nextButton.innerText = 'Следующая';
        nextButton.onclick = () => {
            currentPage++;
            fetchMakers(currentPage);
        };
        pagination.appendChild(nextButton);
    }

    const pageInfo = document.createElement('span');
    pageInfo.innerText = ` Страница ${currentPage}`;
    pagination.appendChild(pageInfo);
}

document.getElementById('maker-search').addEventListener('input', () => {
    const query = document.getElementById('maker-search').value.trim();
    console.log('Поисковый запрос:', query); // Проверяем, вызывается ли событие
    currentPage = 1; // Сбрасываем на первую страницу
    fetchMakers(currentPage, query);
});


function openArchiveModal() {
    const modal = document.getElementById('archive-modal');
    modal.style.display = 'block';

    // Устанавливаем текущую дату
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('archive-status-date').value = today;

    loadArchiveStatuses();
}

// Экспортируем функцию для глобального доступа
window.openArchiveModal = openArchiveModal;

function closeArchiveModal() {
    const modal = document.getElementById('archive-modal');
    modal.style.display = 'none';
}

// Экспортируем функцию для глобального доступа
window.closeArchiveModal = closeArchiveModal;

async function loadArchiveStatuses() {
    try {
        const statuses = await apiRequest('/veterinary/api/status/');
        const archiveStatuses = statuses.filter(status => ['Убыл', 'Убой', 'Продажа'].includes(status.status_type));

        const statusSelect = document.getElementById('archive-status-select');
        statusSelect.innerHTML = ''; // Очистка существующих опций

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
    const selectedTags = Array.from(selectedMakers.entries())
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

    const statusDate = document.getElementById('archive-status-date').value;
    if (!statusDate) {
        alert('Укажите дату присвоения статуса.');
        return;
    }

    try {
        for (const tag of selectedTags) {
            await apiRequest(`/animals/maker/${tag}/`, 'PATCH', { 
                animal_status_id: statusId,
                status_date: statusDate
            });
        }
        alert('Выбранные записи успешно перенесены в архив.');
        
        // Очищаем все выбранные элементы
        selectedMakers.clear();
        
        // Снимаем галочку с "выбрать все"
        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }
        
        closeArchiveModal();
        fetchMakers(currentPage); // Обновляем текущую страницу
        toggleDeleteButton(); // Скрываем кнопки
    } catch (error) {
        console.error('Ошибка при переносе в архив:', error);
        alert('Ошибка при переносе записей.');
    }
}

// Экспортируем функции для глобального доступа
window.applyArchiveStatus = applyArchiveStatus;
window.deleteSelectedMakers = deleteSelectedMakers;
window.toggleSelectAll = toggleSelectAll;
window.toggleSelectMaker = toggleSelectMaker;
window.toggleDeleteButton = toggleDeleteButton;
window.saveMaker = saveMaker;
window.fetchMakers = fetchMakers;

function setupArchiveButton() {
    // Кнопка архива теперь находится в другом месте, не нужно настраивать href
    console.log('Archive button setup - using direct link in HTML');
}

// Функции экспорта теперь в export-common.js
