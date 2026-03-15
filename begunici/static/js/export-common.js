// Общие функции для экспорта в Excel

function openExportModal(animalType) {
    const modal = document.getElementById('export-modal');
    modal.style.display = 'flex';
    modal.dataset.animalType = animalType; // Сохраняем тип животного
    
    // Сначала сбрасываем все поля и отключаем их
    resetModalFields();
    
    // Проверяем выбранные животные
    const selectedAnimals = getSelectedAnimals();
    const hasSelectedAnimals = selectedAnimals.length > 0;
    
    // Показываем/скрываем секцию выбранных животных
    const exportSelectedSection = document.getElementById('export-selected-section');
    const selectedCountSpan = document.getElementById('selected-count');
    
    if (hasSelectedAnimals) {
        exportSelectedSection.style.display = 'block';
        selectedCountSpan.textContent = selectedAnimals.length;
        
        // Отключаем другие фильтры
        disableFilterSections(true);
    } else {
        exportSelectedSection.style.display = 'none';
        
        // Включаем другие фильтры (но поля остаются disabled до отметки чекбоксов)
        disableFilterSections(false);
        
        // Добавляем обработчики для включения/выключения полей
        setupFilterEventListeners();
    }
}

function closeExportModal() {
    const modal = document.getElementById('export-modal');
    modal.style.display = 'none';
    
    // Используем функцию сброса полей
    resetModalFields();
    
    // Скрываем секцию выбранных животных
    const exportSelectedSection = document.getElementById('export-selected-section');
    if (exportSelectedSection) {
        exportSelectedSection.style.display = 'none';
    }
    
    // Включаем все секции фильтров (но поля остаются disabled)
    disableFilterSections(false);
}

async function performExport(animalType) {
    const selectedAnimals = getSelectedAnimals();
    const hasSelectedAnimals = selectedAnimals.length > 0;
    
    const data = {
        animal_type: animalType || document.getElementById('export-modal').dataset.animalType,
        include_details: document.getElementById('include-details').checked
    };
    
    // Если есть выбранные животные, экспортируем только их
    if (hasSelectedAnimals) {
        data.selected_animals = selectedAnimals;
    } else {
        // Добавляем фильтры если они включены
        if (document.getElementById('filter-limit-enabled').checked) {
            const limit = document.getElementById('filter-limit').value;
            if (limit) data.limit = parseInt(limit);
        }
        
        if (document.getElementById('filter-weight-enabled').checked) {
            const weightMin = document.getElementById('filter-weight-min').value;
            const weightMax = document.getElementById('filter-weight-max').value;
            if (weightMin) data.weight_min = parseFloat(weightMin);
            if (weightMax) data.weight_max = parseFloat(weightMax);
        }
        
        if (document.getElementById('filter-age-enabled').checked) {
            const ageMin = document.getElementById('filter-age-min').value;
            const ageMax = document.getElementById('filter-age-max').value;
            if (ageMin) data.age_min = parseFloat(ageMin);
            if (ageMax) data.age_max = parseFloat(ageMax);
        }
    }
    
    try {
        const csrfToken = getCSRFToken();
        if (!csrfToken) {
            throw new Error('CSRF токен не найден. Обновите страницу и попробуйте снова.');
        }
        
        console.log('Отправляем данные для экспорта:', data);
        
        const response = await fetch('/animals/api/export-excel/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Ошибка сервера:', errorText);
            throw new Error(`Ошибка сервера: ${response.status} ${response.statusText}`);
        }
        
        // Проверяем, что ответ действительно файл (Excel или CSV)
        const contentType = response.headers.get('content-type');
        const isExcel = contentType && contentType.includes('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        const isCSV = contentType && contentType.includes('text/csv');
        
        if (!contentType || (!isExcel && !isCSV)) {
            const errorText = await response.text();
            console.error('Неожиданный тип ответа:', contentType, errorText);
            throw new Error('Сервер вернул неожиданный тип данных');
        }
        
        // Скачиваем файл
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        
        // Определяем расширение файла по типу контента
        const fileExtension = isExcel ? 'xlsx' : 'csv';
        const filePrefix = hasSelectedAnimals ? `selected_${animalType}s` : `${animalType}s`;
        a.download = `${filePrefix}_${new Date().toISOString().split('T')[0]}.${fileExtension}`;
        
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        closeExportModal();
        const formatName = isExcel ? 'Excel' : 'CSV';
        const exportType = hasSelectedAnimals ? 'выбранных животных' : 'всех животных';
        alert(`Файл с ${exportType} успешно экспортирован в формате ${formatName}!`);
    } catch (error) {
        console.error('Ошибка экспорта:', error);
        alert(`Ошибка при экспорте файла: ${error.message}`);
    }
}

function getCSRFToken() {
    // Сначала пробуем получить из cookies
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') {
            return decodeURIComponent(value);
        }
    }
    
    // Если не найден в cookies, пробуем получить из мета-тега
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfMeta) {
        return csrfMeta.getAttribute('content');
    }
    
    // Если не найден в мета-теге, пробуем получить из скрытого поля формы
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (csrfInput) {
        return csrfInput.value;
    }
    
    console.error('CSRF токен не найден');
    return '';
}

// Функция для получения выбранных животных
function getSelectedAnimals() {
    const checkboxes = document.querySelectorAll('tbody input[type="checkbox"]:checked');
    const selectedIds = [];
    
    checkboxes.forEach(checkbox => {
        if (checkbox.dataset.animalId) {
            selectedIds.push(parseInt(checkbox.dataset.animalId));
        }
    });
    
    return selectedIds;
}

// Функция для включения/отключения секций фильтров
function disableFilterSections(disable) {
    const sections = [
        'filter-limit-section',
        'filter-weight-section', 
        'filter-age-section'
    ];
    
    sections.forEach(sectionId => {
        const section = document.getElementById(sectionId);
        if (section) {
            const inputs = section.querySelectorAll('input');
            inputs.forEach(input => {
                if (input.type === 'checkbox') {
                    input.disabled = disable;
                    if (disable) {
                        input.checked = false;
                    }
                } else {
                    input.disabled = true; // Всегда отключаем поля ввода
                    if (disable) {
                        input.value = '';
                    }
                }
            });
            
            // Визуально показываем что секция отключена
            section.style.opacity = disable ? '0.5' : '1';
            section.style.pointerEvents = disable ? 'none' : 'auto';
        }
    });
}

// Функция для сброса всех полей модала
function resetModalFields() {
    // Сбрасываем чекбоксы
    document.getElementById('filter-limit-enabled').checked = false;
    document.getElementById('filter-weight-enabled').checked = false;
    document.getElementById('filter-age-enabled').checked = false;
    document.getElementById('include-details').checked = false;
    
    // Сбрасываем и отключаем поля ввода
    const inputFields = [
        'filter-limit',
        'filter-weight-min',
        'filter-weight-max',
        'filter-age-min',
        'filter-age-max'
    ];
    
    inputFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.value = '';
            field.disabled = true;
        }
    });
}

// Функция для настройки обработчиков событий фильтров
function setupFilterEventListeners() {
    // Удаляем старые обработчики (если есть) и добавляем новые
    const limitCheckbox = document.getElementById('filter-limit-enabled');
    const weightCheckbox = document.getElementById('filter-weight-enabled');
    const ageCheckbox = document.getElementById('filter-age-enabled');
    
    // Клонируем элементы чтобы удалить все старые обработчики
    const newLimitCheckbox = limitCheckbox.cloneNode(true);
    const newWeightCheckbox = weightCheckbox.cloneNode(true);
    const newAgeCheckbox = ageCheckbox.cloneNode(true);
    
    limitCheckbox.parentNode.replaceChild(newLimitCheckbox, limitCheckbox);
    weightCheckbox.parentNode.replaceChild(newWeightCheckbox, weightCheckbox);
    ageCheckbox.parentNode.replaceChild(newAgeCheckbox, ageCheckbox);
    
    // Добавляем новые обработчики
    newLimitCheckbox.addEventListener('change', (e) => {
        document.getElementById('filter-limit').disabled = !e.target.checked;
        if (!e.target.checked) {
            document.getElementById('filter-limit').value = '';
        }
    });
    
    newWeightCheckbox.addEventListener('change', (e) => {
        document.getElementById('filter-weight-min').disabled = !e.target.checked;
        document.getElementById('filter-weight-max').disabled = !e.target.checked;
        if (!e.target.checked) {
            document.getElementById('filter-weight-min').value = '';
            document.getElementById('filter-weight-max').value = '';
        }
    });
    
    newAgeCheckbox.addEventListener('change', (e) => {
        document.getElementById('filter-age-min').disabled = !e.target.checked;
        document.getElementById('filter-age-max').disabled = !e.target.checked;
        if (!e.target.checked) {
            document.getElementById('filter-age-min').value = '';
            document.getElementById('filter-age-max').value = '';
        }
    });
}
