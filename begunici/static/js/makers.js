// Функция для получения CSRF-токена из cookies
function getCSRFToken() {
    let cookieValue = null;
    const name = 'csrftoken';
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Функция для выполнения API-запросов
async function apiRequest(url, method = 'GET', body = null) {
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken(),
    };
    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            const errorData = await response.json();
            console.error(`Ошибка API [${response.status}]:`, errorData);
            throw new Error(errorData.detail || 'Ошибка API');
        }
        // Если это DELETE, не пытаемся обработать тело ответа
        if (method === 'DELETE') {
            return;
        }
        return await response.json();
    } catch (error) {
        console.error('Ошибка сети:', error);
        throw error; // Пробрасываем ошибку для обработки в вызывающем коде
    }
    
}

document.addEventListener('DOMContentLoaded', function () {
    fetchMakers();  // Загрузка списка производителей при загрузке страницы
    loadAnimalStatuses();
    loadPlaces();

    const createMakerButton = document.querySelector('#create-maker-button');
    if (createMakerButton) {
        createMakerButton.onclick = () => saveMaker();  // Привязываем событие к кнопке
    }
});

// Функция для загрузки статусов животных
async function loadAnimalStatuses() {
    try {
        const statuses = await apiRequest('/veterinary/status/');
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
        const places = await apiRequest('/veterinary/place/');
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


// Функция для создания/обновления производителя
async function saveMaker(isUpdate = false, makerId = null) {
    const method = isUpdate ? 'PUT' : 'POST';
    const url = isUpdate ? `/animals/maker/${makerId}/` : '/animals/maker/';

    const data = {
        tag: document.getElementById('tag').value,
        animal_status_id: parseInt(document.getElementById('animal_status').value), // Исправлено имя поля
        birth_date: document.getElementById('birth_date').value,
        plemstatus: document.getElementById('plemstatus').value,
        working_condition: document.getElementById('working_condition').value,
        note: document.getElementById('note').value,
        place_id: parseInt(document.getElementById('place').value), // Передаём ID места
        
    };

    console.log('Отправляемые данные:', data); // Логируем данные для отладки
    try {
        await apiRequest(url, method, data);
        alert(isUpdate ? 'Производитель успешно обновлен' : 'Производитель успешно создан');
        document.getElementById('create-maker-form').reset();
        fetchMakers();
        resetButton();
    } catch (error) {
        console.error('Ошибка при сохранении производителя:', error);
        alert(`Ошибка: ${error.message}`);
    }
}

// Функция для скрытия/показа формы создания производителя
function toggleForm() {
    const form = document.getElementById('create-maker-form');
    const toggleButton = document.getElementById('toggle-create-maker-form');
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
    toggleButton.innerText = form.style.display === 'none' ? '▼ Создать производителя' : '▲ Скрыть форму';
}

let currentPage = 1; // Текущая страница
const pageSize = 3; // Количество записей на странице
// Функция для загрузки списка производителей
async function fetchMakers(page = 1, query = '') {
    try {
        const response = await apiRequest(`/animals/maker/?page=${page}&page_size=${pageSize}&search=${encodeURIComponent(query)}`);
        console.log('Ответ от сервера:', response); // Логируем ответ от API
        const makerList = document.getElementById('maker-list');
        makerList.innerHTML = '';

        response.results.forEach((maker, index) => {
            const row = `<tr>
            <td>
                <input type="checkbox" class="select-maker" 
                data-id="${maker.id}" 
                data-tag="${maker.tag.tag_number}" 
                onclick="toggleSelectMaker(this)">
            </td>
            <td>${(page - 1) * pageSize + index + 1}</td>
            <td><a href="/animals/maker/${maker.tag.id}/">${maker.tag.tag_number}</a></td>
            <td style="background-color:${maker.animal_status ? maker.animal_status.color : '#FFFFFF'}">
                    ${maker.animal_status ? maker.animal_status.status_type : 'Нет статуса'}
            </td>
            <td>${maker.age ? `${maker.age} мес.` : 'Нет данных'}</td> <!-- Отображаем возраст в том виде, как он приходит из модели -->
            <td>${maker.place ? maker.place.sheepfold : 'Нет данных'}</td> <!-- Используем place.sheepfold -->
            <td>${maker.working_condition || 'Нет данных'}</td>
            <td>${maker.weight_records.length > 0 ? maker.weight_records[0] : 'Нет записей'}</td>
            <td>${maker.veterinary_history.length > 0 ? maker.veterinary_history[0] : 'Нет записей'}</td>
            <td>${maker.note}</td>
            </tr>`;
            makerList.innerHTML += row;
        });
        updateCheckboxStates(); // Восстанавливаем состояние чекбоксов
        updatePagination(response);
    } catch (error) {
        console.error('Ошибка при загрузке производителей:', error);
    }
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
        const makerId = cb.dataset.id;
        const tag = cb.dataset.tag;

        cb.checked = checkbox.checked;
        selectedMakers.set(makerId, { tag, isSelected: checkbox.checked });
    });
    console.log('Текущее состояние selectedMakers после выбора всех:', selectedMakers); // Отладочный вывод
    toggleDeleteButton();
}


// Функция для управления отдельным чекбоксом
function toggleSelectMaker(checkbox) {
    const makerId = checkbox.dataset.id;
    const tag = checkbox.dataset.tag;

    selectedMakers.set(makerId, { tag, isSelected: checkbox.checked });
    console.log('Текущее состояние selectedMakers:', selectedMakers); // Отладочный вывод
    toggleDeleteButton();
}


// Функция для отображения кнопки удаления
function toggleDeleteButton() {
    const deleteButton = document.getElementById('delete-selected-button');
    deleteButton.style.display = Array.from(selectedMakers.values()).some(value => value) ? 'block' : 'none';
}

// Обновление состояния чекбоксов при загрузке страницы
function updateCheckboxStates() {
    const checkboxes = document.querySelectorAll('.select-maker');
    checkboxes.forEach(cb => {
        const id = cb.dataset.id;
        if (selectedMakers.has(id)) {
            cb.checked = selectedMakers.get(id); // Устанавливаем состояние из selectedMakers
        }
    });
}


function getTagFromTable(makerId) {
    const row = document.querySelector(`.select-maker[data-id="${makerId}"]`);
    if (row) {
        return row.closest('tr').querySelector('td:nth-child(3)').innerText.trim(); // Извлекаем бирку
    }
    return 'Неизвестно';
}

// Функция для удаления выбранных записей
async function deleteSelectedMakers() {
    const selectedIds = Array.from(selectedMakers.entries())
        .filter(([id, { isSelected }]) => isSelected)
        .map(([id, { tag }]) => ({ id, tag }));

    console.log('Выбранные для удаления:', selectedIds); // Отладочный вывод

    if (selectedIds.length === 0) {
        alert('Нет выбранных записей для удаления');
        return;
    }

    const tags = selectedIds.map(item => item.tag);
    const confirmMessage = `Вы уверены, что хотите удалить следующие бирки: ${tags.join(', ')}?`;
    if (!confirm(confirmMessage)) return;

    try {
        for (const { id } of selectedIds) {
            await apiRequest(`/animals/maker/${id}/`, 'DELETE');
            selectedMakers.delete(id); // Удаляем из состояния
        }
        alert('Выбранные записи успешно удалены');
        fetchMakers(currentPage); // Обновляем текущую страницу
        toggleDeleteButton(); // Скрываем кнопку
    } catch (error) {
        console.error('Ошибка при удалении выбранных записей:', error);
        alert('Ошибка при удалении записей');
    }
}


// Обновление функции редактирования для работы с новым полем
async function editMaker(makerId) {
    try {
        const maker = await apiRequest(`/animals/maker/${makerId}/`);

        // Заполняем поля формы
        document.getElementById('tag').value = maker.tag.tag_number;  // Бирка
        document.getElementById('animal_status').value = maker.animal_status ? maker.animal_status.id : '';  // Статус
        document.getElementById('birth_date').value = maker.birth_date;
        document.getElementById('note').value = maker.note;
        document.getElementById('plemstatus').value = maker.plemstatus;
        document.getElementById('working_condition').value = maker.working_condition;
        document.getElementById('place').value = maker.place ? maker.place.id : '';  // Статус;

        const createButton = document.getElementById('create-maker-button');
        createButton.innerText = 'Сохранить изменения';
        createButton.setAttribute('data-id', makerId);
        createButton.onclick = () => saveMaker(true, makerId);
    } catch (error) {
        console.error('Ошибка при редактировании производителя:', error);
    }
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


