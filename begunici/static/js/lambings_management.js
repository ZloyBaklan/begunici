import { apiRequest, getApiErrorMessage, getCSRFToken } from "./utils.js";

// Глобальные переменные
let selectedMothers = new Set(); // Для хранения ID выбранных матерей
let selectedMothersData = new Map(); // Для хранения полной информации о выбранных матерях
let selectedFather = null;
let fatherDropdownOptions = new Map();
let kinshipFatherDropdownOptions = new Map();
let activeGroupsById = new Map();
let selectedGroupAddMothers = new Set();
let selectedGroupAddMothersData = new Map();
let currentPage = 1;
let groupsCurrentPage = 1;
const pageSize = 10;
let dateFrom = '';
let dateTo = '';
let plannedDateFrom = '';
let plannedDateTo = '';
let motherTagFilter = '';
let fatherTagFilter = '';
let groupDateFrom = '';
let groupDateTo = '';
let groupMotherTagFilter = '';
let groupFatherTagFilter = '';
const managementViewStorageKey = 'lambingsManagementView';

function getPlaceSortKey(placeName) {
    const numbers = String(placeName || '').match(/\d+/g) || [];
    return [
        numbers[0] ? Number(numbers[0]) : Number.MAX_SAFE_INTEGER,
        numbers[1] ? Number(numbers[1]) : Number.MAX_SAFE_INTEGER,
        String(placeName || '')
    ];
}

function sortPlacesBySheepfold(places) {
    return [...places].sort((left, right) => {
        const leftKey = getPlaceSortKey(left.sheepfold);
        const rightKey = getPlaceSortKey(right.sheepfold);

        if (leftKey[0] !== rightKey[0]) {
            return leftKey[0] - rightKey[0];
        }
        if (leftKey[1] !== rightKey[1]) {
            return leftKey[1] - rightKey[1];
        }
        return leftKey[2].localeCompare(rightKey[2], 'ru');
    });
}

function getSavedManagementView() {
    try {
        return localStorage.getItem(managementViewStorageKey) || 'groups';
    } catch (error) {
        return 'groups';
    }
}

function saveManagementView(view) {
    try {
        localStorage.setItem(managementViewStorageKey, view);
    } catch (error) {
        // Если localStorage недоступен, переключение все равно должно работать.
    }
}

function switchLambingManagementView(view) {
    const selectedView = view === 'lambings' ? 'lambings' : 'groups';
    const groupsSection = document.getElementById('groups-management-section');
    const lambingsSection = document.getElementById('lambings-management-section');
    const groupsButton = document.getElementById('groups-management-button');
    const lambingsButton = document.getElementById('lambings-management-button');

    if (groupsSection) {
        groupsSection.style.display = selectedView === 'groups' ? 'block' : 'none';
    }
    if (lambingsSection) {
        lambingsSection.style.display = selectedView === 'lambings' ? 'block' : 'none';
    }
    if (groupsButton) {
        groupsButton.classList.toggle('active', selectedView === 'groups');
        groupsButton.setAttribute('aria-pressed', selectedView === 'groups' ? 'true' : 'false');
    }
    if (lambingsButton) {
        lambingsButton.classList.toggle('active', selectedView === 'lambings');
        lambingsButton.setAttribute('aria-pressed', selectedView === 'lambings' ? 'true' : 'false');
    }

    saveManagementView(selectedView);
}

function getFatherDisplayName(animal) {
    if (!animal) {
        return '';
    }
    if (animal.display_name) {
        return animal.display_name;
    }
    if (animal.type_code === 'maker' && animal.name) {
        return `${animal.name}(${animal.tag_number})`;
    }
    return animal.tag_number || '';
}

function getFatherOptionLabel(animal) {
    const displayName = getFatherDisplayName(animal);
    const typeName = animal?.animal_type || (animal?.type_code === 'maker' ? 'Баран-Производитель' : 'Баранчик');
    const statusText = animal?.status ? ` - ${animal.status}` : '';
    return `${displayName} (${typeName})${statusText}`;
}

function setSelectedFatherFromAnimal(animal, options = {}) {
    if (!animal || !animal.tag_number) {
        selectedFather = null;
        const display = document.getElementById('selected-father-display');
        if (display) {
            display.textContent = 'Не выбран';
            display.className = 'mt-2 text-muted';
        }
        if (options.syncSelect !== false) {
            const select = document.getElementById('father-select');
            if (select) {
                select.value = '';
            }
        }
        checkAutoKinship();
        return;
    }

    selectedFather = {
        tag_number: animal.tag_number,
        type: animal.type_code,
        tag: animal.tag_number,
        display_name: getFatherDisplayName(animal)
    };

    const display = document.getElementById('selected-father-display');
    if (display) {
        const typeText = selectedFather.type === 'maker' ? 'Баран-Производитель' : 'Баранчик';
        display.textContent = `${selectedFather.display_name} (${typeText})`;
        display.className = 'mt-2 text-success';
    }

    if (options.syncSelect !== false) {
        const select = document.getElementById('father-select');
        if (select) {
            select.value = selectedFather.tag_number;
        }
    }

    checkAutoKinship();
}

function setSelectedKinshipFatherFromAnimal(animal, options = {}) {
    if (!animal || !animal.tag_number) {
        selectedKinshipFather = null;
        const display = document.getElementById('kinship-father-display');
        if (display) {
            display.textContent = 'Не выбран';
            display.className = 'mt-2 text-muted';
        }
        if (options.syncSelect !== false) {
            const select = document.getElementById('kinship-father-select');
            if (select) {
                select.value = '';
            }
        }
        updateKinshipCheckButton();
        resetKinshipResult();
        return;
    }

    selectedKinshipFather = {
        tag_number: animal.tag_number,
        type: animal.type_code,
        tag: animal.tag_number,
        display_name: getFatherDisplayName(animal)
    };

    const display = document.getElementById('kinship-father-display');
    if (display) {
        const typeText = selectedKinshipFather.type === 'maker' ? 'Баран-Производитель' : 'Баранчик';
        display.textContent = `${selectedKinshipFather.display_name} (${typeText})`;
        display.className = 'mt-2 text-success';
    }

    if (options.syncSelect !== false) {
        const select = document.getElementById('kinship-father-select');
        if (select) {
            select.value = selectedKinshipFather.tag_number;
        }
    }

    updateKinshipCheckButton();
    resetKinshipResult();
}

async function loadFatherSelectOptions() {
    const select = document.getElementById('father-select');
    if (!select) {
        return;
    }

    select.innerHTML = '<option value="">Загрузка производителей...</option>';
    select.disabled = true;
    fatherDropdownOptions = new Map();

    try {
        const fathers = await apiRequest('/animals/api/all-fathers/');
        select.innerHTML = '<option value="">Выберите производителя</option>';

        (fathers || []).filter(father => father.type_code === 'maker').forEach(father => {
            if (!father.tag_number) {
                return;
            }
            fatherDropdownOptions.set(father.tag_number, father);
            const option = document.createElement('option');
            option.value = father.tag_number;
            option.textContent = getFatherOptionLabel(father);
            select.appendChild(option);
        });

        if (!fatherDropdownOptions.size) {
            select.innerHTML = '<option value="">Нет свободных производителей</option>';
        }
    } catch (error) {
        console.error('Ошибка загрузки производителей:', error);
        select.innerHTML = '<option value="">Ошибка загрузки производителей</option>';
    } finally {
        select.disabled = !fatherDropdownOptions.size;
    }
}

async function loadKinshipFatherSelectOptions() {
    const select = document.getElementById('kinship-father-select');
    if (!select) {
        return;
    }

    select.innerHTML = '<option value="">Загрузка производителей...</option>';
    select.disabled = true;
    kinshipFatherDropdownOptions = new Map();

    try {
        const fathers = await apiRequest('/animals/api/all-fathers/?include_busy=1');
        select.innerHTML = '<option value="">Выберите производителя</option>';

        (fathers || []).filter(father => father.type_code === 'maker').forEach(father => {
            if (!father.tag_number) {
                return;
            }
            kinshipFatherDropdownOptions.set(father.tag_number, father);
            const option = document.createElement('option');
            option.value = father.tag_number;
            option.textContent = getFatherOptionLabel(father);
            select.appendChild(option);
        });

        if (!kinshipFatherDropdownOptions.size) {
            select.innerHTML = '<option value="">Производители не найдены</option>';
        }
    } catch (error) {
        console.error('Ошибка загрузки производителей для подбора пар:', error);
        select.innerHTML = '<option value="">Ошибка загрузки производителей</option>';
    } finally {
        select.disabled = !kinshipFatherDropdownOptions.size;
    }
}

async function loadGroupPlaceOptions() {
    const select = document.getElementById('group-place-select');
    if (!select) {
        return;
    }

    try {
        const response = await apiRequest('/veterinary/api/place/?page_size=500');
        const places = response.results || response || [];
        select.innerHTML = '<option value="">Без перемещения</option>';

        sortPlacesBySheepfold(places).forEach(place => {
            const option = document.createElement('option');
            option.value = place.id;
            option.textContent = place.sheepfold;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка загрузки овчарен для постановки в группу:', error);
        select.innerHTML = '<option value="">Не удалось загрузить овчарни</option>';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM загружен, инициализируем страницу управления окотами');
    switchLambingManagementView(getSavedManagementView());
    
    // Устанавливаем текущую дату как дату начала окота
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('lambing-start-date').value = today;
    
    // Восстанавливаем сохраненные значения фильтра дат
    if (window.lambingsDateFrom) {
        document.getElementById('date-from').value = window.lambingsDateFrom;
        dateFrom = window.lambingsDateFrom;
    }
    if (window.lambingsDateTo) {
        document.getElementById('date-to').value = window.lambingsDateTo;
        dateTo = window.lambingsDateTo;
    }
    if (window.lambingsPlannedDateFrom) {
        document.getElementById('planned-date-from').value = window.lambingsPlannedDateFrom;
        plannedDateFrom = window.lambingsPlannedDateFrom;
    }
    if (window.lambingsPlannedDateTo) {
        document.getElementById('planned-date-to').value = window.lambingsPlannedDateTo;
        plannedDateTo = window.lambingsPlannedDateTo;
    }
    if (window.lambingsMotherTagFilter) {
        document.getElementById('mother-tag-filter').value = window.lambingsMotherTagFilter;
        motherTagFilter = window.lambingsMotherTagFilter;
    }
    if (window.lambingsFatherTagFilter) {
        document.getElementById('father-tag-filter').value = window.lambingsFatherTagFilter;
        fatherTagFilter = window.lambingsFatherTagFilter;
    }
    if (window.groupDateFrom) {
        document.getElementById('group-date-from').value = window.groupDateFrom;
        groupDateFrom = window.groupDateFrom;
    }
    if (window.groupDateTo) {
        document.getElementById('group-date-to').value = window.groupDateTo;
        groupDateTo = window.groupDateTo;
    }
    if (window.groupMotherTagFilter) {
        document.getElementById('group-mother-tag-filter').value = window.groupMotherTagFilter;
        groupMotherTagFilter = window.groupMotherTagFilter;
    }
    if (window.groupFatherTagFilter) {
        document.getElementById('group-father-tag-filter').value = window.groupFatherTagFilter;
        groupFatherTagFilter = window.groupFatherTagFilter;
    }
    
    // Загружаем активные группы и случки
    loadActiveGroups();
    loadActiveLambings();
    loadFatherSelectOptions();
    loadKinshipFatherSelectOptions();
    loadGroupPlaceOptions();

    const fatherSelect = document.getElementById('father-select');
    if (fatherSelect) {
        fatherSelect.addEventListener('change', function() {
            const animal = fatherDropdownOptions.get(this.value);
            setSelectedFatherFromAnimal(animal, { syncSelect: false });
        });
    }

    const kinshipFatherSelect = document.getElementById('kinship-father-select');
    if (kinshipFatherSelect) {
        kinshipFatherSelect.addEventListener('change', function() {
            const animal = kinshipFatherDropdownOptions.get(this.value);
            setSelectedKinshipFatherFromAnimal(animal, { syncSelect: false });
        });
    }
    
    // Обработчики поиска для модальных окон
    const searchMothersBtn = document.getElementById('searchMothersBtn');
    if (searchMothersBtn) {
        searchMothersBtn.addEventListener('click', searchMothers);
    }
    
    const mothersSearchInput = document.getElementById('mothersSearch');
    if (mothersSearchInput) {
        mothersSearchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchMothers();
            }
        });
    }

    const searchGroupAddMothersBtn = document.getElementById('searchGroupAddMothersBtn');
    if (searchGroupAddMothersBtn) {
        searchGroupAddMothersBtn.addEventListener('click', searchGroupAddMothers);
    }

    const groupAddMothersSearchInput = document.getElementById('groupAddMothersSearch');
    if (groupAddMothersSearchInput) {
        groupAddMothersSearchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchGroupAddMothers();
            }
        });
    }
    
    const searchFathersBtn = document.getElementById('searchFathersBtn');
    if (searchFathersBtn) {
        searchFathersBtn.addEventListener('click', searchFathers);
    }
    
    const fathersSearchInput = document.getElementById('fathersSearch');
    if (fathersSearchInput) {
        fathersSearchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchFathers();
            }
        });
    }
    
    // Обработчики для проверки родства
    const searchKinshipFathersBtn = document.getElementById('searchKinshipFathersBtn');
    if (searchKinshipFathersBtn) {
        searchKinshipFathersBtn.addEventListener('click', searchKinshipFathers);
    }
    
    const kinshipFathersSearchInput = document.getElementById('kinshipFathersSearch');
    if (kinshipFathersSearchInput) {
        kinshipFathersSearchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchKinshipFathers();
            }
        });
    }
    
    const searchKinshipMothersBtn = document.getElementById('searchKinshipMothersBtn');
    if (searchKinshipMothersBtn) {
        searchKinshipMothersBtn.addEventListener('click', searchKinshipMothers);
    }
    
    const kinshipMothersSearchInput = document.getElementById('kinshipMothersSearch');
    if (kinshipMothersSearchInput) {
        kinshipMothersSearchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchKinshipMothers();
            }
        });
    }
    
    // Обработчик изменения количества ягнят
    document.addEventListener('change', function(e) {
        if (e.target && e.target.id === 'lambs-count') {
            if (isEarlyFailureMode()) {
                return;
            }
            const count = parseInt(e.target.value) || 0;
            generateLambForms(count);
        }
        if (e.target && e.target.id === 'early-failure-checkbox') {
            setCompletionMode(e.target.checked ? 'early_failure' : 'normal');
        }
        if (e.target && e.target.id === 'unsuccessful-insemination-checkbox') {
            setCompletionMode(e.target.checked ? 'unsuccessful_insemination' : 'normal');
        }
    });
});

// Загрузка активных групп
async function loadActiveGroups() {
    try {
        let url = `/animals/lambing-group/?is_active=true&page=${groupsCurrentPage}&page_size=${pageSize}`;

        if (groupDateFrom) {
            url += `&placement_date_from=${groupDateFrom}`;
        }
        if (groupDateTo) {
            url += `&placement_date_to=${groupDateTo}`;
        }
        if (groupMotherTagFilter) {
            url += `&mother_tag=${encodeURIComponent(groupMotherTagFilter)}`;
        }
        if (groupFatherTagFilter) {
            url += `&father_tag=${encodeURIComponent(groupFatherTagFilter)}`;
        }

        const response = await apiRequest(url);
        const groups = response.results || response;
        const tableBody = document.getElementById('active-groups-table');
        tableBody.innerHTML = '';
        activeGroupsById = new Map();
        groups.forEach(group => {
            activeGroupsById.set(Number(group.id), group);
        });

        if (groups.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Нет активных групп</td></tr>';
        } else {
            groups.forEach(group => {
                tableBody.appendChild(createGroupRow(group));
            });
        }

        updateGroupsPagination(response);
    } catch (error) {
        console.error('Ошибка загрузки групп:', error);
        document.getElementById('active-groups-table').innerHTML =
            '<tr><td colspan="5" class="text-center text-danger">Ошибка загрузки групп: ' + error.message + '</td></tr>';
    }
}

function createGroupRow(group) {
    const row = document.createElement('tr');
    const mothers = Array.isArray(group.mothers) ? group.mothers : [];
    const motherLinks = mothers.length
        ? mothers.map(mother => createAnimalLink(mother.tag_number, mother.animal_type, true)).join('<br>')
        : '-';
    const fatherTag = group.father_tag || 'Неизвестно';
    const fatherType = group.father_type || 'Неизвестно';
    const fatherDisplayName = group.father_display_name || fatherTag;
    const fatherLink = createAnimalLink(fatherTag, fatherType, true, fatherDisplayName);
    const placementDate = group.placement_date ? new Date(group.placement_date).toLocaleDateString('ru-RU') : '-';
    const note = group.note || '';

    row.innerHTML = `
        <td>${motherLinks}</td>
        <td>${fatherLink}</td>
        <td>${placementDate}</td>
        <td>${note}</td>
        <td>
            <div class="d-flex flex-column gap-1">
                <button class="btn btn-success btn-sm" onclick="showRemoveFatherModal(${group.id})">
                    Снять барана
                </button>
                <button class="btn btn-outline-primary btn-sm" onclick="showAddMothersToGroupModal(${group.id})">
                    Добавить ярку/овцематку
                </button>
                <button class="btn btn-outline-danger btn-sm" onclick="showRemoveMothersFromGroupModal(${group.id})">
                    Убрать ярку/овцематку
                </button>
            </div>
        </td>
    `;

    return row;
}

function updateGroupsPagination(response) {
    const paginationList = document.getElementById('groups-pagination-list');
    const paginationInfo = document.getElementById('groups-pagination-info');

    paginationList.innerHTML = '';
    paginationInfo.innerHTML = '';

    if (!response.count) {
        return;
    }

    const totalPages = Math.ceil(response.count / pageSize);
    const currentPageNum = groupsCurrentPage;

    if (response.previous) {
        const prevItem = document.createElement('li');
        prevItem.className = 'page-item';
        prevItem.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="changeGroupsPage(${currentPageNum - 1})">‹</a>`;
        paginationList.appendChild(prevItem);
    }

    const startPage = Math.max(1, currentPageNum - 2);
    const endPage = Math.min(totalPages, currentPageNum + 2);

    if (startPage > 1) {
        const firstItem = document.createElement('li');
        firstItem.className = 'page-item';
        firstItem.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="changeGroupsPage(1)">1</a>`;
        paginationList.appendChild(firstItem);
        if (startPage > 2) {
            const dotsItem = document.createElement('li');
            dotsItem.className = 'page-item disabled';
            dotsItem.innerHTML = `<span class="page-link">...</span>`;
            paginationList.appendChild(dotsItem);
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        const pageItem = document.createElement('li');
        pageItem.className = `page-item ${i === currentPageNum ? 'active' : ''}`;
        pageItem.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="changeGroupsPage(${i})">${i}</a>`;
        paginationList.appendChild(pageItem);
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const dotsItem = document.createElement('li');
            dotsItem.className = 'page-item disabled';
            dotsItem.innerHTML = `<span class="page-link">...</span>`;
            paginationList.appendChild(dotsItem);
        }

        const lastItem = document.createElement('li');
        lastItem.className = 'page-item';
        lastItem.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="changeGroupsPage(${totalPages})">${totalPages}</a>`;
        paginationList.appendChild(lastItem);
    }

    if (response.next) {
        const nextItem = document.createElement('li');
        nextItem.className = 'page-item';
        nextItem.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="changeGroupsPage(${currentPageNum + 1})">›</a>`;
        paginationList.appendChild(nextItem);
    }

    const startItem = (currentPageNum - 1) * pageSize + 1;
    const endItem = Math.min(currentPageNum * pageSize, response.count);
    paginationInfo.innerHTML = `Показано ${startItem}-${endItem} из ${response.count} групп`;
}

function changeGroupsPage(page) {
    groupsCurrentPage = page;
    loadActiveGroups();
}

function applyGroupFilter() {
    groupDateFrom = document.getElementById('group-date-from').value;
    groupDateTo = document.getElementById('group-date-to').value;
    groupMotherTagFilter = document.getElementById('group-mother-tag-filter').value.trim();
    groupFatherTagFilter = document.getElementById('group-father-tag-filter').value.trim();

    window.groupDateFrom = groupDateFrom;
    window.groupDateTo = groupDateTo;
    window.groupMotherTagFilter = groupMotherTagFilter;
    window.groupFatherTagFilter = groupFatherTagFilter;

    groupsCurrentPage = 1;
    loadActiveGroups();
}

function clearGroupFilter() {
    document.getElementById('group-date-from').value = '';
    document.getElementById('group-date-to').value = '';
    document.getElementById('group-mother-tag-filter').value = '';
    document.getElementById('group-father-tag-filter').value = '';

    window.groupDateFrom = '';
    window.groupDateTo = '';
    window.groupMotherTagFilter = '';
    window.groupFatherTagFilter = '';

    groupDateFrom = '';
    groupDateTo = '';
    groupMotherTagFilter = '';
    groupFatherTagFilter = '';
    groupsCurrentPage = 1;
    loadActiveGroups();
}

function exportGroupsToExcel() {
    const params = new URLSearchParams();
    params.set('is_active', 'true');

    if (groupDateFrom) {
        params.set('placement_date_from', groupDateFrom);
    }
    if (groupDateTo) {
        params.set('placement_date_to', groupDateTo);
    }
    if (groupMotherTagFilter) {
        params.set('mother_tag', groupMotherTagFilter);
    }
    if (groupFatherTagFilter) {
        params.set('father_tag', groupFatherTagFilter);
    }

    window.location.href = `/animals/api/lambing-groups/export-excel/?${params.toString()}`;
}

function showRemoveFatherModal(groupId) {
    window.currentGroupId = groupId;
    document.getElementById('removing-group-id').value = groupId;
    document.getElementById('group-removal-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('group-removal-note').value = '';

    const modal = new bootstrap.Modal(document.getElementById('removeFatherModal'));
    modal.show();
}

async function confirmRemoveFather() {
    const groupId = window.currentGroupId || document.getElementById('removing-group-id').value;
    const removalDate = document.getElementById('group-removal-date').value;
    const note = document.getElementById('group-removal-note').value.trim();

    if (!groupId) {
        alert('Не выбрана группа');
        return;
    }
    if (!removalDate) {
        alert('Укажите дату снятия барана');
        return;
    }

    try {
        const response = await apiRequest(`/animals/lambing-group/${groupId}/remove-father/`, 'POST', {
            removal_date: removalDate,
            note: note || ''
        });

        alert(`Баран снят. Создано случек: ${response.created_lambings_count || 0}`);
        const modal = bootstrap.Modal.getInstance(document.getElementById('removeFatherModal'));
        modal.hide();

        loadActiveGroups();
        loadActiveLambings();
    } catch (error) {
        console.error('Ошибка снятия барана:', error);
        alert('Ошибка при снятии барана: ' + (error.message || 'Неизвестная ошибка'));
    }
}

function resetGroupAddMothersSelection() {
    selectedGroupAddMothers.clear();
    selectedGroupAddMothersData.clear();
    updateGroupAddMothersDisplay();
}

function updateGroupAddMothersDisplay() {
    const display = document.getElementById('selected-group-add-mothers-display');
    if (!display) {
        return;
    }

    const selectedMothersArray = Array.from(selectedGroupAddMothersData.values());
    if (selectedMothersArray.length === 0) {
        display.textContent = 'Не выбрано';
        display.className = 'mt-2 text-muted';
    } else {
        display.textContent = `Выбрано: ${selectedMothersArray.length} (${selectedMothersArray.map(m => m.tag).join(', ')})`;
        display.className = 'mt-2 text-success';
    }
}

function saveSelectedGroupAddMothers() {
    const checkboxes = document.querySelectorAll('.group-add-mother-checkbox');
    checkboxes.forEach(checkbox => {
        const tagNumber = checkbox.value;
        if (checkbox.checked) {
            selectedGroupAddMothers.add(tagNumber);
            selectedGroupAddMothersData.set(tagNumber, {
                tag_number: tagNumber,
                type: checkbox.dataset.type,
                tag: checkbox.dataset.tag
            });
        } else {
            selectedGroupAddMothers.delete(tagNumber);
            selectedGroupAddMothersData.delete(tagNumber);
        }
    });
    updateGroupAddMothersDisplay();
}

function restoreSelectedGroupAddMothers() {
    const checkboxes = document.querySelectorAll('.group-add-mother-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectedGroupAddMothers.has(checkbox.value);
    });
}

function createGroupAddMotherItem(animal) {
    const item = document.createElement('div');
    item.className = 'form-check mb-2';

    item.innerHTML = `
        <input class="form-check-input group-add-mother-checkbox" type="checkbox"
               value="${animal.tag_number}" data-type="${animal.type_code}" data-tag="${animal.tag_number}">
        <label class="form-check-label">
            ${animal.tag_number} (${animal.animal_type}) - ${animal.status}
        </label>
    `;

    return item;
}

function showAddMothersToGroupModal(groupId) {
    window.currentEditGroupId = groupId;
    resetGroupAddMothersSelection();
    document.getElementById('adding-mothers-group-id').value = groupId;
    document.getElementById('groupAddMothersSearch').value = '';
    document.getElementById('group-add-mothers-list').innerHTML = `
        <div class="text-muted text-center py-3">
            Введите бирку или РСХН и нажмите "Поиск" для отображения доступных ярок/овцематок
        </div>
    `;

    const modal = new bootstrap.Modal(document.getElementById('addMothersToGroupModal'));
    modal.show();
}

async function searchGroupAddMothers() {
    const search = document.getElementById('groupAddMothersSearch').value.trim();

    if (!search) {
        document.getElementById('group-add-mothers-list').innerHTML = `
            <div class="text-muted text-center py-3">
                Введите бирку или РСХН для поиска
            </div>
        `;
        return;
    }

    saveSelectedGroupAddMothers();
    document.getElementById('group-add-mothers-list').innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Поиск...</span>
            </div>
            <div class="mt-2">Поиск доступных ярок/овцематок...</div>
        </div>
    `;

    try {
        const response = await apiRequest(`/animals/api/inactive-mothers/?search=${encodeURIComponent(search)}`);
        const mothers = response || [];
        const mothersList = document.getElementById('group-add-mothers-list');
        mothersList.innerHTML = '';

        const limitedMothers = mothers.slice(0, 50);
        if (limitedMothers.length === 0) {
            mothersList.innerHTML = '<div class="text-center text-muted">Доступные ярки/овцематки не найдены</div>';
            return;
        }

        const ewes = limitedMothers.filter(m => m.type_code === 'ewe');
        const sheep = limitedMothers.filter(m => m.type_code === 'sheep');

        if (ewes.length > 0) {
            const eweHeader = document.createElement('h6');
            eweHeader.textContent = 'Ярки';
            eweHeader.className = 'mt-3 mb-2 text-primary';
            mothersList.appendChild(eweHeader);

            ewes.forEach(ewe => {
                mothersList.appendChild(createGroupAddMotherItem(ewe));
            });
        }

        if (sheep.length > 0) {
            const sheepHeader = document.createElement('h6');
            sheepHeader.textContent = 'Овцематки';
            sheepHeader.className = 'mt-3 mb-2 text-primary';
            mothersList.appendChild(sheepHeader);

            sheep.forEach(sheepAnimal => {
                mothersList.appendChild(createGroupAddMotherItem(sheepAnimal));
            });
        }

        if (mothers.length > 50) {
            const info = document.createElement('div');
            info.className = 'text-muted text-center mt-2 small';
            info.textContent = `Показано первых 50 из ${mothers.length} результатов`;
            mothersList.appendChild(info);
        }

        restoreSelectedGroupAddMothers();
    } catch (error) {
        console.error('Ошибка поиска матерей для добавления в группу:', error);
        document.getElementById('group-add-mothers-list').innerHTML = `
            <div class="text-danger text-center py-3">
                Ошибка поиска
            </div>
        `;
    }
}

async function confirmAddMothersToGroup() {
    const groupId = window.currentEditGroupId || document.getElementById('adding-mothers-group-id').value;
    saveSelectedGroupAddMothers();
    const selectedMothersArray = Array.from(selectedGroupAddMothersData.values());

    if (!groupId) {
        alert('Не выбрана группа');
        return;
    }

    if (selectedMothersArray.length === 0) {
        alert('Выберите хотя бы одну ярку/овцематку');
        return;
    }

    try {
        const response = await apiRequest(`/animals/lambing-group/${groupId}/add-mothers/`, 'POST', {
            mother_tag_numbers: selectedMothersArray.map(m => m.tag_number)
        });

        alert(`Матери добавлены в группу: ${response.added_count || 0}`);
        const modal = bootstrap.Modal.getInstance(document.getElementById('addMothersToGroupModal'));
        modal.hide();
        resetGroupAddMothersSelection();

        loadActiveGroups();
    } catch (error) {
        console.error('Ошибка добавления матерей в группу:', error);
        alert('Ошибка при добавлении матерей в группу: ' + (error.message || 'Неизвестная ошибка'));
    }
}

function createRemoveGroupMotherItem(mother) {
    const item = document.createElement('div');
    item.className = 'form-check mb-2';

    item.innerHTML = `
        <input class="form-check-input group-remove-mother-checkbox" type="checkbox"
               value="${mother.tag_number}" data-type="${mother.type_code}">
        <label class="form-check-label">
            ${mother.tag_number} (${mother.animal_type})
        </label>
    `;

    return item;
}

function showRemoveMothersFromGroupModal(groupId) {
    window.currentEditGroupId = groupId;
    document.getElementById('removing-mothers-group-id').value = groupId;

    const group = activeGroupsById.get(Number(groupId));
    const mothers = group && Array.isArray(group.mothers) ? group.mothers : [];
    const list = document.getElementById('group-remove-mothers-list');
    list.innerHTML = '';

    if (mothers.length === 0) {
        list.innerHTML = '<div class="text-center text-muted">В группе нет матерей</div>';
    } else {
        mothers.forEach(mother => {
            list.appendChild(createRemoveGroupMotherItem(mother));
        });
    }

    const modal = new bootstrap.Modal(document.getElementById('removeMothersFromGroupModal'));
    modal.show();
}

async function confirmRemoveMothersFromGroup() {
    const groupId = window.currentEditGroupId || document.getElementById('removing-mothers-group-id').value;
    const selectedTags = Array.from(document.querySelectorAll('.group-remove-mother-checkbox:checked'))
        .map(checkbox => checkbox.value);

    if (!groupId) {
        alert('Не выбрана группа');
        return;
    }

    if (selectedTags.length === 0) {
        alert('Выберите хотя бы одну ярку/овцематку');
        return;
    }

    try {
        const response = await apiRequest(`/animals/lambing-group/${groupId}/remove-mothers/`, 'POST', {
            mother_tag_numbers: selectedTags
        });

        alert(`Матери убраны из группы: ${response.removed_count || 0}`);
        const modal = bootstrap.Modal.getInstance(document.getElementById('removeMothersFromGroupModal'));
        modal.hide();

        loadActiveGroups();
    } catch (error) {
        console.error('Ошибка удаления матерей из группы:', error);
        alert('Ошибка при удалении матерей из группы: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Загрузка активных случек
async function loadActiveLambings() {
    try {
        console.log('Загружаем активные случки, страница:', currentPage);
        
        // Строим URL с параметрами фильтрации
        let url = `/animals/lambing/?is_active=true&page=${currentPage}&page_size=${pageSize}&ordering=planned_lambing_date`;
        
        if (dateFrom) {
            url += `&start_date_from=${dateFrom}`;
        }
        if (dateTo) {
            url += `&start_date_to=${dateTo}`;
        }
        if (plannedDateFrom) {
            url += `&planned_date_from=${plannedDateFrom}`;
        }
        if (plannedDateTo) {
            url += `&planned_date_to=${plannedDateTo}`;
        }
        if (motherTagFilter) {
            url += `&mother_tag=${encodeURIComponent(motherTagFilter)}`;
        }
        if (fatherTagFilter) {
            url += `&father_tag=${encodeURIComponent(fatherTagFilter)}`;
        }
        
        const response = await apiRequest(url);
        console.log('Ответ API:', response);
        
        const lambings = response.results || response;
        
        const tableBody = document.getElementById('active-lambings-table');
        tableBody.innerHTML = '';
        
        if (lambings.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Нет активных случек</td></tr>';
        } else {
            lambings.forEach(lambing => {
                const row = createLambingRow(lambing);
                tableBody.appendChild(row);
            });
        }
        
        // Обновляем пагинацию
        updatePagination(response);
        
    } catch (error) {
        console.error('Ошибка загрузки активных случек:', error);
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
    const fatherDisplayName = lambing.father_display_name || fatherTag; // Используем display_name для отображения
    const motherType = lambing.mother_type || 'Неизвестно';
    const fatherType = lambing.father_type || 'Неизвестно';
    const motherFound = lambing.mother_found !== undefined ? lambing.mother_found : true; // По умолчанию считаем найденной
    const note = lambing.note || '';
    
    // Создаем ссылки на животных
    const motherLink = createAnimalLink(motherTag, motherType, motherFound);
    const fatherLink = createAnimalLink(fatherTag, fatherType, true, fatherDisplayName); // Передаем display_name
    
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
                Окот
            </button>
        </td>
    `;
    
    return row;
}

// Создание ссылки на животное
function createAnimalLink(tagNumber, animalType, isFound = true, displayName = null) {
    if (tagNumber === 'Неизвестно' || animalType === 'Неизвестно') {
        return `${tagNumber} (${animalType})`;
    }

    const typeLabelMap = {
        'Производитель': 'Баран-Производитель',
        'Баран-Производитель': 'Баран-Производитель',
        'Баран': 'Баранчик',
        'Баранчик': 'Баранчик',
        'Ярка': 'Ярка',
        'Овца': 'Овцематка',
        'Овцематка': 'Овцематка',
    };
    const displayType = typeLabelMap[animalType] || animalType;
    
    // Если животное не найдено в БД, показываем без ссылки
    if (!isFound) {
        return `${displayName || tagNumber} (${displayType}) (не найдена)`;
    }
    
    // Определяем URL в зависимости от типа животного
    let url = '#';
    switch (animalType) {
        case 'Производитель':
        case 'Баран-Производитель':
            url = `/animals/maker/${tagNumber}/info/`;
            break;
        case 'Баран':
        case 'Баранчик':
            url = `/animals/ram/${tagNumber}/info/`;
            break;
        case 'Ярка':
            url = `/animals/ewe/${tagNumber}/info/`;
            break;
        case 'Овца':
        case 'Овцематка':
            url = `/animals/sheep/${tagNumber}/info/`;
            break;
    }
    
    // Используем displayName если передан, иначе tagNumber
    const linkText = displayName || tagNumber;
    
    return `<a href="${url}" style="color: #007bff; text-decoration: underline; font-weight: bold;">${linkText}</a> (${displayType})`;
}

// Обновление пагинации
function updatePagination(response) {
    const paginationList = document.getElementById('pagination-list');
    const paginationInfo = document.getElementById('pagination-info');
    
    paginationList.innerHTML = '';
    paginationInfo.innerHTML = '';

    if (!response.count) {
        return;
    }

    const totalPages = Math.ceil(response.count / pageSize);
    const currentPageNum = currentPage;

    // Кнопка "Предыдущая"
    if (response.previous) {
        const prevItem = document.createElement('li');
        prevItem.className = 'page-item';
        prevItem.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="changePage(${currentPageNum - 1})">‹</a>`;
        paginationList.appendChild(prevItem);
    }

    // Номера страниц
    const startPage = Math.max(1, currentPageNum - 2);
    const endPage = Math.min(totalPages, currentPageNum + 2);

    // Показываем первую страницу и многоточие, если нужно
    if (startPage > 1) {
        const firstItem = document.createElement('li');
        firstItem.className = 'page-item';
        firstItem.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="changePage(1)">1</a>`;
        paginationList.appendChild(firstItem);
        
        if (startPage > 2) {
            const dotsItem = document.createElement('li');
            dotsItem.className = 'page-item disabled';
            dotsItem.innerHTML = `<span class="page-link">...</span>`;
            paginationList.appendChild(dotsItem);
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        const pageItem = document.createElement('li');
        pageItem.className = `page-item ${i === currentPageNum ? 'active' : ''}`;
        pageItem.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="changePage(${i})">${i}</a>`;
        paginationList.appendChild(pageItem);
    }

    // Показываем многоточие и последнюю страницу, если нужно
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const dotsItem = document.createElement('li');
            dotsItem.className = 'page-item disabled';
            dotsItem.innerHTML = `<span class="page-link">...</span>`;
            paginationList.appendChild(dotsItem);
        }
        
        const lastItem = document.createElement('li');
        lastItem.className = 'page-item';
        lastItem.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="changePage(${totalPages})">${totalPages}</a>`;
        paginationList.appendChild(lastItem);
    }

    // Кнопка "Следующая"
    if (response.next) {
        const nextItem = document.createElement('li');
        nextItem.className = 'page-item';
        nextItem.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="changePage(${currentPageNum + 1})">›</a>`;
        paginationList.appendChild(nextItem);
    }

    // Информация о странице
    const startItem = (currentPageNum - 1) * pageSize + 1;
    const endItem = Math.min(currentPageNum * pageSize, response.count);
    paginationInfo.innerHTML = `Показано ${startItem}-${endItem} из ${response.count} случек`;
}

// Смена страницы
function changePage(page) {
    currentPage = page;
    loadActiveLambings();
}

// Применить фильтр по датам
function applyDateFilter() {
    dateFrom = document.getElementById('date-from').value;
    dateTo = document.getElementById('date-to').value;
    plannedDateFrom = document.getElementById('planned-date-from').value;
    plannedDateTo = document.getElementById('planned-date-to').value;
    motherTagFilter = document.getElementById('mother-tag-filter').value.trim();
    fatherTagFilter = document.getElementById('father-tag-filter').value.trim();
    
    // Сохраняем значения в глобальных переменных
    window.lambingsDateFrom = dateFrom;
    window.lambingsDateTo = dateTo;
    window.lambingsPlannedDateFrom = plannedDateFrom;
    window.lambingsPlannedDateTo = plannedDateTo;
    window.lambingsMotherTagFilter = motherTagFilter;
    window.lambingsFatherTagFilter = fatherTagFilter;
    
    currentPage = 1; // Сбрасываем на первую страницу
    loadActiveLambings();
}

// Сбросить фильтр по датам
function clearDateFilter() {
    document.getElementById('date-from').value = '';
    document.getElementById('date-to').value = '';
    document.getElementById('planned-date-from').value = '';
    document.getElementById('planned-date-to').value = '';
    document.getElementById('mother-tag-filter').value = '';
    document.getElementById('father-tag-filter').value = '';
    
    // Очищаем глобальные переменные
    window.lambingsDateFrom = '';
    window.lambingsDateTo = '';
    window.lambingsPlannedDateFrom = '';
    window.lambingsPlannedDateTo = '';
    window.lambingsMotherTagFilter = '';
    window.lambingsFatherTagFilter = '';
    
    dateFrom = '';
    dateTo = '';
    plannedDateFrom = '';
    plannedDateTo = '';
    motherTagFilter = '';
    fatherTagFilter = '';
    currentPage = 1;
    loadActiveLambings();
}

function exportLambingsToExcel() {
    const params = new URLSearchParams();
    params.set('is_active', 'true');

    if (dateFrom) {
        params.set('start_date_from', dateFrom);
    }
    if (dateTo) {
        params.set('start_date_to', dateTo);
    }
    if (plannedDateFrom) {
        params.set('planned_date_from', plannedDateFrom);
    }
    if (plannedDateTo) {
        params.set('planned_date_to', plannedDateTo);
    }
    if (motherTagFilter) {
        params.set('mother_tag', motherTagFilter);
    }
    if (fatherTagFilter) {
        params.set('father_tag', fatherTagFilter);
    }

    window.location.href = `/animals/api/lambings/export-excel/?${params.toString()}`;
}

// Показать модальное окно выбора матерей
async function showSelectMothersModal() {
    document.getElementById('mothersSearch').value = '';
    document.getElementById('mothers-list').innerHTML = `
        <div class="text-muted text-center py-3">
            Введите бирку или РСХН и нажмите "Поиск" для отображения результатов
        </div>
    `;
    
    // Показываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('selectMothersModal'));
    modal.show();
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
    // Сохраняем текущие выбранные чекбоксы
    saveSelectedMothers();
    
    // Создаем массив из всех выбранных животных
    const selectedMothersArray = Array.from(selectedMothersData.values());
    
    // Обновляем отображение
    const display = document.getElementById('selected-mothers-display');
    if (selectedMothersArray.length === 0) {
        display.textContent = 'Не выбрано';
        display.className = 'mt-2 text-muted';
    } else {
        display.textContent = `Выбрано: ${selectedMothersArray.length} животных (${selectedMothersArray.map(m => m.tag).join(', ')})`;
        display.className = 'mt-2 text-success';
    }
    
    // Сохраняем массив для использования в других функциях
    window.selectedMothersForLambing = selectedMothersArray;
    
    // Закрываем модальное окно
    const modal = bootstrap.Modal.getInstance(document.getElementById('selectMothersModal'));
    modal.hide();
    
    // Запускаем автоматическую проверку родства
    checkAutoKinship();
}

// Показать модальное окно выбора отца
async function showSelectFatherModal() {
    // Очищаем поле поиска и результаты
    document.getElementById('fathersSearch').value = '';
    document.getElementById('fathers-list').innerHTML = `
        <div class="text-muted text-center py-3">
            Введите бирку или РСХН и нажмите "Поиск" для отображения результатов
        </div>
    `;
    
    // Показываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('selectFatherModal'));
    modal.show();
}

async function searchMothers() {
    const search = document.getElementById('mothersSearch').value.trim();
    
    if (!search) {
        document.getElementById('mothers-list').innerHTML = `
            <div class="text-muted text-center py-3">
                Введите бирку или РСХН для поиска
            </div>
        `;
        return;
    }
    
    // Сохраняем текущие выбранные чекбоксы
    saveSelectedMothers();
    
    // Показываем индикатор загрузки
    document.getElementById('mothers-list').innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Поиск...</span>
            </div>
            <div class="mt-2">Поиск ярок/овцематок...</div>
        </div>
    `;
    
    try {
        // Загружаем неактивных матерей с поиском
        const response = await apiRequest(`/animals/api/inactive-mothers/?search=${encodeURIComponent(search)}`);
        const mothers = response || [];
        
        const mothersList = document.getElementById('mothers-list');
        mothersList.innerHTML = '';
        
        // Ограничиваем до 50 результатов
        const limitedMothers = mothers.slice(0, 50);
        
        if (limitedMothers.length === 0) {
            mothersList.innerHTML = '<div class="text-center text-muted">Ярки/овцематки не найдены</div>';
        } else {
            // Группируем по типу - сначала ярки, потом овцематки
            const ewes = limitedMothers.filter(m => m.type_code === 'ewe');
            const sheep = limitedMothers.filter(m => m.type_code === 'sheep');
            
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
            
            // Добавляем овцематок
            if (sheep.length > 0) {
                const sheepHeader = document.createElement('h6');
                sheepHeader.textContent = 'Овцематки';
                sheepHeader.className = 'mt-3 mb-2 text-primary';
                mothersList.appendChild(sheepHeader);
                
                sheep.forEach(sheepAnimal => {
                    const item = createMotherItem(sheepAnimal);
                    mothersList.appendChild(item);
                });
            }
            
            // Показываем информацию о количестве результатов
            if (mothers.length > 50) {
                const info = document.createElement('div');
                info.className = 'text-muted text-center mt-2 small';
                info.textContent = `Показано первых 50 из ${mothers.length} результатов`;
                mothersList.appendChild(info);
            }
            
            // Восстанавливаем выбранные чекбоксы
            restoreSelectedMothers();
        }
    } catch (error) {
        console.error('Ошибка поиска матерей:', error);
        document.getElementById('mothers-list').innerHTML = `
            <div class="text-danger text-center py-3">
                Ошибка поиска
            </div>
        `;
    }
}

// Функция для сохранения выбранных матерей
function saveSelectedMothers() {
    const checkboxes = document.querySelectorAll('.mother-checkbox');
    checkboxes.forEach(checkbox => {
        const tagNumber = checkbox.value;
        if (checkbox.checked) {
            selectedMothers.add(tagNumber);
            // Сохраняем полную информацию о животном
            selectedMothersData.set(tagNumber, {
                tag_number: tagNumber,
                type: checkbox.dataset.type,
                tag: checkbox.dataset.tag
            });
        } else {
            // Если чекбокс снят, удаляем из обеих структур
            selectedMothers.delete(tagNumber);
            selectedMothersData.delete(tagNumber);
        }
    });
}

// Функция для восстановления выбранных матерей
function restoreSelectedMothers() {
    const checkboxes = document.querySelectorAll('.mother-checkbox');
    checkboxes.forEach(checkbox => {
        if (selectedMothers.has(checkbox.value)) {
            checkbox.checked = true;
        }
    });
}

async function searchFathers() {
    const search = document.getElementById('fathersSearch').value.trim();
    
    if (!search) {
        document.getElementById('fathers-list').innerHTML = `
            <div class="text-muted text-center py-3">
                Введите бирку или РСХН для поиска
            </div>
        `;
        return;
    }
    
    // Показываем индикатор загрузки
    document.getElementById('fathers-list').innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Поиск...</span>
            </div>
            <div class="mt-2">Поиск баранов-производителей/баранчиков...</div>
        </div>
    `;
    
    try {
        // Загружаем всех отцов с поиском
        const response = await apiRequest(`/animals/api/all-fathers/?search=${encodeURIComponent(search)}`);
        const fathers = response || [];
        
        const fathersList = document.getElementById('fathers-list');
        fathersList.innerHTML = '';
        
        // Ограничиваем до 50 результатов
        const limitedFathers = fathers.slice(0, 50);
        
        if (limitedFathers.length === 0) {
            fathersList.innerHTML = '<div class="text-center text-muted">Бараны-Производители/баранчики не найдены</div>';
        } else {
            // Группируем по типу - сначала бараны-производители, потом баранчики
            const makers = limitedFathers.filter(f => f.type_code === 'maker');
            const rams = limitedFathers.filter(f => f.type_code === 'ram');
            
            // Добавляем баранов-производителей
            if (makers.length > 0) {
                const makerHeader = document.createElement('h6');
                makerHeader.textContent = 'Бараны-Производители';
                makerHeader.className = 'mt-3 mb-2 text-primary';
                fathersList.appendChild(makerHeader);
                
                makers.forEach(maker => {
                    const item = createFatherItem(maker);
                    fathersList.appendChild(item);
                });
            }
            
            // Добавляем баранчиков
            if (rams.length > 0) {
                const ramHeader = document.createElement('h6');
                ramHeader.textContent = 'Баранчики';
                ramHeader.className = 'mt-3 mb-2 text-primary';
                fathersList.appendChild(ramHeader);
                
                rams.forEach(ram => {
                    const item = createFatherItem(ram);
                    fathersList.appendChild(item);
                });
            }
            
            // Показываем информацию о количестве результатов
            if (fathers.length > 50) {
                const info = document.createElement('div');
                info.className = 'text-muted text-center mt-2 small';
                info.textContent = `Показано первых 50 из ${fathers.length} результатов`;
                fathersList.appendChild(info);
            }
        }
    } catch (error) {
        console.error('Ошибка поиска отцов:', error);
        document.getElementById('fathers-list').innerHTML = `
            <div class="text-danger text-center py-3">
                Ошибка поиска
            </div>
        `;
    }
}

// Создание элемента для выбора отца
function createFatherItem(animal) {
    const item = document.createElement('div');
    item.className = 'form-check mb-2';
    
    // Определяем отображаемое имя
    let displayName = animal.tag_number;
    if (animal.type_code === 'maker' && animal.name) {
        displayName = `${animal.name}(${animal.tag_number})`;
    }
    
    item.innerHTML = `
        <input class="form-check-input father-radio" type="radio" name="father" 
               value="${animal.tag_number}" data-type="${animal.type_code}" data-tag="${animal.tag_number}">
        <label class="form-check-label">
            ${displayName} (${animal.animal_type}) - ${animal.status}
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
    
    // Получаем текст из label для отображения
    const label = checkedRadio.nextElementSibling;
    const labelText = label.textContent.trim();
    // Извлекаем только имя/бирку до первой скобки с типом животного
    const displayName = labelText.split(' (')[0];

    setSelectedFatherFromAnimal({
        tag_number: checkedRadio.value,
        type_code: checkedRadio.dataset.type,
        animal_type: checkedRadio.dataset.type === 'maker' ? 'Баран-Производитель' : 'Баранчик',
        display_name: displayName
    });
    
    // Закрываем модальное окно
    const modal = bootstrap.Modal.getInstance(document.getElementById('selectFatherModal'));
    modal.hide();
}

// Постановка выбранных животных в группу
async function createMultipleLambings() {
    const placementDate = document.getElementById('lambing-start-date').value;
    const note = document.getElementById('group-lambing-note').value.trim();
    const placeSelect = document.getElementById('group-place-select');
    const placeId = placeSelect ? placeSelect.value : '';
    
    // Валидация
    if (!placementDate) {
        alert('Укажите дату постановки в группу');
        return;
    }
    
    if (!window.selectedMothersForLambing || window.selectedMothersForLambing.length === 0) {
        alert('Выберите овцематок/ярок');
        return;
    }
    
    if (!selectedFather) {
        alert('Выберите отца');
        return;
    }
    
    try {
        const data = {
            placement_date: placementDate,
            father_tag_number: selectedFather.tag_number,
            mother_tag_numbers: window.selectedMothersForLambing.map(m => m.tag_number),
            note: note || ''
        };
        if (placeId) {
            data.place_id = placeId;
        }
        
        const response = await apiRequest('/animals/lambing-group/', 'POST', data);
        
        let message = `Группа создана. Матерей в группе: ${response.mothers_count || 0}`;
        if (response.moved_count) {
            message += `\nПеремещено животных: ${response.moved_count}`;
        }
        if (response.errors && response.errors.length > 0) {
            message += `\n\nОшибки:\n${response.errors.join('\n')}`;
        }
        
        alert(message);
        
        // Очищаем форму
        resetForm();
        
        // Перезагружаем таблицы
        loadActiveGroups();
        loadActiveLambings();
        
    } catch (error) {
        console.error('Ошибка создания группы:', error);
        alert('Ошибка при создании группы: ' + (error.message || 'Неизвестная ошибка'));
    }
}

// Сброс формы
function resetForm() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('lambing-start-date').value = today;
    document.getElementById('group-lambing-note').value = '';
    
    selectedMothers.clear();
    selectedMothersData.clear();
    window.selectedMothersForLambing = [];
    selectedFather = null;
    
    document.getElementById('selected-mothers-display').textContent = 'Не выбрано';
    document.getElementById('selected-mothers-display').className = 'mt-2 text-muted';
    
    document.getElementById('selected-father-display').textContent = 'Не выбран';
    document.getElementById('selected-father-display').className = 'mt-2 text-muted';
    const fatherSelect = document.getElementById('father-select');
    if (fatherSelect) {
        fatherSelect.value = '';
    }
    const groupPlaceSelect = document.getElementById('group-place-select');
    if (groupPlaceSelect) {
        groupPlaceSelect.value = '';
    }
    
    // Скрываем блок автоматической проверки родства
    document.getElementById('auto-kinship-result').style.display = 'none';
    loadFatherSelectOptions();
}

// Показать модальное окно завершения окота
function showCompleteLambingModal(lambingId) {
    // Сохраняем ID окота для использования в модальном окне
    window.currentLambingId = lambingId;
    document.getElementById('completing-lambing-id').value = lambingId;
    
    // Устанавливаем текущую дату как дату фактических родов
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('actual-lambing-date').value = today;
    const deadLambsCountInput = document.getElementById('dead-lambs-count');
    if (deadLambsCountInput) {
        deadLambsCountInput.value = '0';
    }
    const lambsCountInput = document.getElementById('lambs-count');
    if (lambsCountInput) {
        lambsCountInput.value = '1';
    }
    const completionNoteInput = document.getElementById('completion-lambing-note');
    if (completionNoteInput) {
        completionNoteInput.value = '';
    }
    const createLambsCheckbox = document.getElementById('create-lambs-checkbox');
    if (createLambsCheckbox) {
        createLambsCheckbox.checked = true;
    }
    const earlyFailureCheckbox = document.getElementById('early-failure-checkbox');
    if (earlyFailureCheckbox) {
        earlyFailureCheckbox.checked = false;
    }
    const unsuccessfulCheckbox = document.getElementById('unsuccessful-insemination-checkbox');
    if (unsuccessfulCheckbox) {
        unsuccessfulCheckbox.checked = false;
    }
    window.currentCompletionMode = 'normal';
    resetUnsuccessfulInseminationWarning();
    updateCompletionMode();
    
    // Генерируем формы для ягнят
    generateLambForms(1);
    
    // Показываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('completeLambingModal'));
    modal.show();
}

function isEarlyFailureMode() {
    return window.currentCompletionMode === 'early_failure'
        || Boolean(document.getElementById('early-failure-checkbox')?.checked);
}

function isUnsuccessfulInseminationMode() {
    return window.currentCompletionMode === 'unsuccessful_insemination';
}

function resetUnsuccessfulInseminationWarning() {
    const warning = document.getElementById('unsuccessful-insemination-warning');
    if (warning) {
        warning.style.display = 'none';
        warning.textContent = '';
    }
}

async function loadUnsuccessfulInseminationWarning() {
    const warning = document.getElementById('unsuccessful-insemination-warning');
    if (!warning || !window.currentLambingId) return;

    warning.style.display = 'none';
    warning.textContent = '';

    try {
        const response = await apiRequest(`/animals/lambing/${window.currentLambingId}/unsuccessful-insemination-warning/`, 'GET');
        if (response.warning) {
            warning.textContent = response.warning;
            warning.style.display = 'block';
        }
    } catch (error) {
        console.error('Ошибка проверки неудачных осеменений:', error);
    }
}

function setCompletionMode(mode) {
    window.currentCompletionMode = mode || 'normal';

    const earlyFailureCheckbox = document.getElementById('early-failure-checkbox');
    if (earlyFailureCheckbox) {
        earlyFailureCheckbox.checked = window.currentCompletionMode === 'early_failure';
    }
    const unsuccessfulCheckbox = document.getElementById('unsuccessful-insemination-checkbox');
    if (unsuccessfulCheckbox) {
        unsuccessfulCheckbox.checked = window.currentCompletionMode === 'unsuccessful_insemination';
    }

    resetUnsuccessfulInseminationWarning();
    updateCompletionMode();

    if (isUnsuccessfulInseminationMode()) {
        loadUnsuccessfulInseminationWarning();
    }
}

function selectUnsuccessfulInseminationMode() {
    setCompletionMode('unsuccessful_insemination');
}

function updateCompletionMode() {
    const isEarlyFailure = isEarlyFailureMode();
    const isUnsuccessful = isUnsuccessfulInseminationMode();
    const dateLabel = document.getElementById('actual-lambing-date-label');
    const infoHeading = document.getElementById('lambing-info-heading');
    const dateField = document.getElementById('actual-lambing-date-field');
    const earlyFailureCheck = document.querySelector('.early-failure-check');
    const unsuccessfulAction = document.getElementById('unsuccessful-insemination-action');
    const lambsCountField = document.getElementById('lambs-count-field');
    const deadLambsCountField = document.getElementById('dead-lambs-count-field');
    const lambsCreationSection = document.getElementById('lambs-creation-section');
    const createLambsCheckbox = document.getElementById('create-lambs-checkbox');
    const separator = document.getElementById('lambing-completion-separator');
    const submitButton = document.getElementById('complete-lambing-submit-btn');

    if (dateLabel) {
        dateLabel.textContent = isEarlyFailure ? 'Дата завершения:' : 'Дата фактических родов:';
    }
    if (infoHeading) {
        infoHeading.style.display = isUnsuccessful ? 'none' : '';
    }
    if (dateField) {
        dateField.style.display = isUnsuccessful ? 'none' : '';
    }
    if (earlyFailureCheck) {
        earlyFailureCheck.style.display = isUnsuccessful ? 'none' : '';
    }
    if (unsuccessfulAction) {
        unsuccessfulAction.style.display = isUnsuccessful ? 'none' : '';
    }
    if (lambsCountField) {
        lambsCountField.style.display = (isEarlyFailure || isUnsuccessful) ? 'none' : '';
    }
    if (deadLambsCountField) {
        deadLambsCountField.style.display = (isEarlyFailure || isUnsuccessful) ? 'none' : '';
    }
    if (lambsCreationSection) {
        lambsCreationSection.style.display = (isEarlyFailure || isUnsuccessful) ? 'none' : '';
    }
    if (createLambsCheckbox) {
        createLambsCheckbox.disabled = isEarlyFailure || isUnsuccessful;
    }
    if (separator) {
        separator.style.display = isUnsuccessful ? 'none' : '';
    }
    if (submitButton) {
        submitButton.textContent = isUnsuccessful ? 'Неудачное осеменение' : (isEarlyFailure ? 'Аборт' : 'Окот');
        submitButton.classList.toggle('btn-success', !isEarlyFailure && !isUnsuccessful);
        submitButton.classList.toggle('btn-warning', isEarlyFailure);
        submitButton.classList.toggle('btn-danger', isUnsuccessful);
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
const lambStatusesByAnimalType = {};

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
    
    const genderSelect = div.querySelector('.lamb-gender');
    if (genderSelect) {
        genderSelect.addEventListener('change', () => loadStatusesForLamb(div));
    }

    // Загружаем статусы и места для этой формы
    loadStatusesForLamb(div);
    loadPlacesForLamb(div);
    
    return div;
}

function getLambAnimalTypeByGender(gender) {
    if (gender === 'male') return 'Ram';
    if (gender === 'female') return 'Ewe';
    return '';
}

async function getLambStatusesForAnimalType(animalType) {
    if (!animalType) return [];
    if (!lambStatusesByAnimalType[animalType]) {
        const response = await apiRequest(`/veterinary/api/status/?exclude_archive=1&page_size=100&animal_type=${encodeURIComponent(animalType)}`);
        lambStatusesByAnimalType[animalType] = response.results || response;
    }
    return lambStatusesByAnimalType[animalType];
}

function applyDefaultLambStatus(formElement) {
    const select = formElement.querySelector('.lamb-status');
    const gender = formElement.querySelector('.lamb-gender')?.value;
    if (!select) return;

    const defaultStatusName = gender === 'male' ? 'Откорм' : 'Не определено';
    const defaultOption = Array.from(select.options).find(option => option.textContent === defaultStatusName);
    if (defaultOption) {
        select.value = defaultOption.value;
    }
}
// Загрузка статусов для ягненка
async function loadStatusesForLamb(formElement) {
    try {
        const select = formElement.querySelector('.lamb-status');
        const gender = formElement.querySelector('.lamb-gender')?.value;
        const animalType = getLambAnimalTypeByGender(gender);
        if (!select) return;

        select.innerHTML = animalType
            ? '<option value="">Выберите статус</option>'
            : '<option value="">Сначала выберите тип животного</option>';
        if (!animalType) return;

        const statuses = await getLambStatusesForAnimalType(animalType);
        statuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.id;
            option.textContent = status.status_type;
            select.appendChild(option);
        });

        applyDefaultLambStatus(formElement);
    } catch (error) {
        console.error('Ошибка загрузки статусов для ягненка:', error);
    }
}
// Загрузка мест для ягненка
async function loadPlacesForLamb(formElement) {
    try {
        const response = await apiRequest('/veterinary/api/place/?page_size=100');
        // API возвращает пагинированные данные, берем массив из results
        const places = response.results || response;
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
    if (isUnsuccessfulInseminationMode()) {
        await completeLambingUnsuccessfulInsemination();
        return;
    }

    if (isEarlyFailureMode()) {
        await completeLambingEarlyFailure();
        return;
    }

    const lambingId = window.currentLambingId;
    const actualDate = document.getElementById('actual-lambing-date').value;
    const lambsCount = parseInt(document.getElementById('lambs-count').value) || 0;
    const deadLambsCount = parseInt(document.getElementById('dead-lambs-count')?.value || '0') || 0;
    const lambingNote = document.getElementById('completion-lambing-note').value;
    const createLambs = document.getElementById('create-lambs-checkbox').checked;
    
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

async function completeLambingEarlyFailure() {
    const lambingId = window.currentLambingId;
    const actualDate = document.getElementById('actual-lambing-date').value;
    const lambingNote = document.getElementById('completion-lambing-note').value;

    if (!lambingId) {
        alert('Не выбран окот');
        return;
    }
    if (!actualDate) {
        alert('Пожалуйста, укажите дату досрочного завершения');
        return;
    }

    try {
        await apiRequest(`/animals/lambing/${lambingId}/complete-early-failure/`, 'POST', {
            actual_lambing_date: actualDate,
            note: lambingNote || ''
        });

        alert('Окот досрочно завершен.');

        const modal = bootstrap.Modal.getInstance(document.getElementById('completeLambingModal'));
        modal.hide();

        loadActiveLambings();
    } catch (error) {
        console.error('Ошибка досрочного завершения окота:', error);
        alert('Ошибка при досрочном завершении: ' + (error.message || 'Неизвестная ошибка'));
    }
}

async function completeLambingUnsuccessfulInsemination() {
    const lambingId = window.currentLambingId;
    const lambingNote = document.getElementById('completion-lambing-note').value;

    if (!lambingId) {
        alert('Не выбрана случка');
        return;
    }

    try {
        const response = await apiRequest(`/animals/lambing/${lambingId}/complete-unsuccessful-insemination/`, 'POST', {
            note: lambingNote || ''
        });

        alert(response.warning || 'Неудачное осеменение отмечено.');

        const modal = bootstrap.Modal.getInstance(document.getElementById('completeLambingModal'));
        modal.hide();

        loadActiveLambings();
    } catch (error) {
        console.error('Ошибка отметки неудачного осеменения:', error);
        alert('Ошибка при отметке неудачного осеменения: ' + (error.message || 'Неизвестная ошибка'));
    }
}

async function submitLambingCompletion() {
    if (isUnsuccessfulInseminationMode()) {
        await completeLambingUnsuccessfulInsemination();
        return;
    }

    if (isEarlyFailureMode()) {
        await completeLambingEarlyFailure();
        return;
    }

    await completeLambingWithChildren();
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

async function uploadImportFile(importType, action, fileInputId) {
    const fileInput = document.getElementById(fileInputId);
    const file = fileInput?.files?.[0];
    if (!file) {
        throw new Error('Выберите файл импорта');
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`/animals/api/import/${importType}/${action}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken()
        },
        body: formData
    });

    const data = await response.json();
    if (!response.ok) {
        throw new Error(getApiErrorMessage(data));
    }
    return data;
}

function renderImportResult(resultId, data, title) {
    const resultBlock = document.getElementById(resultId);
    if (!resultBlock) return;

    const errors = data.errors || [];
    const warnings = data.warnings || [];
    const hasIssues = errors.length > 0 || warnings.length > 0;
    const issueItems = []
        .concat(errors.map(error => `<li>${escapeHtml(error)}</li>`))
        .concat(warnings.map(warning => `<li>${escapeHtml(warning)}</li>`))
        .join('');

    resultBlock.className = `alert ${hasIssues ? 'alert-warning' : 'alert-success'}`;
    resultBlock.style.display = 'block';
    resultBlock.innerHTML = `
        <div class="fw-semibold mb-1">${escapeHtml(title)}</div>
        <div>Готово к импорту: ${data.valid_count || 0}</div>
        ${issueItems ? `<hr><div class="fw-semibold mb-1">Проверка файла:</div><ul class="mb-0">${issueItems}</ul>` : ''}
    `;
}

async function previewGroupImport() {
    const confirmBtn = document.getElementById('group-import-confirm-btn');
    if (confirmBtn) confirmBtn.disabled = true;

    try {
        const data = await uploadImportFile('group', 'preview', 'group-import-file');
        renderImportResult('group-import-result', data, 'Файл групп прочитан');
        if (confirmBtn) confirmBtn.disabled = !data.can_confirm;
    } catch (error) {
        renderImportResult('group-import-result', { valid_count: 0, errors: [error.message] }, 'Ошибка чтения файла');
    }
}

async function confirmGroupImport() {
    if (!confirm('Подтвердить импорт групп? Ошибочные строки будут пропущены.')) {
        return;
    }

    const confirmBtn = document.getElementById('group-import-confirm-btn');
    if (confirmBtn) confirmBtn.disabled = true;

    try {
        const data = await uploadImportFile('group', 'confirm', 'group-import-file');
        const createdGroups = data.created_groups_count || 0;
        const updatedGroups = data.updated_groups_count || 0;
        const addedMothers = data.added_mothers_count || 0;
        const movedAnimals = data.moved_count || 0;
        const movedText = movedAnimals ? `; перемещено животных: ${movedAnimals}` : '';
        renderImportResult(
            'group-import-result',
            data,
            `Импорт завершен. Новых групп: ${createdGroups}; обновлено групп: ${updatedGroups}; добавлено матерей: ${addedMothers}${movedText}`
        );
        loadActiveGroups();
        loadActiveLambings();
    } catch (error) {
        renderImportResult('group-import-result', { valid_count: 0, errors: [error.message] }, 'Ошибка импорта');
        if (confirmBtn) confirmBtn.disabled = false;
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
window.completeLambingEarlyFailure = completeLambingEarlyFailure;
window.completeLambingUnsuccessfulInsemination = completeLambingUnsuccessfulInsemination;
window.selectUnsuccessfulInseminationMode = selectUnsuccessfulInseminationMode;
window.submitLambingCompletion = submitLambingCompletion;
window.removeLambForm = removeLambForm;
window.changePage = changePage;
window.changeGroupsPage = changeGroupsPage;
window.applyDateFilter = applyDateFilter;
window.clearDateFilter = clearDateFilter;
window.applyGroupFilter = applyGroupFilter;
window.clearGroupFilter = clearGroupFilter;
window.exportLambingsToExcel = exportLambingsToExcel;
window.exportGroupsToExcel = exportGroupsToExcel;
window.switchLambingManagementView = switchLambingManagementView;
window.showRemoveFatherModal = showRemoveFatherModal;
window.confirmRemoveFather = confirmRemoveFather;
window.showAddMothersToGroupModal = showAddMothersToGroupModal;
window.confirmAddMothersToGroup = confirmAddMothersToGroup;
window.showRemoveMothersFromGroupModal = showRemoveMothersFromGroupModal;
window.confirmRemoveMothersFromGroup = confirmRemoveMothersFromGroup;
window.previewGroupImport = previewGroupImport;
window.confirmGroupImport = confirmGroupImport;

// Функции для проверки родства
window.showSelectKinshipFatherModal = showSelectKinshipFatherModal;
window.showSelectKinshipMotherModal = showSelectKinshipMotherModal;
window.confirmKinshipFatherSelection = confirmKinshipFatherSelection;
window.confirmKinshipMotherSelection = confirmKinshipMotherSelection;
window.checkKinship = checkKinship;
window.showKinshipProblemsModal = showKinshipProblemsModal;
window.exportKinshipPairsToExcel = exportKinshipPairsToExcel;

let selectedKinshipFather = null;
let selectedKinshipMothers = new Set();
let selectedKinshipMothersData = new Map();
let lastKinshipCheckResult = null;

function resetKinshipResult() {
    lastKinshipCheckResult = null;
    const resultDiv = document.getElementById('kinship-result');
    const alertDiv = document.getElementById('kinship-alert');
    if (resultDiv) {
        resultDiv.style.display = 'none';
    }
    if (alertDiv) {
        alertDiv.className = 'alert';
        alertDiv.innerHTML = '';
    }
}

async function showSelectKinshipFatherModal() {
    document.getElementById('kinshipFathersSearch').value = '';
    document.getElementById('kinship-fathers-list').innerHTML = `
        <div class="text-muted text-center py-3">
            Введите бирку или РСХН и нажмите "Поиск" для отображения результатов
        </div>
    `;

    const modal = new bootstrap.Modal(document.getElementById('selectKinshipFatherModal'));
    modal.show();
}

async function showSelectKinshipMotherModal() {
    document.getElementById('kinshipMothersSearch').value = '';
    document.getElementById('kinship-mothers-list').innerHTML = `
        <div class="text-muted text-center py-3">
            Введите бирку или РСХН и нажмите "Поиск" для отображения результатов
        </div>
    `;

    const modal = new bootstrap.Modal(document.getElementById('selectKinshipMotherModal'));
    modal.show();
}

async function searchKinshipFathers() {
    const search = document.getElementById('kinshipFathersSearch').value.trim();

    if (!search) {
        document.getElementById('kinship-fathers-list').innerHTML = `
            <div class="text-muted text-center py-3">
                Введите бирку или РСХН для поиска
            </div>
        `;
        return;
    }

    document.getElementById('kinship-fathers-list').innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Поиск...</span>
            </div>
            <div class="mt-2">Поиск баранов-производителей/баранчиков...</div>
        </div>
    `;

    try {
        const response = await apiRequest(`/animals/api/all-fathers/?search=${encodeURIComponent(search)}&include_busy=1`);
        const fathers = response || [];

        const fathersList = document.getElementById('kinship-fathers-list');
        fathersList.innerHTML = '';
        const limitedFathers = fathers.slice(0, 50);

        if (limitedFathers.length === 0) {
            fathersList.innerHTML = '<div class="text-center text-muted">Бараны-Производители/баранчики не найдены</div>';
        } else {
            const makers = limitedFathers.filter(f => f.type_code === 'maker');
            const rams = limitedFathers.filter(f => f.type_code === 'ram');

            if (makers.length > 0) {
                const makerHeader = document.createElement('h6');
                makerHeader.textContent = 'Бараны-Производители';
                makerHeader.className = 'mt-3 mb-2 text-primary';
                fathersList.appendChild(makerHeader);

                makers.forEach(maker => {
                    const item = createKinshipFatherItem(maker);
                    fathersList.appendChild(item);
                });
            }

            if (rams.length > 0) {
                const ramHeader = document.createElement('h6');
                ramHeader.textContent = 'Баранчики';
                ramHeader.className = 'mt-3 mb-2 text-primary';
                fathersList.appendChild(ramHeader);

                rams.forEach(ram => {
                    const item = createKinshipFatherItem(ram);
                    fathersList.appendChild(item);
                });
            }

            if (fathers.length > 50) {
                const info = document.createElement('div');
                info.className = 'text-muted text-center mt-2 small';
                info.textContent = `Показано первых 50 из ${fathers.length} результатов`;
                fathersList.appendChild(info);
            }
        }
    } catch (error) {
        console.error('Ошибка поиска отцов для проверки родства:', error);
        document.getElementById('kinship-fathers-list').innerHTML = `
            <div class="text-danger text-center py-3">
                Ошибка поиска
            </div>
        `;
    }
}

async function searchKinshipMothers() {
    const search = document.getElementById('kinshipMothersSearch').value.trim();

    if (!search) {
        document.getElementById('kinship-mothers-list').innerHTML = `
            <div class="text-muted text-center py-3">
                Введите бирку или РСХН для поиска
            </div>
        `;
        return;
    }

    saveSelectedKinshipMothers();

    document.getElementById('kinship-mothers-list').innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Поиск...</span>
            </div>
            <div class="mt-2">Поиск ярок/овцематок...</div>
        </div>
    `;

    try {
        const response = await apiRequest(`/animals/api/inactive-mothers/?search=${encodeURIComponent(search)}&include_busy=1`);
        const mothers = response || [];

        const mothersList = document.getElementById('kinship-mothers-list');
        mothersList.innerHTML = '';
        const limitedMothers = mothers.slice(0, 50);

        if (limitedMothers.length === 0) {
            mothersList.innerHTML = '<div class="text-center text-muted">Ярки/овцематки не найдены</div>';
        } else {
            const ewes = limitedMothers.filter(m => m.type_code === 'ewe');
            const sheep = limitedMothers.filter(m => m.type_code === 'sheep');

            if (ewes.length > 0) {
                const eweHeader = document.createElement('h6');
                eweHeader.textContent = 'Ярки';
                eweHeader.className = 'mt-3 mb-2 text-primary';
                mothersList.appendChild(eweHeader);

                ewes.forEach(ewe => {
                    const item = createKinshipMotherItem(ewe);
                    mothersList.appendChild(item);
                });
            }

            if (sheep.length > 0) {
                const sheepHeader = document.createElement('h6');
                sheepHeader.textContent = 'Овцематки';
                sheepHeader.className = 'mt-3 mb-2 text-primary';
                mothersList.appendChild(sheepHeader);

                sheep.forEach(sheepAnimal => {
                    const item = createKinshipMotherItem(sheepAnimal);
                    mothersList.appendChild(item);
                });
            }

            if (mothers.length > 50) {
                const info = document.createElement('div');
                info.className = 'text-muted text-center mt-2 small';
                info.textContent = `Показано первых 50 из ${mothers.length} результатов`;
                mothersList.appendChild(info);
            }
        }

        restoreSelectedKinshipMothers();
    } catch (error) {
        console.error('Ошибка поиска матерей для проверки родства:', error);
        document.getElementById('kinship-mothers-list').innerHTML = `
            <div class="text-danger text-center py-3">
                Ошибка поиска
            </div>
        `;
    }
}

function createKinshipFatherItem(animal) {
    const item = document.createElement('div');
    item.className = 'form-check mb-2';

    let displayName = animal.tag_number;
    if (animal.type_code === 'maker' && animal.name) {
        displayName = `${animal.name}(${animal.tag_number})`;
    }

    item.innerHTML = `
        <input class="form-check-input kinship-father-radio" type="radio" name="kinship-father" 
               value="${animal.tag_number}" data-type="${animal.type_code}" data-tag="${animal.tag_number}">
        <label class="form-check-label">
            ${displayName} (${animal.animal_type}) - ${animal.status}
        </label>
    `;

    return item;
}

function createKinshipMotherItem(animal) {
    const item = document.createElement('div');
    item.className = 'form-check mb-2';

    item.innerHTML = `
        <input class="form-check-input kinship-mother-checkbox" type="checkbox" 
               value="${animal.tag_number}" data-type="${animal.type_code}" data-tag="${animal.tag_number}">
        <label class="form-check-label">
            ${animal.tag_number} (${animal.animal_type}) - ${animal.status}
        </label>
    `;

    return item;
}

function saveSelectedKinshipMothers() {
    const checkboxes = document.querySelectorAll('.kinship-mother-checkbox');
    checkboxes.forEach(checkbox => {
        const tagNumber = checkbox.value;
        if (checkbox.checked) {
            selectedKinshipMothers.add(tagNumber);
            selectedKinshipMothersData.set(tagNumber, {
                tag_number: tagNumber,
                type: checkbox.dataset.type,
                tag: checkbox.dataset.tag
            });
        } else {
            selectedKinshipMothers.delete(tagNumber);
            selectedKinshipMothersData.delete(tagNumber);
        }
    });
}

function restoreSelectedKinshipMothers() {
    const checkboxes = document.querySelectorAll('.kinship-mother-checkbox');
    checkboxes.forEach(checkbox => {
        if (selectedKinshipMothers.has(checkbox.value)) {
            checkbox.checked = true;
        }
    });
}

function updateKinshipMothersDisplay() {
    const display = document.getElementById('kinship-mother-display');
    const selectedMothersArray = Array.from(selectedKinshipMothersData.values());

    if (selectedMothersArray.length === 0) {
        display.textContent = 'Не выбрано';
        display.className = 'mt-2 text-muted';
        return;
    }

    display.textContent = `Выбрано: ${selectedMothersArray.length} (${selectedMothersArray.map(m => m.tag).join(', ')})`;
    display.className = 'mt-2 text-success';
}

function confirmKinshipFatherSelection() {
    const checkedRadio = document.querySelector('.kinship-father-radio:checked');

    if (!checkedRadio) {
        alert('Выберите отца');
        return;
    }

    const label = checkedRadio.nextElementSibling;
    const labelText = label.textContent.trim();
    const displayName = labelText.split(' (')[0];

    setSelectedKinshipFatherFromAnimal({
        tag_number: checkedRadio.value,
        type_code: checkedRadio.dataset.type,
        animal_type: checkedRadio.dataset.type === 'maker' ? 'Баран-Производитель' : 'Баранчик',
        display_name: displayName
    });

    const modal = bootstrap.Modal.getInstance(document.getElementById('selectKinshipFatherModal'));
    modal.hide();
}

function confirmKinshipMotherSelection() {
    saveSelectedKinshipMothers();

    if (selectedKinshipMothersData.size === 0) {
        alert('Выберите хотя бы одну мать');
        return;
    }

    updateKinshipMothersDisplay();
    updateKinshipCheckButton();
    resetKinshipResult();

    const modal = bootstrap.Modal.getInstance(document.getElementById('selectKinshipMotherModal'));
    modal.hide();
}

function updateKinshipCheckButton() {
    const checkButton = document.getElementById('check-kinship-btn');
    const exportButton = document.getElementById('export-kinship-btn');
    const isReady = Boolean(selectedKinshipFather && selectedKinshipMothersData.size > 0);

    if (checkButton) {
        checkButton.disabled = !isReady;
    }
    if (exportButton) {
        exportButton.disabled = !isReady;
    }
}

async function checkKinship() {
    if (!selectedKinshipFather || selectedKinshipMothersData.size === 0) {
        alert('Выберите отца и хотя бы одну мать для проверки родства');
        return;
    }

    const resultDiv = document.getElementById('kinship-result');
    const alertDiv = document.getElementById('kinship-alert');
    const selectedMothersArray = Array.from(selectedKinshipMothersData.values());

    resultDiv.style.display = 'block';
    alertDiv.className = 'alert alert-info';
    alertDiv.innerHTML = `
        <div class="d-flex align-items-center">
            <div class="spinner-border spinner-border-sm me-2" role="status">
                <span class="visually-hidden">Проверка...</span>
            </div>
            Проверка родства до 4-го колена...
        </div>
    `;

    try {
        const problematic = [];
        const valid = [];

        for (const mother of selectedMothersArray) {
            const response = await apiRequest('/animals/api/check-kinship/', 'POST', {
                father_tag: selectedKinshipFather.tag_number,
                mother_tag: mother.tag_number
            });

            if (response.has_kinship) {
                problematic.push({
                    mother_tag: mother.tag_number,
                    message: response.message_with_links || response.message,
                    plain_message: response.message || response.message_with_links || 'Есть проблемы с родством'
                });
            } else {
                valid.push({
                    mother_tag: mother.tag_number
                });
            }
        }

        lastKinshipCheckResult = {
            father_tag: selectedKinshipFather.tag_number,
            father_display_name: selectedKinshipFather.display_name,
            total: selectedMothersArray.length,
            valid,
            problematic
        };

        if (problematic.length > 0) {
            alertDiv.className = 'alert alert-warning';
            alertDiv.innerHTML = `
                <h6 class="alert-heading">Есть проблемы с родством</h6>
                <p class="mb-1">Проверено пар: ${selectedMothersArray.length}. Без проблем: ${valid.length}. Проблемных: ${problematic.length}.</p>
                <p class="mb-0"><a href="#" onclick="showKinshipProblemsModal(event)">Посмотреть детальнее</a></p>
            `;
        } else {
            alertDiv.className = 'alert alert-success';
            alertDiv.innerHTML = `
                <h6 class="alert-heading">Родство не обнаружено</h6>
                <p class="mb-0">Проверено пар: ${selectedMothersArray.length}. Все пары подобраны без проблем до 4-го колена.</p>
            `;
        }
    } catch (error) {
        console.error('Ошибка проверки родства:', error);
        alertDiv.className = 'alert alert-danger';
        alertDiv.innerHTML = `
            <h6 class="alert-heading">Ошибка проверки</h6>
            <p class="mb-0">Произошла ошибка при проверке родства: ${error.message || 'Неизвестная ошибка'}</p>
        `;
    }
}

function showKinshipProblemsModal(event) {
    if (event) {
        event.preventDefault();
    }

    const tableBody = document.getElementById('kinship-problems-details');
    if (!tableBody) {
        return;
    }

    const problematic = lastKinshipCheckResult?.problematic || [];
    tableBody.innerHTML = '';

    if (problematic.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="3" class="text-center text-muted">Проблем не найдено</td>
            </tr>
        `;
    } else {
        problematic.forEach((item, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${item.mother_tag}</td>
                <td>${item.message}</td>
            `;
            tableBody.appendChild(row);
        });
    }

    const modal = new bootstrap.Modal(document.getElementById('kinshipProblemsModal'));
    modal.show();
}

async function exportKinshipPairsToExcel() {
    if (!selectedKinshipFather || selectedKinshipMothersData.size === 0) {
        alert('Выберите отца и хотя бы одну мать для экспорта');
        return;
    }

    const exportButton = document.getElementById('export-kinship-btn');
    const originalText = exportButton.textContent;
    exportButton.disabled = true;
    exportButton.textContent = 'Экспорт...';

    try {
        const response = await fetch('/animals/api/kinship-pairs/export-excel/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                father_tag: selectedKinshipFather.tag_number,
                mother_tags: Array.from(selectedKinshipMothersData.values()).map(m => m.tag_number)
            })
        });

        if (!response.ok) {
            let errorMessage = 'Ошибка экспорта';
            try {
                const errorData = await response.json();
                errorMessage = getApiErrorMessage(errorData, errorMessage);
            } catch (jsonError) {
                // no-op
            }
            throw new Error(errorMessage);
        }

        const blob = await response.blob();
        const disposition = response.headers.get('Content-Disposition') || '';
        const filenameMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
        const filename = filenameMatch ? filenameMatch[1] : 'kinship_pairs.xlsx';

        const downloadUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(downloadUrl);
    } catch (error) {
        console.error('Ошибка экспорта подбора пар:', error);
        alert(`Не удалось экспортировать подбор пар: ${error.message || 'Неизвестная ошибка'}`);
    } finally {
        exportButton.textContent = originalText;
        updateKinshipCheckButton();
    }
}
async function checkAutoKinship() {
    const resultDiv = document.getElementById('auto-kinship-result');
    const alertDiv = document.getElementById('auto-kinship-alert');
    
    // Проверяем, выбраны ли отец и матери
    if (!selectedFather || !window.selectedMothersForLambing || window.selectedMothersForLambing.length === 0) {
        // Скрываем блок, если не все выбрано
        resultDiv.style.display = 'none';
        return;
    }
    
    // Показываем блок и индикатор загрузки
    resultDiv.style.display = 'block';
    alertDiv.className = 'alert alert-info';
    alertDiv.innerHTML = `
        <div class="d-flex align-items-center">
            <div class="spinner-border spinner-border-sm me-2" role="status">
                <span class="visually-hidden">Проверка...</span>
            </div>
            Автоматическая проверка родства...
        </div>
    `;
    
    try {
        let hasAnyKinship = false;
        let kinshipResults = [];
        
        // Проверяем родство отца с каждой матерью
        for (const mother of window.selectedMothersForLambing) {
            try {
                const response = await apiRequest('/animals/api/check-kinship/', 'POST', {
                    father_tag: selectedFather.tag_number,
                    mother_tag: mother.tag_number
                });
                
                if (response.has_kinship) {
                    hasAnyKinship = true;
                    kinshipResults.push({
                        mother: mother.tag_number,
                        message: response.message_with_links || response.message
                    });
                }
            } catch (error) {
                console.error(`Ошибка проверки родства для ${mother.tag_number}:`, error);
                // Продолжаем проверку других животных
            }
        }
        
        // Отображаем результат
        if (hasAnyKinship) {
            alertDiv.className = 'alert alert-warning';
            let warningMessage = '<h6 class="alert-heading">Обнаружено родство!</h6>';
            
            if (kinshipResults.length === 1) {
                warningMessage += `<p class="mb-0">${kinshipResults[0].message}</p>`;
            } else {
                warningMessage += '<p class="mb-1">Обнаружено родство с несколькими животными:</p>';
                warningMessage += '<ul class="mb-0">';
                kinshipResults.forEach(result => {
                    warningMessage += `<li>${result.mother}: ${result.message}</li>`;
                });
                warningMessage += '</ul>';
            }
            
            alertDiv.innerHTML = warningMessage;
        } else {
            alertDiv.className = 'alert alert-success';
            alertDiv.innerHTML = `
                <h6 class="alert-heading">Родство не обнаружено</h6>
                <p class="mb-0">Проверка родства между выбранными животными не выявила общих предков до 4-го колена</p>
            `;
        }
        
    } catch (error) {
        console.error('Ошибка автоматической проверки родства:', error);
        alertDiv.className = 'alert alert-danger';
        alertDiv.innerHTML = `
            <h6 class="alert-heading">Ошибка проверки</h6>
            <p class="mb-0">Произошла ошибка при автоматической проверке родства</p>
        `;
    }
}
