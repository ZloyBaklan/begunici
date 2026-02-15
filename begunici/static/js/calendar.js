class LambingCalendar {
    constructor() {
        this.currentDate = new Date();
        this.lambingData = {};
        this.notesData = {};
        this.vetData = {};
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
            this.loadNotesData(),
            this.loadVetData()
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
                await Promise.all([
                    this.loadNotesData(),
                    this.loadVetData()
                ]);
                this.renderCalendar();
            });
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', async () => {
                this.currentDate.setMonth(this.currentDate.getMonth() + 1);
                await Promise.all([
                    this.loadNotesData(),
                    this.loadVetData()
                ]);
                this.renderCalendar();
            });
        }
        
        if (fullCalendarBtn) {
            // Обработчик для кнопки "Открыть полный календарь"
            fullCalendarBtn.addEventListener('click', async () => {
                // Перезагружаем все данные
                await Promise.all([
                    this.loadLambingData(),
                    this.loadNotesData(),
                    this.loadVetData()
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
    
    async loadVetData() {
        try {
            const year = this.currentDate.getFullYear();
            const month = this.currentDate.getMonth() + 1;
            const response = await fetch(`/animals/notes/vet-calendar-data/?year=${year}&month=${month}`);
            if (response.ok) {
                this.vetData = await response.json();
            } else {
                console.error('Ошибка загрузки ветеринарных данных календаря:', response.statusText);
            }
        } catch (error) {
            console.error('Ошибка загрузки ветеринарных данных календаря:', error);
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
                    const hasVet = this.vetData[currentDateStr];
                    
                    // Определяем типы событий
                    const eventTypes = [];
                    if (hasLambing) eventTypes.push('lambing');
                    if (hasNotes) eventTypes.push('notes');
                    if (hasVet && hasVet.vet_treatments && hasVet.vet_treatments.length > 0) eventTypes.push('vet_treatments');
                    if (hasVet && hasVet.vet_expiring && hasVet.vet_expiring.length > 0) eventTypes.push('vet_expiring');
                    
                    let totalCount = 0;
                    if (hasLambing) totalCount += hasLambing.length;
                    if (hasNotes) totalCount += hasNotes.length;
                    if (hasVet && hasVet.vet_treatments) totalCount += hasVet.vet_treatments.length;
                    if (hasVet && hasVet.vet_expiring) totalCount += hasVet.vet_expiring.length;
                    
                    if (eventTypes.length > 1) {
                        // Многоцветная ячейка - делим на части
                        cell.classList.add('has-multiple-events');
                        
                        // Создаем градиент в зависимости от количества типов событий
                        let gradientColors = [];
                        let gradientPercentages = [];
                        
                        const partSize = 100 / eventTypes.length;
                        
                        eventTypes.forEach((type, index) => {
                            let color = '';
                            switch(type) {
                                case 'lambing':
                                    color = '#dc3545';
                                    break;
                                case 'vet_treatments':
                                    color = '#ff9800';
                                    break;
                                case 'vet_expiring':
                                    color = '#ffeb3b';
                                    break;
                                case 'notes':
                                    color = '#28a745';
                                    break;
                            }
                            
                            const startPercent = index * partSize;
                            const endPercent = (index + 1) * partSize;
                            
                            gradientColors.push(`${color} ${startPercent}%`);
                            gradientColors.push(`${color} ${endPercent}%`);
                        });
                        
                        // Применяем градиент как фон
                        cell.style.background = `linear-gradient(to right, ${gradientColors.join(', ')})`;
                        cell.style.color = 'white';
                        cell.style.fontWeight = 'bold';
                        
                        cell.innerHTML += `<div class="lambing-count">${totalCount}</div>`;
                    } else if (eventTypes.length === 1) {
                        // Одноцветная ячейка
                        const eventType = eventTypes[0];
                        
                        if (eventType === 'lambing') {
                            cell.classList.add('has-lambing');
                        } else if (eventType === 'notes') {
                            cell.classList.add('has-notes');
                        } else if (eventType === 'vet_treatments') {
                            cell.classList.add('has-vet-treatment');
                        } else if (eventType === 'vet_expiring') {
                            cell.classList.add('has-vet-expiring');
                        }
                        
                        cell.innerHTML += `<div class="lambing-count">${totalCount}</div>`;
                    }
                    
                    // Добавляем обработчик клика
                    if (eventTypes.length > 0) {
                        cell.addEventListener('click', () => {
                            this.showDayDetails(currentDateStr, hasLambing, hasNotes, hasVet);
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
    
    showDayDetails(dateStr, lambings, notes, vetData) {
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
            content += '<div class="list-group mb-3" style="max-height: 300px; overflow-y: auto;">';
            
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
        
        // Показываем ветобработки
        if (vetData && vetData.vet_treatments && vetData.vet_treatments.length > 0) {
            content += '<h6 style="color: #ff9800;">Ветобработки:</h6>';
            content += '<div class="list-group mb-3" style="max-height: 300px; overflow-y: auto;">';
            
            vetData.vet_treatments.forEach(vet => {
                content += `
                    <div class="list-group-item">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1">
                                <a href="/animals/${this.getAnimalTypeRoute(vet.animal_type)}/${vet.tag_number}/info/" class="text-decoration-none">
                                    ${vet.tag_number}
                                </a>
                                <span class="text-muted ms-2">${vet.care_type} - ${vet.care_name}</span>
                            </h6>
                        </div>
                        <small>
                            Срок действия: ${vet.duration_days === 0 ? 'Бессрочно' : vet.duration_days + ' дней'}
                            ${vet.expiry_date ? ` (до ${new Date(vet.expiry_date).toLocaleDateString('ru-RU')})` : ''}
                        </small>
                    </div>
                `;
            });
            
            content += '</div>';
        }
        
        // Показываем истекающие ветобработки
        if (vetData && vetData.vet_expiring && vetData.vet_expiring.length > 0) {
            content += '<h6 style="color: #ffeb3b;">Окончание срока действия ветобработки:</h6>';
            content += '<div class="list-group mb-3" style="max-height: 300px; overflow-y: auto;">';
            
            vetData.vet_expiring.forEach(vet => {
                content += `
                    <div class="list-group-item">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1">
                                <a href="/animals/${this.getAnimalTypeRoute(vet.animal_type)}/${vet.tag_number}/info/" class="text-decoration-none">
                                    ${vet.tag_number}
                                </a>
                                <span class="text-muted ms-2">${vet.care_type} - ${vet.care_name}</span>
                            </h6>
                        </div>
                        <small>
                            Дата обработки: ${new Date(vet.date_of_care).toLocaleDateString('ru-RU')}
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
    
    getAnimalTypeRoute(animalType) {
        const typeMap = {
            'Maker': 'maker',
            'Ram': 'ram', 
            'Ewe': 'ewe',
            'Sheep': 'sheep'
        };
        
        return typeMap[animalType] || 'maker';
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