(function () {
    const ACT_STATUSES = new Set([
        "Падеж",
        "Вынужденная прирезка",
        "Убой на мясо",
        "Реализация в живом весе",
        "Продажа на племя",
    ]);
    let selectedAnimals = [];
    let sequentialMode = false;
    let sequentialAnimals = [];
    let sequentialEntries = [];
    let sequentialIndex = 0;
    let statusAssignmentMode = false;
    let assignedStatusEntries = [];
    let groupingMode = false;
    let pendingGroupEntries = [];
    let groupingCandidates = [];
    let groupInfoByEntryIndex = {};

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

    function translateApiErrorText(message) {
        const text = String(message || "").trim();
        const translations = {
            "This field is required.": "Это поле обязательно для заполнения.",
            "This field may not be blank.": "Это поле не может быть пустым.",
            "This field may not be null.": "Это поле не может быть пустым.",
            "A valid integer is required.": "Нужно указать целое число.",
            "A valid number is required.": "Нужно указать число.",
            "Enter a valid date.": "Укажите корректную дату.",
            "Date has wrong format. Use one of these formats instead: YYYY-MM-DD.": "Неверный формат даты. Используйте формат ДД.ММ.ГГГГ.",
            "This field must be unique.": "Такое значение уже используется.",
        };
        if (translations[text]) return translations[text];
        if (text.includes("Invalid pk")) return "Выбранное значение не найдено в базе.";
        return text;
    }

    function parseApiErrorString(message) {
        const text = String(message || "").trim();
        if (!text) return "";

        const cleaned = text.replace(
            /ErrorDetail\(string=(['"])(.*?)\1,\s*code=(['"]).*?\3\)/g,
            (_, quote, errorMessage) => `'${String(errorMessage).replaceAll("'", "\\'")}'`
        );

        const fieldMessages = [];
        const fieldRegex = /['"]([^'"]+)['"]\s*:\s*(\[[\s\S]*?\]|['"][\s\S]*?['"])/g;
        let fieldMatch;
        while ((fieldMatch = fieldRegex.exec(cleaned)) !== null) {
            const field = fieldMatch[1].replaceAll("_", " ");
            const rawValue = fieldMatch[2];
            const values = [];
            const valueRegex = /['"]([^'"]+)['"]/g;
            let valueMatch;
            while ((valueMatch = valueRegex.exec(rawValue)) !== null) {
                values.push(translateApiErrorText(valueMatch[1]));
            }
            if (values.length) fieldMessages.push(`${field}: ${values.join(", ")}`);
        }

        if (fieldMessages.length) return fieldMessages.join("\n");

        const detailMessages = [];
        const detailRegex = /ErrorDetail\(string=(['"])(.*?)\1,\s*code=(['"]).*?\3\)/g;
        let detailMatch;
        while ((detailMatch = detailRegex.exec(text)) !== null) {
            detailMessages.push(translateApiErrorText(detailMatch[2]));
        }

        return detailMessages.length ? detailMessages.join("\n") : translateApiErrorText(text);
    }

    function getApiErrorMessage(errorData, fallback) {
        if (!errorData) return fallback;
        if (typeof errorData === "string") return parseApiErrorString(errorData);
        if (typeof errorData !== "object") return fallback;
        if (typeof errorData.error === "string") return parseApiErrorString(errorData.error);
        if (typeof errorData.detail === "string") return parseApiErrorString(errorData.detail);

        const messages = Object.entries(errorData).map(([field, value]) => {
            const rawValue = Array.isArray(value) ? value.join(", ") : String(value || "");
            const message = parseApiErrorString(rawValue);
            if (!message) return "";
            if (["detail", "error", "non_field_errors"].includes(field)) return message;
            return `${String(field).replaceAll("_", " ")}: ${message}`;
        }).filter(Boolean);

        return messages.length ? messages.join("\n") : fallback;
    }

    function getSelectedStatusName() {
        const statusSelect = document.getElementById("archive-status-select");
        return statusSelect?.options[statusSelect.selectedIndex]?.text?.trim() || "";
    }

    function getStatusOptions() {
        const statusSelect = document.getElementById("archive-status-select");
        if (!statusSelect) return [];
        return Array.from(statusSelect.options)
            .filter((option) => option.value)
            .map((option) => ({
                id: option.value,
                name: option.textContent.trim(),
            }));
    }

    function getStatusNameById(statusId) {
        const status = getStatusOptions().find((option) => option.id === String(statusId));
        return status?.name || "";
    }

    function getAnimalKey(animal) {
        const normalized = normalizeSelectedAnimal(animal);
        if (!normalized) return "";
        return `${normalized.animal_type}::${normalized.tag_number}`;
    }

    function buildValidationError(message) {
        return { __archiveActError: message };
    }

    function hasTemplate(statusName) {
        return ACT_STATUSES.has(statusName);
    }

    function getTodayInputValue() {
        const now = new Date();
        const offset = now.getTimezoneOffset();
        return new Date(now.getTime() - offset * 60000).toISOString().split("T")[0];
    }

    function getAnimalLabel(animal) {
        const typeLabels = {
            maker: "Баран-производитель",
            ram: "Баранчик",
            ewe: "Ярка",
            sheep: "Овцематка",
        };
        const typeLabel = typeLabels[animal?.animal_type] || "Животное";
        return `${typeLabel}: ${animal?.tag_number || "-"}`;
    }

    function getDisplayAnimalLabel(animal) {
        return `${getAnimalLabel(animal)}`
            .replace(/^Баран-производитель: /, "Баран-производитель ")
            .replace(/^Баранчик: /, "Баранчик ")
            .replace(/^Ярка: /, "Ярка ")
            .replace(/^Овцематка: /, "Овцематка ");
    }

    function formatDateForUser(value) {
        if (!value) return "-";
        const parts = String(value).split("-");
        if (parts.length !== 3) return value;
        return `${parts[2]}.${parts[1]}.${parts[0]}`;
    }

    function generateGroupKey() {
        if (window.crypto?.randomUUID) {
            return window.crypto.randomUUID();
        }
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
            const random = Math.random() * 16 | 0;
            const value = char === "x" ? random : (random & 0x3 | 0x8);
            return value.toString(16);
        });
    }

    function setGroupingUi(active) {
        const statusAssignment = document.getElementById("archive-status-assignment");
        const perAnimalFields = document.getElementById("archive-per-animal-fields");
        const grouping = document.getElementById("archive-act-grouping");
        if (statusAssignment) statusAssignment.style.display = "none";
        if (perAnimalFields) perAnimalFields.style.display = active ? "none" : "block";
        if (grouping) grouping.style.display = active ? "block" : "none";
    }

    function setStatusAssignmentUi(active) {
        const statusAssignment = document.getElementById("archive-status-assignment");
        const perAnimalFields = document.getElementById("archive-per-animal-fields");
        const grouping = document.getElementById("archive-act-grouping");
        if (statusAssignment) statusAssignment.style.display = active ? "block" : "none";
        if (perAnimalFields) perAnimalFields.style.display = active ? "none" : "block";
        if (grouping) grouping.style.display = "none";
    }

    function resetPerAnimalFields() {
        const fields = [
            "archive-act-number",
            "archive-act-date",
            "archive-act-diagnosis",
            "archive-act-weight-date",
            "archive-act-live-weight",
            "archive-carcass-weight",
        ];
        fields.forEach((id) => {
            const input = document.getElementById(id);
            if (input) input.value = "";
        });

        const statusDate = document.getElementById("archive-status-date");
        if (statusDate) {
            statusDate.value = getTodayInputValue();
            statusDate.disabled = false;
        }

        const statusSelect = document.getElementById("archive-status-select");
        if (statusSelect) statusSelect.disabled = false;

        const actNumber = document.getElementById("archive-act-number");
        if (actNumber) actNumber.disabled = false;

        const deathReason = document.getElementById("archive-act-death-reason");
        if (deathReason) deathReason.value = "Травма";

        const fatness = document.getElementById("archive-act-fatness");
        if (fatness) fatness.value = "ср";

        const download = document.getElementById("archive-act-download");
        if (download) download.checked = true;
    }

    function updateSequentialUi() {
        if (statusAssignmentMode) {
            const currentAnimalBlock = document.getElementById("archive-current-animal");
            if (currentAnimalBlock) {
                currentAnimalBlock.style.display = "none";
                currentAnimalBlock.innerHTML = "";
            }
            const applyButton = document.getElementById("archive-apply-button");
            if (applyButton) applyButton.textContent = "Далее";
            return;
        }

        if (groupingMode) {
            const currentAnimalBlock = document.getElementById("archive-current-animal");
            if (currentAnimalBlock) {
                currentAnimalBlock.style.display = "block";
                currentAnimalBlock.innerHTML = `
                    <div class="fw-semibold">Группировка актов</div>
                    <div>Отметьте животных, которые должны попасть в общий акт.</div>
                `;
            }
            const applyButton = document.getElementById("archive-apply-button");
            if (applyButton) applyButton.textContent = "Далее";
            return;
        }

        const currentAnimal = sequentialMode ? sequentialAnimals[sequentialIndex] : selectedAnimals[0];
        const currentAnimalBlock = document.getElementById("archive-current-animal");
        if (currentAnimalBlock) {
            if (currentAnimal) {
                const progress = sequentialMode
                    ? `Животное ${sequentialIndex + 1} из ${sequentialAnimals.length}`
                    : "Животное";
                currentAnimalBlock.style.display = "block";
                currentAnimalBlock.innerHTML = `
                    <div class="fw-semibold">${escapeHtml(progress)}</div>
                    <div>${escapeHtml(getAnimalLabel(currentAnimal))}</div>
                `;
            } else {
                currentAnimalBlock.style.display = "none";
                currentAnimalBlock.innerHTML = "";
            }
        }

        const applyButton = document.getElementById("archive-apply-button");
        if (applyButton) {
            if (sequentialMode && sequentialIndex < sequentialAnimals.length - 1) {
                applyButton.textContent = "Сохранить и далее";
            } else if (sequentialMode) {
                applyButton.textContent = "Завершить архивирование";
            } else {
                applyButton.textContent = "Применить";
            }
        }
    }

    function reset() {
        selectedAnimals = [];
        sequentialMode = false;
        sequentialAnimals = [];
        sequentialEntries = [];
        sequentialIndex = 0;
        statusAssignmentMode = false;
        assignedStatusEntries = [];
        groupingMode = false;
        pendingGroupEntries = [];
        groupingCandidates = [];
        groupInfoByEntryIndex = {};
        resetPerAnimalFields();
        setStatusAssignmentUi(false);
        setGroupingUi(false);

        const preview = document.getElementById("archive-act-preview");
        if (preview) {
            preview.classList.add("text-muted");
            preview.innerHTML = "Выберите статус и животных, чтобы увидеть данные.";
        }

        const latestWeightSummary = document.getElementById("archive-latest-weight-summary");
        if (latestWeightSummary) {
            latestWeightSummary.style.display = "none";
            latestWeightSummary.innerHTML = "Последняя запись о весе: -";
        }

        updateSequentialUi();
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
        sequentialMode = false;
        sequentialAnimals = [];
        sequentialEntries = [];
        sequentialIndex = 0;
        statusAssignmentMode = false;
        assignedStatusEntries = [];
        groupingMode = false;
        pendingGroupEntries = [];
        groupingCandidates = [];
        groupInfoByEntryIndex = {};
        setStatusAssignmentUi(false);
        setGroupingUi(false);
        updateSequentialUi();
        loadPreview();
    }

    function startSequentialArchive(animals) {
        sequentialAnimals = Array.isArray(animals)
            ? animals.map(normalizeSelectedAnimal).filter(Boolean)
            : [];
        sequentialEntries = [];
        sequentialIndex = 0;
        sequentialMode = false;
        statusAssignmentMode = sequentialAnimals.length > 1;
        assignedStatusEntries = [];
        groupingMode = false;
        pendingGroupEntries = [];
        groupingCandidates = [];
        groupInfoByEntryIndex = {};
        setGroupingUi(false);
        selectedAnimals = sequentialAnimals.slice();
        resetPerAnimalFields();
        if (statusAssignmentMode) {
            setStatusAssignmentUi(true);
            renderStatusAssignmentStep();
        } else {
            setStatusAssignmentUi(false);
        }
        updateSequentialUi();
        if (!statusAssignmentMode) {
            loadPreview();
        }
    }

    function updateStatusSpecificFields() {
        const statusName = getSelectedStatusName();
        const diagnosisGroup = document.getElementById("archive-act-diagnosis-group");
        const deathReasonGroup = document.getElementById("archive-act-death-reason-group");

        if (diagnosisGroup) diagnosisGroup.style.display = "block";
        if (deathReasonGroup) deathReasonGroup.style.display = statusName === "Падеж" ? "block" : "none";
    }

    function renderStatusAssignmentStep() {
        const container = document.getElementById("archive-status-assignment");
        if (!container) return;

        const statuses = getStatusOptions();
        if (!statuses.length) {
            container.innerHTML = `
                <h6 class="mb-2">Выбор архивных статусов</h6>
                <div class="text-muted">Загружаю статусы...</div>
            `;
            return;
        }

        const optionHtml = statuses.map((statusOption) => `
            <option value="${escapeHtml(statusOption.id)}">${escapeHtml(statusOption.name)}</option>
        `).join("");

        const rows = sequentialAnimals.map((animal, index) => `
                <tr>
                    <td>${escapeHtml(getDisplayAnimalLabel(animal))}</td>
                    <td>
                        <select class="form-select archive-status-assignment-select" data-entry-index="${index}">
                            ${optionHtml}
                        </select>
                    </td>
                </tr>
            `).join("");

        container.innerHTML = `
            <h6 class="mb-2">Выбор архивных статусов</h6>
            <div class="table-responsive">
                <table class="table table-sm table-bordered align-middle mb-0">
                    <thead>
                        <tr>
                            <th>Животное</th>
                            <th>Статус</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;

        assignedStatusEntries.forEach((entry, index) => {
            const select = container.querySelector(`.archive-status-assignment-select[data-entry-index="${index}"]`);
            if (select && entry?.statusId) select.value = entry.statusId;
        });
    }

    function collectStatusAssignments() {
        const statusSelects = Array.from(document.querySelectorAll(".archive-status-assignment-select"));
        if (!statusSelects.length) {
            return { error: "Статусы еще не загружены. Попробуйте еще раз." };
        }

        const entries = [];
        for (const select of statusSelects) {
            const index = Number.parseInt(select.dataset.entryIndex, 10);
            const animal = sequentialAnimals[index];
            const statusId = select.value;
            const statusName = select.options[select.selectedIndex]?.text?.trim() || getStatusNameById(statusId);

            if (!animal || !statusId) {
                return { error: "Укажите статус для каждого животного." };
            }

            entries[index] = {
                animal,
                statusId,
                statusName,
            };
        }

        assignedStatusEntries = entries.filter(Boolean);
        statusAssignmentMode = false;
        setStatusAssignmentUi(false);

        if (buildGroupingCandidates(assignedStatusEntries).length) {
            renderGroupingStep(assignedStatusEntries);
            return { complete: false };
        }

        startDetailsStep(assignedStatusEntries);
        return { complete: false };
    }

    function getAssignedEntryInfo(animal) {
        const animalKey = getAnimalKey(animal);
        const index = assignedStatusEntries.findIndex((entry) => getAnimalKey(entry.animal) === animalKey);
        return {
            index,
            entry: index >= 0 ? assignedStatusEntries[index] : null,
        };
    }

    function applyLockedDetailsFields(animal) {
        const { index, entry } = getAssignedEntryInfo(animal);
        const statusSelect = document.getElementById("archive-status-select");
        if (statusSelect && entry?.statusId) {
            statusSelect.value = entry.statusId;
            statusSelect.disabled = true;
        }

        const groupInfo = index >= 0 ? groupInfoByEntryIndex[index] : null;
        const actNumberInput = document.getElementById("archive-act-number");
        if (actNumberInput && groupInfo?.commonActNumber) {
            actNumberInput.value = groupInfo.commonActNumber;
            actNumberInput.disabled = true;
        }

        const statusDateInput = document.getElementById("archive-status-date");
        if (statusDateInput && groupInfo?.statusDate) {
            statusDateInput.value = groupInfo.statusDate;
            statusDateInput.disabled = true;
        }
    }

    function showDetailsForIndex(index) {
        sequentialIndex = index;
        selectedAnimals = [sequentialAnimals[sequentialIndex]].filter(Boolean);
        resetPerAnimalFields();
        applyLockedDetailsFields(selectedAnimals[0]);
        updateSequentialUi();
        toggle();
    }

    function startDetailsStep(entries) {
        assignedStatusEntries = entries;
        sequentialEntries = [];
        sequentialIndex = 0;
        sequentialMode = entries.length > 1;
        groupingMode = false;
        pendingGroupEntries = [];
        groupingCandidates = [];
        setStatusAssignmentUi(false);
        setGroupingUi(false);
        showDetailsForIndex(0);
    }

    function toggle() {
        if (statusAssignmentMode) {
            renderStatusAssignmentStep();
            return;
        }
        if (groupingMode) {
            return;
        }

        const statusName = getSelectedStatusName();
        const isAvailable = hasTemplate(statusName);

        const actFields = document.getElementById("archive-act-fields");
        if (actFields) actFields.style.display = isAvailable ? "block" : "none";

        const unavailable = document.getElementById("archive-act-unavailable");
        if (unavailable) unavailable.style.display = statusName && !isAvailable ? "block" : "none";

        const download = document.getElementById("archive-act-download");
        if (download) download.disabled = !isAvailable;

        updateStatusSpecificFields();

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
            renderLatestWeightSummary([]);
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
                throw new Error(getApiErrorMessage(errorData, "Ошибка предпросмотра акта"));
            }

            const data = await response.json();
            renderPreview(data.results || [], data.errors || []);
            renderLatestWeightSummary(data.results || []);
        } catch (error) {
            console.error("Ошибка предпросмотра акта:", error);
            preview.classList.add("text-muted");
            preview.innerHTML = "Не удалось загрузить данные для акта.";
            renderLatestWeightSummary([]);
        }
    }

    function renderLatestWeightSummary(items) {
        const summary = document.getElementById("archive-latest-weight-summary");
        if (!summary) return;

        if (!items.length) {
            summary.style.display = "none";
            summary.innerHTML = "Последняя запись о весе: -";
            return;
        }

        summary.style.display = "block";
        if (items.length === 1) {
            summary.innerHTML = `Последняя запись о весе: ${escapeHtml(items[0].latest_weight_display || "-")}`;
            return;
        }

        const rows = items.map((item) => `
            <div>
                <strong>${escapeHtml(item.display_name || item.tag_number)}:</strong>
                ${escapeHtml(item.latest_weight_display || "-")}
            </div>
        `).join("");
        summary.innerHTML = `<div class="mb-1">Последние записи о весе:</div>${rows}`;
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
            return `
                <tr>
                    <td>${escapeHtml(item.display_name || item.tag_number)}</td>
                    <td>${escapeHtml(item.animal_type_label)}</td>
                    <td>${escapeHtml(item.sex)}</td>
                    <td>${escapeHtml(item.age)}</td>
                    <td>${escapeHtml(item.latest_weight_display || "-")}</td>
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
            <table class="table table-sm table-bordered mb-0 align-middle">
                <thead>
                    <tr>
                        <th>Бирка</th>
                        <th>Тип</th>
                        <th>Пол</th>
                        <th>Возраст</th>
                        <th>Последняя запись о весе</th>
                        <th>Причина выбытия</th>
                    </tr>
                </thead>
                <tbody>${rows || '<tr><td colspan="6" class="text-muted text-center">Нет данных</td></tr>'}</tbody>
            </table>
        `;
    }

    function collectPayload(animal) {
        const statusName = getSelectedStatusName();
        if (!hasTemplate(statusName)) {
            return {
                act_number: "",
                archive_act_date: null,
                archive_act_live_weight: null,
                archive_act_weight_date: null,
                archive_act_fatness: "",
                archive_act_diagnosis: "",
                archive_act_death_reason: "",
                archive_act_add_weight_record: false,
                archive_act_download: false,
            };
        }

        const actNumber = document.getElementById("archive-act-number")?.value?.trim() || "";
        const actDate = document.getElementById("archive-status-date")?.value || "";
        const fatness = document.getElementById("archive-act-fatness")?.value || "";
        const diagnosis = document.getElementById("archive-act-diagnosis")?.value?.trim() || "";
        const deathReason = statusName === "Падеж"
            ? (document.getElementById("archive-act-death-reason")?.value || "")
            : "";

        if (!actNumber) return buildValidationError("Укажите номер акта.");
        if (!actDate) return buildValidationError("Укажите дату присвоения статуса.");
        if (!fatness) return buildValidationError("Укажите упитанность.");
        if (statusName === "Падеж" && !deathReason) return buildValidationError("Укажите причину падежа.");
        if (!diagnosis) return buildValidationError("Укажите диагноз / основание.");

        const weightRaw = document.getElementById("archive-act-live-weight")?.value?.trim() || "";
        const weightDate = document.getElementById("archive-act-weight-date")?.value || "";

        if ((weightRaw && !weightDate) || (!weightRaw && weightDate)) {
            return buildValidationError("Для дополнительной записи о весе укажите и дату, и вес.");
        }

        if (weightRaw) {
            const parsedWeight = parseFloat(weightRaw);
            if (Number.isNaN(parsedWeight) || parsedWeight < 0) {
                return buildValidationError("Дополнительный вес должен быть числом не меньше 0.");
            }
        }

        return {
            act_number: actNumber,
            archive_act_date: actDate,
            archive_act_live_weight: weightRaw || null,
            archive_act_weight_date: weightDate || null,
            archive_act_fatness: fatness,
            archive_act_diagnosis: diagnosis,
            archive_act_death_reason: deathReason,
            archive_act_add_weight_record: Boolean(weightRaw && weightDate),
            archive_act_download: Boolean(document.getElementById("archive-act-download")?.checked),
        };
    }

    function collectArchiveFormEntry(animal) {
        const normalizedAnimal = normalizeSelectedAnimal(animal);
        if (!normalizedAnimal) {
            return buildValidationError("Не удалось определить животное для архивирования.");
        }

        const statusSelect = document.getElementById("archive-status-select");
        const assignedInfo = getAssignedEntryInfo(normalizedAnimal);
        const assignedEntry = assignedInfo.entry;
        const groupInfo = assignedInfo.index >= 0 ? groupInfoByEntryIndex[assignedInfo.index] : null;
        const statusId = assignedEntry?.statusId || statusSelect?.value;
        const statusName = assignedEntry?.statusName || getSelectedStatusName();
        const statusDate = document.getElementById("archive-status-date")?.value;
        const carcassWeightRaw = document.getElementById("archive-carcass-weight")?.value?.trim();

        if (!statusId) {
            return buildValidationError("Выберите статус.");
        }

        if (!statusDate) {
            return buildValidationError("Укажите дату присвоения статуса.");
        }

        let carcassWeight = null;
        if (carcassWeightRaw) {
            carcassWeight = parseFloat(carcassWeightRaw);
            if (Number.isNaN(carcassWeight) || carcassWeight < 0) {
                return buildValidationError("Вес туши должен быть числом не меньше 0.");
            }
        }

        const archiveActPayload = collectPayload(normalizedAnimal);
        if (archiveActPayload.__archiveActError) {
            return archiveActPayload;
        }
        if (groupInfo) {
            archiveActPayload.archive_act_group_key = groupInfo.groupKey;
            archiveActPayload.act_number = groupInfo.commonActNumber;
            if (!groupInfo.statusDate) {
                groupInfo.statusDate = statusDate;
            }
        } else {
            archiveActPayload.archive_act_group_key = null;
        }

        return {
            animal: normalizedAnimal,
            statusId,
            statusName,
            statusDate,
            carcassWeight,
            archiveActPayload,
        };
    }

    function buildGroupingCandidates(entries) {
        const grouped = new Map();
        entries.forEach((entry, index) => {
            if (!entry?.statusId || !hasTemplate(entry.statusName)) {
                return;
            }
            const key = `${entry.statusId}`;
            if (!grouped.has(key)) {
                grouped.set(key, {
                    key,
                    id: String(grouped.size),
                    statusName: entry.statusName,
                    statusId: entry.statusId,
                    entries: [],
                });
            }
            grouped.get(key).entries.push({ entry, index });
        });

        return Array.from(grouped.values()).filter((candidate) => candidate.entries.length > 1);
    }

    function renderGroupingStep(entries) {
        pendingGroupEntries = entries;
        groupingCandidates = buildGroupingCandidates(entries);
        groupingMode = true;
        setGroupingUi(true);
        updateSequentialUi();

        const grouping = document.getElementById("archive-act-grouping");
        if (!grouping) return;

        const sections = groupingCandidates.map((candidate) => {
            const animalsHtml = candidate.entries.map(({ entry, index }) => `
                <label class="list-group-item d-flex align-items-center gap-2">
                    <input type="checkbox"
                           class="form-check-input mt-0 archive-act-group-checkbox"
                           data-group-id="${escapeHtml(candidate.id)}"
                           value="${index}">
                    <span>${escapeHtml(getDisplayAnimalLabel(entry.animal))}</span>
                </label>
            `).join("");

            return `
                <div class="border rounded p-3 mb-3">
                    <div class="fw-semibold mb-1">${escapeHtml(candidate.statusName)}</div>
                    <label class="form-label" for="archive-act-common-number-${escapeHtml(candidate.id)}">
                        Номер общего акта для отмеченных животных:
                    </label>
                    <input type="text"
                           id="archive-act-common-number-${escapeHtml(candidate.id)}"
                           class="form-control mb-3 archive-act-common-number"
                           data-group-id="${escapeHtml(candidate.id)}"
                           placeholder="Введите номер общего акта">
                    <div class="list-group">${animalsHtml}</div>
                </div>
            `;
        }).join("");

        grouping.innerHTML = `
            ${sections}
        `;
    }

    function applyGroupingSelection() {
        groupInfoByEntryIndex = {};

        for (const candidate of groupingCandidates) {
            const checked = Array.from(document.querySelectorAll(
                `.archive-act-group-checkbox[data-group-id="${candidate.id}"]:checked`
            ));
            if (checked.length < 2) {
                continue;
            }

            const commonActNumberInput = document.querySelector(
                `.archive-act-common-number[data-group-id="${candidate.id}"]`
            );
            const commonActNumber = commonActNumberInput?.value?.trim() || "";
            if (!commonActNumber) {
                return { error: `Укажите номер общего акта для статуса "${candidate.statusName}".` };
            }

            const selectedIndexes = new Set(checked.map((checkbox) => Number.parseInt(checkbox.value, 10)));
            const groupKey = generateGroupKey();
            const groupInfo = {
                groupKey,
                commonActNumber,
                statusDate: null,
            };
            pendingGroupEntries.forEach((entry, index) => {
                if (selectedIndexes.has(index)) {
                    groupInfoByEntryIndex[index] = groupInfo;
                }
            });
        }

        groupingMode = false;
        const entries = pendingGroupEntries;
        pendingGroupEntries = [];
        groupingCandidates = [];
        setGroupingUi(false);
        startDetailsStep(entries);
        return { complete: false };
    }

    function collectEntriesForSelected(animals) {
        if (statusAssignmentMode) {
            return collectStatusAssignments();
        }

        if (groupingMode) {
            return applyGroupingSelection();
        }

        if (sequentialMode) {
            const currentAnimal = sequentialAnimals[sequentialIndex];
            const currentEntry = collectArchiveFormEntry(currentAnimal);
            if (currentEntry.__archiveActError) {
                return { error: currentEntry.__archiveActError };
            }

            sequentialEntries[sequentialIndex] = currentEntry;

            if (sequentialIndex < sequentialAnimals.length - 1) {
                showDetailsForIndex(sequentialIndex + 1);
                return { complete: false };
            }

            const entries = sequentialEntries.filter(Boolean);
            return {
                complete: true,
                entries,
            };
        }

        const entries = [];
        const normalizedAnimals = Array.isArray(animals)
            ? animals.map(normalizeSelectedAnimal).filter(Boolean)
            : [];

        for (const animal of normalizedAnimals) {
            const entry = collectArchiveFormEntry(animal);
            if (entry.__archiveActError) {
                return { error: entry.__archiveActError };
            }
            entries.push(entry);
        }

        return { complete: true, entries };
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
        startSequentialArchive,
        toggle,
        collectPayload,
        collectEntriesForSelected,
        downloadArchiveAct,
        hasTemplate,
    };
})();
