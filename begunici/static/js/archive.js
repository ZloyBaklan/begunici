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
        if (method === 'DELETE') return;
        return await response.json();
    } catch (error) {
        console.error('Ошибка сети:', error);
        throw error; // Пробрасываем ошибку для обработки в вызывающем коде
    }
    
}


async function fetchArchive() {
    const type = document.getElementById('type-filter').value; // Получаем выбранный тип из фильтра
    const url = `/animals/archive/${type ? `?type=${type}` : ''}`; // Формируем URL для запроса
    const tableBody = document.getElementById('archive-table-body');
    tableBody.innerHTML = ''; // Очищаем таблицу перед добавлением данных

    try {
        const data = await apiRequest(url); // Запрос данных архива

        if (data.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="6">Нет данных для отображения.</td></tr>`;
            return;
        }

        // Заполняем таблицу данными
        data.forEach(item => {
            const row = `
                <tr>
                    <td>${item.tag_number}</td>
                    <td>${item.animal_type}</td>
                    <td>${item.status}</td>
                    <td>${item.age}</td>
                    <td>${item.birth_date}</td>
                    <td>${item.place}</td>
                </tr>
            `;
            tableBody.innerHTML += row;
        });
    } catch (error) {
        console.error('Ошибка загрузки архива:', error);
        tableBody.innerHTML = `<tr><td colspan="6">Ошибка загрузки данных.</td></tr>`;
    }
}

// Автоматическая загрузка при открытии страницы
document.addEventListener('DOMContentLoaded', async () => {
    // Получаем параметр type из URL
    const params = new URLSearchParams(window.location.search);
    const type = params.get('type');

    if (type) {
        // Устанавливаем фильтр в поле выбора типа, если параметр передан
        const typeFilter = document.getElementById('type-filter');
        if (typeFilter) {
            typeFilter.value = type;
        }
    }

    // Загружаем данные архива с учетом типа
    await fetchArchive();
});
