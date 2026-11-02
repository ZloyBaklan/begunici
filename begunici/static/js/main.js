function getAnimalPurposeText(animal) {
    const purposes = [];
    if (animal.is_reject) purposes.push('Брак');
    if (animal.is_for_sale) purposes.push('К продаже');
    if (animal.is_in_treatment) purposes.push('Лечение');
    return purposes.join(', ') || '-';
}

function getAnimalPurposeRowClass(animal) {
    if (animal.is_reject && animal.is_for_sale) return 'animal-reject-for-sale';
    if (animal.is_for_sale) return 'animal-for-sale';
    return animal.is_reject ? 'table-warning' : '';
}

// CLINICAL BRIDGE: the server supplies a relative URL after refusing a transition.
window.handleClinicalTransition = function(data) {
    const raw = data?.treatment_url;
    const url = Array.isArray(raw) ? raw[0] : raw;
    if (typeof url !== 'string' || !/^\/animals\/treatment\/\d+\//.test(url)) return false;
    if (confirm('Животное находится на лечении. Сначала нужно подтвердить исход и расход препаратов. Перейти к завершению лечения?')) location.href = url;
    return true;
};

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
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
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


// При необходимости можно добавить другие обработчики для других вкладок
