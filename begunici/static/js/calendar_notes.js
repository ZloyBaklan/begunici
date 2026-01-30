// Глобальные переменные
let currentDate = new Date();
let currentViewMode = 'week'; // 'week' или 'month'
let currentNoteId = null;
let currentNoteDate = null;
let allTags = [];
let allStatuses = [];

// ИСПРАВЛЕННАЯ функция для навигации
function navigateWeek(direction) {
    if (direction === 'next') {
        currentDate.setDate(currentDate.getDate() + 7);
    } else {
        currentDate.setDate(currentDate.getDate() - 7);
    }
    updateCalendar();
}

function navigateMonth(direction) {
    if (direction === 'next') {
        currentDate.setMonth(currentDate.getMonth() + 1);
    } else {
        currentDate.setMonth(currentDate.getMonth() - 1);
    }
    updateCalendar();
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('Инициализация календаря заметок...');
    
    // Загружаем данные
    loadAllTags();
    loadAllStatuses();
    
    // Инициализируем календарь
    updateCalendar();
    
    // Проверяем наличие элементов перед привязкой событий
    const prevBtn = document.getElementById('prevPeriod');
    const nextBtn = document.getElementById('nextPeriod');
    const weekBtn = document.getElementById('weekViewBtn');
    const monthBtn = document.getElementById('monthViewBtn');
    const saveBtn = document.getElementById('saveNoteBtn');
    const insertBtn = document.getElementById('insertTagBtn');
    const searchInput = document.getElementById('tagSearch');
    
    console.log('Элементы найдены:', {
        prevBtn: !!prevBtn,
        nextBtn: !!nextBtn,
        weekBtn: !!weekBtn,
        monthBtn: !!monthBtn,
        saveBtn: !!saveBtn,
        insertBtn: !!insertBtn,
        searchInput: !!searchInput
    });
    
    // Обработчики событий навигации
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            console.log('Клик по предыдущему периоду');
            if (currentViewMode === 'week') {
                navigateWeek('prev');
            } else {
                navigateMonth('prev');
            }
        });
    }
    
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            console.log('Клик по следующему периоду');
            if (currentViewMode === 'week') {
                navigateWeek('next');
            } else {
                navigateMonth('next');
            }
        });
    }
    
    // Переключатель режима отображения
    if (weekBtn) {
        weekBtn.addEventListener('click', () => {
            console.log('Переключение на недельный режим');
            if (currentViewMode !== 'week') {
                currentViewMode = 'week';
                weekBtn.classList.add('active');
                if (monthBtn) monthBtn.classList.remove('active');
                updateCalendar();
            }
        });
    }
    
    if (monthBtn) {
        monthBtn.addEventListener('click', () => {
            console.log('Переключение на месячный режим');
            if (currentViewMode !== 'month') {
                currentViewMode = 'month';
                monthBtn.classList.add('active');
                if (weekBtn) weekBtn.classList.remove('active');
                updateCalendar();
            }
        });
    }
    
    // Обработчики модальных окон
    if (saveBtn) {
        saveBtn.addEventListener('click', saveNote);
    }
    
    const deleteBtn = document.getElementById('deleteNoteBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', deleteNote);
    }
    
    if (insertBtn) {
        insertBtn.addEventListener('click', showTagModal);
    }
    
    if (searchInput) {
        searchInput.addEventListener('input', filterTags);
    }
});

// Обновляет режим отображения
function updateViewMode() {
    const weekCalendar = document.getElementById('weekCalendar');
    const monthCalendar = document.getElementById('monthCalendar');
    const prevLabel = document.getElementById('prevLabel');
    const nextLabel = document.getElementById('nextLabel');
    
    if (currentViewMode === 'week') {
        weekCalendar.style.display = 'block';
        monthCalendar.style.display = 'none';
        prevLabel.textContent = 'Предыдущая неделя';
        nextLabel.textContent = 'Следующая неделя';
    } else {
        weekCalendar.style.display = 'none';
        monthCalendar.style.display = 'block';
        prevLabel.textContent = 'Предыдущий месяц';
        nextLabel.textContent = 'Следующий месяц';
    }
}

// Обновляет календарь в зависимости от режима
async function updateCalendar() {
    updateViewMode();
    
    if (currentViewMode === 'week') {
        await loadWeekData();
    } else {
        await loadMonthData();
    }
}

// Загружает данные для недели БЕЗ обрезки по месяцам
// Загружает данные для недели
async function loadWeekData() {
    try {
        // Находим понедельник для currentDate
        const today = new Date(currentDate.getTime());
        const dayOfWeek = today.getDay();
        const daysFromMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
        
        const monday = new Date(today.getTime());
        monday.setDate(today.getDate() - daysFromMonday);
        
        // Создаем массив всех 7 дней недели, начиная с понедельника
        const weekDays = [];
        const dayNames = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
        
        for (let i = 0; i < 7; i++) {
            const day = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i);
            weekDays.push(day);
        }
        
        const url = `/animals/notes/by-week/?date=${formatDate(monday)}`;
        
        // Загружаем заметки для всей недели
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.error) {
            console.error('Ошибка загрузки данных недели:', data.error);
            return;
        }
        
        // Передаем массив заметок из поля notes
        renderWeekCalendar(weekDays, data.notes || []);
        updateWeekHeader(weekDays);
    } catch (error) {
        console.error('Ошибка загрузки данных недели:', error);
    }
}

// Загружает данные для месяца
async function loadMonthData() {
    try {
        const year = currentDate.getFullYear();
        const month = currentDate.getMonth() + 1;
        
        const response = await fetch(`/animals/notes/calendar-data/?year=${year}&month=${month}`);
        const data = await response.json();
        
        if (data.error) {
            console.error('Ошибка загрузки данных месяца:', data.error);
            return;
        }
        
        renderMonthCalendar(data);
        updateMonthHeader();
    } catch (error) {
        console.error('Ошибка загрузки данных месяца:', error);
    }
}

// Отображает недельный календарь
function renderWeekCalendar(weekDays, notes) {
    const header = document.getElementById('weekDaysHeader');
    const body = document.getElementById('weekDaysBody');
    
    header.innerHTML = '';
    body.innerHTML = '';
    
    const dayNames = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
    
    // Создаем заголовки и ячейки для каждого дня
    for (let index = 0; index < weekDays.length; index++) {
        const date = weekDays[index];
        const dayName = dayNames[index];
        const dateStr = formatDate(date);
        
        // Заголовок
        const th = document.createElement('th');
        th.innerHTML = `
            <div class="day-name">${dayName}</div>
            <div class="day-number">${date.getDate()}</div>
        `;
        header.appendChild(th);
        
        // Ячейка дня
        const td = document.createElement('td');
        td.dataset.date = dateStr;
        
        // Ищем заметку для этого дня
        const dayNote = notes.find(note => {
            const noteDate = note.date;
            if (typeof noteDate === 'string') {
                return noteDate === dateStr || noteDate.split('T')[0] === dateStr;
            }
            return formatDate(new Date(noteDate)) === dateStr;
        });
        
        if (dayNote) {
            td.classList.add('has-note');
            // ИСПРАВЛЕНИЕ: Используем innerHTML для правильного отображения HTML-ссылок
            td.innerHTML = `<div class="note-preview">${dayNote.formatted_text}</div>`;
        }
        
        // Добавляем обработчик события
        td.onclick = function() {
            openNoteModal(dateStr, dayNote);
        };
        
        body.appendChild(td);
    }
}

// Отображает месячный календарь
function renderMonthCalendar(notesData) {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    const calendarBody = document.getElementById('monthCalendarBody');
    calendarBody.innerHTML = '';
    
    // Получаем первый день месяца и количество дней
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    
    // Получаем день недели первого дня (0 = воскресенье, нужно сделать понедельник = 0)
    let startDay = firstDay.getDay();
    startDay = startDay === 0 ? 6 : startDay - 1;
    
    let date = 1;
    let nextMonthDate = 1;
    
    // Создаем 6 недель (строк)
    for (let week = 0; week < 6; week++) {
        const row = document.createElement('tr');
        
        // Создаем 7 дней (колонок)
        for (let day = 0; day < 7; day++) {
            const cell = document.createElement('td');
            
            if (week === 0 && day < startDay) {
                // Дни предыдущего месяца
                const prevMonth = new Date(year, month - 1, 0);
                const prevDate = prevMonth.getDate() - (startDay - day - 1);
                cell.textContent = prevDate;
                cell.classList.add('other-month');
            } else if (date > daysInMonth) {
                // Дни следующего месяца
                cell.textContent = nextMonthDate;
                cell.classList.add('other-month');
                nextMonthDate++;
            } else {
                // Дни текущего месяца
                const currentDateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(date).padStart(2, '0')}`;
                
                cell.innerHTML = `<div class="day-number">${date}</div>`;
                
                // Проверяем, есть ли заметки в этот день
                if (notesData[currentDateStr]) {
                    cell.classList.add('has-note');
                    const firstNote = notesData[currentDateStr][0];
                    cell.innerHTML += `<div class="note-preview">${firstNote.formatted_text}</div>`;
                    
                    // Добавляем обработчик клика
                    cell.addEventListener('click', () => {
                        openNoteModal(currentDateStr, firstNote);
                    });
                } else {
                    cell.addEventListener('click', () => openNoteModal(currentDateStr, null));
                }
                
                date++;
            }
            
            row.appendChild(cell);
        }
        
        calendarBody.appendChild(row);
        
        // Если все дни месяца отображены и мы не в первых 4 неделях, прекращаем
        if (date > daysInMonth && week >= 4) {
            break;
        }
    }
}

// Обновляет заголовок недели
function updateWeekHeader(weekDays) {
    if (weekDays.length === 0) return;
    
    const startStr = formatDateRussian(weekDays[0]);
    const endStr = formatDateRussian(weekDays[weekDays.length - 1]);
    
    document.getElementById('currentPeriod').textContent = `${startStr} - ${endStr}`;
}

// Обновляет заголовок месяца
function updateMonthHeader() {
    const monthNames = [
        'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
        'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ];
    
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    document.getElementById('currentPeriod').textContent = `${monthNames[month]} ${year}`;
}

// Открывает модальное окно для редактирования заметки
function openNoteModal(date, existingNote = null) {
    console.log('Открытие модального окна для даты:', date);
    console.log('Существующая заметка:', existingNote);
    
    currentNoteDate = date;
    currentNoteId = existingNote ? existingNote.id : null;
    
    document.getElementById('noteDate').value = date;
    
    // Показываем/скрываем кнопку удаления
    const deleteBtn = document.getElementById('deleteNoteBtn');
    if (existingNote) {
        deleteBtn.style.display = 'inline-block';
        // Для редактирования показываем исходный текст
        document.getElementById('noteText').value = existingNote.text;
    } else {
        deleteBtn.style.display = 'none';
        document.getElementById('noteText').value = '';
    }
    
    const modal = new bootstrap.Modal(document.getElementById('noteModal'));
    modal.show();
}

// Сохраняет заметку
async function saveNote() {
    const text = document.getElementById('noteText').value.trim();
    
    if (!text) {
        alert('Введите текст заметки');
        return;
    }
    
    console.log('Сохранение заметки:');
    console.log('  Дата:', currentNoteDate);
    console.log('  Текст:', text);
    console.log('  ID заметки:', currentNoteId);
    
    try {
        const url = currentNoteId ? `/animals/notes/${currentNoteId}/` : '/animals/notes/';
        const method = currentNoteId ? 'PUT' : 'POST';
        
        const requestData = {
            date: currentNoteDate,
            text: text
        };
        
        console.log('Отправляем запрос:', { url, method, data: requestData });
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify(requestData)
        });
        
        console.log('Ответ сервера:', response.status);
        
        if (response.ok) {
            const responseData = await response.json();
            console.log('Данные ответа:', responseData);
            
            const modal = bootstrap.Modal.getInstance(document.getElementById('noteModal'));
            if (modal) {
                modal.hide();
            }
            updateCalendar(); // Перезагружаем календарь
        } else {
            const errorData = await response.json();
            console.error('Ошибка ответа:', errorData);
            alert('Ошибка сохранения: ' + (errorData.error || 'Неизвестная ошибка'));
        }
    } catch (error) {
        console.error('Ошибка сохранения заметки:', error);
        alert('Ошибка сохранения заметки');
    }
}

// Загружает все бирки
async function loadAllTags() {
    try {
        const response = await fetch('/animals/api/all-tags/');
        const data = await response.json();
        
        if (data.error) {
            console.error('Ошибка загрузки бирок:', data.error);
            return;
        }
        
        allTags = data;
        renderTags(allTags);
    } catch (error) {
        console.error('Ошибка загрузки бирок:', error);
    }
}

// Загружает все статусы
async function loadAllStatuses() {
    try {
        const response = await fetch('/animals/api/all-statuses/');
        const data = await response.json();
        
        if (data.error) {
            console.error('Ошибка загрузки статусов:', data.error);
            return;
        }
        
        allStatuses = data;
    } catch (error) {
        console.error('Ошибка загрузки статусов:', error);
    }
}

// Показывает модальное окно выбора бирки
function showTagModal() {
    renderTags(allTags);
    const modal = new bootstrap.Modal(document.getElementById('tagModal'));
    modal.show();
}

// Отображает список бирок
function renderTags(tags) {
    const container = document.getElementById('tagsList');
    container.innerHTML = '';
    
    tags.forEach(tag => {
        const div = document.createElement('div');
        div.className = `tag-item ${tag.is_active ? 'active' : 'inactive'}`;
        div.innerHTML = `
            <span class="tag-number">${tag.tag_number}</span>
            ${!tag.is_active ? '<small>(архив)</small>' : ''}
        `;
        
        div.addEventListener('click', () => insertTag(tag));
        container.appendChild(div);
    });
}

// Фильтрует бирки по поисковому запросу
function filterTags() {
    const search = document.getElementById('tagSearch').value.toLowerCase();
    const filteredTags = allTags.filter(tag => 
        tag.tag_number.toLowerCase().includes(search)
    );
    renderTags(filteredTags);
}

// Вставляет бирку в текст заметки
function insertTag(tag) {
    const textarea = document.getElementById('noteText');
    const linkText = tag.tag_number; // Просто номер бирки без скобок
    
    // Вставляем текст в позицию курсора
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    
    textarea.value = text.substring(0, start) + linkText + text.substring(end);
    textarea.selectionStart = textarea.selectionEnd = start + linkText.length;
    textarea.focus();
    
    // Закрываем модальное окно
    const modal = bootstrap.Modal.getInstance(document.getElementById('tagModal'));
    if (modal) {
        modal.hide();
    }
}

// Вспомогательные функции
function formatDate(date) {
    // ИСПРАВЛЕНИЕ: Используем локальные значения вместо UTC
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function formatDateRussian(date) {
    const months = [
        'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
    ];
    
    return `${date.getDate()} ${months[date.getMonth()]}`;
}

function getCsrfToken() {
    // Сначала пробуем получить из мета-тега
    const metaToken = document.querySelector('meta[name="csrf-token"]');
    if (metaToken) {
        return metaToken.getAttribute('content');
    }
    
    // Затем из cookies
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') {
            return value;
        }
    }
    
    // Если не найден, пробуем получить из скрытого поля формы
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (csrfInput) {
        return csrfInput.value;
    }
    
    return '';
}

// Удаляет заметку
async function deleteNote() {
    if (!currentNoteId) {
        alert('Нет заметки для удаления');
        return;
    }
    
    if (!confirm('Вы уверены, что хотите удалить эту заметку?')) {
        return;
    }
    
    try {
        const response = await fetch(`/animals/notes/${currentNoteId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        });
        
        if (response.ok) {
            const modal = bootstrap.Modal.getInstance(document.getElementById('noteModal'));
            if (modal) {
                modal.hide();
            }
            updateCalendar(); // Перезагружаем календарь
        } else {
            const errorData = await response.json();
            alert('Ошибка удаления: ' + (errorData.error || 'Неизвестная ошибка'));
        }
    } catch (error) {
        console.error('Ошибка удаления заметки:', error);
        alert('Ошибка удаления заметки');
    }
}