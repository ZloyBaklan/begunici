// Получение CSRF-токена
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

document.addEventListener('DOMContentLoaded', function () {
    fetchMakers();  // Загрузка списка производителей при загрузке страницы

    const createMakerButton = document.querySelector('#create-maker-button');
    if (createMakerButton) {
        createMakerButton.onclick = handleCreateOrUpdateMaker;  // Привязываем событие к кнопке
    }
});

// Функция для создания/обновления производителя
function handleCreateOrUpdateMaker() {
    const makerId = this.getAttribute('data-id');
    if (makerId) {
        updateMaker(makerId);  // Обновление производителя
    } else {
        createMaker();  // Создание нового производителя
    }
}

// Функция создания нового производителя
async function createMaker() {
    const tag = document.getElementById('tag').value;
    const animalStatus = document.getElementById('animal_status').value;
    const birthDate = document.getElementById('birth_date').value;
    const note = document.getElementById('note').value;
    const plemstatus = document.getElementById('plemstatus').value;
    const workingCondition = document.getElementById('working_condition').value;

    const data = {
        tag: tag,
        animal_status: animalStatus,
        birth_date: birthDate,
        note: note,
        plemstatus: plemstatus,
        working_condition: workingCondition
    };

    try {
        const response = await fetch('/animals/maker/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify(data),
        });

        if (response.ok) {
            alert('Производитель успешно создан');
            document.getElementById('create-maker-form').reset();  // Очистка формы
            fetchMakers();  // Обновляем список производителей
            resetButton();  // Сбросить состояние кнопки
        } else {
            const result = await response.json();
            alert('Ошибка создания производителя: ' + result.detail);
        }
    } catch (error) {
        console.error('Ошибка при создании производителя:', error);
    }
}


// Функция для загрузки списка производителей
async function fetchMakers() {
    try {
        const response = await fetch('/animals/maker/');
        if (!response.ok) {
            throw new Error('Ошибка при загрузке списка производителей');
        }

        const makers = await response.json();
        const makerList = document.getElementById('maker-list');
        makerList.innerHTML = '';  // Очистка таблицы

        makers.forEach((maker, index) => {
            const row = `<tr>
                <td>${index + 1}</td>
                <td>${maker.tag.tag_number}</td>  <!-- Из AnimalBase -->
                <td>${maker.animal_status ? maker.animal_status.status_type : 'Нет статуса'}</td>  <!-- Из AnimalBase -->
                <td>${maker.birth_date}</td>  <!-- Из AnimalBase -->
                <td>${maker.plemstatus}</td>  <!-- Специфично для Maker -->
                <td>${maker.working_condition}</td>  <!-- Специфично для Maker -->
                <td>
                    <button onclick="editMaker(${maker.id})">Редактировать</button>
                    <button onclick="deleteMaker(${maker.id})">Удалить</button>
                </td>
                <td>${maker.note}</td>  <!-- Из AnimalBase -->
            </tr>`;
            makerList.innerHTML += row;
        });
    } catch (error) {
        console.error('Ошибка при загрузке производителей:', error);
    }
}


// Функция для удаления производителя
async function deleteMaker(makerId) {
    if (!confirm('Вы уверены, что хотите удалить производителя?')) return;

    try {
        const response = await fetch(`/animals/maker/${makerId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCSRFToken(),
            },
        });

        if (response.ok) {
            alert('Производитель успешно удален');
            fetchMakers();  // Обновляем список после удаления
        } else {
            alert('Ошибка при удалении производителя');
        }
    } catch (error) {
        console.error('Ошибка при удалении производителя:', error);
    }
}

// Функция для редактирования производителя
async function editMaker(makerId) {
    try {
        const response = await fetch(`/animals/maker/${makerId}/`);
        if (!response.ok) {
            throw new Error('Ошибка при получении данных производителя');
        }
        const maker = await response.json();

        // Заполняем форму данными производителя для редактирования
        document.getElementById('tag').value = maker.tag;
        document.getElementById('animal_status').value = maker.animal_status;
        document.getElementById('birth_date').value = maker.birth_date;
        document.getElementById('note').value = maker.note;

        // Поля специфичные для Maker
        document.getElementById('plemstatus').value = maker.plemstatus;
        document.getElementById('working_condition').value = maker.working_condition;

        // Меняем поведение кнопки "Создать" на "Сохранить"
        const createButton = document.getElementById('create-maker-button');
        createButton.innerText = 'Сохранить изменения';
        createButton.setAttribute('data-id', makerId);  // Привязываем id производителя к кнопке
        createButton.setAttribute('onclick', `updateMaker(${makerId})`);  // Меняем действие на обновление
    } catch (error) {
        console.error('Ошибка при редактировании производителя:', error);
    }
}


// Функция для обновления производителя
async function updateMaker(makerId) {
    const tag = document.getElementById('tag').value;
    const animalStatus = document.getElementById('animal_status').value;
    const birthDate = document.getElementById('birth_date').value;
    const note = document.getElementById('note').value;
    const plemstatus = document.getElementById('plemstatus').value;
    const workingCondition = document.getElementById('working_condition').value;

    const data = {
        tag: tag,
        animal_status: animalStatus,
        birth_date: birthDate,
        note: note,
        plemstatus: plemstatus,
        working_condition: workingCondition
    };

    try {
        const response = await fetch(`/animals/maker/${makerId}/`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify(data),
        });

        if (response.ok) {
            alert('Производитель успешно обновлен');
            document.getElementById('create-maker-form').reset();  // Очистка формы
            fetchMakers();  // Обновляем список производителей
            resetButton();  // Сбросить состояние кнопки
        } else {
            const result = await response.json();
            alert('Ошибка обновления производителя: ' + result.detail);
        }
    } catch (error) {
        console.error('Ошибка при обновлении производителя:', error);
    }
}

// Функция для поиска производителей
function searchMakers() {
    const input = document.getElementById('maker-search').value.toLowerCase();
    const table = document.getElementById('maker-list');
    const rows = table.getElementsByTagName('tr');

    for (let i = 0; i < rows.length; i++) {
        const cells = rows[i].getElementsByTagName('td');
        if (cells.length > 0) {
            const makerName = cells[1].innerText.toLowerCase();
            if (makerName.indexOf(input) > -1) {
                rows[i].style.display = '';
            } else {
                rows[i].style.display = 'none';
            }
        }
    }
}

// Сброс состояния кнопки
function resetButton() {
    const createButton = document.getElementById('create-maker-button');
    createButton.innerText = 'Создать производителя';
    createButton.removeAttribute('data-id');  // Удаляем id, чтобы кнопка снова создавала, а не обновляла
    createButton.setAttribute('onclick', 'createMaker()');  // Возвращаем действие создания
}