// Функция для получения CSRF-токена из cookie
function getCSRFToken() {
    let csrfToken = null;
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.startsWith('csrftoken=')) {
            csrfToken = cookie.substring('csrftoken='.length, cookie.length);
            break;
        }
    }
    return csrfToken;
}

// Функция для переключения вкладок
function showTab(tabId) {
    console.log("Переключение на вкладку:", tabId);
    const createContent = document.getElementById('create-content');
    const showContent = document.getElementById('show-content');

    // Скрываем все вкладки
    createContent.style.display = 'none';
    showContent.style.display = 'none';

    // Показываем выбранную вкладку
    document.getElementById(tabId).style.display = 'block';
}

// Функция для показа нужной формы
function showForm(formId) {
    // Скрыть все формы
    const forms = ['create-status-form', 'create-place-form', 'create-vetcare-form'];
    forms.forEach(form => document.getElementById(form).style.display = 'none');

    // Показать нужную форму
    document.getElementById(formId).style.display = 'block';
}

// Функция для отправки данных через fetch (вы уже используете ее)
async function sendData(url, data) {
    try {
        const csrfToken = getCSRFToken();  // Получаем CSRF токен
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const errorData = await response.json();
            console.error('Ошибка при отправке данных:', errorData);
        } else {
            const responseData = await response.json();
            console.log('Данные успешно отправлены:', responseData);
            alert('Объект успешно создан');
        }
    } catch (error) {
        console.error('Ошибка сети:', error);
    }
}

// Загрузка страницы с первой вкладкой
document.addEventListener('DOMContentLoaded', function () {
    showTab('create-content');
});

// Общие обработчики форм (используем один обработчик для каждой формы)
document.getElementById('status-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    const statusType = document.getElementById('status-type').value;
    const currentDate = new Date().toISOString().split('T')[0];  // Получаем текущую дату в формате YYYY-MM-DD
    await sendData('/api/status/', { status_type: statusType, date_of_status: currentDate });
    await getData('/api/status/', 'status-list', ['id', 'status_type']);  // Обновить список после создания
});

document.getElementById('place-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    const sheepfold = document.getElementById('sheepfold').value;
    const compartment = document.getElementById('compartment').value;
    await sendData('/api/place/', { sheepfold: sheepfold, compartment: compartment });
    await getData('/api/place/', 'place-list', ['id', 'sheepfold', 'compartment']);  // Обновить список после создания
});

document.getElementById('veterinary-care-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    const careType = document.getElementById('care-type').value;
    await sendData('/api/veterinary-care/', { care_type: careType });
    await getData('/api/veterinary-care/', 'veterinary-care-list', ['id', 'care_type']);  // Обновить список после создания
});


// Функция для скрытия всех списков
function hideAllLists() {
    document.getElementById('status-list').style.display = 'none';
    document.getElementById('place-list').style.display = 'none';
    document.getElementById('veterinary-care-list').style.display = 'none';
}

// Функция для получения данных с сервера и обновления списка в таблице
async function showList(url, listElementId, headers) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error('Ошибка загрузки данных');
        }

        const data = await response.json();
        const listElement = document.getElementById(listElementId);
        listElement.innerHTML = '';  // Полная очистка перед новым рендером

        // Создаем таблицу только если есть данные
        if (data.results.length > 0) {
            let table = '<table>';
            
            // Заголовки таблицы
            let headerRow = '<tr>';
            headerRow += '<th>№</th>';  // Добавляем столбец для нумерации
            headers.forEach(header => {
                headerRow += `<th>${header}</th>`;
            });
            headerRow += '</tr>';
            table += headerRow;

            // Заполняем таблицу данными
            data.results.forEach((item, index) => {
                let row = '<tr>';
                row += `<td>${index + 1}</td>`;  // Нумерация
                headers.forEach(header => {
                    row += `<td>${item[header]}</td>`;
                });
                row += '</tr>';
                table += row;
            });

            table += '</table>';
            listElement.innerHTML = table;  // Вставляем таблицу в HTML
        } else {
            listElement.innerHTML = '<p>Нет данных для отображения.</p>';
        }
    } catch (error) {
        console.error('Ошибка при получении данных:', error);
    }
}


function showTabContent(listElementId) {
    const allLists = ['status-list', 'place-list', 'veterinary-care-list'];

    // Скрыть все списки
    allLists.forEach(list => {
        document.getElementById(list).style.display = 'none';
    });

    // Показать только нужный список
    document.getElementById(listElementId).style.display = 'block';
}

// Обработчики для кнопок показа
document.getElementById('show-status-list').addEventListener('click', function () {
    showTabContent('status-list');
    showList('/api/status/', 'status-list', ['status_type']);
});

document.getElementById('show-place-list').addEventListener('click', function () {
    showTabContent('place-list');
    showList('/api/place/', 'place-list', ['sheepfold', 'compartment']);
});

document.getElementById('show-veterinary-care-list').addEventListener('click', function () {
    showTabContent('veterinary-care-list');
    showList('/api/veterinary-care/', 'veterinary-care-list', ['care_type']);
});




// Функция для подгрузки данных в выпадающие списки
async function loadSelectOptions(url, selectElementId, displayField) {
    try {
        const response = await fetch(url);
        const data = await response.json();

        const selectElement = document.getElementById(selectElementId);
        selectElement.innerHTML = '';  // Очистить старые опции

        data.results.forEach(item => {
            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = item[displayField];  // Отображаемое значение
            selectElement.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка при загрузке данных:', error);
    }
}

// Функция для отправки данных через fetch для создания объекта Maker
async function createMaker(url, data) {
    try {
        const csrfToken = getCSRFToken();
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const errorData = await response.json();
            console.error('Ошибка при создании производителя:', errorData);
        } else {
            const responseData = await response.json();
            console.log('Производитель успешно создан:', responseData);
            alert('Производитель успешно создан');
        }
    } catch (error) {
        console.error('Ошибка сети:', error);
    }
}

// Подгрузка данных в выпадающие списки при загрузке формы создания Maker
document.getElementById('create-maker-form').addEventListener('show', function () {
    loadSelectOptions('/api/tags/', 'maker-tag', 'tag_number');  // Подгружаем бирки
    loadSelectOptions('/api/status/', 'maker-status', 'status_type');  // Подгружаем статусы
    loadSelectOptions('/api/place/', 'maker-place', 'sheepfold');  // Подгружаем места
    loadSelectOptions('/api/veterinary-care/', 'maker-veterinary-care', 'care_type');  // Подгружаем ветобработки
});

// Обработчик для формы создания производителя
document.getElementById('maker-form').addEventListener('submit', function (e) {
    e.preventDefault();
    const makerData = {
        tag: document.getElementById('maker-tag').value,
        animal_status: document.getElementById('maker-status').value,
        birth_date: document.getElementById('maker-birth-date').value,
        last_weight: document.getElementById('maker-last-weight').value,
        last_weight_date: document.getElementById('maker-last-weight-date').value,
        working_condition: document.getElementById('maker-working-condition').value,
        place: document.getElementById('maker-place').value,
        veterinary_care: document.getElementById('maker-veterinary-care').value,
        plemstatus: document.getElementById('maker-plemstatus').value,
    };

    createMaker('/api/maker/', makerData)  // Указываем путь для API
        .then(() => getData('/api/maker/', 'maker-table', ['tag', 'animal_status', 'birth_date']));  // Обновляем список производителей
});