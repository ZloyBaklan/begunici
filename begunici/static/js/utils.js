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
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU'); // Формат: дд.мм.гггг
}

export function formatDateToInput(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toISOString().split('T')[0]; // Формат: гггг-мм-дд
}