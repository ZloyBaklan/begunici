(function () {
    const ACT_STATUSES = new Set(["Падеж", "Вынужденная прирезка", "Реализация в живом весе"]);
    let selectedAnimals = [];

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop().split(";").shift();
        }
        return "";
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function getSelectedStatusName() {
        const statusSelect = document.getElementById("archive-status-select");
        return statusSelect?.options[statusSelect.selectedIndex]?.text?.trim() || "";
    }

    function hasTemplate(statusName) {
        return ACT_STATUSES.has(statusName);
    }

    function reset() {
        selectedAnimals = [];

        const fields = [
            "archive-act-number",
            "archive-act-date",
            "archive-act-diagnosis",
            "archive-act-worker-name",
        ];
        fields.forEach((id) => {
            const input = document.getElementById(id);
            if (input) input.value = "";
        });

        const fatness = document.getElementById("archive-act-fatness");
        if (fatness) fatness.value = "ср";

        const download = document.getElementById("archive-act-download");
        if (download) download.checked = true;

        const preview = document.getElementById("archive-act-preview");
        if (preview) {
            preview.classList.add("text-muted");
            preview.innerHTML = "Выберите статус и животных, чтобы увидеть данные.";
        }

        toggle();
    }

    function normalizeSelectedAnimal(item) {
        if (!item || typeof item !== "object") {
            return null;
        }

        const animalType = String(item.animalType || item.animal_type || "").trim();
        const tagNumber = String(item.tagNumber || item.tag_number || "").trim();

        if (!animalType || !tagNumber || tagNumber === "undefined" || tagNumber === "null") {
            return null;
        }

        return {
            animal_type: animalType,
            tag_number: tagNumber,
            animalType,
            tagNumber,
        };
    }

    function setSelectedAnimals(animals) {
        selectedAnimals = Array.isArray(animals)
            ? animals.map(normalizeSelectedAnimal).filter(Boolean)
            : [];
        loadPreview();
    }

    function toggle() {
        const statusName = getSelectedStatusName();
        const isAvailable = hasTemplate(statusName);

        const actFields = document.getElementById("archive-act-fields");
        if (actFields) actFields.style.display = isAvailable ? "block" : "none";

        const unavailable = document.getElementById("archive-act-unavailable");
        if (unavailable) unavailable.style.display = statusName && !isAvailable ? "block" : "none";

        const download = document.getElementById("archive-act-download");
        if (download) download.disabled = !isAvailable;

        if (isAvailable) {
            loadPreview();
        }
    }

    async function loadPreview() {
        const preview = document.getElementById("archive-act-preview");
        const statusName = getSelectedStatusName();
        if (!preview || !hasTemplate(statusName)) return;

        if (!selectedAnimals.length) {
            preview.classList.add("text-muted");
            preview.innerHTML = "Животные не выбраны.";
            return;
        }

        preview.classList.add("text-muted");
        preview.innerHTML = "Загружаю данные...";

        try {
            const response = await fetch("/animals/api/archive/act-preview/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: JSON.stringify({
                    animals: selectedAnimals,
                    status_name: statusName,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || "Ошибка предпросмотра акта");
            }

            const data = await response.json();
            renderPreview(data.results || [], data.errors || []);
        } catch (error) {
            console.error("Ошибка предпросмотра акта:", error);
            preview.classList.add("text-muted");
            preview.innerHTML = "Не удалось загрузить данные для акта.";
        }
    }

    function renderPreview(items, errors) {
        const preview = document.getElementById("archive-act-preview");
        if (!preview) return;

        if (!items.length && errors.length) {
            preview.classList.add("text-muted");
            preview.innerHTML = errors.map(escapeHtml).join("<br>");
            return;
        }

        const rows = items.map((item) => {
            const liveWeight = item.live_weight !== null && item.live_weight !== undefined && item.live_weight !== ""
                ? `${escapeHtml(item.live_weight)} кг`
                : "-";
            return `
                <tr>
                    <td>${escapeHtml(item.display_name || item.tag_number)}</td>
                    <td>${escapeHtml(item.animal_type_label)}</td>
                    <td>${escapeHtml(item.sex)}</td>
                    <td>${escapeHtml(item.age)}</td>
                    <td>${liveWeight}</td>
                    <td>${escapeHtml(item.reason)}</td>
                </tr>
            `;
        }).join("");

        const errorHtml = errors.length
            ? `<div class="text-danger mb-2">${errors.map(escapeHtml).join("<br>")}</div>`
            : "";

        preview.classList.remove("text-muted");
        preview.innerHTML = `
            ${errorHtml}
            <table class="table table-sm table-bordered mb-0">
                <thead>
                    <tr>
                        <th>Бирка</th>
                        <th>Тип</th>
                        <th>Пол</th>
                        <th>Возраст</th>
                        <th>Живая масса</th>
                        <th>Причина</th>
                    </tr>
                </thead>
                <tbody>${rows || '<tr><td colspan="6" class="text-muted text-center">Нет данных</td></tr>'}</tbody>
            </table>
        `;
    }

    function collectPayload() {
        const statusName = getSelectedStatusName();
        if (!hasTemplate(statusName)) {
            return {
                act_number: "",
                archive_act_date: null,
                archive_act_fatness: "",
                archive_act_diagnosis: "",
                archive_act_worker_name: "",
                archive_act_download: false,
            };
        }

        return {
            act_number: document.getElementById("archive-act-number")?.value?.trim() || "",
            archive_act_date: document.getElementById("archive-act-date")?.value || null,
            archive_act_fatness: document.getElementById("archive-act-fatness")?.value || "",
            archive_act_diagnosis: document.getElementById("archive-act-diagnosis")?.value?.trim() || "",
            archive_act_worker_name: document.getElementById("archive-act-worker-name")?.value?.trim() || "",
            archive_act_download: Boolean(document.getElementById("archive-act-download")?.checked),
        };
    }

    function downloadArchiveAct(animalType, tagNumber) {
        if (!animalType || !tagNumber) return;
        const link = document.createElement("a");
        link.href = `/animals/api/archive/act/${encodeURIComponent(animalType)}/${encodeURIComponent(tagNumber)}/`;
        link.target = "_blank";
        link.rel = "noopener";
        document.body.appendChild(link);
        link.click();
        link.remove();
    }

    document.addEventListener("change", (event) => {
        if (event.target?.id === "archive-status-select") {
            toggle();
        }
    });

    window.archiveActModal = {
        reset,
        setSelectedAnimals,
        toggle,
        collectPayload,
        downloadArchiveAct,
        hasTemplate,
    };
})();
