import { apiRequest, formatDateToOutput } from "./utils.js";

let allArchiveData = []; // Храним все данные архива
let currentPage = 1; // Текущая страница
const pageSize = 10; // Количество записей на странице

document.addEventListener('DOMContentLoaded', function () {
    // Устанавливаем начальный фильтр по типу животного, если он передан
    const initialType = window.initialAnimalType || '';
    if (initialType) {
        const typeFilter = document.getElementById('animal-type-filter');
        if (typeFilter) {
            typeFilter.value = initialType;
        }
    }
    
    fetchArchive();  // Загружаем архив при загрузке страницы
});

// Функция загрузки архива
async function fetchArchive(page = 1) {
    try {
        currentPage = page;
        
        // Получаем начальный тип животного из URL или глобальной переменной
        const initialType = window.initialAnimalType || '';
        let url = `/animals/archive/?page=${page}&page_size=${pageSize}`;
        
        // Добавляем параметр type если он есть
        if (initialType) {
            url += `&type=${encodeURIComponent(initialType)}`;
        }
        
        const response = await apiRequest(url);
        allArchiveData = response.results || response;
        displayArchive(allArchiveData);
        updatePagination(response);
    } catch (error) {
        console.error('Ошибка при загрузке архива:', error);
    }
}

// Функция отображения архива
function displayArchive(data) {
    const archiveTable = document.getElementById('archive-list');
    archiveTable.innerHTML = '';

    data.forEach((animal, index) => {
        const row = document.createElement('tr');
        
        // Получаем данные с учетом формата ArchiveAnimalSerializer
        const tagNumber = animal.tag_number;
        const animalTypeCode = animal.animal_type;
        const status = animal.status || 'Не указан';
        const statusColor = animal.status_color || '#FFFFFF';
        const archivedDate = formatDateToOutput(animal.archived_date) || 'Не указана';
        const age = animal.age ? `${animal.age} мес.` : 'Не указан';
        const place = animal.place || 'Не указано';
        
        // Определяем тип животного и URL
        let animalType = 'Неизвестно';
        let detailUrl = '';
        
        if (animalTypeCode === 'Maker') {
            animalType = 'Производитель';
            detailUrl = `/animals/maker/${tagNumber}/info/`;
        } else if (animalTypeCode === 'Ram') {
            animalType = 'Баран';
            detailUrl = `/animals/ram/${tagNumber}/info/`;
        } else if (animalTypeCode === 'Ewe') {
            animalType = 'Ярка';
            detailUrl = `/animals/ewe/${tagNumber}/info/`;
        } else if (animalTypeCode === 'Sheep') {
            animalType = 'Овца';
            detailUrl = `/animals/sheep/${tagNumber}/info/`;
        }
        
        row.innerHTML = `
            <td>${(currentPage - 1) * pageSize + index + 1}</td>
            <td>${animalType}</td>
            <td><a href="${detailUrl}">${tagNumber}</a></td>
            <td style="background-color:${statusColor}">${status}</td>
            <td>${archivedDate}</td>
            <td>${age}</td>
            <td>${place}</td>
            <td>
                <button onclick="restoreAnimal('${animalTypeCode}', '${tagNumber}')">Восстановить</button>
            </td>
        `;
        archiveTable.appendChild(row);
    });
}

// Функция фильтрации архива
async function filterArchiveData(animalType, status, search) {
    try {
        currentPage = 1; // Сбрасываем на первую страницу при фильтрации
        
        // Строим URL с параметрами фильтрации
        let url = `/animals/archive/?page=${currentPage}&page_size=${pageSize}`;
        
        if (animalType) {
            url += `&type=${encodeURIComponent(animalType)}`;
        }
        if (search) {
            url += `&search=${encodeURIComponent(search)}`;
        }
        
        // Делаем новый запрос с фильтрами
        const response = await apiRequest(url);
        allArchiveData = response.results || response;
        
        // Дополнительная фильтрация по статусу (если API не поддерживает)
        let filteredData = allArchiveData;
        if (status) {
            filteredData = filteredData.filter(animal => 
                animal.status && animal.status === status
            );
        }
        
        displayArchive(filteredData);
        updatePagination(response);
    } catch (error) {
        console.error('Ошибка при фильтрации архива:', error);
        // Fallback к локальной фильтрации
        let filteredData = allArchiveData;
        
        if (animalType) {
            filteredData = filteredData.filter(animal => animal.animal_type === animalType);
        }
        if (status) {
            filteredData = filteredData.filter(animal => 
                animal.status && animal.status === status
            );
        }
        if (search) {
            const searchLower = search.toLowerCase();
            filteredData = filteredData.filter(animal => 
                animal.tag_number && animal.tag_number.toLowerCase().includes(searchLower)
            );
        }
        
        displayArchive(filteredData);
    }
}

// Функция восстановления животного из архива
async function restoreAnimal(animalType, tagNumber) {
    const confirmRestore = confirm(`Вы уверены, что хотите восстановить животное ${tagNumber} из архива?`);
    if (!confirmRestore) return;

    try {
        // Определяем URL для восстановления в зависимости от типа животного
        let restoreUrl = '';
        switch (animalType) {
            case 'Maker':
                restoreUrl = `/animals/maker/${tagNumber}/restore/`;
                break;
            case 'Ram':
                restoreUrl = `/animals/ram/${tagNumber}/restore/`;
                break;
            case 'Ewe':
                restoreUrl = `/animals/ewe/${tagNumber}/restore/`;
                break;
            case 'Sheep':
                restoreUrl = `/animals/sheep/${tagNumber}/restore/`;
                break;
            default:
                throw new Error('Неизвестный тип животного');
        }
        
        await apiRequest(restoreUrl, 'POST');
        alert('Животное успешно восстановлено из архива');
        fetchArchive(currentPage); // Обновляем текущую страницу архива
    } catch (error) {
        console.error('Ошибка при восстановлении животного:', error);
        alert('Ошибка при восстановлении животного');
    }
}

// Функция обновления пагинации
function updatePagination(response) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = ''; // Очищаем старую навигацию

    if (response.previous) {
        const prevButton = document.createElement('button');
        prevButton.innerText = 'Предыдущая';
        prevButton.onclick = () => {
            currentPage--;
            fetchArchive(currentPage);
        };
        pagination.appendChild(prevButton);
    }

    if (response.next) {
        const nextButton = document.createElement('button');
        nextButton.innerText = 'Следующая';
        nextButton.onclick = () => {
            currentPage++;
            fetchArchive(currentPage);
        };
        pagination.appendChild(nextButton);
    }

    const pageInfo = document.createElement('span');
    pageInfo.innerText = ` Страница ${currentPage}`;
    pagination.appendChild(pageInfo);
}

// Экспортируем функции для использования в HTML
window.filterArchiveData = filterArchiveData;
window.restoreAnimal = restoreAnimal;
