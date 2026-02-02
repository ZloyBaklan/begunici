import { apiRequest } from "./utils.js";

document.addEventListener('DOMContentLoaded', function () {
    loadPlacesMap();
});

// Загрузка карты овчарен
async function loadPlacesMap() {
    const container = document.getElementById('barns-container');
    container.innerHTML = '<div class="loading">Загрузка карты овчарен</div>';
    
    try {
        // Получаем все места
        const places = await apiRequest('/veterinary/api/place/');
        
        // Получаем всех животных с их местами
        const [makers, rams, ewes, sheep] = await Promise.all([
            apiRequest('/animals/maker/'),
            apiRequest('/animals/ram/'),
            apiRequest('/animals/ewe/'),
            apiRequest('/animals/sheep/')
        ]);

        // Группируем места по овчарням
        const barnGroups = groupPlacesByBarn(places);
        
        // Группируем животных по местам
        const animalsByPlace = groupAnimalsByPlace([
            ...makers.results || makers,
            ...rams.results || rams, 
            ...ewes.results || ewes,
            ...sheep.results || sheep
        ]);

        // Отображаем карту
        displayBarnsMap(barnGroups, animalsByPlace);
        
    } catch (error) {
        console.error('Ошибка при загрузке карты овчарен:', error);
        document.getElementById('barns-container').innerHTML = 
            '<div style="color: red;">Ошибка загрузки данных</div>';
    }
}

// Группировка мест по овчарням
function groupPlacesByBarn(places) {
    const barnGroups = {};
    
    places.forEach(place => {
        const match = place.sheepfold.match(/Овчарня (\d+) Отсек (\d+)/);
        if (match) {
            const barnNumber = parseInt(match[1]);
            const sectionNumber = parseInt(match[2]);
            
            if (!barnGroups[barnNumber]) {
                barnGroups[barnNumber] = {};
            }
            
            barnGroups[barnNumber][sectionNumber] = {
                id: place.id,
                name: place.sheepfold,
                barnNumber,
                sectionNumber
            };
        }
    });
    
    return barnGroups;
}

// Группировка животных по местам
function groupAnimalsByPlace(animals) {
    const animalsByPlace = {};
    
    animals.forEach(animal => {
        if (animal.place && animal.place.id) {
            const placeId = animal.place.id;
            
            if (!animalsByPlace[placeId]) {
                animalsByPlace[placeId] = {
                    makers: [],
                    rams: [],
                    ewes: [],
                    sheep: []
                };
            }
            
            // Определяем тип животного по наличию полей
            if (animal.plemstatus !== undefined) {
                animalsByPlace[placeId].makers.push(animal);
            } else if (animal.tag && animal.tag.animal_type === 'Ram') {
                animalsByPlace[placeId].rams.push(animal);
            } else if (animal.tag && animal.tag.animal_type === 'Ewe') {
                animalsByPlace[placeId].ewes.push(animal);
            } else {
                animalsByPlace[placeId].sheep.push(animal);
            }
        }
    });
    
    return animalsByPlace;
}

// Отображение карты овчарен
function displayBarnsMap(barnGroups, animalsByPlace) {
    const container = document.getElementById('barns-container');
    container.innerHTML = '';
    
    // Сортируем овчарни по номерам
    const sortedBarns = Object.keys(barnGroups).sort((a, b) => parseInt(a) - parseInt(b));
    
    sortedBarns.forEach(barnNumber => {
        const sections = barnGroups[barnNumber];
        const barnDiv = createBarnTable(barnNumber, sections, animalsByPlace);
        container.appendChild(barnDiv);
    });
}

// Создание таблицы для овчарни
function createBarnTable(barnNumber, sections, animalsByPlace) {
    const barnDiv = document.createElement('div');
    barnDiv.className = 'barn-container';
    
    // Заголовок овчарни
    const title = document.createElement('h2');
    title.textContent = `Овчарня ${barnNumber}`;
    title.className = 'barn-title';
    barnDiv.appendChild(title);
    
    // Получаем только существующие номера отсеков и сортируем их
    const sectionNumbers = Object.keys(sections).map(n => parseInt(n)).sort((a, b) => a - b);
    
    if (sectionNumbers.length === 0) {
        // Если нет отсеков, показываем сообщение
        const emptyMessage = document.createElement('div');
        emptyMessage.textContent = 'Нет отсеков в этой овчарне';
        emptyMessage.className = 'empty-barn';
        barnDiv.appendChild(emptyMessage);
        return barnDiv;
    }
    
    // Создаем таблицу с отсеками
    const table = document.createElement('table');
    table.className = 'barn-table';
    
    // Определяем количество строк (по 2 отсека в ряд)
    const rows = Math.ceil(sectionNumbers.length / 2);
    
    for (let row = 0; row < rows; row++) {
        const tr = document.createElement('tr');
        
        // Левый отсек
        const leftIndex = row * 2;
        if (leftIndex < sectionNumbers.length) {
            const leftSectionNum = sectionNumbers[leftIndex];
            const leftCell = createSectionCell(leftSectionNum, sections[leftSectionNum], animalsByPlace);
            tr.appendChild(leftCell);
        }
        
        // Правый отсек (если есть)
        const rightIndex = row * 2 + 1;
        if (rightIndex < sectionNumbers.length) {
            const rightSectionNum = sectionNumbers[rightIndex];
            const rightCell = createSectionCell(rightSectionNum, sections[rightSectionNum], animalsByPlace);
            tr.appendChild(rightCell);
        } else {
            // Если правого отсека нет, добавляем пустую ячейку для выравнивания
            const emptyCell = document.createElement('td');
            emptyCell.className = 'section-cell empty-placeholder';
            emptyCell.style.visibility = 'hidden';
            tr.appendChild(emptyCell);
        }
        
        table.appendChild(tr);
    }
    
    barnDiv.appendChild(table);
    return barnDiv;
}

// Создание ячейки отсека
function createSectionCell(sectionNumber, section, animalsByPlace) {
    const cell = document.createElement('td');
    cell.className = 'section-cell';
    
    // Отсек всегда существует (так как мы передаем только существующие)
    cell.innerHTML = `<div class="section-number">Отсек ${sectionNumber}</div>`;
    
    const animals = animalsByPlace[section.id];
    if (animals) {
        const animalsDiv = document.createElement('div');
        animalsDiv.className = 'animals-info';
        
        // Отображаем количество каждого типа животных
        if (animals.makers.length > 0) {
            const makersSpan = document.createElement('span');
            makersSpan.className = 'animal-count makers';
            makersSpan.textContent = `Производители: ${animals.makers.length}`;
            makersSpan.onclick = () => showAnimalsModal('Производители', animals.makers, section.name);
            animalsDiv.appendChild(makersSpan);
        }
        
        if (animals.rams.length > 0) {
            const ramsSpan = document.createElement('span');
            ramsSpan.className = 'animal-count rams';
            ramsSpan.textContent = `Бараны: ${animals.rams.length}`;
            ramsSpan.onclick = () => showAnimalsModal('Бараны', animals.rams, section.name);
            animalsDiv.appendChild(ramsSpan);
        }
        
        if (animals.ewes.length > 0) {
            const ewesSpan = document.createElement('span');
            ewesSpan.className = 'animal-count ewes';
            ewesSpan.textContent = `Ярки: ${animals.ewes.length}`;
            ewesSpan.onclick = () => showAnimalsModal('Ярки', animals.ewes, section.name);
            animalsDiv.appendChild(ewesSpan);
        }
        
        if (animals.sheep.length > 0) {
            const sheepSpan = document.createElement('span');
            sheepSpan.className = 'animal-count sheep';
            sheepSpan.textContent = `Овцы: ${animals.sheep.length}`;
            sheepSpan.onclick = () => showAnimalsModal('Овцы', animals.sheep, section.name);
            animalsDiv.appendChild(sheepSpan);
        }
        
        cell.appendChild(animalsDiv);
    } else {
        // Отсек пустой
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'empty-section';
        emptyDiv.textContent = 'Пусто';
        cell.appendChild(emptyDiv);
    }
    
    return cell;
}

// Показ модального окна с животными
function showAnimalsModal(animalType, animals, sectionName) {
    const modal = document.getElementById('animals-modal');
    const title = document.getElementById('modal-title');
    const list = document.getElementById('animals-list');
    
    title.textContent = `${animalType} в ${sectionName}`;
    
    list.innerHTML = '';
    animals.forEach(animal => {
        const animalDiv = document.createElement('div');
        animalDiv.className = 'animal-item';
        
        const tagNumber = animal.tag ? animal.tag.tag_number : 'Нет бирки';
        
        if (animal.tag && animal.tag.tag_number) {
            // Определяем тип животного для URL
            let animalTypeRoute = '';
            if (animalType === 'Производители') {
                animalTypeRoute = 'maker';
            } else if (animalType === 'Бараны') {
                animalTypeRoute = 'ram';
            } else if (animalType === 'Ярки') {
                animalTypeRoute = 'ewe';
            } else if (animalType === 'Овцы') {
                animalTypeRoute = 'sheep';
            }
            
            // Создаем кликабельную ссылку
            const link = document.createElement('a');
            link.href = `/animals/${animalTypeRoute}/${tagNumber}/info/`;
            link.textContent = tagNumber;
            link.className = 'animal-link';
            animalDiv.appendChild(link);
        } else {
            // Если нет бирки, показываем просто текст
            animalDiv.textContent = tagNumber;
        }
        
        list.appendChild(animalDiv);
    });
    
    modal.style.display = 'block';
}

// Закрытие модального окна
function closeAnimalsModal() {
    document.getElementById('animals-modal').style.display = 'none';
}

// Экспортируем функции для глобального доступа
window.closeAnimalsModal = closeAnimalsModal;