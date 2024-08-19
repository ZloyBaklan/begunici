// main.js

// Функция для подгрузки и отображения данных// main.js

// Функция для подгрузки и отображения производителей
async function loadMakers() {
    try {
        let response = await fetch('/list/makers/'); // Запрос к API
        let makers = await response.json();         // Преобразование ответа в JSON
        renderList(makers, 'makers-list');          // Рендер списка производителей
    } catch (error) {
        console.error('Ошибка при загрузке производителей:', error);
    }
}

// Функция для подгрузки и отображения баранов
async function loadRams() {
    try {
        let response = await fetch('/list/rams/');   // Запрос к API
        let rams = await response.json();           // Преобразование ответа в JSON
        renderList(rams, 'rams-list');              // Рендер списка баранов
    } catch (error) {
        console.error('Ошибка при загрузке баранов:', error);
    }
}

// Функция для рендеринга списка в HTML
function renderList(data, elementId) {
    const listElement = document.getElementById(elementId);
    listElement.innerHTML = '';  // Очищаем список перед добавлением данных
    data.forEach(item => {
        const listItem = document.createElement('li');
        listItem.textContent = `${item.tag.tag_number} - Возраст: ${item.age}, Вес: ${item.last_weight} кг`;
        listElement.appendChild(listItem);
    });
}

// Привязываем функции к кнопкам
document.getElementById('loadMakers').addEventListener('click', loadMakers);
document.getElementById('loadRams').addEventListener('click', loadRams);
