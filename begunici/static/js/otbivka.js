import { apiRequest } from "./utils.js";

document.addEventListener('DOMContentLoaded', function () {
    fetchOtbivka();  // Загружаем список отбивки при загрузке страницы

    // Добавляем обработчик для поиска
    const searchInput = document.getElementById('otbivka-search');
    if (searchInput) {
        searchInput.addEventListener('input', searchOtbivka);
    }
});

let currentPage = 1;
const pageSize = 10;

// Функция загрузки списка отбивки
async function fetchOtbivka(page = 1, query = '') {
    try {
        const response = await apiRequest(`/animals/api/otbivka/?page=${page}&page_size=${pageSize}&search=${encodeURIComponent(query)}`);
        
        if (response && response.results) {
            renderOtbivka(response.results);
            updatePagination(response);
        } else {
            console.error('Некорректный ответ от API:', response);
            showError('Ошибка: данные отбивки не найдены.');
        }
    } catch (error) {
        console.error('Ошибка при загрузке отбивки:', error);
        showError('Ошибка при загрузке списка отбивки.');
    }
}

// Рендеринг списка отбивки
function renderOtbivka(animals) {
    const otbivkaTable = document.getElementById('otbivka-list');
    otbivkaTable.innerHTML = '';
    
    if (animals.length === 0) {
        otbivkaTable.innerHTML = `
            <tr>
                <td colspan="3" class="text-center py-4">
                    <p class="text-muted">Нет животных с датой отбивки.</p>
                </td>
            </tr>
        `;
        return;
    }
    
    animals.forEach((animal) => {
        const row = `<tr>
            <td>${animal.date_otbivka}</td>
            <td>
                <a href="/animals/${animal.animal_type}/${animal.tag_number}/info/" 
                   class="text-decoration-none">
                    ${animal.tag_number}
                </a>
            </td>
            <td>
                ${animal.age_at_otbivka || '-'}
            </td>
        </tr>`;
        otbivkaTable.innerHTML += row;
    });
}

// Функция поиска отбивки
async function searchOtbivka() {
    const searchTerm = document.getElementById('otbivka-search').value;
    currentPage = 1;
    fetchOtbivka(currentPage, searchTerm);
}

// Обновление пагинации
function updatePagination(response) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';
    
    if (response.total_pages <= 1) {
        return; // Не показываем пагинацию если только одна страница
    }
    
    // Создаем контейнер для пагинации с центрированием
    const paginationContainer = document.createElement('div');
    paginationContainer.style.display = 'flex';
    paginationContainer.style.alignItems = 'center';
    paginationContainer.style.justifyContent = 'center';
    paginationContainer.style.gap = '15px';

    // Кнопка "Предыдущая" (слева)
    if (response.previous) {
        const prevButton = document.createElement('button');
        prevButton.innerText = 'Предыдущая';
        prevButton.className = 'btn btn-outline-primary btn-sm';
        prevButton.onclick = () => {
            currentPage--;
            const searchTerm = document.getElementById('otbivka-search').value;
            fetchOtbivka(currentPage, searchTerm);
        };
        paginationContainer.appendChild(prevButton);
    } else {
        // Пустой элемент для сохранения симметрии
        const emptyDiv = document.createElement('div');
        emptyDiv.style.width = '80px'; // Примерная ширина кнопки
        paginationContainer.appendChild(emptyDiv);
    }

    // Информация о странице (по центру)
    const pageInfo = document.createElement('span');
    pageInfo.innerText = `Страница ${response.current_page} из ${response.total_pages}`;
    pageInfo.style.fontWeight = '500';
    pageInfo.style.minWidth = '150px';
    pageInfo.style.textAlign = 'center';
    paginationContainer.appendChild(pageInfo);

    // Кнопка "Следующая" (справа)
    if (response.next) {
        const nextButton = document.createElement('button');
        nextButton.innerText = 'Следующая';
        nextButton.className = 'btn btn-outline-primary btn-sm';
        nextButton.onclick = () => {
            currentPage++;
            const searchTerm = document.getElementById('otbivka-search').value;
            fetchOtbivka(currentPage, searchTerm);
        };
        paginationContainer.appendChild(nextButton);
    } else {
        // Пустой элемент для сохранения симметрии
        const emptyDiv = document.createElement('div');
        emptyDiv.style.width = '80px'; // Примерная ширина кнопки
        paginationContainer.appendChild(emptyDiv);
    }

    pagination.appendChild(paginationContainer);
}

// Показать ошибку
function showError(message) {
    const otbivkaTable = document.getElementById('otbivka-list');
    otbivkaTable.innerHTML = `
        <tr>
            <td colspan="3" class="text-center py-4">
                <p class="text-danger">${message}</p>
            </td>
        </tr>
    `;
}

// Экспортируем функции для глобального доступа
window.fetchOtbivka = fetchOtbivka;
window.searchOtbivka = searchOtbivka;