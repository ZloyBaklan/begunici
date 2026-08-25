// Общие функции для экспорта в Excel

function getExportApiErrorFieldLabel(field) {
    const labels = {
        animal_type: 'Тип животного',
        include_details: 'Детальный экспорт',
        limit: 'Лимит',
        selected_animals: 'Выбранные животные',
        non_field_errors: 'Общая ошибка',
    };

    return labels[field] || String(field).replaceAll('_', ' ');
}

function translateExportApiErrorText(message) {
    const text = String(message || '').trim();
    const translations = {
        'This field is required.': 'Это поле обязательно для заполнения.',
        'This field may not be blank.': 'Это поле не может быть пустым.',
        'This field may not be null.': 'Это поле не может быть пустым.',
        'A valid integer is required.': 'Нужно указать целое число.',
        'A valid number is required.': 'Нужно указать число.',
        'Enter a valid date.': 'Укажите корректную дату.',
        'Date has wrong format. Use one of these formats instead: YYYY-MM-DD.': 'Неверный формат даты. Используйте формат ДД.ММ.ГГГГ.',
        'This field must be unique.': 'Такое значение уже используется.',
    };
    if (translations[text]) return translations[text];
    if (text.includes('Ensure this value is greater than or equal to 0')) return 'Значение не может быть меньше 0.';
    if (text.includes('Invalid pk')) return 'Выбранное значение не найдено в базе.';
    return text;
}

function parseExportApiErrorString(message) {
    const text = String(message || '').trim();
    if (!text) return '';

    const cleaned = text.replace(
        /ErrorDetail\(string=(['"])(.*?)\1,\s*code=(['"]).*?\3\)/g,
        (_, quote, errorMessage) => `'${String(errorMessage).replaceAll("'", "\\'")}'`
    );

    const fieldMessages = [];
    const fieldRegex = /['"]([^'"]+)['"]\s*:\s*(\[[\s\S]*?\]|['"][\s\S]*?['"])/g;
    let fieldMatch;
    while ((fieldMatch = fieldRegex.exec(cleaned)) !== null) {
        const field = fieldMatch[1];
        const rawValue = fieldMatch[2];
        const values = [];
        const valueRegex = /['"]([^'"]+)['"]/g;
        let valueMatch;
        while ((valueMatch = valueRegex.exec(rawValue)) !== null) {
            values.push(translateExportApiErrorText(valueMatch[1]));
        }

        if (values.length) {
            fieldMessages.push(`${getExportApiErrorFieldLabel(field)}: ${values.join(', ')}`);
        }
    }

    if (fieldMessages.length) return fieldMessages.join('\n');

    const detailMessages = [];
    const detailRegex = /ErrorDetail\(string=(['"])(.*?)\1,\s*code=(['"]).*?\3\)/g;
    let detailMatch;
    while ((detailMatch = detailRegex.exec(text)) !== null) {
        detailMessages.push(translateExportApiErrorText(detailMatch[2]));
    }

    return detailMessages.length ? detailMessages.join('\n') : translateExportApiErrorText(text);
}

function stringifyExportApiErrorValue(value) {
    if (value === undefined || value === null || value === '') return '';
    if (typeof value === 'string') return parseExportApiErrorString(value);
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value)) {
        return value.map(stringifyExportApiErrorValue).filter(Boolean).join(', ');
    }
    if (typeof value === 'object') {
        return Object.entries(value).map(([field, nestedValue]) => {
            const message = stringifyExportApiErrorValue(nestedValue);
            if (!message) return '';
            if (['detail', 'error', 'non_field_errors'].includes(field)) return message;
            return `${getExportApiErrorFieldLabel(field)}: ${message}`;
        }).filter(Boolean).join('\n');
    }
    return String(value);
}

function getExportApiErrorMessage(errorData, fallback = 'Не удалось выполнить экспорт. Проверьте выбранные параметры.') {
    if (!errorData) return fallback;
    if (typeof errorData === 'string') return parseExportApiErrorString(errorData);
    if (typeof errorData !== 'object') return fallback;
    if (typeof errorData.error === 'string') return parseExportApiErrorString(errorData.error);
    if (typeof errorData.detail === 'string') return parseExportApiErrorString(errorData.detail);

    const messages = Object.entries(errorData).map(([field, value]) => {
        const message = stringifyExportApiErrorValue(value);
        if (!message) return '';
        if (['detail', 'error', 'non_field_errors'].includes(field)) return message;
        return `${getExportApiErrorFieldLabel(field)}: ${message}`;
    }).filter(Boolean);

    return messages.length ? messages.join('\n') : fallback;
}

function openExportModal(animalType) {
    const modal = document.getElementById('export-modal');
    modal.style.display = 'flex';
    modal.dataset.animalType = animalType;
    
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

function getAppliedListFiltersForExport() {
    const urlParams = new URLSearchParams(window.location.search);
    const filterKeys = [
        'search',
        'birth_date_from',
        'birth_date_to',
        'date_otbivka_from',
        'date_otbivka_to',
        'age_min',
        'age_max',
        'weight_min',
        'weight_max',
        'father_tag',
        'mother_tag',
        'animal_status',
        'place',
        'has_rshn_tag',
        'is_reject',
    ];
    const filters = {};

    filterKeys.forEach((key) => {
        const value = (urlParams.get(key) || '').trim();
        if (value) {
            filters[key] = value;
        }
    });

    const commonAnimalType = (urlParams.get('animal_type') || '').trim();
    if (commonAnimalType) {
        filters.common_animal_type = commonAnimalType;
    }

    return filters;
}

async function performExport(animalType) {
    const selectedAnimals = getSelectedAnimals();
    const hasSelectedAnimals = selectedAnimals.length > 0;
    const includeDetailsCheckbox = document.getElementById('include-details');
    
    const data = {
        animal_type: animalType || document.getElementById('export-modal').dataset.animalType,
        include_details: Boolean(includeDetailsCheckbox?.checked)
    };
    
    // Если есть выбранные животные, экспортируем только их
    if (hasSelectedAnimals) {
        data.selected_animals = selectedAnimals;
    } else {
        Object.assign(data, getAppliedListFiltersForExport());

        // Добавляем фильтры если они включены
        if (document.getElementById('filter-limit-enabled').checked) {
            const limit = document.getElementById('filter-limit').value;
            if (limit) data.limit = parseInt(limit);
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
            const contentType = response.headers.get('content-type') || '';
            const errorText = await response.text();
            console.error('Ошибка сервера:', errorText);

            if (contentType.includes('application/json')) {
                let errorData = null;
                try {
                    errorData = JSON.parse(errorText);
                } catch (parseError) {
                    errorData = null;
                }
                if (errorData) {
                    throw new Error(getExportApiErrorMessage(errorData));
                }
            }

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
    const includeDetailsCheckbox = document.getElementById('include-details');
    if (includeDetailsCheckbox) includeDetailsCheckbox.checked = false;
    
    // Сбрасываем и отключаем поля ввода
    const inputFields = [
        'filter-limit',
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
    
    // Клонируем элементы чтобы удалить все старые обработчики
    const newLimitCheckbox = limitCheckbox.cloneNode(true);
    
    limitCheckbox.parentNode.replaceChild(newLimitCheckbox, limitCheckbox);
    
    // Добавляем новые обработчики
    newLimitCheckbox.addEventListener('change', (e) => {
        document.getElementById('filter-limit').disabled = !e.target.checked;
        if (!e.target.checked) {
            document.getElementById('filter-limit').value = '';
        }
    });
}


