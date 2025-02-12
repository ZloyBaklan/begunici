// Получение CSRF-токена из cookies
function getCSRFToken() {
    const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
    return cookie ? decodeURIComponent(cookie.split('=')[1]) : null;
}

// Универсальный запрос к API
async function apiRequest(url, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() };
    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    console.log(`Запрос: ${method} ${url}`, body || '');

    try {
        const response = await fetch(url, options);

        // Обработка ошибок
        if (!response.ok) {
            await handleError(response);
        }

        // Обработка пустого тела (204 No Content)
        if (response.status === 204) return {};

        const jsonResponse = await response.json();
        console.log('Ответ JSON:', jsonResponse);
        return jsonResponse;

    } catch (error) {
        console.error('Ошибка запроса:', error.message);
        alert(`Ошибка: ${error.message}`);
        throw error;
    }
}

// Обработчик ошибок ответа сервера
async function handleError(response) {
    let errorMessage = `Ошибка: ${response.statusText}`;
    try {
        const errorText = await response.text();
        errorMessage = JSON.parse(errorText).detail || errorMessage;
    } catch {
        // Если ответ не JSON, оставляем стандартное сообщение
    }
    console.error('Ошибка API:', errorMessage);
    throw new Error(errorMessage);
}


// Загрузка данных при загрузке страницы
document.addEventListener('DOMContentLoaded', async () => {
    const makerId = document.getElementById('maker-detail').dataset.makerId;

    console.log('ID производителя:', makerId);

    try {
        // Загрузка подробной информации о производителе
        await loadMakerDetails(makerId);

        // Загрузка списка доступных родителей (опции для select)
        await loadParents(makerId);

        // Загрузка списка ветобработок
        await loadVetTreatments();

        // Обработчик для кнопки перехода в раздел аналитики
        const analyticsButton = document.getElementById('analytics-button');
        if (analyticsButton) {
            analyticsButton.onclick = () => {
                window.location.href = `/animals/makers/${makerId}/analytics/`;
            };
        }
    } catch (error) {
        console.error('Ошибка при загрузке данных:', error);
    }
});




// Загрузка данных для select
async function loadSelectOptions(selectId, apiEndpoint, selectedId = null) {
    const select = document.getElementById(selectId);
    select.innerHTML = '';
    const items = await apiRequest(apiEndpoint);

    items.forEach(item => {
        const option = document.createElement('option');
        option.value = item.id;
        option.textContent = item.status_type || item.sheepfold;
        if (item.id === selectedId) option.selected = true;
        select.appendChild(option);
    });
}






function formatDateToInput(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toISOString().split('T')[0]; // Приводим к формату yyyy-MM-dd
}

function formatDateToOutput(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', { year: 'numeric', month: 'long', day: 'numeric' });
}


async function loadMakerDetails(makerId) {
    try {
        const maker = await apiRequest(`/animals/maker/${makerId}/api/`);
        console.log('Данные производителя:', maker); // Отладка данных
        document.getElementById('tag').value = maker.tag.tag_number;
        document.getElementById('birth_date').value = maker.birth_date ? formatDateToInput(maker.birth_date) : ''; // Преобразуем дату
        document.getElementById('plemstatus').value = maker.plemstatus;
        document.getElementById('working_condition').value = maker.working_condition || '';
        document.getElementById('note').value = maker.note || '';

        await Promise.all([
            loadSelectOptions('animal_status', '/veterinary/status/', maker.animal_status?.id),
            loadSelectOptions('place', '/veterinary/place/', maker.place?.id),
            loadLastWeight(makerId),
            loadLastVetCare(makerId)
        ]);
    } catch (error) {
        console.error('Ошибка загрузки производителя:', error);
    }
}



// Загрузка последнего веса
async function loadLastWeight(makerId) {
    try {
        const weights = await apiRequest(`/animals/maker/${makerId}/weight_history/`);
        if (weights.length) {
            const lastWeight = weights[0]; // Берем самый последний вес
            document.getElementById('last-weight-date').textContent = formatDateToOutput(lastWeight.weight_date);
            document.getElementById('last-weight-value').textContent = `${lastWeight.weight} кг`;
        } else {
            document.getElementById('last-weight-date').textContent = '-';
            document.getElementById('last-weight-value').textContent = '-';
        }
    } catch (error) {
        console.error('Ошибка загрузки последнего веса:', error);
    }
}


async function loadLastVetCare(makerId) {
    try {
        const vetCares = await apiRequest(`/animals/maker/${makerId}/vet_history/`);
        console.log('История ветобработок:', vetCares);

        if (vetCares.length) {
            const lastCare = vetCares[0]; // Берем первую запись
            document.getElementById('last-vet-date').textContent = lastCare.date_of_care || '-';
            document.getElementById('last-vet-name').textContent = lastCare.veterinary_care?.care_name || 'Не указано';
            document.getElementById('last-vet-type').textContent = lastCare.veterinary_care?.care_type || 'Не указан';
            document.getElementById('last-vet-medication').textContent = lastCare.veterinary_care?.medication || 'Не указан';
            document.getElementById('last-vet-purpose').textContent = lastCare.veterinary_care?.purpose || 'Нет цели';
        } else {
            ['last-vet-date', 'last-vet-name', 'last-vet-type', 'last-vet-medication', 'last-vet-purpose']
                .forEach(id => document.getElementById(id).textContent = '-');
        }
    } catch (error) {
        console.error('Ошибка загрузки истории ветобработок:', error);
    }
}


async function saveMakerDetails() {
    const makerId = document.getElementById('maker-detail').dataset.makerId;

    const data = {
        tag: document.getElementById('tag').value,
        animal_status_id: parseInt(document.getElementById('animal_status').value),
        birth_date: document.getElementById('birth_date').value,
        plemstatus: document.getElementById('plemstatus').value,
        working_condition: document.getElementById('working_condition').value,
        note: document.getElementById('note').value,
        place_id: parseInt(document.getElementById('place').value),
    };

    try {
        await apiRequest(`/animals/maker/${makerId}/`, 'PATCH', data);
        alert('Данные успешно сохранены');
    } catch (error) {
        console.error('Ошибка сохранения данных:', error);
        alert('Ошибка при сохранении данных.');
    }
}



// Добавление взвешивания
async function addWeightRecord() {
    const tagId = parseInt(document.getElementById('maker-detail').dataset.makerId); // ID вместо строки
    const weight = document.getElementById('edit-weight-value').value;
    const weightDate = document.getElementById('edit-weight-date').value;

    if (!weight || !weightDate) {
        alert('Пожалуйста, заполните все поля для добавления веса.');
        return;
    }

    const data = {
        tag: parseInt(tagId), // Преобразуем ID в число
        weight: parseFloat(weight),
        weight_date: weightDate, // Формат: yyyy-MM-dd
    };

    try {
        await apiRequest('/veterinary/weight-record/', 'POST', data);
        alert('Вес добавлен!');
        await loadLastWeight(tagId);
    } catch (error) {
        console.error('Ошибка при добавлении веса:', error);
        alert('Ошибка при добавлении веса.');
    }
}


async function addVetRecord() {
    const makerId = document.getElementById('maker-detail').dataset.makerId;
    const treatmentId = document.getElementById('vet-treatment-select').value;
    const careDate = document.getElementById('vet-treatment-date').value;

    if (!treatmentId || !careDate) {
        alert('Выберите обработку и укажите дату.');
        return;
    }

    const data = {
        tag: makerId, // Указываем ID производителя
        treatment_id: parseInt(treatmentId),
        date_of_care: careDate, // Дата обработки
        comments: document.getElementById('vet-treatment-comments').value || ''
    };

    console.log('Отправляемые данные:', data);

    try {
        await apiRequest('/veterinary/veterinary/vetcare/', 'POST', data);
        alert('Ветобработка добавлена!');
        await loadLastVetCare(makerId); // Обновляем отображение последней обработки
    } catch (error) {
        console.error('Ошибка добавления ветобработки:', error);
    }
}






    
async function loadVetTreatments() {
    try {
        const treatments = await apiRequest('/veterinary/care/');
        console.log('Ответ сервера для ветобработок:', treatments);

        const select = document.getElementById('vet-treatment-select');
        select.innerHTML = '<option value="">Выберите обработку</option>'; // Очистка списка

        treatments.forEach(treatment => {
            const option = document.createElement('option');
            option.value = treatment.id; // ID обработки
            option.textContent = treatment.care_name;

            // Сохраняем дополнительные данные обработки
            option.dataset.type = treatment.care_type || 'Не указан';
            option.dataset.medication = treatment.medication || 'Не указан';
            option.dataset.purpose = treatment.purpose || 'Нет цели';
            select.appendChild(option);
        });

        select.addEventListener('change', displayTreatmentDetails);
    } catch (error) {
        console.error('Ошибка загрузки ветобработок:', error);
    }
}

function displayTreatmentDetails() {
    const select = document.getElementById('vet-treatment-select');
    const selectedOption = select.options[select.selectedIndex];

    // Отображаем данные обработки
    document.getElementById('treatment-type').textContent = `Тип: ${selectedOption.dataset.type}`;
    document.getElementById('treatment-description').textContent = `Цель: ${selectedOption.dataset.purpose}`;
    document.getElementById('treatment-medicine').textContent = `Препарат: ${selectedOption.dataset.medication}`;
}


async function loadParents(makerId) {
    try {
        const maker = await apiRequest(`/animals/maker/${makerId}/`);
        const mother = maker.mother;
        const father = maker.father;

        updateParentDisplay(mother, father);
    } catch (error) {
        console.error('Ошибка загрузки родителей:', error);
    }
}

function updateParentDisplay(mother, father) {
    const motherDisplay = document.getElementById('mother-display');
    const fatherDisplay = document.getElementById('father-display');

    if (mother) {
        motherDisplay.textContent = mother.tag_number;
        document.getElementById('mother-link').href = `/animals/sheep/${mother.id}/info/`;
    } else {
        motherDisplay.textContent = 'Нет данных';
        document.getElementById('mother-link').href = '#';
    }

    if (father) {
        fatherDisplay.textContent = father.tag_number;
        document.getElementById('father-link').href = `/animals/maker/${father.id}/info/`;
    } else {
        fatherDisplay.textContent = 'Нет данных';
        document.getElementById('father-link').href = '#';
    }
}




async function updateParents() {
    const makerId = document.getElementById('maker-detail').dataset.makerId; // ID производителя
    const motherTagNumber = document.getElementById('mother-input').value.trim(); // Бирка мамы
    const fatherTagNumber = document.getElementById('father-input').value.trim(); // Бирка папы

    if (!motherTagNumber && !fatherTagNumber) {
        alert('Введите хотя бы одну бирку родителя для обновления.');
        return;
    }

    try {
        // Отправляем запрос на обновление родителей
        await apiRequest(`/animals/maker/${makerId}/update_parents/`, 'PATCH', {
            mother_tag_number: motherTagNumber || null,
            father_tag_number: fatherTagNumber || null,
        });

        alert('Родители успешно обновлены!');
        await loadParents(makerId); // Обновляем данные родителей на странице
    } catch (error) {
        console.error('Ошибка обновления родителей:', error);
        alert('Ошибка при обновлении родителей');
    }
}






async function findOrValidateTag(tagNumber) {
    try {
        const response = await apiRequest(`/veterinary/tag/search/?tag_number=${tagNumber}`, 'GET');
        return response; // Возвращает объект бирки или null
    } catch (error) {
        console.error('Ошибка поиска бирки:', error);
        return null;
    }
}




