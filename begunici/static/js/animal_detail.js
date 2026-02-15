// ! UTILS.sj cannot be importted due to injection html
// TODO Resolve that
function getCSRFToken() {
    const cookies = document.cookie.split(";").map(c => c.trim());
    const tokenCookie = cookies.find(c => c.startsWith("csrftoken="));
    
    if (!tokenCookie) return undefined;

    return decodeURIComponent(tokenCookie.split("=")[1]);
}

async function apiRequest(url, method, body) {
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken(),
    }

    const options = { method, headers }
    if (body) options.body = JSON.stringify(body)

    console.log(`Отправка запроса: ${method} ${url}`, options);
    
    try {
        const response = await fetch(url, options);
        const responseText = await response.text();
        let responseData;
        
        try {
            responseData = responseText ? JSON.parse(responseText) : {};
        } catch (e) {
            console.error('Ошибка при разборе JSON:', e, 'Текст ответа:', responseText);
            throw new Error(`Неверный формат ответа от сервера: ${responseText.substring(0, 100)}...`);
        }

        console.log(`Ответ от сервера [${response.status} ${response.statusText}]:`, responseData);

        if (!response.ok) {
            console.error(`Ошибка API [${response.status}]:`, responseData);
            throw new Error(responseData.detail || JSON.stringify(responseData) || 'Ошибка API');
        }
        
        return responseData;
    } catch (error) {
        console.error('Ошибка при выполнении запроса:', error);
        throw error;
    }
}

// Загрузка данных при загрузке страницы
// (Обработчик перенесен в конец файла для поддержки окотов)




// Загрузка данных для select
async function loadSelectOptions(selectId, apiEndpoint, selectedId = null) {
    const select = document.getElementById(selectId);
    select.innerHTML = '';
    const items = await apiRequest(apiEndpoint, 'GET');

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


async function loadAnimalDetails(animalType, tagNumber) {
    try {
        const animal = await apiRequest(`/animals/${animalType}/${tagNumber}/api/`, 'GET');
        console.log(`Данные ${animalType}:`, animal); // Отладка данных
        document.getElementById('tag').value = animal.tag.tag_number;
        document.getElementById('birth_date').value = animal.birth_date ? formatDateToInput(animal.birth_date) : ''; // Преобразуем дату
        
        // Поля plemstatus и working_condition есть только у Maker
        const plemsStatusField = document.getElementById('plemstatus');
        const workingConditionField = document.getElementById('working_condition');
        
        if (plemsStatusField) {
            plemsStatusField.value = animal.plemstatus || '';
        }
        if (workingConditionField) {
            workingConditionField.value = animal.working_condition || '';
        }
        
        document.getElementById('note').value = animal.note || '';

        console.log('Загружаем дополнительные данные (статусы, места, вес, ветобработки)...');
        await Promise.all([
            loadSelectOptions('animal_status', '/veterinary/api/status/', animal.animal_status?.id),
            loadSelectOptions('place', '/veterinary/api/place/', animal.place?.id),
            loadLastWeight(animalType, tagNumber),
            loadCurrentVetTreatments()
        ]);
        console.log('Все дополнительные данные загружены');
    } catch (error) {
        console.error('Ошибка загрузки производителя:', error);
    }
}



// Загрузка последнего веса
async function loadLastWeight(animalType, tagNumber) {
    try {
        const weights = await apiRequest(`/animals/${animalType}/${tagNumber}/weight_history/`, 'GET');
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


// Загружаем текущие ветобработки
async function loadCurrentVetTreatments() {
    const tagNumber = document.getElementById('animal-detail').dataset.tagNumber;
    const animalType = document.getElementById('animal-detail').dataset.animalType;
    
    try {
        console.log(`Загружаем текущие ветобработки для ${animalType} ${tagNumber}`);
        const response = await apiRequest(`/animals/${animalType}/${tagNumber}/current_vet_treatments/`, 'GET');
        console.log('Текущие ветобработки:', response);
        
        const tableBody = document.getElementById('current-vet-treatments-body');
        const noTreatmentsDiv = document.getElementById('no-current-treatments');
        
        if (response && response.length > 0) {
            tableBody.innerHTML = '';
            noTreatmentsDiv.style.display = 'none';
            
            response.forEach(treatment => {
                const row = createVetTreatmentRow(treatment);
                tableBody.appendChild(row);
            });
        } else {
            tableBody.innerHTML = '';
            noTreatmentsDiv.style.display = 'block';
        }
    } catch (error) {
        console.error('Ошибка загрузки текущих ветобработок:', error);
        document.getElementById('no-current-treatments').style.display = 'block';
        document.getElementById('no-current-treatments').textContent = 'Ошибка загрузки данных';
    }
}

// Создаем строку таблицы для ветобработки
function createVetTreatmentRow(treatment) {
    const row = document.createElement('tr');
    
    // Вычисляем дату окончания и оставшиеся дни
    const careDate = new Date(treatment.date_of_care);
    const expiryDate = new Date(careDate.getTime() + (treatment.duration_days * 24 * 60 * 60 * 1000));
    
    // Получаем текущую дату в московском времени (только дата, без времени)
    const now = new Date();
    const moscowOffset = 3 * 60; // 3 часа в минутах
    const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    const moscowTime = new Date(utc + (moscowOffset * 60000));
    
    // Приводим к началу дня для корректного сравнения
    const today = new Date(moscowTime.getFullYear(), moscowTime.getMonth(), moscowTime.getDate());
    const expiryDateOnly = new Date(expiryDate.getFullYear(), expiryDate.getMonth(), expiryDate.getDate());
    
    // Вычисляем разность в днях
    const remainingDays = Math.floor((expiryDateOnly - today) / (1000 * 60 * 60 * 24));
    
    // Определяем цвет для оставшихся дней
    let remainingClass = '';
    let remainingText = '';
    
    if (remainingDays < 0) {
        remainingClass = 'text-danger fw-bold';
        remainingText = 'Просрочено';
    } else if (remainingDays === 0) {
        remainingClass = 'text-danger fw-bold';
        remainingText = 'Истекает сегодня';
    } else if (remainingDays <= 3) {
        remainingClass = 'text-warning fw-bold';
        remainingText = `${remainingDays} дн.`;
    } else {
        remainingClass = 'text-success';
        remainingText = `${remainingDays} дн.`;
    }
    
    row.innerHTML = `
        <td>${treatment.veterinary_care?.care_type || 'Не указан'}</td>
        <td>${treatment.veterinary_care?.care_name || 'Не указано'}</td>
        <td>${careDate.toLocaleDateString('ru-RU')}</td>
        <td>${expiryDate.toLocaleDateString('ru-RU')}</td>
        <td class="${remainingClass}">${remainingText}</td>
        <td class="text-muted" style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${treatment.comments || 'Нет комментария'}">${treatment.comments || 'Нет комментария'}</td>
        <td>
            <button class="btn btn-sm btn-outline-secondary" onclick="hideVetTreatment(${treatment.id})">
                Скрыть
            </button>
        </td>
    `;
    
    return row;
}

// Скрыть ветобработку из отслеживания
async function hideVetTreatment(treatmentId) {
    const tagNumber = document.getElementById('animal-detail').dataset.tagNumber;
    const animalType = document.getElementById('animal-detail').dataset.animalType;
    
    if (!confirm('Вы уверены, что хотите скрыть эту ветобработку из отслеживания?')) {
        return;
    }
    
    try {
        const response = await apiRequest(`/animals/${animalType}/${tagNumber}/hide_vet_treatment/`, 'POST', {
            treatment_id: treatmentId
        });
        
        if (response.success) {
            // Перезагружаем таблицу
            await loadCurrentVetTreatments();
        } else {
            alert('Ошибка: ' + (response.error || 'Неизвестная ошибка'));
        }
    } catch (error) {
        console.error('Ошибка скрытия ветобработки:', error);
        alert('Ошибка скрытия ветобработки');
    }
}



async function saveAnimalDetails() {
    const animalDetail = document.getElementById('animal-detail');
    const tagNumber = animalDetail.dataset.tagNumber;
    const animalType = animalDetail.dataset.animalType;

    const animalStatusValue = document.getElementById('animal_status').value;
    const placeValue = document.getElementById('place').value;
    
    const data = {
        tag_number: document.getElementById('tag').value,
        animal_status_id: animalStatusValue ? parseInt(animalStatusValue) : null,
        birth_date: document.getElementById('birth_date').value,
        note: document.getElementById('note').value,
        place_id: placeValue ? parseInt(placeValue) : null,
    };

    // Добавляем специфичные поля для Maker
    if (animalType === 'maker') {
        data.plemstatus = document.getElementById('plemstatus').value;
        data.working_condition = document.getElementById('working_condition').value;
    }

    try {
        await apiRequest(`/animals/${animalType}/${tagNumber}/`, 'PATCH', data);
        alert('Данные успешно сохранены');
        // Перезагружаем страницу для отображения обновлённых данных
        location.reload();
    } catch (error) {
        console.error('Ошибка сохранения данных:', error);
        alert('Ошибка при сохранении данных: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Создаём алиас для обратной совместимости
window.saveMakerDetails = saveAnimalDetails;



// Добавление взвешивания
// Глобальная переменная для хранения данных о производителе
let animalData = null;

async function addWeightRecord() {
    const animalDetail = document.getElementById('animal-detail');
    const tagNum = animalDetail.dataset.tagNumber;
    const animalType = animalDetail.dataset.animalType;
    const weight = document.getElementById('edit-weight-value').value;
    const weightDate = document.getElementById('edit-weight-date').value;
    
    // Если данные о производителе ещё не загружены, загружаем их
    if (!animalData) {
        try {
            animalData = await apiRequest(`/animals/${animalType}/${tagNum}/api/`, 'GET');
        } catch (error) {
            console.error('Ошибка при загрузке данных производителя:', error);
            alert('Не удалось загрузить данные о производителе');
            return;
        }
    }
    
    // Проверяем, что у нас есть данные о бирке
    console.log(`Полные данные ${animalType}:`, JSON.stringify(animalData, null, 2));
    
    let tagNumber = animalData.tag?.tag_number;
    
    if (!tagNumber) {
        console.error('Номер бирки не найден в данных животного. Доступные поля:', Object.keys(animalData.tag || {}));
        alert('Ошибка: не удалось определить номер бирки. Проверьте консоль для деталей.');
        return;
    }

    if (!weight || !weightDate) {
        alert('Пожалуйста, заполните все поля для добавления веса.');
        return;
    }
    
    try {
        console.log('[v3] Начало addWeightRecord');
        // Используем данные из уже загруженного производителя
        if (!animalData || !animalData.id) {
            throw new Error('[v3] Не удалось загрузить данные производителя');
        }
        
        // Проверяем, есть ли у нас данные о бирке
        if (!animalData.tag || !animalData.tag.tag_number) {
            console.error('[v3] Проверка бирки не удалась. animalData.tag:', animalData.tag);
            throw new Error('[v3] Номер бирки не найден в данных производителя');
        }
        
        const data = {
            tag_write: animalData.tag.tag_number,
            weight: parseFloat(weight),
            weight_date: weightDate,
        };
        
        console.log('[v3] Отправляемые данные:', JSON.stringify(data, null, 2));
        
        await apiRequest('/veterinary/api/weight-record/', 'POST', data);
        alert('Вес добавлен!');
        await loadLastWeight(animalType, tagNumber);
    } catch (error) {
        console.error('[v3] Ошибка при добавлении веса:', error);
        alert('Ошибка при добавлении веса: ' + (error.message || 'Неизвестная ошибка'));
    }
}


async function addVetRecord() {
    const animalDetail = document.getElementById('animal-detail');
    const tagNumber = animalDetail.dataset.tagNumber;
    const animalType = animalDetail.dataset.animalType;
    const treatmentId = document.getElementById('vet-treatment-select').value;
    const careDate = document.getElementById('vet-treatment-date').value;

    if (!treatmentId || !careDate) {
        alert('Выберите обработку и укажите дату.');
        return;
    }

    // Получаем выбранную опцию для извлечения срока действия
    const select = document.getElementById('vet-treatment-select');
    const selectedOption = select.options[select.selectedIndex];

    const data = {
        tag_write: tagNumber,
        veterinary_care_write: parseInt(treatmentId),
        date_of_care: careDate,
        duration_days: selectedOption.dataset.defaultDuration ? parseInt(selectedOption.dataset.defaultDuration) : 0,
        comments: document.getElementById('vet-treatment-comments').value || ''
    };

    console.log('Отправляемые данные:', data);

    try {
        console.log('Отправляем запрос на добавление ветобработки...');
        const result = await apiRequest('/veterinary/api/veterinary/', 'POST', data);
        console.log('Ветобработка успешно добавлена, ответ сервера:', result);
        alert('Ветобработка добавлена!');
        
        // Очищаем форму после успешного добавления
        document.getElementById('vet-treatment-select').value = '';
        document.getElementById('vet-treatment-date').value = '';
        document.getElementById('vet-treatment-comments').value = '';
        displayTreatmentDetails(); // Очищаем отображение деталей
        
        console.log('Обновляем отображение текущих ветобработок...');
        await loadCurrentVetTreatments(); // Обновляем таблицу текущих ветобработок
    } catch (error) {
        console.error('Ошибка добавления ветобработки:', error);
        
        // Проверяем, является ли это ошибкой уникальности
        if (error.message && error.message.includes('unique set')) {
            const selectedOption = document.getElementById('vet-treatment-select').options[document.getElementById('vet-treatment-select').selectedIndex];
            const treatmentName = selectedOption ? selectedOption.textContent : 'выбранная обработка';
            
            alert(`Ошибка: Для этого животного уже существует запись "${treatmentName}" на дату ${careDate}.\n\nВыберите другую дату или другой тип обработки.`);
        } else {
            alert(`Ошибка при добавлении ветобработки: ${error.message || 'Неизвестная ошибка'}`);
        }
    }
}






    
async function loadVetTreatments() {
    try {
        const treatments = await apiRequest('/veterinary/api/care/', 'GET');
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
            option.dataset.defaultDuration = treatment.default_duration_days || '0';
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

    if (selectedOption.value) {
        // Отображаем данные обработки
        document.getElementById('treatment-type').innerHTML = `<strong>Тип:</strong> ${selectedOption.dataset.type || '-'}`;
        document.getElementById('treatment-description').innerHTML = `<strong>Цель:</strong> ${selectedOption.dataset.purpose || '-'}`;
        document.getElementById('treatment-medicine').innerHTML = `<strong>Препарат:</strong> ${selectedOption.dataset.medication || '-'}`;
        
        // Отображаем срок действия
        const durationDays = selectedOption.dataset.defaultDuration || '0';
        let durationText = '';
        if (durationDays === '0') {
            durationText = 'Бессрочно';
        } else {
            durationText = `${durationDays} дней`;
        }
        document.getElementById('treatment-duration').innerHTML = `<strong>Срок действия:</strong> ${durationText}`;
    } else {
        // Очищаем отображение если ничего не выбрано
        document.getElementById('treatment-type').innerHTML = '<strong>Тип:</strong> -';
        document.getElementById('treatment-description').innerHTML = '<strong>Цель:</strong> -';
        document.getElementById('treatment-medicine').innerHTML = '<strong>Препарат:</strong> -';
        document.getElementById('treatment-duration').innerHTML = '<strong>Срок действия:</strong> -';
    }
}


async function loadParents(animalType, tagNumber) {
    try {
        const animal = await apiRequest(`/animals/${animalType}/${tagNumber}/api/`, 'GET');
        const mother = animal.mother;
        const father = animal.father;

        console.log('Данные о родителях:', { mother, father }); // Отладочная информация

        updateParentDisplay(mother, father);
        
        // Заполняем поля ввода текущими значениями родителей
        const motherInput = document.getElementById('mother-input');
        const fatherInput = document.getElementById('father-input');
        
        if (motherInput) {
            motherInput.value = mother ? mother.tag_number : '';
            motherInput.placeholder = mother ? `Текущая мать: ${mother.tag_number}` : 'Введите бирку матери или оставьте пустым';
        }
        
        if (fatherInput) {
            fatherInput.value = father ? father.tag_number : '';
            fatherInput.placeholder = father ? `Текущий отец: ${father.tag_number}` : 'Введите бирку отца или оставьте пустым';
        }
        
    } catch (error) {
        console.error('Ошибка загрузки родителей:', error);
    }
}

function updateParentDisplay(mother, father) {
    const motherDisplay = document.getElementById('mother-display');
    const fatherDisplay = document.getElementById('father-display');
    const motherLink = document.getElementById('mother-link');
    const fatherLink = document.getElementById('father-link');

    console.log('Обновление отображения родителей:', { mother, father }); // Отладка

    if (mother) {
        motherDisplay.textContent = mother.tag_number;
        // Определяем тип животного по animal_type в объекте Tag
        const motherType = getAnimalTypeRoute(mother.animal_type);
        console.log(`Мать: ${mother.tag_number}, тип: ${mother.animal_type}, маршрут: ${motherType}`);
        motherLink.href = `/animals/${motherType}/${mother.tag_number}/info/`;
        motherLink.style.display = 'inline';
    } else {
        motherDisplay.textContent = 'Нет данных';
        motherLink.href = '#';
        motherLink.style.display = 'none';
    }

    if (father) {
        fatherDisplay.textContent = father.tag_number;
        // Определяем тип животного по animal_type в объекте Tag
        const fatherType = getAnimalTypeRoute(father.animal_type);
        console.log(`Отец: ${father.tag_number}, тип: ${father.animal_type}, маршрут: ${fatherType}`);
        fatherLink.href = `/animals/${fatherType}/${father.tag_number}/info/`;
        fatherLink.style.display = 'inline';
    } else {
        fatherDisplay.textContent = 'Нет данных';
        fatherLink.href = '#';
        fatherLink.style.display = 'none';
    }
}

// Вспомогательная функция для преобразования типа животного в маршрут
function getAnimalTypeRoute(animalType) {
    const typeMap = {
        'Maker': 'maker',
        'Ram': 'ram', 
        'Ewe': 'ewe',
        'Sheep': 'sheep'
    };
    
    console.log(`Преобразование типа животного: ${animalType} -> ${typeMap[animalType] || 'unknown'}`);
    
    // Если тип не найден, попробуем определить по первой букве или другим признакам
    if (!typeMap[animalType]) {
        console.warn(`Неизвестный тип животного: ${animalType}. Доступные типы:`, Object.keys(typeMap));
        return 'maker'; // По умолчанию
    }
    
    return typeMap[animalType];
}




async function updateParents() {
    const animalDetail = document.getElementById('animal-detail');
    const tagNumber = animalDetail.dataset.tagNumber;
    const animalType = animalDetail.dataset.animalType;
    const motherTagNumber = document.getElementById('mother-input').value.trim(); // Бирка мамы
    const fatherTagNumber = document.getElementById('father-input').value.trim(); // Бирка папы

    // Убираем проверку на обязательность заполнения - теперь можно оставлять поля пустыми
    
    try {
        // Отправляем запрос на обновление родителей
        // Пустые строки преобразуем в null для удаления родителя
        await apiRequest(`/animals/${animalType}/${tagNumber}/update_parents/`, 'PATCH', {
            mother_tag_number: motherTagNumber || null,
            father_tag_number: fatherTagNumber || null,
        });

        alert('Родители успешно обновлены!');
        
        // Перезагружаем данные о родителях, чтобы обновить поля ввода с новыми значениями
        await loadParents(animalType, tagNumber);
        
    } catch (error) {
        console.error('Ошибка обновления родителей:', error);
        alert('Ошибка при обновлении родителей: ' + (error.message || 'Неизвестная ошибка'));
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





// Функция преобразования ярки в овцу
async function convertEweToSheep() {
    const animalDetail = document.getElementById('animal-detail');
    const tagNumber = animalDetail.dataset.tagNumber;
    const animalType = animalDetail.dataset.animalType;
    
    // Проверяем, что это действительно ярка
    if (animalType !== 'ewe') {
        alert('Эта функция доступна только для ярок');
        return;
    }
    
    // Подтверждение действия
    const confirmConvert = confirm(
        `Вы уверены, что хотите преобразовать ярку ${tagNumber} в овцу? ` +
        'Это действие нельзя отменить!'
    );
    
    if (!confirmConvert) {
        return;
    }
    
    try {
        const response = await apiRequest(`/animals/ewe/${tagNumber}/to_sheep/`, 'POST');
        
        alert('Ярка успешно преобразована в овцу!');
        
        // Перенаправляем на страницу новой овцы
        window.location.href = `/animals/sheep/${tagNumber}/info/`;
        
    } catch (error) {
        console.error('Ошибка при преобразовании ярки в овцу:', error);
        alert('Ошибка при преобразовании: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Экспортируем функцию для глобального доступа
window.convertEweToSheep = convertEweToSheep;

// ===== ФУНКЦИИ ДЛЯ РАБОТЫ С ОКОТАМИ =====

// Загрузка активных окотов при загрузке страницы
async function loadLambings() {
    const animalDetail = document.getElementById('animal-detail');
    const tagNumber = animalDetail.dataset.tagNumber;
    const animalType = animalDetail.dataset.animalType;
    
    // Проверяем, что это овца или ярка
    if (animalType !== 'sheep' && animalType !== 'ewe') {
        return;
    }
    
    try {
        const lambings = await apiRequest(`/animals/lambing/by-animal/?animal_type=${animalType}&tag_number=${tagNumber}`, 'GET');
        displayLambings(lambings);
    } catch (error) {
        console.error('Ошибка загрузки окотов:', error);
    }
}

// Отображение окотов
function displayLambings(lambings) {
    const activeLambingsList = document.getElementById('active-lambings-list');
    const lambingHistoryList = document.getElementById('lambing-history-list');
    
    if (!activeLambingsList || !lambingHistoryList) {
        return;
    }
    
    // Разделяем активные и завершенные окоты
    const activeLambings = lambings.filter(l => l.is_active);
    const completedLambings = lambings.filter(l => !l.is_active);
    
    // Отображаем активные окоты
    if (activeLambings.length === 0) {
        activeLambingsList.innerHTML = '<div class="no-lambings">Нет активных окотов</div>';
    } else {
        activeLambingsList.innerHTML = activeLambings.map(lambing => createLambingCard(lambing, true)).join('');
    }
    
    // Отображаем историю окотов
    if (completedLambings.length === 0) {
        lambingHistoryList.innerHTML = '<div class="no-lambings">Нет завершенных окотов</div>';
    } else {
        lambingHistoryList.innerHTML = completedLambings.map(lambing => createLambingCard(lambing, false)).join('');
    }
}

// Создание карточки окота
function createLambingCard(lambing, isActive) {
    const startDate = new Date(lambing.start_date).toLocaleDateString('ru-RU');
    const plannedDate = new Date(lambing.planned_lambing_date).toLocaleDateString('ru-RU');
    const actualDate = lambing.actual_lambing_date ? 
        new Date(lambing.actual_lambing_date).toLocaleDateString('ru-RU') : null;
    
    return `
        <div class="lambing-card ${isActive ? 'active' : 'completed'}">
            <div class="lambing-info">
                <div>
                    <strong>Дата случки:</strong> ${startDate}
                </div>
                <div>
                    <strong>Отец:</strong> ${lambing.father_type} ${lambing.father_tag}
                </div>
                <div>
                    <strong>Планируемые роды:</strong> 
                    <span class="planned-date">${plannedDate}</span>
                </div>
                ${actualDate ? `<div><strong>Фактические роды:</strong> ${actualDate}</div>` : ''}
                ${lambing.number_of_lambs ? `<div><strong>Количество ягнят:</strong> ${lambing.number_of_lambs}</div>` : ''}
                ${lambing.note ? `<div><strong>Примечание:</strong> ${lambing.note}</div>` : ''}
            </div>
            ${isActive ? `
                <div class="lambing-actions">
                    <button type="button" class="btn btn-success btn-sm" onclick="completeLambing(${lambing.id})">
                        Завершить окот
                    </button>
                </div>
            ` : ''}
        </div>
    `;
}

// Показать форму создания окота
function showCreateLambingForm() {
    const form = document.getElementById('create-lambing-form');
    if (form) {
        form.style.display = 'block';
        // Устанавливаем текущую дату как дату начала
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('lambing-start-date').value = today;
    }
}

// Скрыть форму создания окота
function hideCreateLambingForm() {
    const form = document.getElementById('create-lambing-form');
    if (form) {
        form.style.display = 'none';
        // Очищаем форму
        document.getElementById('lambing-start-date').value = '';
        document.getElementById('lambing-father-tag').value = '';
        document.getElementById('lambing-note').value = '';
    }
}

// Создать новый окот
async function createLambing() {
    const animalDetail = document.getElementById('animal-detail');
    const tagNumber = animalDetail.dataset.tagNumber;
    const animalType = animalDetail.dataset.animalType;
    
    const startDate = document.getElementById('lambing-start-date').value;
    const fatherTag = document.getElementById('lambing-father-tag').value.trim();
    const note = document.getElementById('lambing-note').value.trim();
    
    // Валидация
    if (!startDate) {
        alert('Пожалуйста, укажите дату начала окота');
        return;
    }
    
    if (!fatherTag) {
        alert('Пожалуйста, укажите бирку отца');
        return;
    }
    
    try {
        const lambingData = {
            mother_tag_number: tagNumber,
            father_tag_number: fatherTag,
            start_date: startDate,
            note: note || null
        };
        
        await apiRequest('/animals/lambing/', 'POST', lambingData);
        
        alert('Окот успешно создан!');
        hideCreateLambingForm();
        
        // Перезагружаем список окотов
        await loadLambings();
        
    } catch (error) {
        console.error('Ошибка создания окота:', error);
        alert('Ошибка при создании окота: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Завершить окот
async function completeLambing(lambingId) {
    // Сохраняем ID окота для использования в модальном окне
    window.currentLambingId = lambingId;
    
    // Устанавливаем текущую дату как дату фактических родов
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('actual-lambing-date').value = today;
    
    // Загружаем список статусов
    try {
        const response = await fetch('/animals/api/all-statuses/');
        const statuses = await response.json();
        
        const statusSelect = document.getElementById('new-mother-status');
        statusSelect.innerHTML = '<option value="">Выберите статус...</option>';
        
        statuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.textContent = status.status_type;
            statusSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка загрузки статусов:', error);
    }
    
    // Генерируем формы для ягнят
    generateLambForms(1);
    
    // Показываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('completeLambingModal'));
    modal.show();
}

// Добавляем загрузку окотов в основную функцию загрузки страницы
document.addEventListener('DOMContentLoaded', async () => {
    console.log('=== НАЧАЛО ЗАГРУЗКИ СТРАНИЦЫ ===');
    const animalDetail = document.getElementById('animal-detail');
    const tagNumber = animalDetail ? animalDetail.dataset.tagNumber : null;
    const animalType = animalDetail ? animalDetail.dataset.animalType : null;

    if (!tagNumber || !animalType) {
        console.error("Ошибка: tagNumber или animalType не найдены в dataset");
        return;
    }

    console.log(`Загрузка данных для ${animalType} с биркой ${tagNumber}`);

    try {
        console.log('1. Загружаем основные данные животного...');
        await loadAnimalDetails(animalType, tagNumber);
        
        console.log('2. Загружаем данные о родителях...');
        await loadParents(animalType, tagNumber);
        
        console.log('3. Загружаем список ветобработок...');
        await loadVetTreatments();

        // Загружаем окоты для овец и ярок
        if (animalType === 'sheep' || animalType === 'ewe') {
            console.log('4. Загружаем окоты...');
            await loadLambings();
        }

        console.log('5. Настраиваем кнопку аналитики...');
        const analyticsButton = document.getElementById('analytics-button');
        if (analyticsButton) {
            analyticsButton.onclick = () => {
                window.location.href = `/animals/${animalType}/${tagNumber}/analytics/`;
            };
        }
        
        console.log('=== ЗАГРУЗКА СТРАНИЦЫ ЗАВЕРШЕНА ===');
    } catch (error) {
        console.error('Ошибка при загрузке данных:', error);
    }
});

// Экспортируем функции для глобального доступа
window.showCreateLambingForm = showCreateLambingForm;
window.hideCreateLambingForm = hideCreateLambingForm;
window.createLambing = createLambing;
window.completeLambing = completeLambing;
// ===== ФУНКЦИИ ДЛЯ ЗАВЕРШЕНИЯ ОКОТА С СОЗДАНИЕМ ДЕТЕЙ =====

// Генерация форм для ягнят
function generateLambForms(count) {
    const container = document.getElementById('lambs-forms-container');
    container.innerHTML = '';
    
    for (let i = 1; i <= count; i++) {
        const lambForm = createLambForm(i);
        container.appendChild(lambForm);
    }
}

// Создание формы для одного ягненка
function createLambForm(index) {
    const div = document.createElement('div');
    div.className = 'lamb-form';
    div.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-2">
            <h6>Ягненок ${index}</h6>
            ${index > 1 ? `<button type="button" class="remove-lamb-btn" onclick="removeLambForm(this)">Удалить</button>` : ''}
        </div>
        
        <div class="form-row">
            <div class="form-group">
                <label>Тип животного:</label>
                <select class="lamb-gender" required>
                    <option value="">Выберите тип</option>
                    <option value="male">Баран</option>
                    <option value="female">Ярка</option>
                </select>
            </div>
            <div class="form-group">
                <label>Бирка:</label>
                <input type="text" class="lamb-tag" placeholder="Номер бирки" required>
            </div>
        </div>
        
        <div class="form-row">
            <div class="form-group">
                <label>Статус:</label>
                <select class="lamb-status">
                    <option value="">Выберите статус</option>
                </select>
            </div>
            <div class="form-group">
                <label>Овчарня:</label>
                <select class="lamb-place">
                    <option value="">Выберите место</option>
                </select>
            </div>
        </div>
        
        <div class="form-group">
            <label>Примечание:</label>
            <textarea class="lamb-note" rows="2" placeholder="Дополнительная информация"></textarea>
        </div>
    `;
    
    // Загружаем статусы и места для этой формы
    loadStatusesForLamb(div);
    loadPlacesForLamb(div);
    
    return div;
}

// Загрузка статусов для формы ягненка
async function loadStatusesForLamb(formElement) {
    try {
        const statuses = await apiRequest('/veterinary/api/status/');
        const select = formElement.querySelector('.lamb-status');
        
        statuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.textContent = status.status_type;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка загрузки статусов для ягненка:', error);
    }
}

// Загрузка мест для формы ягненка
async function loadPlacesForLamb(formElement) {
    try {
        const places = await apiRequest('/veterinary/api/place/');
        const select = formElement.querySelector('.lamb-place');
        
        places.forEach(place => {
            const option = document.createElement('option');
            option.value = place.id;
            option.textContent = place.sheepfold;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка загрузки мест для ягненка:', error);
    }
}

// Удаление формы ягненка
function removeLambForm(button) {
    const lambForm = button.closest('.lamb-form');
    lambForm.remove();
    
    // Перенумеровываем оставшиеся формы
    const remainingForms = document.querySelectorAll('.lamb-form');
    remainingForms.forEach((form, index) => {
        const title = form.querySelector('h6');
        title.textContent = `Ягненок ${index + 1}`;
    });
}

// Обработчик изменения количества ягнят
document.addEventListener('DOMContentLoaded', () => {
    const lambsCountInput = document.getElementById('lambs-count');
    if (lambsCountInput) {
        lambsCountInput.addEventListener('change', (e) => {
            const count = parseInt(e.target.value) || 0;
            if (count >= 0 && count <= 10) {
                generateLambForms(count);
            }
        });
    }
    
    // Обработчик чекбокса создания ягнят
    const createLambsCheckbox = document.getElementById('create-lambs-checkbox');
    if (createLambsCheckbox) {
        createLambsCheckbox.addEventListener('change', (e) => {
            const container = document.getElementById('lambs-forms-container');
            const lambsCountInput = document.getElementById('lambs-count');
            
            if (e.target.checked) {
                container.style.display = 'block';
                lambsCountInput.disabled = false;
                generateLambForms(parseInt(lambsCountInput.value) || 1);
            } else {
                container.style.display = 'none';
                lambsCountInput.disabled = true;
            }
        });
    }
});

// Завершение окота с созданием детей
async function completeLambingWithChildren() {
    const lambingId = window.currentLambingId;
    const actualDate = document.getElementById('actual-lambing-date').value;
    const lambsCount = parseInt(document.getElementById('lambs-count').value) || 0;
    const lambingNote = document.getElementById('lambing-note').value;
    const createLambs = document.getElementById('create-lambs-checkbox').checked;
    const newMotherStatusId = document.getElementById('new-mother-status').value;
    
    if (!actualDate) {
        alert('Пожалуйста, укажите дату фактических родов');
        return;
    }
    
    if (!newMotherStatusId) {
        alert('Пожалуйста, выберите новый статус для матери');
        return;
    }
    
    try {
        // Собираем данные о ягнятах, если нужно их создавать
        let lambsData = [];
        
        if (createLambs && lambsCount > 0) {
            const lambForms = document.querySelectorAll('.lamb-form');
            
            for (let form of lambForms) {
                const gender = form.querySelector('.lamb-gender').value;
                const tag = form.querySelector('.lamb-tag').value.trim();
                const status = form.querySelector('.lamb-status').value;
                const place = form.querySelector('.lamb-place').value;
                const note = form.querySelector('.lamb-note').value.trim();
                
                if (!gender || !tag) {
                    alert('Пожалуйста, заполните тип животного и бирку для всех ягнят');
                    return;
                }
                
                lambsData.push({
                    gender: gender,
                    tag_number: tag,
                    animal_status_id: status ? parseInt(status) : null,
                    place_id: place ? parseInt(place) : null,
                    note: note || ''
                });
            }
        }
        
        // Отправляем запрос на завершение окота
        const completionData = {
            actual_lambing_date: actualDate,
            number_of_lambs: lambsCount,
            note: lambingNote,
            new_mother_status_id: parseInt(newMotherStatusId),
            lambs: lambsData
        };
        
        await apiRequest(`/animals/lambing/${lambingId}/complete-with-children/`, 'POST', completionData);
        
        alert('Окот успешно завершен!' + (lambsData.length > 0 ? ` Создано ${lambsData.length} ягнят.` : ''));
        
        // Закрываем модальное окно
        const modal = bootstrap.Modal.getInstance(document.getElementById('completeLambingModal'));
        modal.hide();
        
        // Перезагружаем список окотов
        await loadLambings();
        
    } catch (error) {
        console.error('Ошибка завершения окота:', error);
        alert('Ошибка при завершении окота: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Экспортируем новые функции для глобального доступа
window.completeLambingWithChildren = completeLambingWithChildren;
window.removeLambForm = removeLambForm;