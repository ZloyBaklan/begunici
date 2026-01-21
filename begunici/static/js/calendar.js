class LambingCalendar {
    constructor() {
        this.currentDate = new Date();
        this.lambingData = {};
        this.monthNames = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ];
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadLambingData();
        this.renderCalendar();
    }
    
    bindEvents() {
        document.getElementById('prevMonth').addEventListener('click', () => {
            this.currentDate.setMonth(this.currentDate.getMonth() - 1);
            this.renderCalendar();
        });
        
        document.getElementById('nextMonth').addEventListener('click', () => {
            this.currentDate.setMonth(this.currentDate.getMonth() + 1);
            this.renderCalendar();
        });
    }
    
    async loadLambingData() {
        try {
            const response = await fetch('/animals/lambing/calendar/');
            if (response.ok) {
                this.lambingData = await response.json();
                this.renderCalendar();
            } else {
                console.error('Ошибка загрузки данных календаря:', response.statusText);
            }
        } catch (error) {
            console.error('Ошибка загрузки данных календаря:', error);
        }
    }
    
    renderCalendar() {
        const year = this.currentDate.getFullYear();
        const month = this.currentDate.getMonth();
        
        // Обновляем заголовок
        document.getElementById('currentMonth').textContent = 
            `${this.monthNames[month]} ${year}`;
        
        // Получаем первый день месяца и количество дней
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const daysInMonth = lastDay.getDate();
        
        // Получаем день недели первого дня (0 = воскресенье, нужно сделать понедельник = 0)
        let startDay = firstDay.getDay();
        startDay = startDay === 0 ? 6 : startDay - 1; // Преобразуем в понедельник = 0
        
        // Очищаем календарь
        const calendarBody = document.getElementById('calendarBody');
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
                    
                    // Проверяем, есть ли роды в этот день
                    if (this.lambingData[currentDateStr]) {
                        cell.classList.add('has-lambing');
                        const count = this.lambingData[currentDateStr].length;
                        cell.innerHTML += `<div class="lambing-count">${count}</div>`;
                        
                        // Добавляем обработчик клика
                        cell.addEventListener('click', () => {
                            this.showLambingDetails(currentDateStr, this.lambingData[currentDateStr]);
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
    
    showLambingDetails(dateStr, lambings) {
        const modal = new bootstrap.Modal(document.getElementById('lambingModal'));
        const modalBody = document.getElementById('lambingModalBody');
        const modalTitle = document.getElementById('lambingModalLabel');
        
        // Форматируем дату для заголовка
        const date = new Date(dateStr);
        const formattedDate = date.toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'long',
            year: 'numeric'
        });
        
        modalTitle.textContent = `Ожидаемые роды на ${formattedDate}`;
        
        // Создаем содержимое модального окна
        let content = '<div class="list-group">';
        
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
        modalBody.innerHTML = content;
        
        modal.show();
    }
}

// Инициализируем календарь после загрузки страницы
document.addEventListener('DOMContentLoaded', () => {
    new LambingCalendar();
});