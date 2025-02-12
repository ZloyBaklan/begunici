// Обновленный функционал аналитики (maker_analytics.js)

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




document.addEventListener('DOMContentLoaded', async () => {
    const makerId = document.getElementById('analytics-detail').dataset.makerId;

    try {
        await loadWeightHistory(makerId);
        await loadChildren(makerId);
        await loadVetCalendar(makerId);
        await loadStatusHistory(makerId);
        await loadPlaceHistory(makerId);
    } catch (error) {
        console.error('Ошибка загрузки данных аналитики:', error);
    }
});

async function loadWeightHistory(makerId) {
    try {
        const response = await apiRequest(`/animals/maker/${makerId}/weight_history/`);
        const weightData = response.map(record => ({
            date: new Date(record.weight_date),
            weight: parseFloat(record.weight),
        }));

        renderWeightChart(weightData);
    } catch (error) {
        console.error('Ошибка загрузки истории веса:', error);
    }
}

function renderWeightChart(data) {
    const ctx = document.getElementById('weight-chart').getContext('2d');
    const chartData = {
        labels: data.map(item => item.date.toLocaleDateString()),
        datasets: [{
            label: 'Вес (кг)',
            data: data.map(item => item.weight),
            borderWidth: 1,
        }],
    };
    new Chart(ctx, {
        type: 'line',
        data: chartData,
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: true,
                },
            },
        },
    });
}

const analyticsPageSize = 3;

async function loadChildren(makerId, page = 1) {
    try {
        const response = await apiRequest(`/animals/maker/${makerId}/children/?page=${page}&page_size=${analyticsPageSize}`);
        console.log('Дети:', response); // Убедитесь, что объект приходит корректно

        const childrenList = document.getElementById('children-list');
        const prevButton = document.getElementById('children-prev');
        const nextButton = document.getElementById('children-next');

        childrenList.innerHTML = '';

        response.results.forEach(child => {
            console.log('Ссылка:', child.link); // Проверьте наличие 'link' <td><a href="${child.link}">${child.tag_number}</a></td>
            const row = document.createElement('tr');
            row.innerHTML = `
                
                <td>
                    ${child.is_archived ? `<span style="color: red; cursor: pointer;" onclick="onChildClick(${makerId}, ${child.id})">${child.tag_number}</span>` :
                    `<a href="#" onclick="onChildClick(${makerId}, ${child.id})">${child.tag_number}</a>`}
                </td>
                <td>${child.animal_type}</td>
                <td>${child.age}</td>
            `;
            childrenList.appendChild(row);
        });
        prevButton.disabled = !response.previous;
        nextButton.disabled = !response.next;

        prevButton.onclick = () => loadChildren(makerId, page - 1);
        nextButton.onclick = () => loadChildren(makerId, page + 1);

        document.getElementById('children-count').textContent = response.count;;
    } catch (error) {
        console.error('Ошибка загрузки детей:', error);
    }
}


async function loadVetCalendar(makerId, page = 1) {
    try {
        const response = await apiRequest(`/animals/maker/${makerId}/vet_history/?page=${page}&page_size=${analyticsPageSize}`);
        const Vetcalendar = document.getElementById('vet-calendar');
        const prevButton = document.getElementById('vet-calendar-prev');
        const nextButton = document.getElementById('vet-calendar-next');

        Vetcalendar.innerHTML = '';

        response.results.forEach(entry => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${entry.date_of_care}</td>
                <td>${entry.veterinary_care.care_name || 'Не указано'}</td>
            `;
            Vetcalendar.appendChild(row);
        });

        prevButton.disabled = !response.previous;
        nextButton.disabled = !response.next;

        prevButton.onclick = () => loadVetCalendar(makerId, page - 1);
        nextButton.onclick = () => loadVetCalendar(makerId, page + 1);

    } catch (error) {
        console.error('Ошибка загрузки календаря ветобработок:', error);
    }
}

async function loadStatusHistory(makerId, page = 1) {
    try {
        const response = await apiRequest(`/animals/maker/${makerId}/status_history/?page=${page}&page_size=${analyticsPageSize}`);
        const statusHistoryList = document.getElementById('status-history-list');
        const prevButton = document.getElementById('status-history-prev');
        const nextButton = document.getElementById('status-history-next');

        statusHistoryList.innerHTML = '';

        response.results.forEach(record => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${record.new_status.date_of_status}</td>
                <td>${record.new_status.status_type}</td>
                <td>${record.old_status.status_type || 'Не указано'}</td>
                
            `;
            statusHistoryList.appendChild(row);
        });

        prevButton.disabled = !response.previous;
        nextButton.disabled = !response.next;

        prevButton.onclick = () => loadStatusHistory(makerId, page - 1);
        nextButton.onclick = () => loadStatusHistory(makerId, page + 1);

    } catch (error) {
        console.error('Ошибка загрузки истории статусов:', error);
    }
}


async function loadPlaceHistory(tagId, page = 1) {
    try {
        const response = await apiRequest(`/animals/maker/${tagId}/place_history/?page=${page}&page_size=${analyticsPageSize}`);
        console.log('Ответ API:', response);
        const placeHistoryList = document.getElementById('place-history');
        const prevButton = document.getElementById('place-history-prev');
        const nextButton = document.getElementById('place-history-next');

        placeHistoryList.innerHTML = '';

        // Обрабатываем только массив `results` из ответа
        response.results.forEach(record => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${record.new_place.date_of_transfer}</td>
                <td>${record.new_place ? record.new_place.sheepfold : 'Не указано'}</td>
                <td>${record.old_place ? record.old_place.sheepfold : 'Не указано'}</td>
                
                
            `;
            placeHistoryList.appendChild(row);
        });
        // Настраиваем кнопки пагинации
        prevButton.disabled = !response.previous;
        nextButton.disabled = !response.next;

        prevButton.onclick = () => loadPlaceHistory(tagId, page - 1);
        nextButton.onclick = () => loadPlaceHistory(tagId, page + 1);

    } catch (error) {
        console.error('Ошибка загрузки истории перемещений:', error);
    }
}




function renderTableWithPagination(data, tableBodyId, pageSize = 3) {
    const tableBody = document.getElementById(tableBodyId);
    tableBody.innerHTML = ''; // Очищаем текущую таблицу

    let currentPage = 1;
    const totalPages = Math.ceil(data.length / pageSize);

    function renderPage(page) {
        tableBody.innerHTML = ''; // Очищаем таблицу для новой страницы
        const startIndex = (page - 1) * pageSize;
        const endIndex = Math.min(startIndex + pageSize, data.length);

        for (let i = startIndex; i < endIndex; i++) {
            const row = document.createElement('tr');
            const record = data[i];
            row.innerHTML = `
                <td>${record.date}</td>
                <td>${record.name || record.description}</td>
            `;
            tableBody.appendChild(row);
        }
    }

    // Добавляем элементы управления пагинацией
    function createPaginationControls() {
        const paginationControls = document.createElement('div');
        paginationControls.id = `${tableBodyId}-pagination`;

        const prevButton = document.createElement('button');
        prevButton.textContent = 'Назад';
        prevButton.disabled = currentPage === 1;
        prevButton.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                renderPage(currentPage);
                updateControls();
            }
        });

        const nextButton = document.createElement('button');
        nextButton.textContent = 'Вперёд';
        nextButton.disabled = currentPage === totalPages;
        nextButton.addEventListener('click', () => {
            if (currentPage < totalPages) {
                currentPage++;
                renderPage(currentPage);
                updateControls();
            }
        });

        paginationControls.appendChild(prevButton);
        paginationControls.appendChild(nextButton);
        tableBody.parentNode.appendChild(paginationControls);

        function updateControls() {
            prevButton.disabled = currentPage === 1;
            nextButton.disabled = currentPage === totalPages;
        }
    }

    renderPage(currentPage);
    createPaginationControls();
}



async function onChildClick(makerId, childId) {
    try {
        // Делаем запрос на API для получения всех детей производителя
        const response = await apiRequest(`/animals/maker/${makerId}/children/`);

        // Ищем конкретного ребёнка по ID
        const child = response.results.find(c => c.id === childId);

        if (!child) {
            console.error(`Ребёнок с ID ${childId} не найден.`);
            return;
        }

        const isArchived = child.is_archived;  // Флаг архивированности
        const archiveStatus = child.archive_status; // Статус в архиве
        const archiveDate = child.archive_date; // Дата архивирования

        if (isArchived) {
            // Если ребёнок в архиве, показываем всплывающее окно
            showArchiveMessage(archiveStatus, archiveDate);
        } else {
            // Если не в архиве, перенаправляем пользователя
            window.location.href = child.link;
        }
    } catch (error) {
        console.error('Ошибка при обработке ребёнка:', error);
    }
}

function showArchiveMessage(status, date) {
    // Создаём всплывающее окно
    const modal = document.createElement('div');
    modal.classList.add('modal');
    modal.innerHTML = `
        <div class="modal-content">
            <p>Данное животное перенесено в архив.</p>
            <p><strong>Статус:</strong> ${status || 'Не указано'}</p>
            <p><strong>Дата архивирования:</strong> ${date || 'Не указано'}</p>
            <button class="modal-close">Закрыть</button>
        </div>
    `;
    document.body.appendChild(modal);

    // Закрытие окна при клике
    const closeButton = modal.querySelector('.modal-close');
    closeButton.addEventListener('click', () => {
        modal.remove();
    });
}

