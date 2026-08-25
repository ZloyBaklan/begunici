export function getCSRFToken() {
    const cookies = document.cookie.split(";").map(c => c.trim());
    const tokenCookie = cookies.find(c => c.startsWith("csrftoken="));
    
    if (!tokenCookie) return undefined;

    return decodeURIComponent(tokenCookie.split("=")[1]);
}

export function isTruthyFilterValue(value) {
    return ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase());
}

export function getCheckboxFilterValue(elementId) {
    return document.getElementById(elementId)?.checked ? '1' : '';
}

export function setCheckboxFilterValue(elementId, value) {
    const checkbox = document.getElementById(elementId);
    if (checkbox) {
        checkbox.checked = isTruthyFilterValue(value);
    }
}

export function addRshnPresenceFilter(containerId, checkboxId) {
    const container = document.getElementById(containerId);
    if (!container || document.getElementById(checkboxId)) {
        return;
    }

    const checkboxHtml = `
        <div class="form-check mb-1">
            <input type="checkbox" id="${checkboxId}" class="form-check-input">
            <label for="${checkboxId}" class="form-check-label small">Наличие бирки РСХН</label>
        </div>
    `;
    const slot = document.getElementById(`${checkboxId}-slot`);
    if (slot) {
        slot.innerHTML = checkboxHtml;
        return;
    }

    const row = document.createElement('div');
    row.className = 'row g-2 mt-2';
    row.innerHTML = `
        <div class="col-md-12">
            ${checkboxHtml}
        </div>
    `;
    container.appendChild(row);
}

const API_ERROR_FIELD_LABELS = {
    animal_status: 'Статус',
    animal_status_id: 'Статус',
    archive_act_date: 'Дата акта',
    archive_act_death_reason: 'Причина падежа',
    archive_act_diagnosis: 'Диагноз / основание',
    archive_act_fatness: 'Упитанность',
    archive_act_live_weight: 'Живой вес для акта',
    archive_act_number: 'Номер акта',
    archive_act_weight_date: 'Дата дополнительного веса',
    birth_date: 'Дата рождения',
    carcass_weight: 'Вес туши',
    care_class: 'Класс ветобработки',
    care_type: 'Тип ветобработки',
    date: 'Дата',
    date_of_status: 'Дата статуса',
    dead_lambs_count: 'Мертвые ягнята',
    detail: 'Ошибка',
    dorper_percentage: 'Кровность по основной породе',
    ewe: 'Ярка',
    father: 'Отец',
    father_tag: 'Бирка отца',
    lambs: 'Ягнята',
    medication: 'Препарат',
    mother: 'Мать',
    mother_tag: 'Бирка матери',
    non_field_errors: 'Общая ошибка',
    note: 'Примечание',
    place: 'Овчарня',
    place_id: 'Овчарня',
    planned_lambing_date: 'Плановый окот',
    plemstatus: 'Племенной статус',
    purpose: 'Цель',
    rshn_tag: 'Бирка РСХН',
    sheep: 'Овцематка',
    start_date: 'Дата постановки в группу',
    status_date: 'Дата статуса',
    tag: 'Бирка',
    tag_number: 'Бирка',
    veterinary_care: 'Ветобработка',
    veterinary_care_id: 'Ветобработка',
    weight: 'Вес',
    weight_date: 'Дата взвешивания',
    working_condition: 'Рабочее состояние',
};

function getApiErrorFieldLabel(field) {
    return API_ERROR_FIELD_LABELS[field] || field.replaceAll('_', ' ');
}

function translateApiErrorText(message) {
    const text = String(message || '').trim();
    const translations = {
        'This field is required.': 'Это поле обязательно для заполнения.',
        'This field may not be blank.': 'Это поле не может быть пустым.',
        'This field may not be null.': 'Это поле не может быть пустым.',
        'A valid integer is required.': 'Нужно указать целое число.',
        'A valid number is required.': 'Нужно указать число.',
        'Enter a valid date.': 'Укажите корректную дату.',
        'Date has wrong format. Use one of these formats instead: YYYY-MM-DD.': 'Неверный формат даты. Используйте формат ДД.ММ.ГГГГ.',
        'Enter a valid date/time.': 'Укажите корректные дату и время.',
        'This field must be unique.': 'Такое значение уже используется.',
        'Invalid pk "null" - object does not exist.': 'Выбранное значение не найдено.',
        'Incorrect type. Expected pk value, received str.': 'Выбрано некорректное значение.',
    };

    if (translations[text]) {
        return translations[text];
    }

    if (text.includes('Ensure this value is greater than or equal to 0')) {
        return 'Значение не может быть меньше 0.';
    }
    if (text.includes('Ensure this value is less than or equal to')) {
        return 'Значение больше допустимого максимума.';
    }
    if (text.includes('Ensure this value has no more than')) {
        return 'Значение содержит слишком много символов или цифр.';
    }
    if (text.includes('Invalid pk')) {
        return 'Выбранное значение не найдено в базе.';
    }
    if (text.includes('Got a `TypeError` when calling')) {
        return 'Сервер не смог сохранить данные из-за неподдерживаемого поля. Сообщите разработчику, на какой форме возникла ошибка.';
    }

    return text;
}

function parseApiErrorString(message) {
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
            values.push(translateApiErrorText(valueMatch[1]));
        }

        if (values.length) {
            fieldMessages.push(`${getApiErrorFieldLabel(field)}: ${values.join(', ')}`);
        }
    }

    if (fieldMessages.length) {
        return fieldMessages.join('\n');
    }

    const detailMessages = [];
    const detailRegex = /ErrorDetail\(string=(['"])(.*?)\1,\s*code=(['"]).*?\3\)/g;
    let detailMatch;
    while ((detailMatch = detailRegex.exec(text)) !== null) {
        detailMessages.push(translateApiErrorText(detailMatch[2]));
    }

    if (detailMessages.length) {
        return detailMessages.join('\n');
    }

    return translateApiErrorText(text);
}

function stringifyApiErrorValue(value, field = '') {
    if (value === undefined || value === null || value === '') {
        return '';
    }

    if (typeof value === 'string') {
        return parseApiErrorString(value);
    }

    if (typeof value === 'number' || typeof value === 'boolean') {
        return String(value);
    }

    if (Array.isArray(value)) {
        return value
            .map((item) => stringifyApiErrorValue(item, field))
            .filter(Boolean)
            .join(', ');
    }

    if (typeof value === 'object') {
        const nestedMessages = Object.entries(value)
            .map(([nestedField, nestedValue]) => {
                const nestedMessage = stringifyApiErrorValue(nestedValue, nestedField);
                if (!nestedMessage) return '';
                if (nestedField === 'non_field_errors' || nestedField === 'detail' || nestedField === 'error') {
                    return nestedMessage;
                }
                return `${getApiErrorFieldLabel(nestedField)}: ${nestedMessage}`;
            })
            .filter(Boolean);
        return nestedMessages.join('\n');
    }

    return String(value);
}

export function getApiErrorMessage(errorData, fallback = 'Не удалось выполнить действие. Проверьте введенные данные.') {
    if (!errorData) {
        return fallback;
    }

    if (typeof errorData === 'string') {
        return parseApiErrorString(errorData);
    }

    if (Array.isArray(errorData)) {
        return stringifyApiErrorValue(errorData) || fallback;
    }

    if (typeof errorData !== 'object') {
        return fallback;
    }

    if (typeof errorData.detail === 'string') {
        return parseApiErrorString(errorData.detail);
    }

    if (typeof errorData.error === 'string') {
        return parseApiErrorString(errorData.error);
    }

    const messages = Object.entries(errorData)
        .filter(([field]) => field !== 'requires_confirmation')
        .map(([field, value]) => {
            const message = stringifyApiErrorValue(value, field);
            if (!message) return '';
            if (field === 'non_field_errors' || field === 'detail' || field === 'error') {
                return message;
            }
            return `${getApiErrorFieldLabel(field)}: ${message}`;
        })
        .filter(Boolean);

    return messages.length ? messages.join('\n') : fallback;
}

export async function apiRequest(url, method = 'GET', body) {
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken(),
    }

    const options = { method, headers }
    if (body) options.body = JSON.stringify(body)

    try {
        const response = await fetch(url, options)

        if (!response.ok) {
            // Проверяем, является ли ответ JSON
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const errorData = await response.json();
                console.error(`Ошибка API [${response.status}]:`, errorData);
                const error = new Error(getApiErrorMessage(errorData));
                error.data = errorData;
                error.status = response.status;
                throw error;
            } else {
                // Если не JSON, читаем как текст для отладки
                const errorText = await response.text();
                console.error(`Ошибка API [${response.status}] (не JSON):`, errorText);
                throw new Error(`Ошибка сервера: ${response.status}`);
            }
        }

        if (response.status === 204) {
            return null; // No content
        }
        
        // Проверяем, что ответ действительно JSON
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return await response.json();
        } else {
            // Если не JSON, читаем как текст и выводим ошибку
            const responseText = await response.text();
            console.error('Ответ сервера не является JSON:', responseText);
            throw new Error('Сервер вернул некорректный ответ');
        }
    } catch (error) {
        console.error('Ошибка сети:', error);
        throw error;
    }
}

export function formatDateToOutput(dateString) {
    if (!dateString) return '-';
    
    // Если дата в формате YYYY-MM-DD, просто переформатируем
    if (dateString.match(/^\d{4}-\d{2}-\d{2}$/)) {
        const [year, month, day] = dateString.split('-');
        return `${day}.${month}.${year}`;
    }
    
    // Если дата содержит время (например, "2026-01-12T21:00:00Z"), обрабатываем с учетом московского времени
    if (dateString.includes('T')) {
        const date = new Date(dateString);
        
        // Преобразуем в московское время
        const moscowOffset = 3 * 60; // Москва UTC+3 в минутах
        const utcTime = date.getTime() + (date.getTimezoneOffset() * 60000);
        const moscowTime = new Date(utcTime + (moscowOffset * 60000));
        
        const day = String(moscowTime.getDate()).padStart(2, '0');
        const month = String(moscowTime.getMonth() + 1).padStart(2, '0');
        const year = moscowTime.getFullYear();
        
        return `${day}.${month}.${year}`;
    }
    
    // Для других форматов используем стандартную обработку
    const date = new Date(dateString);
    const day = String(date.getUTCDate()).padStart(2, '0');
    const month = String(date.getUTCMonth() + 1).padStart(2, '0');
    const year = date.getUTCFullYear();
    
    return `${day}.${month}.${year}`;
}

export function formatDateToInput(dateString) {
    if (!dateString) return '';
    
    // Если дата в формате YYYY-MM-DD, возвращаем как есть
    if (dateString.match(/^\d{4}-\d{2}-\d{2}$/)) {
        return dateString;
    }
    
    // Если дата содержит время (например, "2026-01-12T21:00:00Z"), извлекаем только дату
    if (dateString.includes('T')) {
        return dateString.split('T')[0]; // Берем только часть до 'T'
    }
    
    // Для других форматов используем стандартную обработку
    const date = new Date(dateString);
    const year = date.getUTCFullYear();
    const month = String(date.getUTCMonth() + 1).padStart(2, '0');
    const day = String(date.getUTCDate()).padStart(2, '0');
    
    return `${year}-${month}-${day}`;
}


