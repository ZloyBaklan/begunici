import { apiRequest } from "./utils.js";

// Глобальные переменные
let selectedMothers = [];
let selectedFather = null;
let currentPage = 1;
const pageSize = 10;

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM загружен, инициализируем страницу управления окотами');
    
    // Устанавливаем текущую дату как дату начала окота
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('lambing-start-date').value = today;
    
    // Загружаем активные окоты
    loadActiveLambings();
    
    // Обработчик изменения количества ягнят
    document.addEventListener('change', function(e) {
        if (e.target && e.target.id === 'lambs-count') {
            const count = parseInt(e.target.value) || 0;
            generateLambForms(count);
        }
    });
});

// Загрузка активных окотов
async function loadActiveLambings() {
    try {
        console.log('Загружаем активные окоты, страница:', currentPage);
        const response = await apiRequest(`/animals/lambing/?is_active=true&page=${currentPage}&page_size=${pageSize}&ordering=planned_lambing_date`);
        console.log('Ответ API:', response);
        
        const lambings = response.results || response;
        
        const tableBody = document.getElementById('active-lambings-table');
        tableBody.innerHTML = '';
        
        if (lambings.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Нет активных окотов</td></tr>';
        } else {
            lambings.forEach(lambing => {
                const row = createLambingRow(lambing);
                tableBody.appendChild(row);
            });
        }
        
        // Обновляем пагинацию
        updatePagination(response);
        
    } catch (error) {
        console.error('Ошибка загрузки активных окотов:', error);
        document.getElementById('active-lambings-table').innerHTML = 
            '<tr><td colspan="6" class="text-center text-danger">Ошибка загрузки данных: ' + error.message + '</td></tr>';
    }
}

// Создание строки таблицы для окота
function createLambingRow(lambing) {
    const row = document.createElement('tr');
    
    // Получаем информацию о матери и отце из сериализатора
    const motherTag = lambing.mother_tag || 'Неизвестно';
    const fatherTag = lambing.father_tag || 'Неизвестно';
    const motherType = lambing.mother_type || 'Неизвестно';
    const fatherType = lambing.father_type || 'Неизвестно';
    const note = lambing.note || '';
    
    // Создаем ссылки на животных
    const motherLink = createAnimalLink(motherTag, motherType);
    const fatherLink = createAnimalLink(fatherTag, fatherType);
    
    // Форматируем даты
    const startDate = new Date(lambing.start_date).toLocaleDateString('ru-RU');
    const plannedDate = new Date(lambing.planned_lambing_date).toLocaleDateString('ru-RU');
    
    row.innerHTML = `
        <td>${motherLink}</td>
        <td>${fatherLink}</td>
        <td>${startDate}</td>
        <td>${plannedDate}</td>
        <td>${note}</td>
        <td>
            <button class="btn btn-success btn-sm" onclick="showCompleteLambingModal(${lambing.id})">
                Завершить окот
            </button>
        </td>
    `;
    
    return row;
}

// Создание ссылки на животное
function createAnimalLink(tagNumber, animalType) {
    if (tagNumber === 'Неизвестно' || animalType === 'Неизвестно') {
        return `${tagNumber} (${animalType})`;
    }
    
    // Определяем URL в зависимости от типа животного
    let url = '#';
    switch (animalType) {
        case 'Производитель':
            url = `/animals/maker/${tagNumber}/info/`;
            break;
        case 'Баран':
            url = `/animals/ram/${tagNumber}/info/`;
            break;
        case 'Ярка':
            url = `/animals/ewe/${tagNumber}/info/`;
            break;
        case 'Овца':
            url = `/animals/sheep/${tagNumber}/info/`;
            break;
    }
    
    return `<a href="${url}" style="color: #007bff; text-decoration: underline; font-weight: bold;">${tagNumber}</a> (${animalType})`;
}

// Обновление пагинации
function updatePagination(response) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';

    if (response.previous) {
        const prevButton = document.createElement('button');
        prevButton.innerText = 'Предыдущая';
        prevButton.className = 'btn btn-secondary me-2';
        prevButton.onclick = () => {
            currentPage--;
            loadActiveLambings();
        };
        pagination.appendChild(prevButton);
    }

    if (response.next) {
        const nextButton = document.createElement('button');
        nextButton.innerText = 'Следующая';
        nextButton.className = 'btn btn-secondary me-2';
        nextButton.onclick = () => {
            currentPage++;
            loadActiveLambings();
        };
        pagination.appendChild(nextButton);
    }

    const pageInfo = document.createElement('span');
    pageInfo.innerText = ` Страница ${currentPage}`;
    pagination.appendChild(pageInfo);
}

// Показать модальное окно выбора матерей
async function showSelectMothersModal() {
    try {
        // Загружаем неактивных матерей (без активных окотов)
        const response = await apiRequest('/animals/api/inactive-mothers/');
        const mothers = response || [];
        
        const mothersList = document.getElementById('mothers-list');
        mothersList.innerHTML = '';
        
        if (mothers.length === 0) {
            mothersList.innerHTML = '<div class="text-center text-muted">Нет доступных ярок/овец без активных окотов</div>';
        } else {
            // Группируем по типу - сначала ярки, потом овцы
            const ewes = mothers.filter(m => m.type_code === 'ewe');
            const sheep = mothers.filter(m => m.type_code === 'sheep');
            
            // Добавляем ярок
            if (ewes.length > 0) {
                const eweHeader = document.createElement('h6');
                eweHeader.textContent = 'Ярки';
                eweHeader.className = 'mt-3 mb-2 text-primary';
                mothersList.appendChild(eweHeader);
                
                ewes.forEach(ewe => {
                    const item = createMotherItem(ewe);
                    mothersList.appendChild(item);
                });
            }
            
            // Добавляем овец
            if (sheep.length > 0) {
                const sheepHeader = document.createElement('h6');
                sheepHeader.textContent = 'Овцы';
                sheepHeader.className = 'mt-3 mb-2 text-primary';
                mothersList.appendChild(sheepHeader);
                
                sheep.forEach(sheepAnimal => {
                    const item = createMotherItem(sheepAnimal);
                    mothersList.appendChild(item);
                });
            }
        }
        
        // Показываем модальное окно
        const modal = new bootstrap.Modal(document.getElementById('selectMothersModal'));
        modal.show();
        
    } catch (error) {
        console.error('Ошибка загрузки списка матерей:', error);
        alert('Ошибка загрузки списка ярок/овец');
    }
}

// Создание элемента для выбора матери
function createMotherItem(animal) {
    const item = document.createElement('div');
    item.className = 'form-check mb-2';
    
    item.innerHTML = `
        <input class="form-check-input mother-checkbox" type="checkbox" 
               value="${animal.tag_number}" data-type="${animal.type_code}" data-tag="${animal.tag_number}">
        <label class="form-check-label">
            ${animal.tag_number} (${animal.animal_type}) - ${animal.status}
        </label>
    `;
    
    return item;
}

// Подтверждение выбора матерей
function confirmMothersSelection() {
    const checkedBoxes = document.querySelectorAll('.mother-checkbox:checked');
    selectedMothers = Array.from(checkedBoxes).map(checkbox => ({
        tag_number: checkbox.value,
        type: checkbox.dataset.type,
        tag: checkbox.dataset.tag
    }));
    
    // Обновляем отображение
    const display = document.getElementById('selected-mothers-display');
    if (selectedMothers.length === 0) {
        display.textContent = 'Не выбрано';
        display.className = 'mt-2 text-muted';
    } else {
        display.textContent = `Выбрано: ${selectedMothers.length} животных (${selectedMothers.map(m => m.tag).join(', ')})`;
        display.className = 'mt-2 text-success';
    }
    
    // Закрываем модальное окно
    const modal = bootstrap.Modal.getInstance(document.getElementById('selectMothersModal'));
    modal.hide();
}

// Показать модальное окно выбора отца
async function showSelectFatherModal() {
    try {
        // Загружаем всех отцов (производителей и баранов)
        const response = await apiRequest('/animals/api/all-fathers/');
        const fathers = response || [];
        
        const fathersList = document.getElementById('fathers-list');
        fathersList.innerHTML = '';
        
        if (fathers.length === 0) {
            fathersList.innerHTML = '<div class="text-center text-muted">Нет доступных производителей/баранов</div>';
        } else {
            // Группируем по типу - сначала производители, потом бараны
            const makers = fathers.filter(f => f.type_code === 'maker');
            const rams = fathers.filter(f => f.type_code === 'ram');
            
            // Добавляем производителей
            if (makers.length > 0) {
                const makerHeader = document.createElement('h6');
                makerHeader.textContent = 'Производители';
                makerHeader.className = 'mt-3 mb-2 text-primary';
                fathersList.appendChild(makerHeader);
                
                makers.forEach(maker => {
                    const item = createFatherItem(maker);
                    fathersList.appendChild(item);
                });
            }
            
            // Добавляем баранов
            if (rams.length > 0) {
                const ramHeader = document.createElement('h6');
                ramHeader.textContent = 'Бараны';
                ramHeader.className = 'mt-3 mb-2 text-primary';
                fathersList.appendChild(ramHeader);
                
                rams.forEach(ram => {
                    const item = createFatherItem(ram);
                    fathersList.appendChild(item);
                });
            }
        }
        
        // Показываем модальное окно
        const modal = new bootstrap.Modal(document.getElementById('selectFatherModal'));
        modal.show();
        
    } catch (error) {
        console.error('Ошибка загрузки списка отцов:', error);
        alert('Ошибка загрузки списка производителей/баранов');
    }
}

// Создание элемента для выбора отца
function createFatherItem(animal) {
    const item = document.createElement('div');
    item.className = 'form-check mb-2';
    
    item.innerHTML = `
        <input class="form-check-input father-radio" type="radio" name="father" 
               value="${animal.tag_number}" data-type="${animal.type_code}" data-tag="${animal.tag_number}">
        <label class="form-check-label">
            ${animal.tag_number} (${animal.animal_type}) - ${animal.status}
        </label>
    `;
    
    return item;
}

// Подтверждение выбора отца
function confirmFatherSelection() {
    const checkedRadio = document.querySelector('.father-radio:checked');
    
    if (!checkedRadio) {
        alert('Выберите отца');
        return;
    }
    
    selectedFather = {
        tag_number: checkedRadio.value,
        type: checkedRadio.dataset.type,
        tag: checkedRadio.dataset.tag
    };
    
    // Обновляем отображение
    const display = document.getElementById('selected-father-display');
    const typeText = selectedFather.type === 'maker' ? 'Производитель' : 'Баран';
    display.textContent = `${selectedFather.tag} (${typeText})`;
    display.className = 'mt-2 text-success';
    
    // Закрываем модальное окно
    const modal = bootstrap.Modal.getInstance(document.getElementById('selectFatherModal'));
    modal.hide();
}

// Создание множественных окотов
async function createMultipleLambings() {
    const startDate = document.getElementById('lambing-start-date').value;
    const note = document.getElementById('lambing-note').value.trim();
    
    // Валидация
    if (!startDate) {
        alert('Укажите дату начала окота');
        return;
    }
    
    if (selectedMothers.length === 0) {
        alert('Выберите овец/ярок');
        return;
    }
    
    if (!selectedFather) {
        alert('Выберите отца');
        return;
    }
    
    try {
        const data = {
            start_date: startDate,
            father_tag_number: selectedFather.tag_number,
            mother_tag_numbers: selectedMothers.map(m => m.tag_number),
            note: note || ''
        };
        
        const response = await apiRequest('/animals/api/bulk-create-lambings/', 'POST', data);
        
        let message = `Успешно создано ${response.created_count} окотов!`;
        if (response.errors && response.errors.length > 0) {
            message += `\n\nОшибки:\n${response.errors.join('\n')}`;
        }
        
        alert(message);
        
        // Очищаем форму
        resetForm();
        
        // Перезагружаем таблицу
        loadActiveLambings();
        
    } catch (error) {
        console.error('Ошибка создания окотов:', error);
        alert('Ошибка при создании окотов: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Сброс формы
function resetForm() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('lambing-start-date').value = today;
    document.getElementById('lambing-note').value = '';
    
    selectedMothers = [];
    selectedFather = null;
    
    document.getElementById('selected-mothers-display').textContent = 'Не выбрано';
    document.getElementById('selected-mothers-display').className = 'mt-2 text-muted';
    
    document.getElementById('selected-father-display').textContent = 'Не выбран';
    document.getElementById('selected-father-display').className = 'mt-2 text-muted';
}

// Показать модальное окно завершения окота
function showCompleteLambingModal(lambingId) {
    // Сохраняем ID окота для использования в модальном окне
    window.currentLambingId = lambingId;
    document.getElementById('completing-lambing-id').value = lambingId;
    
    // Устанавливаем текущую дату как дату фактических родов
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('actual-lambing-date').value = today;
    
    // Загружаем список статусов
    loadStatusesForMother();
    
    // Генерируем формы для ягнят
    generateLambForms(1);
    
    // Показываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('completeLambingModal'));
    modal.show();
}

// Загрузка статусов для матери
async function loadStatusesForMother() {
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
}

// Генерация форм для ягнят
function generateLambForms(count) {
    const container = document.getElementById('lambs-forms-container');
    container.innerHTML = '';
    
    for (let i = 1; i <= count; i++) {
        const lambForm = createLambForm(i);
        container.appendChild(lambForm);
    }
}

// Создание формы для ягненка
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

// Загрузка статусов для ягненка
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

// Загрузка мест для ягненка
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
        loadActiveLambings();
        
    } catch (error) {
        console.error('Ошибка завершения окота:', error);
        alert('Ошибка при завершении окота: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Экспортируем функции для глобального доступа
window.showSelectMothersModal = showSelectMothersModal;
window.showSelectFatherModal = showSelectFatherModal;
window.confirmMothersSelection = confirmMothersSelection;
window.confirmFatherSelection = confirmFatherSelection;
window.createMultipleLambings = createMultipleLambings;
window.showCompleteLambingModal = showCompleteLambingModal;
window.completeLambingWithChildren = completeLambingWithChildren;
window.removeLambForm = removeLambForm;