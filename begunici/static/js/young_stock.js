import {
    addRshnPresenceFilter,
    apiRequest,
    getCheckboxFilterValue,
    setCheckboxFilterValue,
} from "./utils.js";

let selectedYoungStock = new Map();
let currentPage = 1;
let currentFilters = {};

function getSelectionKey(animalType, tagNumber) {
    return `${animalType}:${tagNumber}`;
}

function saveSelectedYoungStock() {
    sessionStorage.setItem("selectedYoungStock", JSON.stringify(Array.from(selectedYoungStock.values())));
}

function loadSelectedYoungStock() {
    const saved = sessionStorage.getItem("selectedYoungStock");
    if (!saved) return;

    try {
        selectedYoungStock = new Map();
        JSON.parse(saved).forEach((item) => {
            const animalType = String(item?.animalType || "").trim();
            const tagNumber = String(item?.tagNumber || "").trim();
            if (!animalType || !tagNumber || tagNumber === "undefined" || tagNumber === "null") return;
            selectedYoungStock.set(getSelectionKey(animalType, tagNumber), { animalType, tagNumber });
        });
    } catch (error) {
        console.error("Ошибка восстановления выделенного приплода:", error);
        selectedYoungStock = new Map();
    }
}

async function pruneStaleSelectedYoungStock() {
    const staleKeys = [];

    await Promise.all(Array.from(selectedYoungStock.entries()).map(async ([key, item]) => {
        const animalType = String(item?.animalType || "").trim();
        const tagNumber = String(item?.tagNumber || "").trim();
        if (!animalType || !tagNumber) {
            staleKeys.push(key);
            return;
        }

        try {
            const response = await fetch(`/animals/${animalType}/${encodeURIComponent(tagNumber)}/`);
            if (!response.ok) {
                staleKeys.push(key);
                return;
            }

            const animal = await response.json();
            if (animal?.is_archived) {
                staleKeys.push(key);
            }
        } catch (error) {
            console.warn("Не удалось проверить выбранный приплод перед архивацией:", item, error);
        }
    }));

    if (staleKeys.length > 0) {
        staleKeys.forEach((key) => selectedYoungStock.delete(key));
        saveSelectedYoungStock();
        document.querySelectorAll(".select-young-stock").forEach((checkbox) => {
            if (staleKeys.includes(checkbox.dataset.key)) {
                checkbox.checked = false;
            }
        });
        toggleSelectedActions();
        console.info("Устаревший выбранный приплод удален из списка:", staleKeys);
    }

    return staleKeys;
}

loadSelectedYoungStock();

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function linkedText(text, url) {
    const safeText = escapeHtml(text || "-");
    return url ? `<a href="${escapeHtml(url)}">${safeText}</a>` : safeText;
}

function toggleYoungStockAdditionalFilters() {
    const filtersBlock = document.getElementById("young-stock-advanced-filters");
    if (!filtersBlock) return;
    filtersBlock.style.display =
        filtersBlock.style.display === "none" || filtersBlock.style.display === "" ? "block" : "none";
}

function getYoungStockFiltersFromInputs() {
    return {
        search: document.getElementById("young-stock-search")?.value || "",
        birth_date_from: document.getElementById("young-stock-birth-date-from")?.value || "",
        birth_date_to: document.getElementById("young-stock-birth-date-to")?.value || "",
        date_otbivka_from: document.getElementById("young-stock-date-otbivka-from-filter")?.value || "",
        date_otbivka_to: document.getElementById("young-stock-date-otbivka-to-filter")?.value || "",
        age_min: document.getElementById("young-stock-age-min-filter")?.value || "",
        age_max: document.getElementById("young-stock-age-max-filter")?.value || "",
        father_tag: document.getElementById("young-stock-father-tag-filter")?.value || "",
        mother_tag: document.getElementById("young-stock-mother-tag-filter")?.value || "",
        animal_type: document.getElementById("young-stock-animal-type-filter")?.value || "",
        has_rshn_tag: getCheckboxFilterValue("young-stock-has-rshn-tag-filter"),
        is_reject: getCheckboxFilterValue("young-stock-is-reject-filter"),
    };
}

function initializeYoungStockFiltersFromUrl() {
    addRshnPresenceFilter("young-stock-advanced-filters", "young-stock-has-rshn-tag-filter");

    const urlParams = new URLSearchParams(window.location.search);
    const filters = {
        search: urlParams.get("search") || "",
        birth_date_from: urlParams.get("birth_date_from") || "",
        birth_date_to: urlParams.get("birth_date_to") || "",
        date_otbivka_from: urlParams.get("date_otbivka_from") || "",
        date_otbivka_to: urlParams.get("date_otbivka_to") || "",
        age_min: urlParams.get("age_min") || "",
        age_max: urlParams.get("age_max") || "",
        father_tag: urlParams.get("father_tag") || "",
        mother_tag: urlParams.get("mother_tag") || "",
        animal_type: urlParams.get("animal_type") || "",
        has_rshn_tag: urlParams.get("has_rshn_tag") || "",
        is_reject: urlParams.get("is_reject") || "",
    };

    const inputs = {
        search: "young-stock-search",
        birth_date_from: "young-stock-birth-date-from",
        birth_date_to: "young-stock-birth-date-to",
        date_otbivka_from: "young-stock-date-otbivka-from-filter",
        date_otbivka_to: "young-stock-date-otbivka-to-filter",
        age_min: "young-stock-age-min-filter",
        age_max: "young-stock-age-max-filter",
        father_tag: "young-stock-father-tag-filter",
        mother_tag: "young-stock-mother-tag-filter",
        animal_type: "young-stock-animal-type-filter",
    };

    Object.entries(inputs).forEach(([key, id]) => {
        const element = document.getElementById(id);
        if (element) element.value = filters[key];
    });

    setCheckboxFilterValue("young-stock-has-rshn-tag-filter", filters.has_rshn_tag);
    setCheckboxFilterValue("young-stock-is-reject-filter", filters.is_reject);

    if (filters.birth_date_from || filters.birth_date_to || filters.date_otbivka_from || filters.date_otbivka_to || filters.age_min || filters.age_max || filters.father_tag || filters.mother_tag || filters.animal_type || filters.has_rshn_tag || filters.is_reject) {
        const filtersBlock = document.getElementById("young-stock-advanced-filters");
        if (filtersBlock) filtersBlock.style.display = "block";
    }

    return filters;
}

document.addEventListener("DOMContentLoaded", function () {
    const initialFilters = initializeYoungStockFiltersFromUrl();
    fetchYoungStock(1, initialFilters);
});

async function fetchYoungStock(page = 1, filters = {}) {
    try {
        currentFilters = { ...currentFilters, ...(filters || {}) };

        const urlParams = new URLSearchParams(window.location.search);
        const filterKeys = ["search", "birth_date_from", "birth_date_to", "date_otbivka_from", "date_otbivka_to", "age_min", "age_max", "father_tag", "mother_tag", "animal_type", "has_rshn_tag", "is_reject"];
        filterKeys.forEach((key) => {
            const value = (currentFilters[key] || "").toString().trim();
            currentFilters[key] = value;
            if (value) {
                urlParams.set(key, value);
            } else {
                urlParams.delete(key);
            }
        });
        window.history.replaceState({}, "", `${window.location.pathname}${urlParams.toString() ? "?" + urlParams.toString() : ""}`);

        const params = new URLSearchParams();
        params.set("page", page);
        filterKeys.forEach((key) => {
            if (currentFilters[key]) params.set(key, currentFilters[key]);
        });

        currentPage = page;
        const response = await apiRequest(`/animals/api/young-stock/?${params.toString()}`);
        const animals = Array.isArray(response) ? response : response.results || response;
        if (!animals) {
            alert("Ошибка: не удалось получить список приплода.");
            return;
        }

        renderYoungStock(animals);
        updatePagination(response);
    } catch (error) {
        console.error("Ошибка загрузки приплода:", error);
        alert("Ошибка при загрузке списка приплода.");
    }
}

function renderYoungStock(animals) {
    const list = document.getElementById("young-stock-list");
    if (!list) return;

    const rows = animals.map((animal, index) => {
        const recordNumber = (currentPage - 1) * 10 + index + 1;
        const tagNumber = animal.tag_number || "";
        const selectionKey = getSelectionKey(animal.animal_type, tagNumber);

        return `
            <tr class="${animal.is_reject ? "table-warning" : ""}">
                <td>
                    <input type="checkbox"
                           class="select-young-stock"
                           data-key="${escapeHtml(selectionKey)}"
                           data-type="${escapeHtml(animal.animal_type)}"
                           data-tag="${escapeHtml(tagNumber)}">
                </td>
                <td>${recordNumber}</td>
                <td>${linkedText(tagNumber, animal.tag_url)}</td>
                <td>${escapeHtml(animal.birth_type || "-")}</td>
                <td>${escapeHtml(animal.birth_date || "-")}</td>
                <td>${escapeHtml(animal.birth_weight || "-")}</td>
                <td>${escapeHtml(animal.weaning || "-")}</td>
                <td>${linkedText(animal.mother_tag, animal.mother_url)}</td>
            </tr>
        `;
    });

    list.innerHTML = rows.join("");

    document.querySelectorAll(".select-young-stock").forEach((checkbox) => {
        checkbox.addEventListener("click", (event) => toggleSelectYoungStock(event.target));
        if (selectedYoungStock.has(checkbox.dataset.key)) {
            checkbox.checked = true;
        }
    });

    const visibleCheckboxes = Array.from(document.querySelectorAll(".select-young-stock"));
    const selectAllCheckbox = document.getElementById("select-all");
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = visibleCheckboxes.length > 0 && visibleCheckboxes.every((checkbox) => checkbox.checked);
    }

    toggleSelectedActions();
}

function toggleSelectAll(checkbox) {
    document.querySelectorAll(".select-young-stock").forEach((item) => {
        const animalType = item.dataset.type;
        const tagNumber = item.dataset.tag;
        const key = item.dataset.key;
        item.checked = checkbox.checked;

        if (checkbox.checked) {
            selectedYoungStock.set(key, { animalType, tagNumber });
        } else {
            selectedYoungStock.delete(key);
        }
    });

    saveSelectedYoungStock();
    console.log("Текущее состояние selectedYoungStock после выбора всех:", selectedYoungStock);
    toggleSelectedActions();
}

function toggleSelectYoungStock(checkbox) {
    const animalType = checkbox.dataset.type;
    const tagNumber = checkbox.dataset.tag;
    const key = checkbox.dataset.key;

    if (checkbox.checked) {
        selectedYoungStock.set(key, { animalType, tagNumber });
    } else {
        selectedYoungStock.delete(key);
    }

    saveSelectedYoungStock();
    console.log("Текущее состояние selectedYoungStock:", selectedYoungStock);

    const visibleCheckboxes = Array.from(document.querySelectorAll(".select-young-stock"));
    const selectAllCheckbox = document.getElementById("select-all");
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = visibleCheckboxes.length > 0 && visibleCheckboxes.every((item) => item.checked);
    }

    toggleSelectedActions();
}

function toggleSelectedActions() {
    const selectedActionsDiv = document.getElementById("selected-actions");
    if (!selectedActionsDiv) return;
    selectedActionsDiv.style.display = selectedYoungStock.size > 0 ? "block" : "none";
}

async function deleteSelectedYoungStock() {
    const selected = Array.from(selectedYoungStock.values());
    if (selected.length === 0) {
        alert("Нет выбранного приплода для удаления.");
        return;
    }

    const modal = document.getElementById("delete-modal");
    const modalMessage = document.getElementById("delete-modal-message");
    const confirmButton = document.getElementById("delete-confirm-button");
    if (!modal || !modalMessage || !confirmButton) return;

    modalMessage.textContent = `Вы уверены, что хотите удалить выбранные бирки: ${selected.map((item) => item.tagNumber).join(", ")}?`;
    modal.style.display = "block";

    confirmButton.onclick = async () => {
        try {
            for (const item of selected) {
                await apiRequest(`/animals/${item.animalType}/${encodeURIComponent(item.tagNumber)}/`, "DELETE");
            }

            selectedYoungStock.clear();
            saveSelectedYoungStock();
            closeDeleteModal();
            toggleSelectedActions();
            fetchYoungStock(currentPage, currentFilters);
            alert("Выбранный приплод успешно удалён.");
        } catch (error) {
            console.error("Ошибка удаления приплода:", error);
            alert("Ошибка при удалении выбранного приплода: " + (error.message || "Неизвестная ошибка"));
        }
    };
}

function closeDeleteModal() {
    const modal = document.getElementById("delete-modal");
    if (modal) modal.style.display = "none";
}

async function openArchiveModal() {
    const staleKeys = await pruneStaleSelectedYoungStock();
    const archiveAnimals = Array.from(selectedYoungStock.values()).filter((item) => item?.animalType && item?.tagNumber);

    if (archiveAnimals.length === 0) {
        alert(staleKeys.length > 0
            ? "Выбранный приплод уже перенесен в архив или не найден. Выбор очищен."
            : "Нет выбранного приплода для переноса.");
        return;
    }

    const modal = document.getElementById("archive-modal");
    if (!modal) return;

    modal.style.display = "block";
    const now = new Date();
    const offset = now.getTimezoneOffset();
    const localDate = new Date(now.getTime() - offset * 60000).toISOString().split("T")[0];
    const archiveDateInput = document.getElementById("archive-status-date");
    if (archiveDateInput) archiveDateInput.value = localDate;

    const carcassWeightInput = document.getElementById("archive-carcass-weight");
    if (carcassWeightInput) carcassWeightInput.value = "";

    window.archiveActModal?.reset();
    if (archiveAnimals.length > 1) {
        window.archiveActModal?.startSequentialArchive(archiveAnimals);
    } else {
        window.archiveActModal?.setSelectedAnimals(archiveAnimals);
    }
    loadArchiveStatuses();
}

function closeArchiveModal() {
    const modal = document.getElementById("archive-modal");
    if (modal) modal.style.display = "none";
}

function toggleArchiveActNumberField() {
    window.archiveActModal?.toggle();
}

async function loadArchiveStatuses() {
    try {
        const response = await apiRequest("/veterinary/api/status/?page_size=100");
        const statuses = response.results || response;
        const archiveStatuses = statuses.filter((status) =>
            ["Падеж", "Вынужденная прирезка", "Реализация в живом весе", "Продажа на племя", "Убой на мясо"].includes(status.status_type)
        );

        const statusSelect = document.getElementById("archive-status-select");
        if (!statusSelect) return;
        statusSelect.innerHTML = "";

        if (archiveStatuses.length === 0) {
            alert("Нет статусов для переноса в архив. Создайте необходимые статусы.");
            closeArchiveModal();
            return;
        }

        archiveStatuses.forEach((status) => {
            const option = document.createElement("option");
            option.value = status.id;
            option.text = status.status_type;
            statusSelect.add(option);
        });
        statusSelect.onchange = toggleArchiveActNumberField;
        toggleArchiveActNumberField();
    } catch (error) {
        console.error("Ошибка загрузки архивных статусов:", error);
    }
}

async function applyArchiveStatus() {
    const selected = Array.from(selectedYoungStock.values()).filter((item) => item?.animalType && item?.tagNumber);
    if (selected.length === 0) {
        alert("Нет выбранного приплода для переноса.");
        return;
    }

    const archiveStep = window.archiveActModal?.collectEntriesForSelected?.(selected);
    if (archiveStep?.error) {
        alert(archiveStep.error);
        return;
    }
    if (!archiveStep?.complete) {
        return;
    }

    try {

        const downloadedArchiveActKeys = new Set();
        const archiveActDownloads = [];

        for (const entry of archiveStep.entries) {
            const item = entry.animal;
            await apiRequest(`/animals/${item.animalType}/${encodeURIComponent(item.tagNumber)}/`, "PATCH", {
                animal_status_id: entry.statusId,
                status_date: entry.statusDate,
                carcass_weight: entry.carcassWeight,
                ...entry.archiveActPayload,
            });
            const archiveActDownloadKey = entry.archiveActPayload.archive_act_group_key || `${item.animalType}:${item.tagNumber}`;
            if (entry.archiveActPayload.archive_act_download && !downloadedArchiveActKeys.has(archiveActDownloadKey)) {
                downloadedArchiveActKeys.add(archiveActDownloadKey);
                archiveActDownloads.push({ animalType: item.animalType, tagNumber: item.tagNumber });
            }
        }

        archiveActDownloads.forEach((download) => {
            window.archiveActModal?.downloadArchiveAct(download.animalType, download.tagNumber);
        });

        selectedYoungStock.clear();
        saveSelectedYoungStock();
        const selectAllCheckbox = document.getElementById("select-all");
        if (selectAllCheckbox) selectAllCheckbox.checked = false;

        closeArchiveModal();
        toggleSelectedActions();
        fetchYoungStock(currentPage, currentFilters);
        alert("Выбранный приплод успешно перенесён в архив.");
    } catch (error) {
        console.error("Ошибка переноса приплода в архив:", error);
        alert("Ошибка при переносе выбранного приплода в архив: " + (error.message || "Неизвестная ошибка"));
    }
}

function updatePagination(response) {
    const pagination = document.getElementById("pagination");
    if (!pagination) return;

    pagination.innerHTML = "";
    const container = document.createElement("div");
    container.style.display = "flex";
    container.style.alignItems = "center";
    container.style.justifyContent = "center";
    container.style.gap = "15px";

    if (response.previous) {
        const prevButton = document.createElement("button");
        prevButton.innerText = "Предыдущая";
        prevButton.className = "btn btn-outline-primary btn-sm";
        prevButton.onclick = () => fetchYoungStock(currentPage - 1, currentFilters);
        container.appendChild(prevButton);
    } else {
        const emptyDiv = document.createElement("div");
        emptyDiv.style.width = "90px";
        container.appendChild(emptyDiv);
    }

    const pageInfo = document.createElement("span");
    pageInfo.innerText = `Страница ${currentPage}`;
    pageInfo.style.fontWeight = "500";
    pageInfo.style.minWidth = "120px";
    pageInfo.style.textAlign = "center";
    container.appendChild(pageInfo);

    if (response.next) {
        const nextButton = document.createElement("button");
        nextButton.innerText = "Следующая";
        nextButton.className = "btn btn-outline-primary btn-sm";
        nextButton.onclick = () => fetchYoungStock(currentPage + 1, currentFilters);
        container.appendChild(nextButton);
    } else {
        const emptyDiv = document.createElement("div");
        emptyDiv.style.width = "90px";
        container.appendChild(emptyDiv);
    }

    pagination.appendChild(container);
}

function exportYoungStock() {
    const params = new URLSearchParams();
    const filters = getYoungStockFiltersFromInputs();
    Object.entries(filters).forEach(([key, value]) => {
        const cleanValue = String(value || "").trim();
        if (cleanValue) params.set(key, cleanValue);
    });

    const selected = Array.from(selectedYoungStock.values())
        .map((item) => `${item.animalType}:${item.tagNumber}`)
        .join(",");
    if (selected) {
        params.set("selected", selected);
    }

    window.location.href = `/animals/api/young-stock/export-excel/?${params.toString()}`;
}

window.addEventListener("beforeunload", function () {
    if (!window.location.pathname.includes("/animals/young-stock/")) {
        sessionStorage.removeItem("selectedYoungStock");
    }
});

window.fetchYoungStock = fetchYoungStock;
window.getYoungStockFiltersFromInputs = getYoungStockFiltersFromInputs;
window.toggleYoungStockAdditionalFilters = toggleYoungStockAdditionalFilters;
window.toggleSelectAll = toggleSelectAll;
window.deleteSelectedYoungStock = deleteSelectedYoungStock;
window.closeDeleteModal = closeDeleteModal;
window.openArchiveModal = openArchiveModal;
window.closeArchiveModal = closeArchiveModal;
window.applyArchiveStatus = applyArchiveStatus;
window.exportYoungStock = exportYoungStock;



