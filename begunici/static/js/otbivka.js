import { apiRequest } from "./utils.js";

// Глобальные переменные для ковровой отбивки
let selectedAnimals = new Set(); // Для хранения выбранных животных
let selectedAnimalsData = new Map(); // Для хранения полной информации о выбранных животных

document.addEventListener('DOMContentLoaded', function () {
    fetchOtbivka();  // Загружаем список отбивки при загрузке страницы

    // Убираем автоматические обработчики для поиска и дат
    // Теперь фильтрация работает только по кнопке "Применить"
    
    // Устанавливаем текущую дату как дату отбивки
    const today = new Date().toISOString().split('T')[0];
    const otbivkaDateInput = document.getElementById('otbivka-date');
    if (otbivkaDateInput) {
        otbivkaDateInput.value = today;
    }
    
    // Обработчики для ковровой отбивки
    const searchAnimalsBtn = document.getElementById('searchAnimalsBtn');
    if (searchAnimalsBtn) {
        searchAnimalsBtn.addEventListener('click', searchAnimals);
    }
    
    const animalsSearchInput = document.getElementById('animalsSearch');
    if (animalsSearchInput) {
        animalsSearchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchAnimals();
            }
        });
    }
    
    // Добавляем обработчик Enter для поля поиска по бирке
    const searchInput = document.getElementById('otbivka-search');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                performOtbivkaSearch();
            }
        });
    }
});

let currentPage = 1;
const pageSize = 10;

// Функция загрузки списка отбивки
async function fetchOtbivka(page = 1, query = '', dateFrom = '', dateTo = '') {
    try {
        let url = `/animals/api/otbivka/?page=${page}&page_size=${pageSize}&search=${encodeURIComponent(query)}`;
        
        if (dateFrom) {
            url += `&date_from=${encodeURIComponent(dateFrom)}`;
        }
        if (dateTo) {
            url += `&date_to=${encodeURIComponent(dateTo)}`;
        }
        
        const response = await apiRequest(url);
        
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
                    ${animal.display_name || animal.tag_number}
                </a>
            </td>
            <td>
                ${animal.age_at_otbivka || '-'}
            </td>
        </tr>`;
        otbivkaTable.innerHTML += row;
    });
}

// Функция поиска отбивки с фильтрацией по датам
async function performOtbivkaSearch() {
    const searchTerm = document.getElementById('otbivka-search').value;
    const dateFrom = document.getElementById('otbivka-date-from').value;
    const dateTo = document.getElementById('otbivka-date-to').value;
    
    currentPage = 1;
    fetchOtbivka(currentPage, searchTerm, dateFrom, dateTo);
}

function exportOtbivkaToExcel() {
    const params = new URLSearchParams();
    const searchTerm = document.getElementById('otbivka-search').value.trim();
    const dateFrom = document.getElementById('otbivka-date-from').value;
    const dateTo = document.getElementById('otbivka-date-to').value;

    if (searchTerm) {
        params.set('search', searchTerm);
    }
    if (dateFrom) {
        params.set('date_from', dateFrom);
    }
    if (dateTo) {
        params.set('date_to', dateTo);
    }

    window.location.href = `/animals/api/otbivka/export-excel/?${params.toString()}`;
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
            const dateFrom = document.getElementById('otbivka-date-from').value;
            const dateTo = document.getElementById('otbivka-date-to').value;
            fetchOtbivka(currentPage, searchTerm, dateFrom, dateTo);
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
            const dateFrom = document.getElementById('otbivka-date-from').value;
            const dateTo = document.getElementById('otbivka-date-to').value;
            fetchOtbivka(currentPage, searchTerm, dateFrom, dateTo);
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
window.performOtbivkaSearch = performOtbivkaSearch;
window.exportOtbivkaToExcel = exportOtbivkaToExcel;

// Функции для ковровой отбивки
window.showSelectAnimalsModal = showSelectAnimalsModal;
window.confirmAnimalsSelection = confirmAnimalsSelection;
window.performBulkOtbivka = performBulkOtbivka;

// Показать модальное окно выбора животных
async function showSelectAnimalsModal() {
    // Очищаем выбранных животных и поле поиска
    selectedAnimals.clear();
    selectedAnimalsData.clear();
    document.getElementById('animalsSearch').value = '';
    document.getElementById('animals-list').innerHTML = `
        <div class="text-muted text-center py-3">
            Введите номер бирки и нажмите "Поиск" для отображения результатов
        </div>
    `;
    
    // Показываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('selectAnimalsModal'));
    modal.show();
}

// Поиск животных без отбивки
async function searchAnimals() {
    const search = document.getElementById('animalsSearch').value.trim();
    
    if (!search) {
        document.getElementById('animals-list').innerHTML = `
            <div class="text-muted text-center py-3">
                Введите номер бирки для поиска
            </div>
        `;
        return;
    }
    
    // Сохраняем текущие выбранные чекбоксы
    saveSelectedAnimals();
    
    // Показываем индикатор загрузки
    document.getElementById('animals-list').innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Поиск...</span>
            </div>
            <div class="mt-2">Поиск животных без отбивки...</div>
        </div>
    `;
    
    try {
        const response = await apiRequest(`/animals/api/animals-without-otbivka/?search=${encodeURIComponent(search)}`);
        const animals = response || [];
        
        const animalsList = document.getElementById('animals-list');
        animalsList.innerHTML = '';
        
        if (animals.length === 0) {
            animalsList.innerHTML = '<div class="text-center text-muted">Животные без отбивки не найдены</div>';
        } else {
            animals.forEach(animal => {
                const item = createAnimalItem(animal);
                animalsList.appendChild(item);
            });
            
            // Показываем информацию о количестве результатов
            if (animals.length >= 100) {
                const info = document.createElement('div');
                info.className = 'text-muted text-center mt-2 small';
                info.textContent = `Показано первых 100 результатов`;
                animalsList.appendChild(info);
            }
            
            // Восстанавливаем выбранные чекбоксы
            restoreSelectedAnimals();
        }
    } catch (error) {
        console.error('Ошибка поиска животных:', error);
        document.getElementById('animals-list').innerHTML = `
            <div class="text-danger text-center py-3">
                Ошибка поиска
            </div>
        `;
    }
}

// Создание элемента для выбора животного
function createAnimalItem(animal) {
    const item = document.createElement('div');
    item.className = 'form-check mb-2';
    
    item.innerHTML = `
        <input class="form-check-input animal-checkbox" type="checkbox" 
               value="${animal.tag_number}" data-type="${animal.type_code}" data-display="${animal.display_name}">
        <label class="form-check-label">
            ${animal.display_name} (${animal.animal_type}) - ${animal.status}
        </label>
    `;
    
    return item;
}

// Функция для сохранения выбранных животных
function saveSelectedAnimals() {
    const checkboxes = document.querySelectorAll('.animal-checkbox');
    checkboxes.forEach(checkbox => {
        const tagNumber = checkbox.value;
        if (checkbox.checked) {
            selectedAnimals.add(tagNumber);
            selectedAnimalsData.set(tagNumber, {
                tag_number: tagNumber,
                type: checkbox.dataset.type,
                display_name: checkbox.dataset.display
            });
        } else {
            selectedAnimals.delete(tagNumber);
            selectedAnimalsData.delete(tagNumber);
        }
    });
}

// Функция для восстановления выбранных животных
function restoreSelectedAnimals() {
    const checkboxes = document.querySelectorAll('.animal-checkbox');
    checkboxes.forEach(checkbox => {
        if (selectedAnimals.has(checkbox.value)) {
            checkbox.checked = true;
        }
    });
}

// Подтверждение выбора животных
function confirmAnimalsSelection() {
    // Сохраняем текущие выбранные чекбоксы
    saveSelectedAnimals();
    
    // Создаем массив из всех выбранных животных
    const selectedAnimalsArray = Array.from(selectedAnimalsData.values());
    
    // Обновляем отображение
    const display = document.getElementById('selected-animals-display');
    const bulkOtbivkaBtn = document.getElementById('bulk-otbivka-btn');
    
    if (selectedAnimalsArray.length === 0) {
        display.textContent = 'Не выбрано';
        display.className = 'mt-2 text-muted';
        bulkOtbivkaBtn.disabled = true;
    } else {
        display.textContent = `Выбрано: ${selectedAnimalsArray.length} животных`;
        display.className = 'mt-2 text-success';
        bulkOtbivkaBtn.disabled = false;
    }
    
    // Сохраняем массив для использования в других функциях
    window.selectedAnimalsForOtbivka = selectedAnimalsArray;
    
    // Закрываем модальное окно
    const modal = bootstrap.Modal.getInstance(document.getElementById('selectAnimalsModal'));
    modal.hide();
}

// Выполнение массовой отбивки
async function performBulkOtbivka() {
    const otbivkaDate = document.getElementById('otbivka-date').value;
    
    if (!otbivkaDate) {
        alert('Укажите дату отбивки');
        return;
    }
    
    if (!window.selectedAnimalsForOtbivka || window.selectedAnimalsForOtbivka.length === 0) {
        alert('Выберите животных для отбивки');
        return;
    }
    
    // Подтверждение операции
    const confirmMessage = `Выполнить отбивку для ${window.selectedAnimalsForOtbivka.length} животных на дату ${otbivkaDate}?\n\nВсем животным будет установлен статус "Откорм".`;
    if (!confirm(confirmMessage)) {
        return;
    }
    
    try {
        const animalTags = window.selectedAnimalsForOtbivka.map(animal => animal.tag_number);
        
        const response = await apiRequest('/animals/api/bulk-otbivka/', 'POST', {
            otbivka_date: otbivkaDate,
            animal_tags: animalTags
        });
        
        let message = `Успешно выполнена отбивка для ${response.updated_count} из ${response.total_requested} животных!`;
        
        if (response.errors && response.errors.length > 0) {
            message += `\n\nОшибки:\n${response.errors.join('\n')}`;
        }
        
        alert(message);
        
        // Очищаем форму
        resetBulkOtbivkaForm();
        
        // Перезагружаем список отбивки
        fetchOtbivka();
        
    } catch (error) {
        console.error('Ошибка выполнения массовой отбивки:', error);
        alert('Ошибка при выполнении отбивки: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Сброс формы массовой отбивки
function resetBulkOtbivkaForm() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('otbivka-date').value = today;
    
    selectedAnimals.clear();
    selectedAnimalsData.clear();
    window.selectedAnimalsForOtbivka = [];
    
    document.getElementById('selected-animals-display').textContent = 'Не выбрано';
    document.getElementById('selected-animals-display').className = 'mt-2 text-muted';
    document.getElementById('bulk-otbivka-btn').disabled = true;
}
