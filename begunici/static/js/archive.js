import { apiRequest, formatDateToOutput } from "./utils.js";

const pageSize = 10;
let currentPage = 1;

function getUserPermissions() {
    return window.userPermissions || { can_restore_from_archive: true };
}

function getUrlParams() {
    return new URLSearchParams(window.location.search);
}

function setUrlParams(params) {
    const query = params.toString();
    const newUrl = `${window.location.pathname}${query ? `?${query}` : ""}`;
    window.history.replaceState({}, "", newUrl);
}

function toggleMotherFilterByType(animalType) {
    const group = document.getElementById("mother-tag-filter-group");
    const header = document.getElementById("mother-column-header");
    if (!group) return;

    const isLambType = animalType === "Lamb";
    window.isLambArchive = isLambType;

    if (isLambType) {
        group.classList.remove("d-none");
        if (header) {
            header.classList.remove("d-none");
        }
    } else {
        group.classList.add("d-none");
        if (header) {
            header.classList.add("d-none");
        }
        const motherInput = document.getElementById("mother-tag-filter");
        if (motherInput) {
            motherInput.value = "";
        }
    }
}

function buildAnimalInfo(animal) {
    const tagNumber = animal.tag_number;
    const animalTypeCode = animal.animal_type;

    if (animalTypeCode === "Maker") {
        return { label: "Баран-Производитель", detailUrl: `/animals/maker/${tagNumber}/info/` };
    }
    if (animalTypeCode === "Ram") {
        return { label: "Баранчик", detailUrl: `/animals/ram/${tagNumber}/info/` };
    }
    if (animalTypeCode === "Ewe") {
        return { label: "Ярка", detailUrl: `/animals/ewe/${tagNumber}/info/` };
    }
    if (animalTypeCode === "Sheep") {
        return { label: "Овцематка", detailUrl: `/animals/sheep/${tagNumber}/info/` };
    }

    return { label: "Неизвестно", detailUrl: "#" };
}

function formatWeightCell(value) {
    if (value === null || value === undefined || value === "" || value === "-") {
        return "-";
    }
    return `${value} кг`;
}

function buildMotherCell(animal) {
    if (!window.isLambArchive) {
        return "";
    }

    const motherTag = animal.mother_tag || "-";
    if (!animal.mother_url || motherTag === "-") {
        return `<td>${motherTag}</td>`;
    }

    return `<td><a href="${animal.mother_url}">${motherTag}</a></td>`;
}

function buildActionsCell(animal, animalTypeCode, tagNumber) {
    const permissions = getUserPermissions();

    if (!animal.is_archived) {
        return "<span class=\"text-muted\">-</span>";
    }

    if (!permissions.can_restore_from_archive) {
        return "<span class=\"text-muted\">Нет прав</span>";
    }

    return `
        <button class="btn btn-outline-success btn-sm" onclick="restoreAnimal('${animalTypeCode}', '${tagNumber}')">
            Восстановить
        </button>
    `;
}

function displayArchive(data) {
    const archiveTable = document.getElementById("archive-list");
    if (!archiveTable) return;

    archiveTable.innerHTML = "";

    data.forEach((animal, index) => {
        const row = document.createElement("tr");
        const tagNumber = animal.tag_number;
        const status = animal.status || "Не указан";
        const statusColor = animal.status_color || "#FFFFFF";
        const archivedDate = formatDateToOutput(animal.archived_date) || "Не указана";
        const age = animal.age || "Не указан";
        const place = animal.place || "Не указано";
        const recordNumber = (currentPage - 1) * pageSize + index + 1;
        const animalInfo = buildAnimalInfo(animal);

        row.innerHTML = `
            <td>${recordNumber}</td>
            <td>${animalInfo.label}</td>
            <td><a href="${animalInfo.detailUrl}">${animal.display_name || tagNumber}</a></td>
            <td style="background-color:${statusColor}">${status}</td>
            ${buildMotherCell(animal)}
            <td>${archivedDate}</td>
            <td>${age}</td>
            <td>${place}</td>
            <td>${formatWeightCell(animal.last_live_weight)}</td>
            <td>${formatWeightCell(animal.carcass_weight)}</td>
            <td>${buildActionsCell(animal, animal.animal_type, tagNumber)}</td>
        `;

        archiveTable.appendChild(row);
    });
}

function getAnimalNameByType(animalType) {
    if (animalType === "Maker") return "баранов-производителей";
    if (animalType === "Sheep") return "овцематок";
    if (animalType === "Ewe") return "ярок";
    if (animalType === "Ram") return "баранчиков";
    if (animalType === "Lamb") return "ягнят";
    return "животных";
}

function updateArchivePagination(response) {
    const pagination = document.getElementById("pagination");
    if (!pagination) return;

    pagination.innerHTML = "";

    const paginationContainer = document.createElement("div");
    paginationContainer.style.display = "flex";
    paginationContainer.style.alignItems = "center";
    paginationContainer.style.justifyContent = "center";
    paginationContainer.style.gap = "15px";

    if (response.previous) {
        const prevButton = document.createElement("button");
        prevButton.innerText = "Предыдущая";
        prevButton.className = "btn btn-outline-primary btn-sm";
        prevButton.onclick = () => fetchArchive(currentPage - 1);
        paginationContainer.appendChild(prevButton);
    } else {
        const emptyLeft = document.createElement("div");
        emptyLeft.style.width = "100px";
        paginationContainer.appendChild(emptyLeft);
    }

    const urlParams = getUrlParams();
    const animalType = urlParams.get("type") || "";
    const pageInfo = document.createElement("span");
    pageInfo.innerText = `Страница ${currentPage} (всего: ${response.count} ${getAnimalNameByType(animalType)})`;
    pageInfo.style.fontWeight = "500";
    pageInfo.style.minWidth = "260px";
    pageInfo.style.textAlign = "center";
    paginationContainer.appendChild(pageInfo);

    if (response.next) {
        const nextButton = document.createElement("button");
        nextButton.innerText = "Следующая";
        nextButton.className = "btn btn-outline-primary btn-sm";
        nextButton.onclick = () => fetchArchive(currentPage + 1);
        paginationContainer.appendChild(nextButton);
    } else {
        const emptyRight = document.createElement("div");
        emptyRight.style.width = "100px";
        paginationContainer.appendChild(emptyRight);
    }

    pagination.appendChild(paginationContainer);
}

async function loadArchiveStatuses() {
    try {
        const response = await apiRequest("/veterinary/api/status/?page_size=200");
        const statuses = response.results || response;

        const archiveStatuses = statuses.filter((status) =>
            ["Убой", "Убыл", "Продажа на мясо", "Продажа на племя"].includes(status.status_type)
        );

        const statusSelect = document.getElementById("status-filter");
        if (!statusSelect) return;

        statusSelect.innerHTML = '<option value="">Все статусы</option>';
        archiveStatuses.forEach((status) => {
            const option = document.createElement("option");
            option.value = status.id;
            option.text = status.status_type;
            statusSelect.add(option);
        });
    } catch (error) {
        console.error("Ошибка при загрузке статусов:", error);
    }
}

async function fetchArchive(page = 1) {
    try {
        const paramsFromUrl = getUrlParams();
        const requestParams = new URLSearchParams();

        requestParams.set("page", page);
        requestParams.set("page_size", pageSize);

        const supportedParams = [
            "search",
            "type",
            "animal_status",
            "place",
            "archive_date_from",
            "archive_date_to",
            "mother_tag",
        ];

        supportedParams.forEach((key) => {
            const value = paramsFromUrl.get(key);
            if (value) {
                requestParams.set(key, value);
            }
        });

        currentPage = page;
        const response = await apiRequest(`/animals/archive/?${requestParams.toString()}`);

        if (response && response.results) {
            displayArchive(response.results);
            updateArchivePagination(response);
            return;
        }

        if (Array.isArray(response)) {
            displayArchive(response);
            updateArchivePagination({ previous: null, next: null, count: response.length });
            return;
        }

        console.error("Неожиданный формат ответа:", response);
    } catch (error) {
        console.error("Ошибка при загрузке архива:", error);
    }
}

function performArchiveSearch() {
    const animalType = document.getElementById("animal-type-filter")?.value || "";
    const status = document.getElementById("status-filter")?.value || "";
    const place = document.getElementById("place-filter")?.value || "";
    const search = document.getElementById("archive-search")?.value || "";
    const archiveDateFrom = document.getElementById("archive-date-from")?.value || "";
    const archiveDateTo = document.getElementById("archive-date-to")?.value || "";
    const motherTag = document.getElementById("mother-tag-filter")?.value || "";

    toggleMotherFilterByType(animalType);

    const params = getUrlParams();
    const values = {
        search,
        type: animalType,
        animal_status: status,
        place,
        archive_date_from: archiveDateFrom,
        archive_date_to: archiveDateTo,
        mother_tag: animalType === "Lamb" ? motherTag : "",
    };

    Object.entries(values).forEach(([key, value]) => {
        const trimmed = typeof value === "string" ? value.trim() : value;
        if (trimmed) {
            params.set(key, trimmed);
        } else {
            params.delete(key);
        }
    });

    setUrlParams(params);
    fetchArchive(1);
}

function exportArchiveToExcel() {
    const animalType = document.getElementById("animal-type-filter")?.value || "";
    const status = document.getElementById("status-filter")?.value || "";
    const place = document.getElementById("place-filter")?.value || "";
    const search = document.getElementById("archive-search")?.value?.trim() || "";
    const archiveDateFrom = document.getElementById("archive-date-from")?.value || "";
    const archiveDateTo = document.getElementById("archive-date-to")?.value || "";
    const motherTag = document.getElementById("mother-tag-filter")?.value?.trim() || "";

    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (animalType) params.set("type", animalType);
    if (status) params.set("animal_status", status);
    if (place) params.set("place", place);
    if (archiveDateFrom) params.set("archive_date_from", archiveDateFrom);
    if (archiveDateTo) params.set("archive_date_to", archiveDateTo);
    if (animalType === "Lamb" && motherTag) params.set("mother_tag", motherTag);

    window.location.href = `/animals/api/archive/export-excel/?${params.toString()}`;
}

async function loadRestoreStatuses() {
    try {
        const response = await apiRequest("/veterinary/api/status/?page_size=200");
        const statuses = response.results || response;

        const activeStatuses = statuses.filter((status) =>
            !["Убыл", "Убой", "Продажа на мясо", "Продажа на племя"].includes(status.status_type)
        );

        const statusSelect = document.getElementById("restore-status-select");
        if (!statusSelect) return;

        statusSelect.innerHTML = '<option value="">Выберите статус</option>';
        if (activeStatuses.length === 0) {
            statusSelect.innerHTML = '<option value="">Нет доступных статусов</option>';
            return;
        }

        activeStatuses.forEach((status) => {
            const option = document.createElement("option");
            option.value = status.id;
            option.textContent = status.status_type;
            statusSelect.appendChild(option);
        });
    } catch (error) {
        console.error("Ошибка при загрузке статусов:", error);
        const statusSelect = document.getElementById("restore-status-select");
        if (statusSelect) {
            statusSelect.innerHTML = '<option value="">Ошибка загрузки статусов</option>';
        }
    }
}

async function openRestoreModal(animalType, tagNumber) {
    const modal = document.getElementById("restore-modal");
    const confirmButton = document.getElementById("restore-confirm-button");

    await loadRestoreStatuses();

    if (modal) {
        modal.style.display = "block";
    }

    if (confirmButton) {
        confirmButton.onclick = () => performRestore(animalType, tagNumber);
    }
}

function closeRestoreModal() {
    const modal = document.getElementById("restore-modal");
    if (modal) {
        modal.style.display = "none";
    }
}

async function performRestore(animalType, tagNumber) {
    const statusId = document.getElementById("restore-status-select")?.value;
    if (!statusId) {
        alert("Пожалуйста, выберите статус для животного");
        return;
    }

    try {
        let restoreUrl = "";
        if (animalType === "Maker") restoreUrl = `/animals/maker/${tagNumber}/restore/`;
        if (animalType === "Ram") restoreUrl = `/animals/ram/${tagNumber}/restore/`;
        if (animalType === "Ewe") restoreUrl = `/animals/ewe/${tagNumber}/restore/`;
        if (animalType === "Sheep") restoreUrl = `/animals/sheep/${tagNumber}/restore/`;

        if (!restoreUrl) {
            throw new Error("Неизвестный тип животного");
        }

        await apiRequest(restoreUrl, "POST", { status_id: statusId });
        alert("Животное успешно восстановлено из архива");
        closeRestoreModal();
        fetchArchive(currentPage);
    } catch (error) {
        console.error("Ошибка при восстановлении животного:", error);
        alert("Ошибка при восстановлении животного");
    }
}

function restoreAnimal(animalType, tagNumber) {
    openRestoreModal(animalType, tagNumber);
}

function hydrateFiltersFromUrl() {
    const params = getUrlParams();

    const search = params.get("search") || "";
    const animalType = params.get("type") || window.initialAnimalType || "";
    const archiveDateFrom = params.get("archive_date_from") || "";
    const archiveDateTo = params.get("archive_date_to") || "";
    const motherTag = params.get("mother_tag") || "";

    const searchInput = document.getElementById("archive-search");
    const typeFilter = document.getElementById("animal-type-filter");
    const dateFromInput = document.getElementById("archive-date-from");
    const dateToInput = document.getElementById("archive-date-to");
    const motherTagInput = document.getElementById("mother-tag-filter");

    if (searchInput) searchInput.value = search;
    if (typeFilter) typeFilter.value = animalType;
    if (dateFromInput) dateFromInput.value = archiveDateFrom;
    if (dateToInput) dateToInput.value = archiveDateTo;
    if (motherTagInput) motherTagInput.value = motherTag;

    toggleMotherFilterByType(animalType);
}

document.addEventListener("DOMContentLoaded", async () => {
    hydrateFiltersFromUrl();

    await loadArchiveStatuses();

    const params = getUrlParams();
    const selectedStatus = params.get("animal_status");
    if (selectedStatus) {
        const statusSelect = document.getElementById("status-filter");
        if (statusSelect) {
            statusSelect.value = selectedStatus;
        }
    }

    const typeSelect = document.getElementById("animal-type-filter");
    if (typeSelect) {
        typeSelect.addEventListener("change", () => {
            toggleMotherFilterByType(typeSelect.value);
        });
    }

    fetchArchive(1);
});

window.filterArchiveData = performArchiveSearch;
window.performArchiveSearch = performArchiveSearch;
window.exportArchiveToExcel = exportArchiveToExcel;
window.restoreAnimal = restoreAnimal;
window.closeRestoreModal = closeRestoreModal;

