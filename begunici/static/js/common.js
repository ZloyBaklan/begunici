import { apiRequest, formatDateToOutput } from "./utils.js";

let selectedAnimals = new Map();
let currentPage = 1;
let currentFilters = {};

const typeDisplayMap = {
    maker: "Баран-Производитель",
    ram: "Баранчик",
    ewe: "Ярка",
    sheep: "Овцематка",
};

function getSelectionKey(animalType, tagNumber) {
    return `${animalType}:${tagNumber}`;
}

function saveSelectedAnimals() {
    sessionStorage.setItem("selectedCommonAnimals", JSON.stringify(Array.from(selectedAnimals.values())));
}

function loadSelectedAnimals() {
    const saved = sessionStorage.getItem("selectedCommonAnimals");
    if (!saved) return;

    try {
        const parsed = JSON.parse(saved);
        selectedAnimals = new Map();
        parsed.forEach((item) => {
            const key = getSelectionKey(item.animalType, item.tagNumber);
            selectedAnimals.set(key, item);
        });
    } catch (error) {
        console.error("Ошибка восстановления выделенных животных:", error);
        selectedAnimals = new Map();
    }
}

loadSelectedAnimals();

function toggleCommonAdditionalFilters() {
    const filtersBlock = document.getElementById("common-advanced-filters");
    if (!filtersBlock) return;

    filtersBlock.style.display =
        filtersBlock.style.display === "none" || filtersBlock.style.display === "" ? "block" : "none";
}

function getCommonFiltersFromInputs() {
    return {
        search: document.getElementById("common-search")?.value || "",
        birth_date_from: document.getElementById("common-birth-date-from")?.value || "",
        birth_date_to: document.getElementById("common-birth-date-to")?.value || "",
        age_min: document.getElementById("common-age-min-filter")?.value || "",
        age_max: document.getElementById("common-age-max-filter")?.value || "",
        father_tag: document.getElementById("common-father-tag-filter")?.value || "",
        mother_tag: document.getElementById("common-mother-tag-filter")?.value || "",
        animal_type: document.getElementById("common-animal-type-filter")?.value || "",
    };
}

function initializeCommonFiltersFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    const filters = {
        search: urlParams.get("search") || "",
        birth_date_from: urlParams.get("birth_date_from") || "",
        birth_date_to: urlParams.get("birth_date_to") || "",
        age_min: urlParams.get("age_min") || "",
        age_max: urlParams.get("age_max") || "",
        father_tag: urlParams.get("father_tag") || "",
        mother_tag: urlParams.get("mother_tag") || "",
        animal_type: urlParams.get("animal_type") || "",
    };

    const searchInput = document.getElementById("common-search");
    if (searchInput) searchInput.value = filters.search;

    const birthDateFromInput = document.getElementById("common-birth-date-from");
    if (birthDateFromInput) birthDateFromInput.value = filters.birth_date_from;

    const birthDateToInput = document.getElementById("common-birth-date-to");
    if (birthDateToInput) birthDateToInput.value = filters.birth_date_to;

    const ageMinInput = document.getElementById("common-age-min-filter");
    if (ageMinInput) ageMinInput.value = filters.age_min;

    const ageMaxInput = document.getElementById("common-age-max-filter");
    if (ageMaxInput) ageMaxInput.value = filters.age_max;

    const fatherTagInput = document.getElementById("common-father-tag-filter");
    if (fatherTagInput) fatherTagInput.value = filters.father_tag;

    const motherTagInput = document.getElementById("common-mother-tag-filter");
    if (motherTagInput) motherTagInput.value = filters.mother_tag;

    const animalTypeInput = document.getElementById("common-animal-type-filter");
    if (animalTypeInput) animalTypeInput.value = filters.animal_type;

    if (filters.birth_date_from || filters.birth_date_to || filters.age_min || filters.age_max || filters.father_tag || filters.mother_tag || filters.animal_type) {
        const filtersBlock = document.getElementById("common-advanced-filters");
        if (filtersBlock) {
            filtersBlock.style.display = "block";
        }
    }

    return filters;
}

function updateCreateFormByType() {
    const selectedType = document.getElementById("create-animal-type")?.value || "";
    const makerFields = document.getElementById("maker-fields");
    const createButton = document.getElementById("create-common-button");
    const formTitle = document.getElementById("form-title");

    if (makerFields) {
        makerFields.style.display = selectedType === "maker" ? "block" : "none";
    }

    const typeLabel = typeDisplayMap[selectedType] || "животное";

    if (createButton) {
        createButton.textContent = selectedType ? `Создать (${typeLabel})` : "Создать животное";
    }

    if (formTitle) {
        formTitle.textContent = selectedType ? `Создать: ${typeLabel}` : "Создать животное";
    }
}

document.addEventListener("DOMContentLoaded", function () {
    const initialFilters = initializeCommonFiltersFromUrl();
    fetchCommonAnimals(1, initialFilters);
    loadStatuses();
    loadPlaces();

    const createTypeSelect = document.getElementById("create-animal-type");
    if (createTypeSelect) {
        createTypeSelect.addEventListener("change", updateCreateFormByType);
    }

    updateCreateFormByType();
});

async function loadStatuses() {
    try {
        const response = await apiRequest("/veterinary/api/status/?page_size=100");
        const statuses = response.results || response;
        const select = document.getElementById("animal_status");
        if (!select) return;

        select.innerHTML = "";
        statuses.forEach((status) => {
            const option = document.createElement("option");
            option.value = status.id;
            option.textContent = status.status_type;
            select.appendChild(option);
        });
    } catch (error) {
        console.error("Ошибка загрузки статусов:", error);
    }
}

async function loadPlaces() {
    try {
        const response = await apiRequest("/veterinary/api/place/?page_size=100");
        const places = response.results || response;
        const select = document.getElementById("place");
        if (!select) return;

        select.innerHTML = "";
        places.forEach((place) => {
            const option = document.createElement("option");
            option.value = place.id;
            option.textContent = place.sheepfold;
            select.appendChild(option);
        });
    } catch (error) {
        console.error("Ошибка загрузки мест:", error);
    }
}

async function saveCommonAnimal() {
    const animalType = document.getElementById("create-animal-type")?.value || "";

    if (!animalType) {
        alert("Выберите тип животного");
        return;
    }

    const endpointMap = {
        maker: "/animals/maker/",
        ram: "/animals/ram/",
        ewe: "/animals/ewe/",
        sheep: "/animals/sheep/",
    };

    const statusIdRaw = document.getElementById("animal_status")?.value;
    const placeIdRaw = document.getElementById("place")?.value;
    const tagNumber = document.getElementById("tag")?.value?.trim();

    if (!tagNumber || !statusIdRaw || !placeIdRaw) {
        alert("Заполните обязательные поля: тип, бирка, статус, овчарня.");
        return;
    }

    const data = {
        tag_number: tagNumber,
        animal_status_id: parseInt(statusIdRaw, 10),
        birth_date: document.getElementById("birth_date")?.value || null,
        place_id: parseInt(placeIdRaw, 10),
        rshn_tag: document.getElementById("rshn_tag")?.value || null,
        dorper_percentage: document.getElementById("dorper_percentage")?.value || null,
        is_manual_dorper: !!document.getElementById("dorper_percentage")?.value,
        note: document.getElementById("note")?.value || "",
    };

    if (animalType === "maker") {
        const plemstatus = document.getElementById("plemstatus")?.value?.trim() || "";
        const workingCondition = document.getElementById("working_condition")?.value?.trim() || "";

        if (!plemstatus || !workingCondition) {
            alert("Для барана-производителя заполните поля: Племенной статус и Рабочее состояние.");
            return;
        }

        data.plemstatus = plemstatus;
        data.working_condition = workingCondition;
        data.name = document.getElementById("name")?.value || null;
    }

    try {
        await apiRequest(endpointMap[animalType], "POST", data);
        alert("Животное успешно создано");

        const form = document.getElementById("create-common-form");
        if (form) form.reset();

        updateCreateFormByType();
        fetchCommonAnimals(1, currentFilters);
    } catch (error) {
        console.error("Ошибка создания животного:", error);
        alert(`Ошибка: ${error.message || "проверьте введенные данные"}`);
    }
}

async function fetchCommonAnimals(page = 1, filters = {}) {
    try {
        if (typeof filters === "string") {
            filters = { search: filters };
        }

        if (!filters || typeof filters !== "object") {
            filters = {};
        }

        currentFilters = { ...currentFilters, ...filters };

        const urlParams = new URLSearchParams(window.location.search);
        const filterKeys = ["search", "birth_date_from", "birth_date_to", "age_min", "age_max", "father_tag", "mother_tag", "animal_type"];

        filterKeys.forEach((key) => {
            const value = (currentFilters[key] || "").toString().trim();
            currentFilters[key] = value;

            if (value) {
                urlParams.set(key, value);
            } else {
                urlParams.delete(key);
            }
        });

        const newUrl = `${window.location.pathname}${urlParams.toString() ? "?" + urlParams.toString() : ""}`;
        window.history.replaceState({}, "", newUrl);

        const params = new URLSearchParams();
        params.set("page", page);

        if (currentFilters.search) params.set("search", currentFilters.search);
        if (currentFilters.birth_date_from) params.set("birth_date_from", currentFilters.birth_date_from);
        if (currentFilters.birth_date_to) params.set("birth_date_to", currentFilters.birth_date_to);
        if (currentFilters.age_min) params.set("age_min", currentFilters.age_min);
        if (currentFilters.age_max) params.set("age_max", currentFilters.age_max);
        if (currentFilters.father_tag) params.set("father_tag", currentFilters.father_tag);
        if (currentFilters.mother_tag) params.set("mother_tag", currentFilters.mother_tag);
        if (currentFilters.animal_type) params.set("animal_type", currentFilters.animal_type);

        currentPage = page;
        const response = await apiRequest(`/animals/api/common/?${params.toString()}`);
        const animals = Array.isArray(response) ? response : response.results || response;

        if (!animals) {
            alert("Ошибка: не удалось получить список животных.");
            return;
        }

        renderCommonAnimals(animals);
        updatePagination(response);
    } catch (error) {
        console.error("Ошибка загрузки общего списка животных:", error);
        alert("Ошибка при загрузке общего списка животных.");
    }
}

function renderCommonAnimals(animals) {
    const list = document.getElementById("common-list");
    if (!list) return;

    const rows = [];

    animals.forEach((animal, index) => {
        const recordNumber = (currentPage - 1) * 10 + index + 1;
        const tagNumber = animal.tag?.tag_number || "";
        const displayName = animal.display_name || tagNumber;
        const selectionKey = getSelectionKey(animal.animal_type, tagNumber);
        const statusColor = animal.animal_status ? animal.animal_status.color : "#FFFFFF";
        const statusText = animal.animal_status ? animal.animal_status.status_type : "Нет статуса";

        const weightText = animal.last_weight_date && animal.last_weight !== null
            ? `${animal.last_weight_date}: ${animal.last_weight} кг`
            : "Нет записей";

        const vetText = formatLastVetTreatment(
            animal.last_vet_date,
            animal.last_vet_name,
            animal.last_vet_medication
        );

        rows.push(`
            <tr>
                <td>
                    <input type="checkbox"
                           class="select-common"
                           data-key="${selectionKey}"
                           data-type="${animal.animal_type}"
                           data-tag="${tagNumber}"
                           data-tag-id="${animal.tag_id}"
                           data-animal-id="${animal.tag_id}">
                </td>
                <td>${recordNumber}</td>
                <td>${animal.animal_type_label || typeDisplayMap[animal.animal_type] || "-"}</td>
                <td><a href="/animals/${animal.animal_type}/${tagNumber}/info/">${displayName}</a></td>
                <td style="background-color:${statusColor}">${statusText}</td>
                <td>${animal.age || "-"}</td>
                <td>${animal.place ? animal.place.sheepfold : "Нет данных"}</td>
                <td>${animal.dorper_display || "-"}</td>
                <td>${weightText}</td>
                <td>${vetText}</td>
                <td>${animal.animal_type === "maker" ? (animal.working_condition || "-") : "-"}</td>
                <td>${animal.rshn_tag || "-"}</td>
                <td>${animal.note || ""}</td>
            </tr>
        `);
    });

    list.innerHTML = rows.join("");

    document.querySelectorAll(".select-common").forEach((checkbox) => {
        checkbox.addEventListener("click", (e) => toggleSelectAnimal(e.target));

        const key = checkbox.dataset.key;
        if (selectedAnimals.has(key)) {
            checkbox.checked = true;
        }
    });

    const visibleCheckboxes = Array.from(document.querySelectorAll(".select-common"));
    const allVisibleChecked = visibleCheckboxes.length > 0 && visibleCheckboxes.every((cb) => cb.checked);
    const selectAllCheckbox = document.getElementById("select-all");
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = allVisibleChecked;
    }

    toggleSelectedActions();
}

function formatLastVetTreatment(lastVetDate, lastVetType, lastVetMedication) {
    if (!lastVetDate || !lastVetType) {
        return "Нет записей";
    }

    const formattedDate = formatDateToOutput(lastVetDate);
    const medication = lastVetMedication || "без препарата";
    return `${formattedDate}: ${lastVetType} (${medication})`;
}

function toggleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll(".select-common");

    checkboxes.forEach((cb) => {
        const animalType = cb.dataset.type;
        const tagNumber = cb.dataset.tag;
        const tagId = parseInt(cb.dataset.tagId || "0", 10);
        const key = cb.dataset.key;

        cb.checked = checkbox.checked;

        if (checkbox.checked) {
            selectedAnimals.set(key, {
                animalType,
                tagNumber,
                tagId,
            });
        } else {
            selectedAnimals.delete(key);
        }
    });

    saveSelectedAnimals();
    toggleSelectedActions();
}

function toggleSelectAnimal(checkbox) {
    const animalType = checkbox.dataset.type;
    const tagNumber = checkbox.dataset.tag;
    const tagId = parseInt(checkbox.dataset.tagId || "0", 10);
    const key = checkbox.dataset.key;

    if (checkbox.checked) {
        selectedAnimals.set(key, {
            animalType,
            tagNumber,
            tagId,
        });
    } else {
        selectedAnimals.delete(key);
    }

    saveSelectedAnimals();

    const visibleCheckboxes = Array.from(document.querySelectorAll(".select-common"));
    const allVisibleChecked = visibleCheckboxes.length > 0 && visibleCheckboxes.every((cb) => cb.checked);
    const selectAllCheckbox = document.getElementById("select-all");
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = allVisibleChecked;
    }

    toggleSelectedActions();
}

function toggleSelectedActions() {
    const selectedActionsDiv = document.getElementById("selected-actions");
    if (!selectedActionsDiv) return;

    selectedActionsDiv.style.display = selectedAnimals.size > 0 ? "block" : "none";
}

async function deleteSelectedAnimals() {
    const selected = Array.from(selectedAnimals.values());
    if (selected.length === 0) {
        alert("Нет выбранных животных для удаления");
        return;
    }

    const modal = document.getElementById("delete-modal");
    const modalMessage = document.getElementById("delete-modal-message");
    const confirmButton = document.getElementById("delete-confirm-button");

    if (!modal || !modalMessage || !confirmButton) return;

    modalMessage.textContent = `Вы уверены, что хотите удалить выбранные бирки: ${selected.map((x) => x.tagNumber).join(", ")}?`;
    modal.style.display = "block";

    confirmButton.onclick = async () => {
        try {
            for (const item of selected) {
                await apiRequest(`/animals/${item.animalType}/${item.tagNumber}/`, "DELETE");
            }

            selectedAnimals.clear();
            saveSelectedAnimals();

            const selectAllCheckbox = document.getElementById("select-all");
            if (selectAllCheckbox) selectAllCheckbox.checked = false;

            modal.style.display = "none";
            toggleSelectedActions();
            fetchCommonAnimals(currentPage, currentFilters);
            alert("Выбранные животные успешно удалены");
        } catch (error) {
            console.error("Ошибка удаления животных:", error);
            alert("Ошибка при удалении выбранных животных");
        }
    };
}

function closeDeleteModal() {
    const modal = document.getElementById("delete-modal");
    if (modal) modal.style.display = "none";
}

function openArchiveModal() {
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
    const actNumberInput = document.getElementById("archive-act-number");
    if (actNumberInput) actNumberInput.value = "";
    const actNumberGroup = document.getElementById("archive-act-number-group");
    if (actNumberGroup) actNumberGroup.style.display = "none";

    loadArchiveStatuses();
}

function closeArchiveModal() {
    const modal = document.getElementById("archive-modal");
    if (modal) modal.style.display = "none";
}

function toggleArchiveActNumberField() {
    const statusSelect = document.getElementById("archive-status-select");
    const actNumberGroup = document.getElementById("archive-act-number-group");
    const actNumberInput = document.getElementById("archive-act-number");
    if (!statusSelect || !actNumberGroup) return;

    const selectedStatusName =
        statusSelect.options[statusSelect.selectedIndex]?.text?.trim() || "";
    const shouldShow = selectedStatusName === "Убыл";
    actNumberGroup.style.display = shouldShow ? "block" : "none";
    if (!shouldShow && actNumberInput) {
        actNumberInput.value = "";
    }
}

async function loadArchiveStatuses() {
    try {
        const response = await apiRequest("/veterinary/api/status/?page_size=100");
        const statuses = response.results || response;

        const archiveStatuses = statuses.filter((status) =>
            ["Убыл", "Убой", "Продажа на мясо", "Продажа на племя"].includes(status.status_type)
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
    const selected = Array.from(selectedAnimals.values());

    if (selected.length === 0) {
        alert("Нет выбранных животных для переноса.");
        return;
    }

    const statusSelect = document.getElementById("archive-status-select");
    const statusId = statusSelect?.value;
    const statusDate = document.getElementById("archive-status-date")?.value;
    const carcassWeightRaw = document.getElementById("archive-carcass-weight")?.value?.trim();
    const selectedStatusName = statusSelect?.options[statusSelect.selectedIndex]?.text?.trim() || "";
    const actNumberRaw = document.getElementById("archive-act-number")?.value?.trim() || "";

    if (!statusId) {
        alert("Выберите статус.");
        return;
    }

    if (!statusDate) {
        alert("Укажите дату присвоения статуса.");
        return;
    }

    let carcassWeight = null;
    if (carcassWeightRaw) {
        carcassWeight = parseFloat(carcassWeightRaw);
        if (Number.isNaN(carcassWeight) || carcassWeight < 0) {
            alert("Вес туши должен быть числом не меньше 0.");
            return;
        }
    }

    try {
        for (const item of selected) {
            await apiRequest(`/animals/${item.animalType}/${item.tagNumber}/`, "PATCH", {
                animal_status_id: statusId,
                status_date: statusDate,
                carcass_weight: carcassWeight,
                act_number: selectedStatusName === "Убыл" ? actNumberRaw : "",
            });
        }

        selectedAnimals.clear();
        saveSelectedAnimals();

        const selectAllCheckbox = document.getElementById("select-all");
        if (selectAllCheckbox) selectAllCheckbox.checked = false;

        closeArchiveModal();
        toggleSelectedActions();
        fetchCommonAnimals(currentPage, currentFilters);
        alert("Выбранные животные успешно перенесены в архив.");
    } catch (error) {
        console.error("Ошибка переноса в архив:", error);
        alert("Ошибка при переносе выбранных животных в архив");
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
        prevButton.onclick = () => fetchCommonAnimals(currentPage - 1, currentFilters);
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
        nextButton.onclick = () => fetchCommonAnimals(currentPage + 1, currentFilters);
        container.appendChild(nextButton);
    } else {
        const emptyDiv = document.createElement("div");
        emptyDiv.style.width = "90px";
        container.appendChild(emptyDiv);
    }

    pagination.appendChild(container);
}

window.addEventListener("beforeunload", function () {
    if (!window.location.pathname.includes("/animals/common/")) {
        sessionStorage.removeItem("selectedCommonAnimals");
    }
});

window.fetchCommonAnimals = fetchCommonAnimals;
window.performCommonSearch = function () {
    fetchCommonAnimals(1, getCommonFiltersFromInputs());
};
window.toggleCommonAdditionalFilters = toggleCommonAdditionalFilters;
window.toggleSelectAll = toggleSelectAll;
window.deleteSelectedAnimals = deleteSelectedAnimals;
window.closeDeleteModal = closeDeleteModal;
window.openArchiveModal = openArchiveModal;
window.closeArchiveModal = closeArchiveModal;
window.applyArchiveStatus = applyArchiveStatus;
window.saveCommonAnimal = saveCommonAnimal;

