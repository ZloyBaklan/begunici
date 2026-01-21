// Общие функции для экспорта в Excel

function openExportModal(animalType) {
    const modal = document.getElementById('export-modal');
    modal.style.display = 'flex';
    modal.dataset.animalType = animalType; // Сохраняем тип животного
    
    // Обработчики для включения/выключения полей
    document.getElementById('filter-limit-enabled').addEventListener('change', (e) => {
        document.getElementById('filter-limit').disabled = !e.target.checked;
    });
    
    document.getElementById('filter-weight-enabled').addEventListener('change', (e) => {
        document.getElementById('filter-weight-min').disabled = !e.target.checked;
        document.getElementById('filter-weight-max').disabled = !e.target.checked;
    });
    
    document.getElementById('filter-age-enabled').addEventListener('change', (e) => {
        document.getElementById('filter-age-min').disabled = !e.target.checked;
        document.getElementById('filter-age-max').disabled = !e.target.checked;
    });
}

function closeExportModal() {
    const modal = document.getElementById('export-modal');
    modal.style.display = 'none';
    
    // Сбрасываем форму
    document.getElementById('filter-limit-enabled').checked = false;
    document.getElementById('filter-weight-enabled').checked = false;
    document.getElementById('filter-age-enabled').checked = false;
    document.getElementById('include-details').checked = false;
    document.getElementById('filter-limit').value = '';
    document.getElementById('filter-weight-min').value = '';
    document.getElementById('filter-weight-max').value = '';
    document.getElementById('filter-age-min').value = '';
    document.getElementById('filter-age-max').value = '';
    document.getElementById('filter-limit').disabled = true;
    document.getElementById('filter-weight-min').disabled = true;
    document.getElementById('filter-weight-max').disabled = true;
    document.getElementById('filter-age-min').disabled = true;
    document.getElementById('filter-age-max').disabled = true;
}

async function performExport(animalType) {
    const data = {
        animal_type: animalType || document.getElementById('export-modal').dataset.animalType,
        include_details: document.getElementById('include-details').checked
    };
    
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
        a.download = `${animalType}s_${new Date().toISOString().split('T')[0]}.${fileExtension}`;
        
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        closeExportModal();
        const formatName = isExcel ? 'Excel' : 'CSV';
        alert(`Файл успешно экспортирован в формате ${formatName}!`);
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
