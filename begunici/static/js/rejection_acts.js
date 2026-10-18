import { apiRequest, formatDateToOutput } from "./utils.js";

document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("rejection-acts");
    if (!root) return;
    const form = document.getElementById("rejection-act-filters");
    const table = document.getElementById("rejection-acts-list");
    const pagination = document.getElementById("rejection-pagination");
    const error = document.getElementById("rejection-error");
    const warning = document.getElementById("rejection-unknown-dates");
    const yearSelect = document.getElementById("rejection-year");
    const filterNames = ["act_date", "month", "year"];
    const initialParams = new URLSearchParams(window.location.search);
    let requestId = 0;

    function fillYears(years, selectedYear) {
        yearSelect.replaceChildren(new Option("Все годы", ""));
        const values = new Set(years.map(String));
        if (/^\d{4}$/.test(selectedYear)) values.add(selectedYear);
        [...values].sort((a, b) => Number(b) - Number(a)).forEach((year) => {
            yearSelect.add(new Option(year, year));
        });
        yearSelect.value = selectedYear;
    }

    fillYears([], initialParams.get("year") || "");
    filterNames.forEach((name) => {
        form.elements.namedItem(name).value = initialParams.get(name) || "";
    });

    function showMessage(message) {
        const row = table.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 4;
        cell.className = "text-center text-muted py-4";
        cell.textContent = message;
    }

    function pageButton(label, page) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-outline-primary btn-sm";
        button.textContent = label;
        button.disabled = page == null;
        button.addEventListener("click", () => loadActs(page));
        return button;
    }

    async function loadActs(page = 1) {
        const currentRequest = ++requestId;
        const params = new URLSearchParams({ page: String(page), page_size: "10" });
        filterNames.forEach((name) => {
            const value = form.elements.namedItem(name).value;
            if (value) params.set(name, value);
        });
        error.hidden = true;
        warning.hidden = true;
        table.replaceChildren();
        pagination.replaceChildren();
        root.setAttribute("aria-busy", "true");
        showMessage("Загрузка...");
        try {
            const response = await apiRequest(`${root.dataset.listUrl}?${params}`);
            if (currentRequest !== requestId) return;
            params.set("page", String(response.page));
            window.history.replaceState({}, "", `${window.location.pathname}?${params}`);
            fillYears(response.years || [], params.get("year") || "");
            table.replaceChildren();
            if (!response.results.length) showMessage("Акты выбраковки не найдены");
            response.results.forEach((act) => {
                const row = table.insertRow();
                [act.act_number, formatDateToOutput(act.act_date), act.animal_count].forEach((value) => {
                    row.insertCell().textContent = value;
                });
                const link = document.createElement("a");
                link.href = `${root.dataset.listUrl}${encodeURIComponent(act.act_number)}/`;
                link.className = "btn btn-outline-primary btn-sm";
                link.textContent = "Скачать акт";
                row.insertCell().appendChild(link);
            });
            if (response.count) {
                const info = document.createElement("span");
                info.textContent = `Страница ${response.page} (всего: ${response.count})`;
                pagination.append(pageButton("Предыдущая", response.previous), info,
                    pageButton("Следующая", response.next));
            }
            if (response.unknown_date_count) {
                warning.textContent = `Есть записи брака без известной даты: ${response.unknown_date_count}. В акты они пока не включены.`;
                warning.hidden = false;
            }
        } catch (failure) {
            if (currentRequest !== requestId) return;
            table.replaceChildren();
            error.textContent = failure.message || "Не удалось загрузить акты выбраковки";
            error.hidden = false;
        } finally {
            if (currentRequest === requestId) root.setAttribute("aria-busy", "false");
        }
    }

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        loadActs();
    });
    form.addEventListener("reset", (event) => {
        event.preventDefault();
        filterNames.forEach((name) => { form.elements.namedItem(name).value = ""; });
        loadActs();
    });
    loadActs(Math.max(1, Number.parseInt(initialParams.get("page"), 10) || 1));
});
