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

function buildAnimalInfo(animal) {
    const tagNumber = animal.tag_number;
    const animalTypeCode = animal.animal_type;

    if (animalTypeCode === "Maker") {
        return { detailUrl: `/animals/maker/${encodeURIComponent(tagNumber)}/info/` };
    }
    if (animalTypeCode === "Ram") {
        return { detailUrl: `/animals/ram/${encodeURIComponent(tagNumber)}/info/` };
    }
    if (animalTypeCode === "Ewe") {
        return { detailUrl: `/animals/ewe/${encodeURIComponent(tagNumber)}/info/` };
    }
    if (animalTypeCode === "Sheep") {
        return { detailUrl: `/animals/sheep/${encodeURIComponent(tagNumber)}/info/` };
    }

    return { detailUrl: "#" };
}

function downloadArchiveAct(animalType, tagNumber) {
    const link = document.createElement("a");
    link.href = `/animals/api/archive/act/${encodeURIComponent(animalType)}/${encodeURIComponent(tagNumber)}/`;
    link.target = "_blank";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function buildActionsCell(animal) {
    if (!animal.can_download_act) {
        return '<span class="text-muted">Акт недоступен</span>';
    }

    return `
        <button class="btn btn-outline-primary btn-sm"
                onclick="downloadArchiveActFromActs('${escapeHtml(animal.animal_type)}', '${escapeHtml(animal.tag_number)}')">
            Скачать акт
        </button>
    `;
}

function displayArchiveActs(data) {
    const table = document.getElementById("archive-acts-list");
    if (!table) return;

    table.innerHTML = "";

    if (!data.length) {
        table.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-4">
                    <p class="text-muted mb-0">Архивированные животные не найдены.</p>
                </td>
            </tr>
        `;
        return;
    }

    data.forEach((animal, index) => {
        const row = document.createElement("tr");
        const recordNumber = (currentPage - 1) * pageSize + index + 1;
        const tagNumber = animal.tag_number || "-";
        const animalInfo = buildAnimalInfo(animal);
        const status = animal.status || "Не указан";
        const statusColor = animal.status_color || "#FFFFFF";
        const archivedDate = formatDateToOutput(animal.archived_date) || "Не указана";

        row.innerHTML = `
            <td>${recordNumber}</td>
            <td><a href="${animalInfo.detailUrl}">${escapeHtml(animal.display_name || tagNumber)}</a></td>
            <td style="background-color:${escapeHtml(statusColor)}">${escapeHtml(status)}</td>
            <td>${escapeHtml(archivedDate)}</td>
            <td>${buildActionsCell(animal)}</td>
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
        prevButton.onclick = () => fetchArchiveActs(currentPage - 1);
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
        nextButton.onclick = () => fetchArchiveActs(currentPage + 1);
        container.appendChild(nextButton);
    } else {
        const emptyRight = document.createElement("div");
        emptyRight.style.width = "100px";
        container.appendChild(emptyRight);
    }

    pagination.appendChild(container);
}

async function fetchArchiveActs(page = 1) {
    currentPage = page;
    const params = getUrlParams();
    const search = document.getElementById("archive-acts-search")?.value?.trim() || "";

    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    if (search) {
        params.set("search", search);
    } else {
        params.delete("search");
    }
    setUrlParams(params);

    const response = await apiRequest(`/animals/archive/?${params.toString()}`);
    displayArchiveActs(response.results || []);
    updatePagination(response);
}

function initializeFromUrl() {
    const params = getUrlParams();
    const search = params.get("search") || "";
    const page = Number.parseInt(params.get("page") || "1", 10) || 1;
    const searchInput = document.getElementById("archive-acts-search");
    if (searchInput) searchInput.value = search;
    currentPage = Math.max(page, 1);
}

function performArchiveActsSearch() {
    fetchArchiveActs(1);
}

document.addEventListener("DOMContentLoaded", () => {
    initializeFromUrl();
    fetchArchiveActs(currentPage);

    const searchInput = document.getElementById("archive-acts-search");
    if (searchInput) {
        searchInput.addEventListener("keypress", (event) => {
            if (event.key === "Enter") {
                performArchiveActsSearch();
            }
        });
    }
});

window.performArchiveActsSearch = performArchiveActsSearch;
window.downloadArchiveActFromActs = downloadArchiveAct;
