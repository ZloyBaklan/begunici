// Подгрузка данных в выпадающие списки при загрузке формы создания Maker
document.addEventListener('DOMContentLoaded', function () {
    const createMakerForm = document.getElementById('create-maker-form');
    
    if (createMakerForm) {
        createMakerForm.addEventListener('show', function () {
            loadSelectOptions('/tags/', 'maker-tag', 'tag_number');  // Подгружаем бирки
            loadSelectOptions('/status/', 'maker-status', 'status_type');  // Подгружаем статусы
            loadSelectOptions('/place/', 'maker-place', 'sheepfold');  // Подгружаем места
            loadSelectOptions('/veterinary-care/', 'maker-veterinary-care', 'care_type');  // Подгружаем ветобработки
        });
    }

    const makerForm = document.getElementById('maker-form');
    
    if (makerForm) {
        makerForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const makerData = {
                tag: document.getElementById('maker-tag').value,
                animal_status: document.getElementById('maker-status').value,
                birth_date: document.getElementById('maker-birth-date').value,
                last_weight: document.getElementById('maker-last-weight').value,
                last_weight_date: document.getElementById('maker-last-weight-date').value,
                working_condition: document.getElementById('maker-working-condition').value,
                place: document.getElementById('maker-place').value,
                veterinary_care: document.getElementById('maker-veterinary-care').value,
                plemstatus: document.getElementById('maker-plemstatus').value,
            };

            await createMaker('/maker/', makerData);  // Указываем путь для API
            await getAnimalData('/maker/', 'maker-table', ['tag', 'animal_status', 'birth_date']);  // Обновляем список производителей
        });
    }
});

// Функция для создания объекта Maker через API
export async function createMaker(url, data) {
    try {
        const csrfToken = getCSRFToken();
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const errorData = await response.json();
            console.error('Ошибка при создании производителя:', errorData);
        } else {
            const responseData = await response.json();
            console.log('Производитель успешно создан:', responseData);
            alert('Производитель успешно создан');
        }
    } catch (error) {
        console.error('Ошибка сети:', error);
    }
}

// Функция для получения данных о животных и их отображения в таблице
export async function getAnimalData(url, tableId, headers) {
    await showList(url, tableId, headers);
}

// Функция для подгрузки данных в выпадающие списки
async function loadSelectOptions(url, selectElementId, displayField) {
    try {
        const response = await fetch(url);
        const data = await response.json();

        const selectElement = document.getElementById(selectElementId);
        selectElement.innerHTML = '';  // Очистить старые опции

        data.results.forEach(item => {
            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = item[displayField];  // Отображаемое значение
            selectElement.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка при загрузке данных:', error);
    }
}
