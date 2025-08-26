import { apiRequest } from "./utils.js";

let allArchiveData = []; // Храним все данные архива

document.addEventListener('DOMContentLoaded', function () {
    fetchArchive();  // Загружаем архив при загрузке страницы
});

// Функция загрузки архива
async function fetchArchive() {
    try {
        const archive = await apiRequest('/animals/archive/');
        allArchiveData = archive.results || archive;
        displayArchive(allArchiveData);
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
        const archivedDate = animal.archived_date || 'Не указана';
        const age = animal.age || 'Не указан';
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
            <td>${index + 1}</td>
            <td>${animalType}</td>
            <td><a href="${detailUrl}">${tagNumber}</a></td>
            <td>${status}</td>
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
function filterArchiveData(animalType, status, search) {
    let filteredData = allArchiveData;
    
    // Фильтр по типу животного
    if (animalType) {
        filteredData = filteredData.filter(animal => animal.animal_type === animalType);
    }
    
    // Фильтр по статусу
    if (status) {
        filteredData = filteredData.filter(animal => 
            animal.status && animal.status === status
        );
    }
    
    // Фильтр по поиску
    if (search) {
        const searchLower = search.toLowerCase();
        filteredData = filteredData.filter(animal => 
            animal.tag_number && animal.tag_number.toLowerCase().includes(searchLower)
        );
    }
    
    displayArchive(filteredData);
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
        fetchArchive(); // Обновляем список архива
    } catch (error) {
        console.error('Ошибка при восстановлении животного:', error);
        alert('Ошибка при восстановлении животного');
    }
}

// Экспортируем функцию фильтрации для использования в HTML
window.filterArchiveData = filterArchiveData;
window.restoreAnimal = restoreAnimal;
