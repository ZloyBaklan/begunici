import { apiRequest } from "./utils.js";

document.addEventListener('DOMContentLoaded', async () => {
    const analyticsDetail = document.getElementById("analytics-detail");
    
    if (!analyticsDetail) {
        console.error("Ошибка: Элемент #analytics-detail не найден!");
        return;
    }

    const tagNumber = analyticsDetail.dataset.tagNumber;
    const animalType = analyticsDetail.dataset.animalType;
    
    if (!tagNumber || !animalType) {
        console.error("Ошибка: tagNumber или animalType отсутствуют в dataset!");
        return;
    }

    console.log(`Загрузка аналитики для ${animalType} с биркой ${tagNumber}`);
    try {
        await loadWeightHistory(animalType, tagNumber);
        await loadChildren(animalType, tagNumber);
        await loadVetCalendar(animalType, tagNumber);
        await loadStatusHistory(animalType, tagNumber);
        await loadPlaceHistory(animalType, tagNumber);
        
        // Обработчик чекбокса для скрытия архивных детей
        const hideArchivedCheckbox = document.getElementById('hide-archived-children');
        if (hideArchivedCheckbox) {
            hideArchivedCheckbox.addEventListener('change', () => {
                loadChildren(animalType, tagNumber, 1);
            });
        }
    } catch (error) {
        console.error('Ошибка загрузки данных аналитики:', error);
    }
});

async function loadWeightHistory(animalType, tagNumber) {
    try {
        const response = await apiRequest(`/animals/${animalType}/${tagNumber}/weight_history/`);
        const weightData = response.map(record => ({
            date: new Date(record.weight_date),
            weight: parseFloat(record.weight),
        }));

        // Сортируем данные по дате от старых к новым
        weightData.sort((a, b) => a.date - b.date);

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

async function loadChildren(animalType, tagNumber, page = 1) {
    try {
        const hideArchived = document.getElementById('hide-archived-children')?.checked || false;
        const url = `/animals/${animalType}/${tagNumber}/children/?page=${page}&page_size=${analyticsPageSize}`;
        const response = await apiRequest(url);
        console.log('Дети:', response);

        const childrenList = document.getElementById('children-list');
        const prevButton = document.getElementById('children-prev');
        const nextButton = document.getElementById('children-next');
        const pageNumbers = document.getElementById('children-page-numbers');

        childrenList.innerHTML = '';

        // Фильтруем детей если нужно скрыть архивных
        let filteredChildren = response.results;
        if (hideArchived) {
            filteredChildren = response.results.filter(child => !child.is_archived);
        }

        filteredChildren.forEach((child, index) => {
            console.log(`Ребенок ${index}:`, child); // Отладочный вывод
            
            // Форматируем информацию о первом весе
            let firstWeightText = 'Нет данных';
            if (child.first_weight) {
                const weightDate = new Date(child.first_weight.date).toLocaleDateString('ru-RU');
                firstWeightText = `${child.first_weight.weight} кг (${weightDate})`;
            }
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    ${child.is_archived ? 
                        `<span style="color: red; cursor: pointer;" onclick="window.onChildClick('${animalType}', '${tagNumber}', '${child.tag_number || 'unknown'}')">${child.tag_number || 'Нет бирки'}</span>` :
                        `<a href="${child.link || '#'}">${child.tag_number || 'Нет бирки'}</a>`
                    }
                </td>
                <td>${child.animal_type || 'Неизвестно'}</td>
                <td>${child.age ? `${child.age} мес.` : '-'}</td>
                <td>${firstWeightText}</td>
            `;
            childrenList.appendChild(row);
        });

        // Обновляем пагинацию
        prevButton.disabled = !response.previous;
        nextButton.disabled = !response.next;
        prevButton.onclick = () => loadChildren(animalType, tagNumber, page - 1);
        nextButton.onclick = () => loadChildren(animalType, tagNumber, page + 1);

        // Создаём номера страниц
        const totalPages = Math.ceil(response.count / analyticsPageSize);
        renderPageNumbers(pageNumbers, page, totalPages, (p) => loadChildren(animalType, tagNumber, p));

        document.getElementById('children-count').textContent = response.count;
    } catch (error) {
        console.error('Ошибка загрузки детей:', error);
    }
}


async function loadVetCalendar(animalType, tagNumber, page = 1) {
    try {
        const response = await apiRequest(`/animals/${animalType}/${tagNumber}/vet_history/?page=${page}&page_size=${analyticsPageSize}`);
        const Vetcalendar = document.getElementById('vet-calendar');
        const prevButton = document.getElementById('vet-calendar-prev');
        const nextButton = document.getElementById('vet-calendar-next');
        const pageNumbers = document.getElementById('vet-calendar-page-numbers');

        Vetcalendar.innerHTML = '';

        if (response.results && response.results.length > 0) {
            response.results.forEach(entry => {
                // Форматируем только дату (без времени)
                const date = new Date(entry.date_of_care);
                const formattedDate = date.toLocaleDateString('ru-RU', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit'
                });
                
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${formattedDate}</td>
                    <td>${entry.veterinary_care?.care_name || 'Не указано'}</td>
                    <td>${entry.comments || 'Нет комментария'}</td>
                `;
                Vetcalendar.appendChild(row);
            });
        } else {
            Vetcalendar.innerHTML = '<tr><td colspan="3">Нет записей о ветобработках</td></tr>';
        }

        prevButton.disabled = !response.previous;
        nextButton.disabled = !response.next;
        prevButton.onclick = () => loadVetCalendar(animalType, tagNumber, page - 1);
        nextButton.onclick = () => loadVetCalendar(animalType, tagNumber, page + 1);

        // Создаём номера страниц
        const totalPages = Math.ceil(response.count / analyticsPageSize);
        renderPageNumbers(pageNumbers, page, totalPages, (p) => loadVetCalendar(animalType, tagNumber, p));

    } catch (error) {
        console.error('Ошибка загрузки календаря ветобработок:', error);
    }
}

async function loadStatusHistory(animalType, tagNumber, page = 1) {
    try {
        const response = await apiRequest(`/animals/${animalType}/${tagNumber}/status_history/?page=${page}&page_size=${analyticsPageSize}`);
        const statusHistoryList = document.getElementById('status-history-list');
        const prevButton = document.getElementById('status-history-prev');
        const nextButton = document.getElementById('status-history-next');
        const pageNumbers = document.getElementById('status-history-page-numbers');

        statusHistoryList.innerHTML = '';

        if (response.results && response.results.length > 0) {
            response.results.forEach(record => {
                // Форматируем дату и время изменения статуса
                let formattedDateTime = '-';
                if (record.change_date) {
                    const dateTime = new Date(record.change_date);
                    formattedDateTime = dateTime.toLocaleString('ru-RU', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                }
                
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${formattedDateTime}</td>
                    <td>${record.new_status?.status_type || 'Не указано'}</td>
                    <td>${record.old_status?.status_type || 'Не указано'}</td>
                `;
                statusHistoryList.appendChild(row);
            });
        } else {
            statusHistoryList.innerHTML = '<tr><td colspan="3">Нет истории изменения статусов</td></tr>';
        }

        prevButton.disabled = !response.previous;
        nextButton.disabled = !response.next;
        prevButton.onclick = () => loadStatusHistory(animalType, tagNumber, page - 1);
        nextButton.onclick = () => loadStatusHistory(animalType, tagNumber, page + 1);

        // Создаём номера страниц
        const totalPages = Math.ceil(response.count / analyticsPageSize);
        renderPageNumbers(pageNumbers, page, totalPages, (p) => loadStatusHistory(animalType, tagNumber, p));

    } catch (error) {
        console.error('Ошибка загрузки истории статусов:', error);
    }
}


async function loadPlaceHistory(animalType, tagNumber, page = 1) {
    try {
        const response = await apiRequest(`/animals/${animalType}/${tagNumber}/place_history/?page=${page}&page_size=${analyticsPageSize}`);
        console.log('Ответ API:', response);
        const placeHistoryList = document.getElementById('place-history');
        const prevButton = document.getElementById('place-history-prev');
        const nextButton = document.getElementById('place-history-next');
        const pageNumbers = document.getElementById('place-history-page-numbers');

        placeHistoryList.innerHTML = '';

        if (response.results && response.results.length > 0) {
            response.results.forEach(record => {
                // Форматируем дату и время для перемещения
                let formattedDateTime = '-';
                if (record.new_place?.date_of_transfer) {
                    const dateTime = new Date(record.new_place.date_of_transfer);
                    formattedDateTime = dateTime.toLocaleString('ru-RU', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                }
                
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${formattedDateTime}</td>
                    <td>${record.new_place?.sheepfold || 'Не указано'}</td>
                    <td>${record.old_place?.sheepfold || 'Не указано'}</td>
                `;
                placeHistoryList.appendChild(row);
            });
        } else {
            placeHistoryList.innerHTML = '<tr><td colspan="3">Нет истории перемещений</td></tr>';
        }

        prevButton.disabled = !response.previous;
        nextButton.disabled = !response.next;
        prevButton.onclick = () => loadPlaceHistory(animalType, tagNumber, page - 1);
        nextButton.onclick = () => loadPlaceHistory(animalType, tagNumber, page + 1);

        // Создаём номера страниц
        const totalPages = Math.ceil(response.count / analyticsPageSize);
        renderPageNumbers(pageNumbers, page, totalPages, (p) => loadPlaceHistory(animalType, tagNumber, p));

    } catch (error) {
        console.error('Ошибка загрузки истории перемещений:', error);
    }
}


// Делаем функцию глобальной
window.onChildClick = async function(animalType, tagNumber, childTagNumber) {
    try {
        // Делаем запрос на API для получения всех детей производителя
        const response = await apiRequest(`/animals/${animalType}/${tagNumber}/children/`);

        // Ищем конкретного ребёнка по tag_number
        const child = response.results.find(c => c.tag_number === childTagNumber);

        if (!child) {
            console.error(`Ребёнок с биркой ${childTagNumber} не найден.`);
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

// Функция для рендеринга номеров страниц
function renderPageNumbers(container, currentPage, totalPages, onPageClick) {
    container.innerHTML = '';
    
    if (totalPages <= 1) return;
    
    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    if (endPage - startPage < maxVisiblePages - 1) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        const pageButton = document.createElement('button');
        pageButton.textContent = i;
        pageButton.className = i === currentPage ? 'page-number active' : 'page-number';
        pageButton.disabled = i === currentPage;
        pageButton.onclick = () => onPageClick(i);
        container.appendChild(pageButton);
    }
}

