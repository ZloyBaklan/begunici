import { apiRequest, formatDateToOutput } from "./utils.js";

const pageSize = 10;
let currentPage = 1;

function getUrlParams() {
    return new URLSearchParams(window.location.search);
}

function setUrlParams(params) {
    const query = params.toString();
    window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function downloadWeightAct(actNumber) {
    const link = document.createElement("a");
    link.href = `/animals/api/acts/weight/${encodeURIComponent(actNumber)}/`;
    link.target = "_blank";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function getFilterValues() {
    return {
        weighingDate: document.getElementById("weight-date-filter")?.value || "",
        previousWeightDate: document.getElementById("previous-weight-date-filter")?.value || "",
        month: document.getElementById("weight-month-filter")?.value || "",
        year: document.getElementById("weight-year-filter")?.value || "",
    };
}

function setFilterParams(params) {
    const filters = getFilterValues();

    if (filters.weighingDate) {
        params.set("weighing_date", filters.weighingDate);
    } else {
        params.delete("weighing_date");
    }

    if (filters.previousWeightDate) {
        params.set("previous_weight_date", filters.previousWeightDate);
    } else {
        params.delete("previous_weight_date");
    }

    if (filters.month) {
        params.set("month", filters.month);
    } else {
        params.delete("month");
    }

    if (filters.year) {
        params.set("year", filters.year);
    } else {
        params.delete("year");
    }
}

function populateYearFilter(years = []) {
    const yearSelect = document.getElementById("weight-year-filter");
    if (!yearSelect) return;

    const params = getUrlParams();
    const selectedYear = yearSelect.value || params.get("year") || "";

    yearSelect.innerHTML = '<option value="">Все годы</option>';
    years.forEach((year) => {
        const option = document.createElement("option");
        option.value = String(year);
        option.textContent = String(year);
        yearSelect.appendChild(option);
    });

    if (selectedYear && !years.map(String).includes(String(selectedYear))) {
        const option = document.createElement("option");
        option.value = String(selectedYear);
        option.textContent = String(selectedYear);
        yearSelect.appendChild(option);
    }

    yearSelect.value = selectedYear;
}

function displayWeightActs(data) {
    const table = document.getElementById("weight-acts-list");
    if (!table) return;

    table.innerHTML = "";

    if (!data.length) {
        table.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-4">
                    <p class="text-muted mb-0">Акты взвешивания не найдены.</p>
                </td>
            </tr>
        `;
        return;
    }

    data.forEach((act) => {
        const row = document.createElement("tr");
        const weighingDate = formatDateToOutput(act.weighing_date) || "Не указана";
        const previousWeightDate = formatDateToOutput(act.previous_weight_date) || "Не указана";
        const animalCount = act.animal_count ?? "-";

        row.innerHTML = `
            <td>${escapeHtml(act.act_number)}</td>
            <td>${escapeHtml(weighingDate)}</td>
            <td>${escapeHtml(previousWeightDate)}</td>
            <td>${escapeHtml(animalCount)}</td>
            <td>
                <button class="btn btn-outline-primary btn-sm"
                        onclick="downloadWeightActFromActs('${escapeHtml(act.act_number)}')">
                    Скачать акт
                </button>
            </td>
        `;
        table.appendChild(row);
    });
}

function updatePagination(response) {
    const pagination = document.getElementById("pagination");
    if (!pagination) return;

    pagination.innerHTML = "";

    const container = document.createElement("div");
    container.className = "d-flex align-items-center justify-content-center gap-3";

    if (response.previous) {
        const prevButton = document.createElement("button");
        prevButton.innerText = "Предыдущая";
        prevButton.className = "btn btn-outline-primary btn-sm";
        prevButton.onclick = () => fetchWeightActs(currentPage - 1);
        container.appendChild(prevButton);
    } else {
        const emptyLeft = document.createElement("div");
        emptyLeft.style.width = "100px";
        container.appendChild(emptyLeft);
    }

    const pageInfo = document.createElement("span");
    pageInfo.innerText = `Страница ${currentPage} (всего: ${response.count})`;
    pageInfo.style.fontWeight = "500";
    pageInfo.style.minWidth = "220px";
    pageInfo.style.textAlign = "center";
    container.appendChild(pageInfo);

    if (response.next) {
        const nextButton = document.createElement("button");
        nextButton.innerText = "Следующая";
        nextButton.className = "btn btn-outline-primary btn-sm";
        nextButton.onclick = () => fetchWeightActs(currentPage + 1);
        container.appendChild(nextButton);
    } else {
        const emptyRight = document.createElement("div");
        emptyRight.style.width = "100px";
        container.appendChild(emptyRight);
    }

    pagination.appendChild(container);
}

async function fetchWeightActs(page = 1) {
    currentPage = page;
    const params = getUrlParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    setFilterParams(params);
    setUrlParams(params);

    const response = await apiRequest(`/animals/api/acts/weight/?${params.toString()}`);
    populateYearFilter(response.years || []);
    displayWeightActs(response.results || []);
    updatePagination(response);
}

function initializeFromUrl() {
    const params = getUrlParams();
    const page = Number.parseInt(params.get("page") || "1", 10) || 1;
    const weighingDateInput = document.getElementById("weight-date-filter");
    const previousWeightDateInput = document.getElementById("previous-weight-date-filter");
    const monthSelect = document.getElementById("weight-month-filter");

    if (weighingDateInput) weighingDateInput.value = params.get("weighing_date") || "";
    if (previousWeightDateInput) previousWeightDateInput.value = params.get("previous_weight_date") || "";
    if (monthSelect) monthSelect.value = params.get("month") || "";
    currentPage = Math.max(page, 1);
}

function applyWeightActFilters() {
    fetchWeightActs(1);
}

function resetWeightActFilters() {
    const weighingDateInput = document.getElementById("weight-date-filter");
    const previousWeightDateInput = document.getElementById("previous-weight-date-filter");
    const monthSelect = document.getElementById("weight-month-filter");
    const yearSelect = document.getElementById("weight-year-filter");

    if (weighingDateInput) weighingDateInput.value = "";
    if (previousWeightDateInput) previousWeightDateInput.value = "";
    if (monthSelect) monthSelect.value = "";
    if (yearSelect) yearSelect.value = "";

    fetchWeightActs(1);
}

document.addEventListener("DOMContentLoaded", () => {
    initializeFromUrl();
    fetchWeightActs(currentPage);
});

window.downloadWeightActFromActs = downloadWeightAct;
window.applyWeightActFilters = applyWeightActFilters;
window.resetWeightActFilters = resetWeightActFilters;
