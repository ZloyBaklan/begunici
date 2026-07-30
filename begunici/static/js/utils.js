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

    const row = document.createElement('div');
    row.className = 'row g-2 mt-2';
    row.innerHTML = `
        <div class="col-md-12">
            <div class="form-check">
                <input type="checkbox" id="${checkboxId}" class="form-check-input">
                <label for="${checkboxId}" class="form-check-label">Наличие бирки РСХН</label>
            </div>
        </div>
    `;
    container.appendChild(row);
}

function getApiErrorMessage(errorData) {
    if (!errorData || typeof errorData !== 'object') {
        return 'Ошибка API';
    }

    if (typeof errorData.detail === 'string') {
        return errorData.detail;
    }

    if (typeof errorData.error === 'string') {
        return errorData.error;
    }

    const messages = [];
    Object.entries(errorData).forEach(([field, value]) => {
        if (Array.isArray(value)) {
            messages.push(`${field}: ${value.join(', ')}`);
        } else if (value && typeof value === 'object') {
            messages.push(`${field}: ${JSON.stringify(value)}`);
        } else if (value !== undefined && value !== null) {
            messages.push(`${field}: ${value}`);
        }
    });

    return messages.length ? messages.join('\n') : 'Ошибка API';
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
                throw new Error(getApiErrorMessage(errorData));
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
