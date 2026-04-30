import { apiRequest } from "./utils.js";

let currentPage = 1;
const pageSize = 10;

const CARE_CLASSES_BY_TYPE = {
    "Вакцинация": ["Иммунизация"],
    "Противопаразитарная": ["Антигельминтная", "Противопротозойная", "Дезинсекция"],
};

function getUserPermissions() {
    return window.userPermissions || {
        can_delete_vet_data: true,
    };
}

function syncCareClassOptions(selectedType, selectedClass = null) {
    const classSelect = document.getElementById("care-name");
    if (!classSelect) return;

    const classes = CARE_CLASSES_BY_TYPE[selectedType] || [];
    classSelect.innerHTML = "";

    classes.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        classSelect.appendChild(option);
    });

    if (selectedClass && classes.includes(selectedClass)) {
        classSelect.value = selectedClass;
    } else if (classes.length > 0) {
        classSelect.value = classes[0];
    }
}

function initCareTypeClassControls() {
    const typeSelect = document.getElementById("care-type");
    if (!typeSelect) return;

    syncCareClassOptions(typeSelect.value);
    typeSelect.addEventListener("change", () => {
        syncCareClassOptions(typeSelect.value);
    });
}

document.addEventListener("DOMContentLoaded", function () {
    initCareTypeClassControls();
    fetchCares();

    const createCareButton = document.querySelector("#create-care-button");
    if (createCareButton) {
        createCareButton.onclick = handleCreateOrUpdateCare;
    }

    const searchInput = document.getElementById("care-search");
    if (searchInput) {
        searchInput.addEventListener("input", function () {
            currentPage = 1;
            fetchCares(1, this.value);
        });
    }

    const exportButton = document.getElementById("export-cares-button");
    if (exportButton) {
        exportButton.addEventListener("click", exportCares);
    }
});

function handleCreateOrUpdateCare() {
    const createCareButton = document.getElementById("create-care-button");
    const careId = createCareButton.getAttribute("data-id");
    if (careId) {
        updateCare(careId);
    } else {
        createCare();
    }
}

function cancelEdit() {
    document.getElementById("create-care-form").reset();
    const typeSelect = document.getElementById("care-type");
    syncCareClassOptions(typeSelect.value);
    resetButton();
    document.getElementById("form-title").textContent = "Создать обработку";
    document.getElementById("cancel-edit-button").style.display = "none";
}
window.cancelEdit = cancelEdit;

async function createCare() {
    const careType = document.getElementById("care-type").value;
    const careName = document.getElementById("care-name").value;
    const medication = document.getElementById("medication").value;
    const purpose = document.getElementById("purpose").value;
    const defaultDurationDays = document.getElementById("default-duration-days").value;

    const data = {
        care_type: careType,
        care_name: careName,
        medication: medication || null,
        purpose: purpose || null,
        default_duration_days: parseInt(defaultDurationDays, 10) || 0,
    };

    try {
        await apiRequest("/veterinary/api/care/", "POST", data);
        showMessage("Ветобработка успешно создана", "success");
        document.getElementById("create-care-form").reset();
        syncCareClassOptions(document.getElementById("care-type").value);
        fetchCares(currentPage);
        resetButton();
    } catch (error) {
        console.error("Ошибка:", error);
        showMessage(`Произошла ошибка при создании ветобработки: ${error.message}`, "danger");
    }
}

async function fetchCares(page = 1, searchQuery = "") {
    try {
        const response = await apiRequest(`/veterinary/api/care/?page=1&page_size=200`);
        let cares = Array.isArray(response) ? response : response.results;

        if (searchQuery && searchQuery.trim()) {
            const searchLower = searchQuery.toLowerCase();
            cares = cares.filter(
                (care) =>
                    (care.care_type && care.care_type.toLowerCase().includes(searchLower)) ||
                    (care.care_name && care.care_name.toLowerCase().includes(searchLower)) ||
                    (care.medication && care.medication.toLowerCase().includes(searchLower)) ||
                    (care.purpose && care.purpose.toLowerCase().includes(searchLower))
            );
        }

        const startIndex = (page - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        const paginatedCares = cares.slice(startIndex, endIndex);

        currentPage = page;

        const careTable = document.getElementById("care-list");
        careTable.innerHTML = "";

        if (paginatedCares && paginatedCares.length > 0) {
            paginatedCares.forEach((care, index) => {
                const row = document.createElement("tr");

                const permissions = getUserPermissions();
                let actionsHtml = `
                    <div class="btn-group btn-group-sm" role="group">
                        <button class="btn btn-outline-primary edit-care-btn" data-id="${care.id}">Редактировать</button>`;

                if (permissions.can_delete_vet_data) {
                    actionsHtml += `
                        <button class="btn btn-outline-danger delete-care-btn" data-id="${care.id}">Удалить</button>`;
                }

                actionsHtml += `</div>`;

                const recordNumber = startIndex + index + 1;

                row.innerHTML = `
                    <td>${recordNumber}</td>
                    <td>${care.care_type}</td>
                    <td>${care.care_name}</td>
                    <td>${care.medication || "Нет препарата"}</td>
                    <td>${care.purpose || "Нет цели"}</td>
                    <td>${care.default_duration_days === 0 ? "Бессрочно" : care.default_duration_days + " дней"}</td>
                    <td>${actionsHtml}</td>
                `;

                row.querySelector(".edit-care-btn").addEventListener("click", () => editCare(care.id));
                const deleteBtn = row.querySelector(".delete-care-btn");
                if (deleteBtn) {
                    deleteBtn.addEventListener("click", () => deleteCare(care.id));
                }

                careTable.appendChild(row);
            });
        } else {
            careTable.innerHTML = '<tr><td colspan="7" class="text-center">Ветобработки не найдены</td></tr>';
        }

        updateLocalCaresPagination(cares.length, page, searchQuery);
    } catch (error) {
        console.error("Ошибка при загрузке ветобработок:", error);
        const careTable = document.getElementById("care-list");
        careTable.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Ошибка загрузки данных</td></tr>';
    }
}

async function editCare(careId) {
    try {
        const care = await apiRequest(`/veterinary/api/care/${careId}/`);

        document.getElementById("care-type").value = care.care_type;
        syncCareClassOptions(care.care_type, care.care_name);
        document.getElementById("medication").value = care.medication || "";
        document.getElementById("purpose").value = care.purpose || "";
        document.getElementById("default-duration-days").value = care.default_duration_days || 0;

        const createCareButton = document.getElementById("create-care-button");
        createCareButton.innerText = "Сохранить изменения";
        createCareButton.setAttribute("data-id", careId);

        document.getElementById("form-title").textContent = "Редактировать обработку";
        document.getElementById("cancel-edit-button").style.display = "block";
    } catch (error) {
        console.error("Ошибка при редактировании обработки:", error);
        showMessage(`Ошибка при загрузке данных обработки: ${error.message}`, "danger");
    }
}

async function updateCare(careId) {
    const careType = document.getElementById("care-type").value;
    const careName = document.getElementById("care-name").value;
    const medication = document.getElementById("medication").value;
    const purpose = document.getElementById("purpose").value;
    const defaultDurationDays = document.getElementById("default-duration-days").value;

    const data = {
        care_type: careType,
        care_name: careName,
        medication: medication || null,
        purpose: purpose || null,
        default_duration_days: parseInt(defaultDurationDays, 10) || 0,
    };

    try {
        await apiRequest(`/veterinary/api/care/${careId}/`, "PUT", data);
        showMessage("Ветобработка успешно обновлена", "success");
        fetchCares(currentPage);
        resetButton();
        cancelEdit();
    } catch (error) {
        console.error("Ошибка при обновлении:", error);
        showMessage(`Ошибка при обновлении обработки: ${error.message}`, "danger");
    }
}

async function deleteCare(careId) {
    const confirmDelete = confirm("Вы уверены, что хотите удалить эту обработку?");
    if (!confirmDelete) return;

    try {
        await apiRequest(`/veterinary/api/care/${careId}/`, "DELETE");
        showMessage("Ветобработка успешно удалена", "success");
        fetchCares(currentPage);
    } catch (error) {
        console.error("Ошибка при удалении обработки:", error);
        showMessage(`Ошибка при удалении обработки: ${error.message}`, "danger");
    }
}

async function exportCares() {
    const exportButton = document.getElementById("export-cares-button");
    const initialText = exportButton ? exportButton.textContent : "";

    if (exportButton) {
        exportButton.disabled = true;
        exportButton.textContent = "Экспорт...";
    }

    try {
        const response = await fetch("/veterinary/api/export-cares/");
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const blob = await response.blob();
        let fileName = "veterinary_cares.xlsx";

        const contentDisposition = response.headers.get("Content-Disposition");
        if (contentDisposition) {
            const match = contentDisposition.match(/filename="?([^"]+)"?/i);
            if (match && match[1]) {
                fileName = match[1];
            }
        }

        const downloadUrl = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(downloadUrl);

        showMessage("Экспорт успешно выполнен", "success");
    } catch (error) {
        console.error("Ошибка экспорта:", error);
        showMessage(`Ошибка при экспорте: ${error.message}`, "danger");
    } finally {
        if (exportButton) {
            exportButton.disabled = false;
            exportButton.textContent = initialText || "Экспорт";
        }
    }
}

function searchCares(query = null) {
    if (query === null) {
        query = document.getElementById("care-search").value;
    }
    currentPage = 1;
    fetchCares(1, query);
}
window.searchCares = searchCares;

function updateLocalCaresPagination(totalItems, currentPage, searchQuery = "") {
    const pagination = document.getElementById("pagination");
    if (!pagination) {
        const paginationDiv = document.createElement("div");
        paginationDiv.id = "pagination";
        paginationDiv.className = "mt-3 d-flex justify-content-between align-items-center";
        document.querySelector(".card-body").appendChild(paginationDiv);
    }

    const paginationElement = document.getElementById("pagination");
    paginationElement.innerHTML = "";

    const totalPages = Math.ceil(totalItems / pageSize);

    const leftContainer = document.createElement("div");
    if (currentPage > 1) {
        const prevButton = document.createElement("button");
        prevButton.className = "btn btn-outline-primary btn-sm";
        prevButton.innerText = "Предыдущая";
        prevButton.onclick = () => {
            fetchCares(currentPage - 1, searchQuery);
        };
        leftContainer.appendChild(prevButton);
    }

    const pageInfo = document.createElement("span");
    pageInfo.className = "text-muted";
    pageInfo.innerText = `Страница ${currentPage} из ${totalPages} (всего: ${totalItems})`;

    const rightContainer = document.createElement("div");
    if (currentPage < totalPages) {
        const nextButton = document.createElement("button");
        nextButton.className = "btn btn-outline-primary btn-sm";
        nextButton.innerText = "Следующая";
        nextButton.onclick = () => {
            fetchCares(currentPage + 1, searchQuery);
        };
        rightContainer.appendChild(nextButton);
    }

    paginationElement.appendChild(leftContainer);
    paginationElement.appendChild(pageInfo);
    paginationElement.appendChild(rightContainer);
}

function resetButton() {
    const createCareButton = document.getElementById("create-care-button");
    createCareButton.innerText = "Создать обработку";
    createCareButton.removeAttribute("data-id");
}

function showMessage(message, type) {
    const messageDiv = document.getElementById("care-message");
    messageDiv.className = `alert alert-${type}`;
    messageDiv.textContent = message;
    messageDiv.style.display = "block";

    setTimeout(() => {
        messageDiv.style.display = "none";
    }, 5000);
}

window.handleCreateOrUpdateCare = handleCreateOrUpdateCare;
