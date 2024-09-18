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

// Функция для отправки данных через fetch
async function sendData(url, data) {
    try {
        const csrfToken = getCSRFToken();
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

// Логика обработки кнопок будет здесь
import { getVeterinaryData, createVeterinaryData } from './vet_statuses.js';
import { getAnimalData, createAnimalData } from './maker.js';

// Обработчики для показа данных
document.getElementById('show-status-list').addEventListener('click', function () {
    showList('/api/status/', 'status-list', ['status_type']);
});

document.getElementById('show-place-list').addEventListener('click', function () {
    showList('/api/place/', 'place-list', ['sheepfold', 'compartment']);
});

document.getElementById('show-veterinary-care-list').addEventListener('click', function () {
    showList('/api/veterinary-care/', 'veterinary-care-list', ['care_type']);
});

// При необходимости можно добавить другие обработчики для других вкладок
