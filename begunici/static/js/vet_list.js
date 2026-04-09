// Глобальные переменные
let currentPage = 1;
const pageSize = 10;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    loadFilterOptions();
    loadVetList();
    
    // Обработчик кнопки поиска
    document.getElementById('search-btn').addEventListener('click', function() {
        currentPage = 1;
        loadVetList();
    });
    
    // Обработчики Enter в полях ввода
    document.getElementById('tag-search').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            currentPage = 1;
            loadVetList();
        }
    });
});

// Функция для API запросов
async function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    const response = await fetch(url, options);
    
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
}

// Получение CSRF токена
function getCookie(name) {
    let cookieValue = null;
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

// Загрузка опций для фильтров
async function loadFilterOptions() {
    try {
        const response = await apiRequest('/animals/api/vet-filter-options/');
        
        // Заполняем селект названий обработок
        const careNameSelect = document.getElementById('care-name-filter');
        careNameSelect.innerHTML = '<option value="">Все</option>';
        response.care_names.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            careNameSelect.appendChild(option);
        });
        
        // Заполняем селект препаратов
        const medicationSelect = document.getElementById('medication-filter');
        medicationSelect.innerHTML = '<option value="">Все</option>';
        response.medications.forEach(medication => {
            const option = document.createElement('option');
            option.value = medication;
            option.textContent = medication;
            medicationSelect.appendChild(option);
        });
        
    } catch (error) {
        console.error('Ошибка загрузки опций фильтров:', error);
    }
}

// Загрузка списка ветобработок
async function loadVetList() {
    const loading = document.getElementById('loading');
    const noData = document.getElementById('no-data');
    const vetList = document.getElementById('vet-list');
    
    // Показываем индикатор загрузки
    loading.style.display = 'block';
    noData.style.display = 'none';
    vetList.innerHTML = '';
    
    try {
        // Собираем параметры фильтрации
        const params = new URLSearchParams({
            page: currentPage,
            page_size: pageSize,
            tag_search: document.getElementById('tag-search').value.trim(),
            care_name: document.getElementById('care-name-filter').value,
            medication: document.getElementById('medication-filter').value,
            care_date_from: document.getElementById('care-date-from').value,
            care_date_to: document.getElementById('care-date-to').value,
            expiry_date_from: document.getElementById('expiry-date-from').value,
            expiry_date_to: document.getElementById('expiry-date-to').value,
            is_hidden: document.getElementById('is-hidden-filter').value
        });
        
        const response = await apiRequest(`/animals/api/vet-list/?${params}`);
        
        loading.style.display = 'none';
        
        if (response.results && response.results.length > 0) {
            renderVetList(response.results);
            renderPagination(response);
            document.getElementById('total-count').textContent = response.count;
        } else {
            noData.style.display = 'block';
            document.getElementById('total-count').textContent = '0';
        }
        
    } catch (error) {
        console.error('Ошибка загрузки списка ветобработок:', error);
        loading.style.display = 'none';
        noData.style.display = 'block';
        document.getElementById('total-count').textContent = '0';
    }
}

// Отображение списка ветобработок
function renderVetList(vetRecords) {
    const vetList = document.getElementById('vet-list');
    const rows = [];
    
    vetRecords.forEach(vet => {
        // Форматируем срок действия
        let durationText = '';
        if (vet.duration_days === 0) {
            durationText = 'Бессрочно';
        } else {
            durationText = `${vet.duration_days} дней`;
        }
        
        // Форматируем дату окончания
        let expiryText = '';
        if (vet.expiry_date) {
            const expiryDate = new Date(vet.expiry_date);
            expiryText = expiryDate.toLocaleDateString('ru-RU');
        } else {
            expiryText = 'Бессрочно';
        }
        
        // Форматируем дату обработки
        const careDate = new Date(vet.care_date);
        const careDateText = careDate.toLocaleDateString('ru-RU');
        
        // Текст скрытого статуса
        const hiddenText = vet.is_hidden ? 'Да' : 'Нет';
        
        const row = `<tr>
            <td>
                <a href="${vet.animal_url}" class="text-decoration-none">
                    ${vet.tag_number}
                </a>
            </td>
            <td>${vet.care_name}</td>
            <td>${vet.medication}</td>
            <td>${durationText}</td>
            <td>${careDateText}</td>
            <td>${expiryText}</td>
            <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" 
                title="${vet.comments}">
                ${vet.comments}
            </td>
            <td class="text-center">${hiddenText}</td>
        </tr>`;
        
        rows.push(row);
    });
    
    vetList.innerHTML = rows.join('');
}

// Отображение пагинации
function renderPagination(response) {
    const paginationContainer = document.getElementById('pagination');
    paginationContainer.innerHTML = '';
    
    if (response.total_pages <= 1) {
        return;
    }
    
    const pagination = document.createElement('nav');
    const ul = document.createElement('ul');
    ul.className = 'pagination justify-content-center';
    
    // Кнопка "Предыдущая"
    if (response.has_previous) {
        const prevLi = document.createElement('li');
        prevLi.className = 'page-item';
        prevLi.innerHTML = `<a class="page-link" href="#" onclick="changePage(${currentPage - 1})">Предыдущая</a>`;
        ul.appendChild(prevLi);
    }
    
    // Номера страниц
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(response.total_pages, currentPage + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        const li = document.createElement('li');
        li.className = `page-item ${i === currentPage ? 'active' : ''}`;
        li.innerHTML = `<a class="page-link" href="#" onclick="changePage(${i})">${i}</a>`;
        ul.appendChild(li);
    }
    
    // Кнопка "Следующая"
    if (response.has_next) {
        const nextLi = document.createElement('li');
        nextLi.className = 'page-item';
        nextLi.innerHTML = `<a class="page-link" href="#" onclick="changePage(${currentPage + 1})">Следующая</a>`;
        ul.appendChild(nextLi);
    }
    
    pagination.appendChild(ul);
    paginationContainer.appendChild(pagination);
}

// Смена страницы
function changePage(page) {
    currentPage = page;
    loadVetList();
}

// Экспортируем функции для глобального доступа
window.changePage = changePage;