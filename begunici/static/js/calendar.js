class LambingCalendar {
    constructor() {
        this.currentDate = new Date();
        this.lambingData = {};
        this.notesData = {};
        this.monthNames = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ];
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        // Загружаем данные параллельно
        Promise.all([
            this.loadLambingData(),
            this.loadNotesData()
        ]).then(() => {
            // После загрузки всех данных рендерим календарь
            this.renderCalendar();
        }).catch(error => {
            console.error('Ошибка инициализации календаря:', error);
            // Рендерим календарь даже если данные не загрузились
            this.renderCalendar();
        });
    }
    
    bindEvents() {
        const prevBtn = document.getElementById('prevMonth');
        const nextBtn = document.getElementById('nextMonth');
        const fullCalendarBtn = document.getElementById('fullCalendarBtn');
        
        if (prevBtn) {
            prevBtn.addEventListener('click', async () => {
                this.currentDate.setMonth(this.currentDate.getMonth() - 1);
                await this.loadNotesData(); // Загружаем заметки для нового месяца
                this.renderCalendar();
            });
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', async () => {
                this.currentDate.setMonth(this.currentDate.getMonth() + 1);
                await this.loadNotesData(); // Загружаем заметки для нового месяца
                this.renderCalendar();
            });
        }
        
        if (fullCalendarBtn) {
            // Обработчик для кнопки "Открыть полный календарь"
            fullCalendarBtn.addEventListener('click', async () => {
                // Перезагружаем все данные
                await Promise.all([
                    this.loadLambingData(),
                    this.loadNotesData()
                ]);
                this.renderCalendar();
            });
        }
    }
    
    async loadLambingData() {
        try {
            const response = await fetch('/animals/lambing/calendar/');
            if (response.ok) {
                this.lambingData = await response.json();
            } else {
                console.error('Ошибка загрузки данных календаря:', response.statusText);
            }
        } catch (error) {
            console.error('Ошибка загрузки данных календаря:', error);
        }
    }
    
    async loadNotesData() {
        try {
            const year = this.currentDate.getFullYear();
            const month = this.currentDate.getMonth() + 1;
            const response = await fetch(`/animals/notes/calendar-data/?year=${year}&month=${month}`);
            if (response.ok) {
                this.notesData = await response.json();
            } else {
                console.error('Ошибка загрузки заметок календаря:', response.statusText);
            }
        } catch (error) {
            console.error('Ошибка загрузки заметок календаря:', error);
        }
    }
    
    renderCalendar() {
        const year = this.currentDate.getFullYear();
        const month = this.currentDate.getMonth();
        
        // Проверяем, что элементы календаря существуют
        const currentMonthElement = document.getElementById('currentMonth');
        const calendarBody = document.getElementById('calendarBody');
        
        if (!currentMonthElement || !calendarBody) {
            console.warn('Элементы календаря не найдены на странице');
            return;
        }
        
        // Обновляем заголовок
        currentMonthElement.textContent = `${this.monthNames[month]} ${year}`;
        
        // Получаем первый день месяца и количество дней
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const daysInMonth = lastDay.getDate();
        
        // Получаем день недели первого дня (0 = воскресенье, нужно сделать понедельник = 0)
        let startDay = firstDay.getDay();
        startDay = startDay === 0 ? 6 : startDay - 1; // Преобразуем в понедельник = 0
        
        // Очищаем календарь
        calendarBody.innerHTML = '';
        
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
                    
                    const hasLambing = this.lambingData[currentDateStr];
                    const hasNotes = this.notesData[currentDateStr];
                    
                    // Определяем класс ячейки в зависимости от наличия родов и заметок
                    if (hasLambing && hasNotes) {
                        cell.classList.add('has-both');
                        const lambingCount = hasLambing.length;
                        const notesCount = hasNotes.length;
                        cell.innerHTML += `<div class="lambing-count">${lambingCount}/${notesCount}</div>`;
                    } else if (hasLambing) {
                        cell.classList.add('has-lambing');
                        const count = hasLambing.length;
                        cell.innerHTML += `<div class="lambing-count">${count}</div>`;
                    } else if (hasNotes) {
                        cell.classList.add('has-notes');
                        const count = hasNotes.length;
                        cell.innerHTML += `<div class="lambing-count">${count}</div>`;
                    }
                    
                    // Добавляем обработчик клика
                    if (hasLambing || hasNotes) {
                        cell.addEventListener('click', () => {
                            this.showDayDetails(currentDateStr, hasLambing, hasNotes);
                        });
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
    
    showDayDetails(dateStr, lambings, notes) {
        const modalElement = document.getElementById('lambingModal');
        if (!modalElement) {
            console.warn('Модальное окно календаря не найдено на странице');
            return;
        }
        
        const modal = new bootstrap.Modal(modalElement);
        const modalBody = document.getElementById('lambingModalBody');
        const modalTitle = document.getElementById('lambingModalLabel');
        
        if (!modalBody || !modalTitle) {
            console.warn('Элементы модального окна не найдены');
            return;
        }
        
        // Форматируем дату для заголовка
        const date = new Date(dateStr);
        const formattedDate = date.toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'long',
            year: 'numeric'
        });
        
        modalTitle.textContent = `События на ${formattedDate}`;
        
        let content = '';
        
        // Показываем роды
        if (lambings && lambings.length > 0) {
            content += '<h6 class="text-danger">Ожидаемые роды:</h6>';
            content += '<div class="list-group mb-3">';
            
            lambings.forEach(lambing => {
                content += `
                    <div class="list-group-item">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1">
                                ${lambing.mother_type}: <strong>${lambing.mother_tag}</strong>
                            </h6>
                            <small>ID: ${lambing.id}</small>
                        </div>
                        <p class="mb-1">
                            <strong>Отец:</strong> ${lambing.father_type} ${lambing.father_tag}
                        </p>
                        <small>
                            <strong>Дата случки:</strong> ${new Date(lambing.start_date).toLocaleDateString('ru-RU')}
                        </small>
                    </div>
                `;
            });
            
            content += '</div>';
        }
        
        // Показываем заметки
        if (notes && notes.length > 0) {
            content += '<h6 class="text-success">Заметки:</h6>';
            content += '<div class="list-group">';
            
            notes.forEach(note => {
                content += `
                    <div class="list-group-item">
                        <div class="mb-2">${note.formatted_text}</div>
                    </div>
                `;
            });
            
            content += '</div>';
        }
        
        if (!content) {
            content = '<p>Нет событий на эту дату.</p>';
        }
        
        modalBody.innerHTML = content;
        modal.show();
    }
    
    showLambingDetails(dateStr, lambings) {
        // Оставляем старый метод для совместимости
        this.showDayDetails(dateStr, lambings, null);
    }
}

// Инициализируем календарь после загрузки страницы
document.addEventListener('DOMContentLoaded', () => {
    // Проверяем, есть ли элементы календаря на странице
    const calendarBody = document.getElementById('calendarBody');
    const currentMonth = document.getElementById('currentMonth');
    
    if (calendarBody && currentMonth) {
        new LambingCalendar();
    } else {
        console.log('Элементы календаря не найдены на странице - календарь не инициализирован');
    }
});