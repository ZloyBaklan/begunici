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

function openAnimalExportModal() {
    const modalElement = document.getElementById('animalExportModal');
    if (!modalElement) return;
    const modal = new bootstrap.Modal(modalElement);
    modal.show();
}

function closeAnimalExportModal() {
    const modalElement = document.getElementById('animalExportModal');
    if (!modalElement) return;
    const modal = bootstrap.Modal.getInstance(modalElement);
    if (modal) {
        modal.hide();
    }
}

function getSelectedAnimalExportSections() {
    return Array.from(document.querySelectorAll('.animal-export-section:checked')).map((checkbox) => checkbox.value);
}

function resolveExportFilename(response, fallbackName) {
    const contentDisposition = response.headers.get('Content-Disposition') || '';
    const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match && utf8Match[1]) {
        return decodeURIComponent(utf8Match[1]);
    }

    const plainMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
    if (plainMatch && plainMatch[1]) {
        return plainMatch[1];
    }

    return fallbackName;
}

async function exportAnimalToExcel() {
    const animalDetail = document.getElementById('animal-detail');
    if (!animalDetail) {
        alert('Не удалось определить животное для экспорта');
        return;
    }

    const selectedSections = getSelectedAnimalExportSections();
    if (selectedSections.length === 0) {
        alert('Выберите хотя бы один раздел для экспорта');
        return;
    }

    const animalType = animalDetail.dataset.animalType;
    const tagNumber = animalDetail.dataset.tagNumber;
    const exportUrl = `/animals/api/${animalType}/${encodeURIComponent(tagNumber)}/export-detail-excel/`;

    try {
        const response = await fetch(exportUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify({ sections: selectedSections }),
        });

        if (!response.ok) {
            let errorText = `Ошибка экспорта (${response.status})`;
            try {
                const errorData = await response.json();
                errorText = errorData.error || errorData.detail || errorText;
            } catch (_) {
                const rawText = await response.text();
                if (rawText) {
                    errorText = rawText;
                }
            }
            throw new Error(errorText);
        }

        const blob = await response.blob();
        const fallbackName = `${animalType}_${tagNumber}.xlsx`;
        const filename = resolveExportFilename(response, fallbackName);

        const downloadUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(downloadUrl);

        closeAnimalExportModal();
    } catch (error) {
        console.error('Ошибка экспорта в Excel:', error);
        alert(`Ошибка при экспорте: ${error.message}`);
    }
}

// Загрузка данных при загрузке страницы
// (Обработчик перенесен в конец файла для поддержки окотов)




// Загрузка данных для select
async function loadSelectOptions(selectId, apiEndpoint, selectedId = null) {
    const select = document.getElementById(selectId);
    select.innerHTML = '';
    
    try {
        // Добавляем page_size=100 для получения всех данных
        const url = apiEndpoint.includes('?') ? `${apiEndpoint}&page_size=100` : `${apiEndpoint}?page_size=100`;
        const response = await apiRequest(url, 'GET');
        console.log(`Ответ API для ${selectId}:`, response);
        
        // Обрабатываем пагинированный ответ
        const items = response.results || response;
        
        if (!Array.isArray(items)) {
            console.error(`Ожидался массив для ${selectId}, получено:`, items);
            return;
        }

        items.forEach(item => {
            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = item.status_type || item.sheepfold;
            if (item.id === selectedId) option.selected = true;
            select.appendChild(option);
        });
    } catch (error) {
        console.error(`Ошибка загрузки ${selectId}:`, error);
    }
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

function formatDateToShortOutput(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU');
}

function updateCarcassWeightDisplay(animal) {
    const carcassRow = document.getElementById('carcass-weight-row');
    const carcassDisplay = document.getElementById('carcass-weight-display');
    if (!carcassRow || !carcassDisplay) return;

    if (!animal.is_archived) {
        carcassRow.style.display = 'none';
        carcassDisplay.textContent = '-';
        return;
    }

    carcassRow.style.display = '';
    if (animal.carcass_weight !== null && animal.carcass_weight !== undefined && animal.carcass_weight !== '') {
        const archiveDate = formatDateToShortOutput(animal.archived_date);
        carcassDisplay.textContent = `${archiveDate}, ${animal.carcass_weight} кг`;
    } else {
        carcassDisplay.textContent = '-';
    }
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
        
        // Поле кровности по основной породе
        const dorperField = document.getElementById('dorper_percentage');
        if (dorperField) {
            dorperField.value = animal.dorper_percentage || '';
        }
        
        // Отображение кровности по основной породе в основной информации
        const dorperDisplay = document.getElementById('dorper-display');
        if (dorperDisplay) {
            dorperDisplay.textContent = animal.dorper_display || '-';
        }
        
        document.getElementById('note').value = animal.note || '';
        updateCarcassWeightDisplay(animal);

        console.log('Загружаем дополнительные данные (статусы, места, вес, ветобработки)...');
        await Promise.all([
            loadSelectOptions('animal_status', '/veterinary/api/status/', animal.animal_status?.id),
            loadSelectOptions('place', '/veterinary/api/place/', animal.place?.id),
            loadLastWeight(animalType, tagNumber),
            loadCurrentVetTreatments()
        ]);
        console.log('Все дополнительные данные загружены');
    } catch (error) {
        console.error('Ошибка загрузки барана-производителя:', error);
    }
}



// Загрузка живого веса
async function loadLastWeight(animalType, tagNumber) {
    try {
        const display = document.getElementById('last-weight-display');
        if (!display) return;

        const weights = await apiRequest(`/animals/${animalType}/${tagNumber}/weight_history/`, 'GET');
        if (weights.length) {
            const lastWeight = weights[0]; // Берем последний живой вес
            display.textContent = `${formatDateToShortOutput(lastWeight.weight_date)}, ${lastWeight.weight} кг`;
        } else {
            display.textContent = '-';
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
        
        // Обрабатываем пагинированный ответ
        const treatments = response.results || response;
        
        if (Array.isArray(treatments) && treatments.length > 0) {
            tableBody.innerHTML = '';
            noTreatmentsDiv.style.display = 'none';
            
            treatments.forEach(treatment => {
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
        <td>${treatment.veterinary_care?.medication || 'Нет препарата'}</td>
        <td>${treatment.veterinary_care?.purpose || 'Нет цели'}</td>
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
    const dorperValue = document.getElementById('dorper_percentage').value;
    
    const data = {
        tag_number: document.getElementById('tag').value,
        animal_status_id: animalStatusValue ? parseInt(animalStatusValue) : null,
        birth_date: document.getElementById('birth_date').value,
        note: document.getElementById('note').value,
        place_id: placeValue ? parseInt(placeValue) : null,
        rshn_tag: document.getElementById('rshn_tag').value || null,
        date_otbivka: document.getElementById('date_otbivka').value || null,
        dorper_percentage: dorperValue ? parseFloat(dorperValue) : null,
        is_manual_dorper: dorperValue ? true : false,
    };

    // Добавляем специфичные поля для Maker
    if (animalType === 'maker') {
        data.name = document.getElementById('name').value || null;
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
// Глобальная переменная для хранения данных о баране-производителе
let animalData = null;

async function addWeightRecord() {
    const animalDetail = document.getElementById('animal-detail');
    const tagNum = animalDetail.dataset.tagNumber;
    const animalType = animalDetail.dataset.animalType;
    const weight = document.getElementById('edit-weight-value').value;
    const weightDate = document.getElementById('edit-weight-date').value;
    
    // Если данные о баране-производителе ещё не загружены, загружаем их
    if (!animalData) {
        try {
            animalData = await apiRequest(`/animals/${animalType}/${tagNum}/api/`, 'GET');
        } catch (error) {
            console.error('Ошибка при загрузке данных барана-производителя:', error);
            alert('Не удалось загрузить данные о баране-производителе');
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
        // Используем данные из уже загруженного барана-производителя
        if (!animalData || !animalData.id) {
            throw new Error('[v3] Не удалось загрузить данные барана-производителя');
        }
        
        // Проверяем, есть ли у нас данные о бирке
        if (!animalData.tag || !animalData.tag.tag_number) {
            console.error('[v3] Проверка бирки не удалась. animalData.tag:', animalData.tag);
            throw new Error('[v3] Номер бирки не найден в данных барана-производителя');
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
        // Добавляем page_size=100 для получения всех ветобработок
        const response = await apiRequest('/veterinary/api/care/?page_size=100', 'GET');
        console.log('Ответ сервера для ветобработок:', response);

        // Обрабатываем пагинированный ответ
        const treatments = response.results || response;
        
        if (!Array.isArray(treatments)) {
            console.error('Ожидался массив ветобработок, получено:', treatments);
            return;
        }

        const select = document.getElementById('vet-treatment-select');
        select.innerHTML = '<option value="">Выберите обработку</option>'; // Очистка списка

        treatments.forEach(treatment => {
            const option = document.createElement('option');
            option.value = treatment.id; // ID обработки
            const medicationText = (treatment.medication || '').trim() || 'Не указан препарат';
            const purposeText = (treatment.purpose || '').trim() || 'Не указана цель';
            option.textContent = `${medicationText} — ${purposeText}`;

            // Сохраняем дополнительные данные обработки
            option.dataset.type = treatment.care_name || 'Не указан';
            option.dataset.class = treatment.care_type || 'Не указан';
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
        document.getElementById('treatment-class').innerHTML = `<strong>Класс:</strong> ${selectedOption.dataset.class || '-'}`;
        document.getElementById('treatment-medicine').innerHTML = `<strong>Препарат:</strong> ${selectedOption.dataset.medication || '-'}`;
        document.getElementById('treatment-description').innerHTML = `<strong>Цель:</strong> ${selectedOption.dataset.purpose || '-'}`;
        
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
        document.getElementById('treatment-class').innerHTML = '<strong>Класс:</strong> -';
        document.getElementById('treatment-description').innerHTML = '<strong>Цель:</strong> -';
        document.getElementById('treatment-medicine').innerHTML = '<strong>Препарат:</strong> -';
        document.getElementById('treatment-duration').innerHTML = '<strong>Срок действия:</strong> -';
    }
}


async function loadParents(animalType, tagNumber) {
    try {
        const animal = await apiRequest(`/animals/${animalType}/${tagNumber}/api/`, 'GET');
        const mother = animal.mother_display;
        const father = animal.father_display;

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

    if (mother && mother.has_link && mother.tag_obj) {
        motherDisplay.textContent = mother.tag_number;
        // Определяем тип животного по animal_type в объекте Tag
        const motherType = getAnimalTypeRoute(mother.tag_obj.animal_type);
        console.log(`Мать: ${mother.tag_number}, тип: ${mother.tag_obj.animal_type}, маршрут: ${motherType}`);
        motherLink.href = `/animals/${motherType}/${mother.tag_number}/info/`;
        motherLink.style.display = 'inline';
    } else if (mother && mother.tag_number) {
        // Родитель существует, но нет ссылки (не найден в БД)
        motherDisplay.textContent = mother.tag_number + ' (не найден)';
        motherLink.href = '#';
        motherLink.style.display = 'none';
    } else {
        motherDisplay.textContent = 'Нет данных';
        motherLink.href = '#';
        motherLink.style.display = 'none';
    }

    if (father && father.has_link && father.tag_obj) {
        fatherDisplay.textContent = father.display_name || father.tag_number;
        // Определяем тип животного по animal_type в объекте Tag
        const fatherType = getAnimalTypeRoute(father.tag_obj.animal_type);
        console.log(`Отец: ${father.tag_number}, тип: ${father.tag_obj.animal_type}, маршрут: ${fatherType}`);
        fatherLink.href = `/animals/${fatherType}/${father.tag_number}/info/`;
        fatherLink.style.display = 'inline';
    } else if (father && father.tag_number) {
        // Родитель существует, но нет ссылки (не найден в БД)
        fatherDisplay.textContent = (father.display_name || father.tag_number) + ' (не найден)';
        fatherLink.href = '#';
        fatherLink.style.display = 'none';
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





// Функция преобразования ярки в овцематку
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
        `Вы уверены, что хотите преобразовать ярку ${tagNumber} в овцематку? ` +
        'Это действие нельзя отменить!'
    );
    
    if (!confirmConvert) {
        return;
    }
    
    try {
        const response = await apiRequest(`/animals/ewe/${tagNumber}/to_sheep/`, 'POST');
        
        alert('Ярка успешно преобразована в овцематку!');
        
        // Перенаправляем на страницу новой овцематки
        window.location.href = `/animals/sheep/${tagNumber}/info/`;
        
    } catch (error) {
        console.error('Ошибка при преобразовании ярки в овцематку:', error);
        alert('Ошибка при преобразовании: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Экспортируем функцию для глобального доступа
window.convertEweToSheep = convertEweToSheep;

function openConvertRamToMakerModal() {
    const modalElement = document.getElementById('convertRamToMakerModal');
    if (!modalElement) return;

    const plemstatusInput = document.getElementById('maker-plemstatus-input');
    const workingConditionInput = document.getElementById('maker-working-condition-input');
    if (plemstatusInput) plemstatusInput.value = '';
    if (workingConditionInput) workingConditionInput.value = '';

    const modal = new bootstrap.Modal(modalElement);
    modal.show();
}

// Функция преобразования баранчика в барана-производителя
async function convertRamToMaker(plemstatus, workingCondition) {
    const animalDetail = document.getElementById('animal-detail');
    const tagNumber = animalDetail.dataset.tagNumber;
    const animalType = animalDetail.dataset.animalType;

    // Проверяем, что это действительно баранчик
    if (animalType !== 'ram') {
        alert('Эта функция доступна только для баранчиков');
        return;
    }

    try {
        await apiRequest(`/animals/ram/${tagNumber}/to_maker/`, 'POST', {
            plemstatus: plemstatus.trim(),
            working_condition: workingCondition.trim(),
        });

        alert('Баранчик успешно преобразован в барана-производителя!');

        // Перенаправляем на страницу нового барана-производителя
        window.location.href = `/animals/maker/${tagNumber}/info/`;
    } catch (error) {
        console.error('Ошибка при преобразовании баранчика в барана-производителя:', error);
        alert('Ошибка при преобразовании: ' + (error.message || 'Неизвестная ошибка'));
    }
}

async function submitRamToMakerConversion() {
    const animalDetail = document.getElementById('animal-detail');
    const tagNumber = animalDetail.dataset.tagNumber;

    const plemstatusInput = document.getElementById('maker-plemstatus-input');
    const workingConditionInput = document.getElementById('maker-working-condition-input');

    const plemstatus = plemstatusInput ? plemstatusInput.value.trim() : '';
    const workingCondition = workingConditionInput ? workingConditionInput.value.trim() : '';

    if (!plemstatus) {
        alert('Племенной статус обязателен');
        return;
    }

    if (!workingCondition) {
        alert('Рабочее состояние обязательно');
        return;
    }

    // Подтверждение действия (оставляем как было)
    const confirmConvert = confirm(
        `Вы уверены, что хотите преобразовать баранчика ${tagNumber} в барана-производителя? ` +
        'Это действие нельзя отменить!'
    );
    if (!confirmConvert) {
        return;
    }

    await convertRamToMaker(plemstatus, workingCondition);
}

// Экспортируем функцию для глобального доступа
window.convertRamToMaker = convertRamToMaker;
window.openConvertRamToMakerModal = openConvertRamToMakerModal;
window.submitRamToMakerConversion = submitRamToMakerConversion;

// ===== ФУНКЦИИ ДЛЯ РАБОТЫ С ОКОТАМИ =====

// Загрузка активных окотов при загрузке страницы
async function loadLambings() {
    const animalDetail = document.getElementById('animal-detail');
    const tagNumber = animalDetail.dataset.tagNumber;
    const animalType = animalDetail.dataset.animalType;
    
    // Проверяем, что это овцематка или ярка
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

// Загрузка истории окотов для отцов (бараны-производители и баранчики)
async function loadFatherLambings() {
    const animalDetail = document.getElementById('animal-detail');
    const tagNumber = animalDetail.dataset.tagNumber;
    const animalType = animalDetail.dataset.animalType;
    
    // Проверяем, что это баран-производитель или баранчик
    if (animalType !== 'maker' && animalType !== 'ram') {
        return;
    }
    
    try {
        const lambings = await apiRequest(`/animals/lambing/by-father/?animal_type=${animalType}&tag_number=${tagNumber}`, 'GET');
        displayFatherLambings(lambings);
    } catch (error) {
        console.error('Ошибка загрузки истории окотов как отец:', error);
    }
}

// Отображение окотов
function displayLambings(lambings) {
    const activeLambingsList = document.getElementById('active-lambings-list');
    const lambingHistoryList = document.getElementById('lambing-history-list');
    
    if (!activeLambingsList || !lambingHistoryList) {
        return;
    }
    
    // Сохраняем все окоты для фильтрации
    window.allLambings = lambings;
    initializeFemaleLambingsYearStats(lambings);
    
    // Разделяем активные и завершенные окоты
    const activeLambings = lambings.filter(l => l.is_active);
    const completedLambings = lambings.filter(l => !l.is_active);
    
    // Отображаем активные окоты (без пагинации, их обычно мало)
    if (activeLambings.length === 0) {
        activeLambingsList.innerHTML = '<div class="no-lambings">Нет активных окотов</div>';
    } else {
        activeLambingsList.innerHTML = activeLambings.map(lambing => createLambingCard(lambing, true)).join('');
    }
    
    // Отображаем историю окотов с пагинацией
    if (completedLambings.length === 0) {
        lambingHistoryList.innerHTML = '<div class="no-lambings">Нет завершенных окотов</div>';
    } else {
        initializeLambingHistoryPagination(completedLambings);
    }
}

// Инициализация пагинации для истории окотов
function initializeFemaleLambingsYearStats(lambings) {
    const yearSelect = document.getElementById('female-lambing-year-select');
    const countElement = document.getElementById('female-lambing-year-count');
    if (!yearSelect || !countElement) {
        return;
    }

    const completedLambings = (lambings || []).filter(
        (lambing) => !lambing.is_active && lambing.actual_lambing_date
    );

    const lambingsByYear = new Map();
    completedLambings.forEach((lambing) => {
        const date = new Date(lambing.actual_lambing_date);
        const year = date.getFullYear();
        if (Number.isNaN(year)) {
            return;
        }
        lambingsByYear.set(year, (lambingsByYear.get(year) || 0) + 1);
    });

    const currentYear = new Date().getFullYear();
    const years = Array.from(lambingsByYear.keys()).sort((a, b) => b - a);
    if (!years.includes(currentYear)) {
        years.unshift(currentYear);
    }

    yearSelect.innerHTML = years.map((year) => `<option value="${year}">${year}</option>`).join('');
    yearSelect.value = String(currentYear);

    const updateCount = () => {
        const selectedYear = Number(yearSelect.value);
        const count = lambingsByYear.get(selectedYear) || 0;
        countElement.textContent = `Количество окотов за год: ${count}`;
    };

    yearSelect.onchange = updateCount;
    updateCount();
}

function initializeLambingHistoryPagination(lambings) {
    const itemsPerPage = 5;
    let currentPage = 1;
    let filteredLambings = lambings; // Для фильтрации
    const totalPages = Math.ceil(filteredLambings.length / itemsPerPage);
    
    function displayPage(page) {
        const startIndex = (page - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const pageItems = filteredLambings.slice(startIndex, endIndex);
        
        const lambingHistoryList = document.getElementById('lambing-history-list');
        
        // Сохраняем текущие значения из полей перед перерисовкой
        const currentDateFrom = document.getElementById('history-date-from')?.value || window.historyDateFrom || '';
        const currentDateTo = document.getElementById('history-date-to')?.value || window.historyDateTo || '';
        
        // Обновляем глобальные переменные
        window.historyDateFrom = currentDateFrom;
        window.historyDateTo = currentDateTo;
        
        // Создаем фильтр с сохраненными значениями
        const filterHtml = `
            <div class="date-filter-container mb-3 p-3 bg-light rounded">
                <h6>Фильтр по дате начала окота</h6>
                <div class="row">
                    <div class="col-md-4">
                        <label for="history-date-from" class="form-label">С:</label>
                        <input type="date" class="form-control" id="history-date-from" value="${currentDateFrom}">
                    </div>
                    <div class="col-md-4">
                        <label for="history-date-to" class="form-label">По:</label>
                        <input type="date" class="form-control" id="history-date-to" value="${currentDateTo}">
                    </div>
                    <div class="col-md-4 d-flex align-items-end">
                        <button type="button" class="btn btn-primary btn-sm me-2" onclick="applyHistoryDateFilter()">Применить</button>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="clearHistoryDateFilter()">Сбросить</button>
                    </div>
                </div>
            </div>
        `;
        
        // Обновляем содержимое
        lambingHistoryList.innerHTML = filterHtml + pageItems.map(lambing => createLambingCard(lambing, false)).join('');
        
        // Обновляем пагинацию
        updateLambingHistoryPagination(page, Math.ceil(filteredLambings.length / itemsPerPage));
    }
    
    function updateLambingHistoryPagination(page, total) {
        let paginationHtml = '<div class="pagination-container mt-3">';
        
        if (total > 1) {
            paginationHtml += '<nav><ul class="pagination pagination-sm justify-content-center">';
            
            // Кнопка "Предыдущая"
            if (page > 1) {
                paginationHtml += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="changeLambingHistoryPage(${page - 1})">‹</a></li>`;
            }
            
            // Определяем диапазон страниц для отображения (текущая + 2 слева + 2 справа)
            const startPage = Math.max(1, page - 2);
            const endPage = Math.min(total, page + 2);
            
            // Показываем первую страницу и многоточие, если нужно
            if (startPage > 1) {
                paginationHtml += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="changeLambingHistoryPage(1)">1</a></li>`;
                if (startPage > 2) {
                    paginationHtml += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
                }
            }
            
            // Номера страниц в диапазоне
            for (let i = startPage; i <= endPage; i++) {
                const activeClass = i === page ? 'active' : '';
                paginationHtml += `<li class="page-item ${activeClass}"><a class="page-link" href="javascript:void(0)" onclick="changeLambingHistoryPage(${i})">${i}</a></li>`;
            }
            
            // Показываем многоточие и последнюю страницу, если нужно
            if (endPage < total) {
                if (endPage < total - 1) {
                    paginationHtml += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
                }
                paginationHtml += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="changeLambingHistoryPage(${total})">${total}</a></li>`;
            }
            
            // Кнопка "Следующая"
            if (page < total) {
                paginationHtml += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="changeLambingHistoryPage(${page + 1})">›</a></li>`;
            }
            
            paginationHtml += '</ul></nav>';
        }
        
        paginationHtml += `<div class="text-center text-muted small">Показано ${Math.min(itemsPerPage, filteredLambings.length - (page - 1) * itemsPerPage)} из ${filteredLambings.length} окотов</div>`;
        paginationHtml += '</div>';
        
        const lambingHistoryList = document.getElementById('lambing-history-list');
        lambingHistoryList.innerHTML += paginationHtml;
    }
    
    // Глобальные функции для фильтрации
    window.applyHistoryDateFilter = function() {
        const dateFrom = document.getElementById('history-date-from').value;
        const dateTo = document.getElementById('history-date-to').value;
        
        // Сохраняем значения в глобальных переменных
        window.historyDateFrom = dateFrom;
        window.historyDateTo = dateTo;
        
        // Применяем фильтр ко всем окотам
        const allLambings = window.allLambings || lambings;
        const filteredAllLambings = allLambings.filter(lambing => {
            const startDate = new Date(lambing.start_date);
            const fromDate = dateFrom ? new Date(dateFrom) : null;
            const toDate = dateTo ? new Date(dateTo) : null;
            
            if (fromDate && startDate < fromDate) return false;
            if (toDate && startDate > toDate) return false;
            return true;
        });
        
        // Разделяем отфильтрованные окоты на активные и завершенные
        const filteredActiveLambings = filteredAllLambings.filter(l => l.is_active);
        const filteredCompletedLambings = filteredAllLambings.filter(l => !l.is_active);
        
        // Обновляем активные окоты
        const activeLambingsList = document.getElementById('active-lambings-list');
        if (filteredActiveLambings.length === 0) {
            activeLambingsList.innerHTML = '<div class="no-lambings">Нет активных окотов в выбранном диапазоне дат</div>';
        } else {
            activeLambingsList.innerHTML = filteredActiveLambings.map(lambing => createLambingCard(lambing, true)).join('');
        }
        
        // Обновляем завершенные окоты
        filteredLambings = filteredCompletedLambings;
        currentPage = 1;
        displayPage(1);
    };
    
    window.clearHistoryDateFilter = function() {
        // Очищаем глобальные переменные
        window.historyDateFrom = '';
        window.historyDateTo = '';
        
        document.getElementById('history-date-from').value = '';
        document.getElementById('history-date-to').value = '';
        
        // Восстанавливаем все окоты
        const allLambings = window.allLambings || lambings;
        const activeLambings = allLambings.filter(l => l.is_active);
        const completedLambings = allLambings.filter(l => !l.is_active);
        
        // Обновляем активные окоты
        const activeLambingsList = document.getElementById('active-lambings-list');
        if (activeLambings.length === 0) {
            activeLambingsList.innerHTML = '<div class="no-lambings">Нет активных окотов</div>';
        } else {
            activeLambingsList.innerHTML = activeLambings.map(lambing => createLambingCard(lambing, true)).join('');
        }
        
        // Обновляем завершенные окоты
        filteredLambings = completedLambings;
        currentPage = 1;
        displayPage(1);
    };
    
    // Глобальная функция для смены страницы
    window.changeLambingHistoryPage = function(page) {
        currentPage = page;
        displayPage(page);
    };
    
    // Показываем первую страницу
    displayPage(1);
}

// Отображение истории окотов для отцов
function displayFatherLambings(lambings) {
    const fatherLambingHistoryList = document.getElementById('father-lambing-history-list');
    
    if (!fatherLambingHistoryList) {
        return;
    }
    
    // Сохраняем все окоты для фильтрации в стабильном порядке:
    // сначала активные, затем завершенные, внутри групп по дате случки (новые сверху)
    window.allFatherLambings = sortFatherLambings(lambings);
    
    if (lambings.length === 0) {
        fatherLambingHistoryList.innerHTML = '<div class="no-lambings">Нет окотов, где это животное выступало как отец</div>';
    } else {
        // Инициализируем пагинацию для истории окотов отцов
        initializeFatherLambingsPagination(window.allFatherLambings);
    }
}

// Инициализация пагинации для истории окотов отцов
function initializeFatherLambingsPagination(lambings) {
    const itemsPerPage = 5;
    let currentPage = 1;
    let filteredLambings = sortFatherLambings(lambings); // Для фильтрации
    const totalPages = Math.ceil(filteredLambings.length / itemsPerPage);
    
    function displayPage(page) {
        const startIndex = (page - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const pageItems = filteredLambings.slice(startIndex, endIndex);
        
        const fatherLambingHistoryList = document.getElementById('father-lambing-history-list');
        
        // Сохраняем текущие значения из полей перед перерисовкой
        const currentDateFrom = document.getElementById('father-history-date-from')?.value || window.fatherHistoryDateFrom || '';
        const currentDateTo = document.getElementById('father-history-date-to')?.value || window.fatherHistoryDateTo || '';
        const currentStatus = document.getElementById('father-history-status-filter')?.value || window.fatherHistoryStatusFilter || 'all';
        
        // Обновляем глобальные переменные
        window.fatherHistoryDateFrom = currentDateFrom;
        window.fatherHistoryDateTo = currentDateTo;
        window.fatherHistoryStatusFilter = currentStatus;
        
        // Создаем фильтр с сохраненными значениями
        const filterHtml = `
            <div class="date-filter-container mb-3 p-3 bg-light rounded">
                <h6>Фильтр по дате начала окота</h6>
                <div class="row">
                    <div class="col-md-3">
                        <label for="father-history-date-from" class="form-label">С:</label>
                        <input type="date" class="form-control" id="father-history-date-from" value="${currentDateFrom}">
                    </div>
                    <div class="col-md-3">
                        <label for="father-history-date-to" class="form-label">По:</label>
                        <input type="date" class="form-control" id="father-history-date-to" value="${currentDateTo}">
                    </div>
                    <div class="col-md-3">
                        <label for="father-history-status-filter" class="form-label">Статус:</label>
                        <select class="form-select" id="father-history-status-filter">
                            <option value="all" ${currentStatus === 'all' ? 'selected' : ''}>Все</option>
                            <option value="active" ${currentStatus === 'active' ? 'selected' : ''}>Активные</option>
                            <option value="completed" ${currentStatus === 'completed' ? 'selected' : ''}>Завершенные</option>
                        </select>
                    </div>
                    <div class="col-md-3 d-flex align-items-end">
                        <button type="button" class="btn btn-primary btn-sm me-2" onclick="applyFatherHistoryDateFilter()">Применить</button>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="clearFatherHistoryDateFilter()">Сбросить</button>
                    </div>
                </div>
            </div>
        `;
        
        // Обновляем содержимое
        fatherLambingHistoryList.innerHTML = filterHtml + pageItems.map(lambing => createFatherLambingCard(lambing)).join('');
        
        // Обновляем пагинацию
        updateFatherLambingsPagination(page, Math.ceil(filteredLambings.length / itemsPerPage));
    }
    
    function updateFatherLambingsPagination(page, total) {
        let paginationHtml = '<div class="pagination-container mt-3">';
        
        if (total > 1) {
            paginationHtml += '<nav><ul class="pagination pagination-sm justify-content-center">';
            
            // Кнопка "Предыдущая"
            if (page > 1) {
                paginationHtml += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="changeFatherLambingsPage(${page - 1})">‹</a></li>`;
            }
            
            // Определяем диапазон страниц для отображения (текущая + 2 слева + 2 справа)
            const startPage = Math.max(1, page - 2);
            const endPage = Math.min(total, page + 2);
            
            // Показываем первую страницу и многоточие, если нужно
            if (startPage > 1) {
                paginationHtml += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="changeFatherLambingsPage(1)">1</a></li>`;
                if (startPage > 2) {
                    paginationHtml += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
                }
            }
            
            // Номера страниц в диапазоне
            for (let i = startPage; i <= endPage; i++) {
                const activeClass = i === page ? 'active' : '';
                paginationHtml += `<li class="page-item ${activeClass}"><a class="page-link" href="javascript:void(0)" onclick="changeFatherLambingsPage(${i})">${i}</a></li>`;
            }
            
            // Показываем многоточие и последнюю страницу, если нужно
            if (endPage < total) {
                if (endPage < total - 1) {
                    paginationHtml += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
                }
                paginationHtml += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="changeFatherLambingsPage(${total})">${total}</a></li>`;
            }
            
            // Кнопка "Следующая"
            if (page < total) {
                paginationHtml += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="changeFatherLambingsPage(${page + 1})">›</a></li>`;
            }
            
            paginationHtml += '</ul></nav>';
        }
        
        paginationHtml += `<div class="text-center text-muted small">Показано ${Math.min(itemsPerPage, filteredLambings.length - (page - 1) * itemsPerPage)} из ${filteredLambings.length} окотов</div>`;
        paginationHtml += '</div>';
        
        const fatherLambingHistoryList = document.getElementById('father-lambing-history-list');
        fatherLambingHistoryList.innerHTML += paginationHtml;
    }
    
    // Глобальные функции для фильтрации
    window.applyFatherHistoryDateFilter = function() {
        const dateFrom = document.getElementById('father-history-date-from').value;
        const dateTo = document.getElementById('father-history-date-to').value;
        const statusFilter = document.getElementById('father-history-status-filter').value;
        
        // Сохраняем значения в глобальных переменных
        window.fatherHistoryDateFrom = dateFrom;
        window.fatherHistoryDateTo = dateTo;
        window.fatherHistoryStatusFilter = statusFilter;
        
        // Применяем фильтр ко всем окотам отца
        const allFatherLambings = window.allFatherLambings || lambings;
        filteredLambings = sortFatherLambings(allFatherLambings.filter(lambing => {
            const startDate = new Date(lambing.start_date);
            const fromDate = dateFrom ? new Date(dateFrom) : null;
            const toDate = dateTo ? new Date(dateTo) : null;
            
            if (fromDate && startDate < fromDate) return false;
            if (toDate && startDate > toDate) return false;
            if (statusFilter === 'active' && !lambing.is_active) return false;
            if (statusFilter === 'completed' && lambing.is_active) return false;
            return true;
        }));
        
        currentPage = 1;
        displayPage(1);
    };
    
    window.clearFatherHistoryDateFilter = function() {
        // Очищаем глобальные переменные
        window.fatherHistoryDateFrom = '';
        window.fatherHistoryDateTo = '';
        window.fatherHistoryStatusFilter = 'all';
        
        document.getElementById('father-history-date-from').value = '';
        document.getElementById('father-history-date-to').value = '';
        document.getElementById('father-history-status-filter').value = 'all';
        
        // Восстанавливаем все окоты отца
        filteredLambings = sortFatherLambings(window.allFatherLambings || lambings);
        currentPage = 1;
        displayPage(1);
    };
    
    // Глобальная функция для смены страницы
    window.changeFatherLambingsPage = function(page) {
        currentPage = page;
        displayPage(page);
    };
    
    // Показываем первую страницу
    displayPage(1);
}

function sortFatherLambings(lambings) {
    return [...lambings].sort((a, b) => {
        if (a.is_active !== b.is_active) {
            return a.is_active ? -1 : 1;
        }

        const aDate = a.start_date ? new Date(a.start_date).getTime() : 0;
        const bDate = b.start_date ? new Date(b.start_date).getTime() : 0;
        if (aDate !== bDate) {
            return bDate - aDate;
        }

        return (b.id || 0) - (a.id || 0);
    });
}

function formatLiveLambTagsLinks(lambing) {
    const liveLambLinks = Array.isArray(lambing.live_lamb_links) ? lambing.live_lamb_links : [];
    if (!liveLambLinks.length) {
        return '';
    }

    return liveLambLinks
        .map((lambLink) => {
            if (lambLink.url) {
                return `<a href="${lambLink.url}">${lambLink.tag_number}</a>`;
            }
            return lambLink.tag_number;
        })
        .join(', ');
}

function formatLiveLambsDisplay(lambing) {
    const liveCount = lambing.number_of_lambs ?? 0;
    const tagsLinks = formatLiveLambTagsLinks(lambing);
    return tagsLinks ? `${liveCount} (${tagsLinks})` : `${liveCount}`;
}

function formatAnimalTypeLabel(animalType) {
    const typeLabelMap = {
        'Производитель': 'Баран-Производитель',
        'Баран-Производитель': 'Баран-Производитель',
        'Баран': 'Баранчик',
        'Баранчик': 'Баранчик',
        'Ярка': 'Ярка',
        'Овца': 'Овцематка',
        'Овцематка': 'Овцематка',
    };
    return typeLabelMap[animalType] || animalType || 'Неизвестно';
}

// Создание карточки окота
function createLambingCard(lambing, isActive) {
    const startDate = new Date(lambing.start_date).toLocaleDateString('ru-RU');
    const plannedDate = new Date(lambing.planned_lambing_date).toLocaleDateString('ru-RU');
    const actualDate = lambing.actual_lambing_date ? 
        new Date(lambing.actual_lambing_date).toLocaleDateString('ru-RU') : null;
    
    // Показываем примечание только если оно не об импорте
    const shouldShowNote = lambing.note && !lambing.note.includes('Импорт из');

    const fatherTypeDisplay = formatAnimalTypeLabel(lambing.father_type);
    let fatherTagContent = lambing.father_display_name || lambing.father_tag || 'Неизвестно';
    if (lambing.father_url && lambing.father_tag) {
        fatherTagContent = `<a href="${lambing.father_url}">${fatherTagContent}</a>`;
    }
    
    return `
        <div class="lambing-card ${isActive ? 'active' : 'completed'}">
            <div class="lambing-info">
                <div>
                    <strong>Дата случки:</strong> ${startDate}
                </div>
                <div>
                    <strong>Отец:</strong> ${fatherTypeDisplay} ${fatherTagContent}
                </div>
                <div>
                    <strong>Планируемые роды:</strong> 
                    <span class="planned-date">${plannedDate}</span>
                </div>
                ${actualDate ? `<div><strong>Фактические роды:</strong> ${actualDate}</div>` : ''}
                ${!isActive ? `
                    <div style="grid-column: 2;">
                        <div><strong>Живые ягнята:</strong> ${formatLiveLambsDisplay(lambing)}</div>
                        <div><strong>Мертвые ягнята:</strong> ${lambing.dead_lambs_count ?? 0}</div>
                    </div>
                ` : ''}
                ${shouldShowNote ? `<div><strong>Примечание:</strong> ${lambing.note}</div>` : ''}
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

// Создание карточки окота для отцов
function createFatherLambingCard(lambing) {
    const startDate = new Date(lambing.start_date).toLocaleDateString('ru-RU');
    const plannedDate = new Date(lambing.planned_lambing_date).toLocaleDateString('ru-RU');
    const actualDate = lambing.actual_lambing_date ? 
        new Date(lambing.actual_lambing_date).toLocaleDateString('ru-RU') : null;
    
    // Определяем статус окота
    const statusClass = lambing.is_active ? 'active' : 'completed';
    const statusText = lambing.is_active ? 'Активный' : 'Завершен';
    
    // Формируем информацию о матери
    let motherTagContent = lambing.mother_tag;
    if (lambing.mother_url && lambing.mother_found) {
        motherTagContent = `<a href="${lambing.mother_url}">${lambing.mother_tag}</a>`;
    }

    let motherInfo = '';
    const motherTypeDisplay = formatAnimalTypeLabel(lambing.mother_type);
    if (lambing.mother_found) {
        motherInfo = `${motherTypeDisplay} ${motherTagContent}`;
    } else {
        motherInfo = `${motherTypeDisplay} ${lambing.mother_tag} (не найдена)`;
    }
    
    // Показываем примечание только если оно не об импорте
    const shouldShowNote = lambing.note && !lambing.note.includes('Импорт из');
    
    return `
        <div class="lambing-card ${statusClass}">
            <div class="lambing-info">
                <div>
                    <strong>Статус:</strong> ${statusText}
                </div>
                <div>
                    <strong>Мать:</strong> ${motherInfo}
                </div>
                <div>
                    <strong>Дата случки:</strong> ${startDate}
                </div>
                <div>
                    <strong>Планируемые роды:</strong> 
                    <span class="planned-date">${plannedDate}</span>
                </div>
                ${actualDate ? `<div><strong>Фактические роды:</strong> ${actualDate}</div>` : ''}
                ${!lambing.is_active ? `
                    <div style="grid-column: 2;">
                        <div><strong>Живые ягнята:</strong> ${formatLiveLambsDisplay(lambing)}</div>
                        <div><strong>Мертвые ягнята:</strong> ${lambing.dead_lambs_count ?? 0}</div>
                    </div>
                ` : ''}
                ${shouldShowNote ? `<div><strong>Примечание:</strong> ${lambing.note}</div>` : ''}
            </div>
            ${lambing.is_active ? `
                <div class="lambing-actions">
                    <button type="button" class="btn btn-success btn-sm" onclick="completeFatherLambing(${lambing.id})">
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
    const deadLambsCountInput = document.getElementById('dead-lambs-count');
    if (deadLambsCountInput) {
        deadLambsCountInput.value = '0';
    }
    
    // Загружаем список статусов
    try {
        const response = await fetch('/animals/api/all-statuses/');
        const data = await response.json();
        
        // Обрабатываем пагинированный ответ
        const statuses = data.results || data;
        
        if (!Array.isArray(statuses)) {
            console.error('Ожидался массив статусов, получено:', statuses);
            return;
        }
        
        const statusSelect = document.getElementById('new-mother-status');
        statusSelect.innerHTML = '<option value="">Выберите статус...</option>';
        let lactatingStatusId = null;

        statuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.textContent = status.status_type;
            statusSelect.appendChild(option);

            if (status.status_type === 'Лактирующая') {
                lactatingStatusId = String(status.id);
            }
        });

        if (lactatingStatusId) {
            statusSelect.value = lactatingStatusId;
        }
    } catch (error) {
        console.error('Ошибка загрузки статусов:', error);
    }
    
    // Инициализируем состояние чекбокса и контейнера форм
    const createLambsCheckbox = document.getElementById('create-lambs-checkbox');
    const lambsFormsContainer = document.getElementById('lambs-forms-container');
    const lambsCountInput = document.getElementById('lambs-count');
    
    // По умолчанию чекбокс отмечен, показываем формы
    createLambsCheckbox.checked = true;
    lambsFormsContainer.style.display = 'block';
    
    // Генерируем формы для ягнят
    generateLambForms(1);
    
    // Добавляем обработчик для чекбокса создания ягнят
    createLambsCheckbox.addEventListener('change', function() {
        if (this.checked) {
            // Создаем записи - показываем формы
            lambsFormsContainer.style.display = 'block';
            // Генерируем формы заново на основе текущего количества
            const lambsCount = parseInt(lambsCountInput.value) || 1;
            generateLambForms(lambsCount);
        } else {
            // Не создаем записи - скрываем формы
            lambsFormsContainer.style.display = 'none';
        }
    });
    
    // Добавляем обработчик для изменения количества ягнят
    lambsCountInput.addEventListener('change', function() {
        const createLambs = createLambsCheckbox.checked;
        if (createLambs) {
            const count = parseInt(this.value) || 0;
            generateLambForms(count);
        }
    });
    
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

        // Загружаем окоты для овцематок и ярок
        if (animalType === 'sheep' || animalType === 'ewe') {
            console.log('4. Загружаем окоты...');
            await loadLambings();
        }

        // Загружаем историю окотов для баранов-производителей и баранчиков (как отцы)
        if (animalType === 'maker' || animalType === 'ram') {
            console.log('4. Загружаем историю окотов как отец...');
            await loadFatherLambings();
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
                    <option value="male">Баранчик</option>
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
                <label>Живой вес (кг):</label>
                <input type="number" class="lamb-live-weight" min="0" step="0.1" placeholder="Необязательно">
            </div>
        </div>

        <div class="form-row">
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
        const response = await apiRequest('/veterinary/api/status/?page_size=100');
        // API возвращает пагинированные данные, берем массив из results
        const statuses = response.results || response;
        
        if (!Array.isArray(statuses)) {
            console.error('Ожидался массив статусов для ягненка, получено:', statuses);
            return;
        }
        
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
        const response = await apiRequest('/veterinary/api/place/?page_size=100');
        // API возвращает пагинированные данные, берем массив из results
        const places = response.results || response;
        
        if (!Array.isArray(places)) {
            console.error('Ожидался массив мест для ягненка, получено:', places);
            return;
        }
        
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

// Завершить окот (для отцов - баранов-производителей и баранчиков)
async function completeFatherLambing(lambingId) {
    // Сохраняем ID окота для использования в модальном окне
    window.currentLambingId = lambingId;
    
    // Устанавливаем текущую дату как дату фактических родов
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('actual-lambing-date').value = today;
    const deadLambsCountInput = document.getElementById('dead-lambs-count');
    if (deadLambsCountInput) {
        deadLambsCountInput.value = '0';
    }
    
    // Загружаем список статусов (но не будем менять статус матери, если её нет в БД)
    try {
        const response = await fetch('/animals/api/all-statuses/');
        const data = await response.json();
        
        const statuses = data.results || data;
        
        if (!Array.isArray(statuses)) {
            console.error('Ожидался массив статусов, получено:', statuses);
            return;
        }
        
        const statusSelect = document.getElementById('new-mother-status');
        statusSelect.innerHTML = '<option value="">Выберите статус...</option>';
        let lactatingStatusId = null;

        statuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.textContent = status.status_type;
            statusSelect.appendChild(option);

            if (status.status_type === 'Лактирующая') {
                lactatingStatusId = String(status.id);
            }
        });

        if (lactatingStatusId) {
            statusSelect.value = lactatingStatusId;
        }
    } catch (error) {
        console.error('Ошибка загрузки статусов:', error);
    }
    
    // Скрываем секцию создания ягнят (для отцов не создаем ягнят)
    const lambsCreationSection = document.getElementById('lambs-creation-section');
    if (lambsCreationSection) {
        lambsCreationSection.style.display = 'none';
    }
    
    // Показываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('completeLambingModal'));
    modal.show();
}

// Обновляем функцию завершения окота для работы с отцами
async function completeLambingWithChildren() {
    const lambingId = window.currentLambingId;
    const actualDate = document.getElementById('actual-lambing-date').value;
    const lambsCount = parseInt(document.getElementById('lambs-count').value) || 0;
    const deadLambsCount = parseInt(document.getElementById('dead-lambs-count')?.value || '0') || 0;
    const lambingNote = document.getElementById('lambing-note').value;
    const createLambs = document.getElementById('create-lambs-checkbox') ? document.getElementById('create-lambs-checkbox').checked : false;
    const newMotherStatusId = document.getElementById('new-mother-status').value;
    
    if (!actualDate) {
        alert('Пожалуйста, укажите дату фактических родов');
        return;
    }

    if (lambsCount < 0 || deadLambsCount < 0) {
        alert('Количество живых и мертвых ягнят не может быть отрицательным');
        return;
    }
    
    try {
        // Собираем данные о ягнятах, если нужно их создавать
        let lambsData = [];
        
        if (createLambs && lambsCount > 0) {
            const lambForms = document.querySelectorAll('.lamb-form');
            
            // Проверяем, что количество форм соответствует количеству ягнят
            if (lambForms.length !== lambsCount) {
                alert(`Количество форм ягнят (${lambForms.length}) не соответствует указанному количеству (${lambsCount})`);
                return;
            }
            
            for (let form of lambForms) {
                const gender = form.querySelector('.lamb-gender').value;
                const tag = form.querySelector('.lamb-tag').value.trim();
                const status = form.querySelector('.lamb-status').value;
                const place = form.querySelector('.lamb-place').value;
                const note = form.querySelector('.lamb-note').value.trim();
                const liveWeightRaw = form.querySelector('.lamb-live-weight')?.value?.trim();
                let liveWeight = null;

                if (liveWeightRaw) {
                    liveWeight = parseFloat(liveWeightRaw);
                    if (Number.isNaN(liveWeight) || liveWeight < 0) {
                        alert('Живой вес ягненка должен быть неотрицательным числом');
                        return;
                    }
                }
                
                if (!gender || !tag) {
                    alert('Пожалуйста, заполните тип животного и бирку для всех ягнят');
                    return;
                }
                
                lambsData.push({
                    gender: gender,
                    tag_number: tag,
                    animal_status_id: status ? parseInt(status) : null,
                    place_id: place ? parseInt(place) : null,
                    note: note || '',
                    live_weight: liveWeight
                });
            }
        }
        
        // Отправляем запрос на завершение окота
        const completionData = {
            actual_lambing_date: actualDate,
            number_of_lambs: lambsCount,
            dead_lambs_count: deadLambsCount,
            note: lambingNote,
            new_mother_status_id: newMotherStatusId ? parseInt(newMotherStatusId) : null,
            lambs: lambsData
        };
        
        await apiRequest(`/animals/lambing/${lambingId}/complete-with-children/`, 'POST', completionData);
        
        // Формируем сообщение об успехе
        let successMessage = 'Окот успешно завершен!';
        if (createLambs && lambsData.length > 0) {
            successMessage += ` Создано ${lambsData.length} ягнят.`;
        } else if (lambsCount > 0) {
            successMessage += ` Зафиксировано ${lambsCount} ягнят (без создания записей).`;
        }
        
        alert(successMessage);
        
        // Закрываем модальное окно
        const modal = bootstrap.Modal.getInstance(document.getElementById('completeLambingModal'));
        modal.hide();
        
        // Перезагружаем список окотов
        const animalDetail = document.getElementById('animal-detail');
        const animalType = animalDetail.dataset.animalType;
        
        if (animalType === 'sheep' || animalType === 'ewe') {
            await loadLambings();
        } else if (animalType === 'maker' || animalType === 'ram') {
            await loadFatherLambings();
        }
        
        // Показываем секцию создания ягнят обратно
        const lambsCreationSection = document.getElementById('lambs-creation-section');
        if (lambsCreationSection) {
            lambsCreationSection.style.display = 'block';
        }
        
    } catch (error) {
        console.error('Ошибка завершения окота:', error);
        alert('Ошибка при завершении окота: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Экспортируем новые функции для глобального доступа
window.completeLambingWithChildren = completeLambingWithChildren;
window.removeLambForm = removeLambForm;
window.openAnimalExportModal = openAnimalExportModal;
window.exportAnimalToExcel = exportAnimalToExcel;

