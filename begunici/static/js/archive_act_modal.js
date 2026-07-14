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
        if (statusDate) statusDate.value = getTodayInputValue();

        const deathReason = document.getElementById("archive-act-death-reason");
        if (deathReason) deathReason.value = "Травма";

        const fatness = document.getElementById("archive-act-fatness");
        if (fatness) fatness.value = "ср";

        const download = document.getElementById("archive-act-download");
        if (download) download.checked = true;
    }

    function updateSequentialUi() {
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
        resetPerAnimalFields();

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
        updateSequentialUi();
        loadPreview();
    }

    function startSequentialArchive(animals) {
        sequentialAnimals = Array.isArray(animals)
            ? animals.map(normalizeSelectedAnimal).filter(Boolean)
            : [];
        sequentialEntries = [];
        sequentialIndex = 0;
        sequentialMode = sequentialAnimals.length > 1;
        selectedAnimals = sequentialMode
            ? [sequentialAnimals[0]]
            : sequentialAnimals.slice();
        resetPerAnimalFields();
        updateSequentialUi();
        loadPreview();
    }

    function updateStatusSpecificFields() {
        const statusName = getSelectedStatusName();
        const diagnosisGroup = document.getElementById("archive-act-diagnosis-group");
        const deathReasonGroup = document.getElementById("archive-act-death-reason-group");

        if (diagnosisGroup) diagnosisGroup.style.display = "block";
        if (deathReasonGroup) deathReasonGroup.style.display = statusName === "Падеж" ? "block" : "none";
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
                throw new Error(errorData.error || "Ошибка предпросмотра акта");
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
        const actDate = document.getElementById("archive-act-date")?.value || "";
        const fatness = document.getElementById("archive-act-fatness")?.value || "";
        const diagnosis = document.getElementById("archive-act-diagnosis")?.value?.trim() || "";
        const deathReason = statusName === "Падеж"
            ? (document.getElementById("archive-act-death-reason")?.value || "")
            : "";

        if (!actNumber) return buildValidationError("Укажите номер акта.");
        if (!actDate) return buildValidationError("Укажите дату акта.");
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
        const statusId = statusSelect?.value;
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

        return {
            animal: normalizedAnimal,
            statusId,
            statusDate,
            carcassWeight,
            archiveActPayload,
        };
    }

    function collectEntriesForSelected(animals) {
        if (sequentialMode) {
            const currentAnimal = sequentialAnimals[sequentialIndex];
            const currentEntry = collectArchiveFormEntry(currentAnimal);
            if (currentEntry.__archiveActError) {
                return { error: currentEntry.__archiveActError };
            }

            sequentialEntries[sequentialIndex] = currentEntry;

            if (sequentialIndex < sequentialAnimals.length - 1) {
                sequentialIndex += 1;
                selectedAnimals = [sequentialAnimals[sequentialIndex]];
                resetPerAnimalFields();
                updateSequentialUi();
                toggle();
                loadPreview();
                return { complete: false };
            }

            return {
                complete: true,
                entries: sequentialEntries.filter(Boolean),
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
