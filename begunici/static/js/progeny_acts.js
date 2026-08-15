import { apiRequest } from "./utils.js";

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

function downloadProgenyAct(actNumber) {
    const link = document.createElement("a");
    link.href = `/animals/api/acts/progeny/${encodeURIComponent(actNumber)}/`;
    link.target = "_blank";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function displayProgenyActs(data) {
    const table = document.getElementById("progeny-acts-list");
    if (!table) return;

    table.innerHTML = "";

    if (!data.length) {
        table.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-4">
                    <p class="text-muted mb-0">Акты оприходования приплода не найдены.</p>
                </td>
            </tr>
        `;
        return;
    }

    data.forEach((act) => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${escapeHtml(act.act_number)}</td>
            <td>${escapeHtml(act.month_name || act.month)}</td>
            <td>${escapeHtml(act.year)}</td>
            <td>${escapeHtml(act.lambing_count ?? "-")}</td>
            <td>${escapeHtml(act.child_count ?? "-")}</td>
            <td>
                <button class="btn btn-outline-primary btn-sm"
                        onclick="downloadProgenyActFromActs('${escapeHtml(act.act_number)}')">
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
        prevButton.onclick = () => fetchProgenyActs(currentPage - 1);
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
        nextButton.onclick = () => fetchProgenyActs(currentPage + 1);
        container.appendChild(nextButton);
    } else {
        const emptyRight = document.createElement("div");
        emptyRight.style.width = "100px";
        container.appendChild(emptyRight);
    }

    pagination.appendChild(container);
}

async function fetchProgenyActs(page = 1) {
    currentPage = page;
    const params = getUrlParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    setUrlParams(params);

    const response = await apiRequest(`/animals/api/acts/progeny/?${params.toString()}`);
    displayProgenyActs(response.results || []);
    updatePagination(response);
}

function initializeFromUrl() {
    const params = getUrlParams();
    const page = Number.parseInt(params.get("page") || "1", 10) || 1;
    currentPage = Math.max(page, 1);
}

document.addEventListener("DOMContentLoaded", () => {
    initializeFromUrl();
    fetchProgenyActs(currentPage);
});

window.downloadProgenyActFromActs = downloadProgenyAct;
