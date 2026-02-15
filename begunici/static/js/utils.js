export function getCSRFToken() {
    const cookies = document.cookie.split(";").map(c => c.trim());
    const tokenCookie = cookies.find(c => c.startsWith("csrftoken="));
    
    if (!tokenCookie) return undefined;

    return decodeURIComponent(tokenCookie.split("=")[1]);
}

export async function apiRequest(url, method, body) {
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken(),
    }

    const options = { method, headers }
    if (body) options.body = JSON.stringify(body)

    try {
        const response = await fetch(url, options)

        if (!response.ok) {
            const errorData = await response.json();
            console.error(`Ошибка API [${response.status}]:`, errorData);
            throw new Error(errorData.detail || 'Ошибка API');
        }

        if (response.status === 204) {
            return null; // No content
        }
        
        return await response.json();
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