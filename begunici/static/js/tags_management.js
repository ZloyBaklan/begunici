import { apiRequest, getApiErrorMessage } from "./utils.js";

let currentSection = "temporary";
let selectedSearchAnimal = null;
let retaggingAnimal = null;

const typeOrder = ["Баран-производитель", "Баранчик", "Ярка", "Овцематка"];

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
}

function showMessage(message, type = "success") {
    const messageElement = document.getElementById("tags-message");
    if (!messageElement) return;

    messageElement.className = `alert alert-${type}`;
    messageElement.textContent = message;
    messageElement.classList.remove("d-none");

    setTimeout(() => {
        messageElement.classList.add("d-none");
    }, 5000);
}

function setSection(section) {
    currentSection = section === "retagging" ? "retagging" : "temporary";
    const temporarySection = document.getElementById("temporary-tags-section");
    const retaggingSection = document.getElementById("retagging-section");
    const temporaryTab = document.getElementById("temporary-tags-tab");
    const retaggingTab = document.getElementById("retagging-tab");

    if (temporarySection) temporarySection.style.display = currentSection === "temporary" ? "" : "none";
    if (retaggingSection) retaggingSection.style.display = currentSection === "retagging" ? "" : "none";

    if (temporaryTab) {
        temporaryTab.classList.toggle("active", currentSection === "temporary");
        temporaryTab.setAttribute("aria-pressed", currentSection === "temporary" ? "true" : "false");
    }
    if (retaggingTab) {
        retaggingTab.classList.toggle("active", currentSection === "retagging");
        retaggingTab.setAttribute("aria-pressed", currentSection === "retagging" ? "true" : "false");
    }

    if (currentSection === "temporary") {
        loadTemporaryTags();
    } else {
        loadRetaggingAnimals();
    }
}

async function loadTemporaryTags() {
    const tbody = document.getElementById("temporary-tags-list");
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Загрузка...</td></tr>';
    try {
        const tags = await apiRequest("/animals/api/tags/temporary/");
        if (!tags.length) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Временных бирок нет</td></tr>';
            return;
        }

        tbody.innerHTML = tags.map((tag, index) => `
            <tr>
                <td>${index + 1}</td>
                <td>${escapeHtml(tag.tag_number)}</td>
                <td>
                    <button type="button" class="btn btn-sm btn-outline-danger delete-temporary-tag-btn" data-id="${tag.id}">
                        Удалить
                    </button>
                </td>
            </tr>
        `).join("");
    } catch (error) {
        console.error("Ошибка загрузки временных бирок:", error);
        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-danger">Ошибка загрузки</td></tr>';
    }
}

async function createTemporaryTag() {
    const input = document.getElementById("temporary-tag-input");
    const tagNumber = input?.value?.trim() || "";
    if (!tagNumber) {
        showMessage("Укажите временную бирку.", "warning");
        return;
    }

    try {
        await apiRequest("/animals/api/tags/temporary/", "POST", { tag_number: tagNumber });
        if (input) input.value = "";
        showMessage("Временная бирка создана");
        await loadTemporaryTags();
    } catch (error) {
        showMessage(getApiErrorMessage(error?.data || error), "warning");
    }
}

async function deleteTemporaryTag(tagId) {
    if (!confirm("Удалить временную бирку?")) {
        return;
    }

    try {
        await apiRequest(`/animals/api/tags/temporary/${tagId}/`, "DELETE");
        showMessage("Временная бирка удалена");
        await loadTemporaryTags();
    } catch (error) {
        showMessage(getApiErrorMessage(error?.data || error), "warning");
    }
}

async function loadRetaggingAnimals() {
    const tbody = document.getElementById("retagging-animals-list");
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Загрузка...</td></tr>';
    try {
        const animals = await apiRequest("/animals/api/tags/retagging/");
        if (!animals.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Животных на перебиркование нет</td></tr>';
            return;
        }

        tbody.innerHTML = animals.map((animal, index) => `
            <tr>
                <td>${index + 1}</td>
                <td>${escapeHtml(animal.animal_type_label)}</td>
                <td>
                    <a href="${escapeHtml(animal.url)}">${escapeHtml(animal.display_name || animal.tag_number)}</a>
                </td>
                <td>${escapeHtml(animal.status)}</td>
                <td>
                    <button type="button" class="btn btn-sm btn-outline-secondary me-2 unmark-retagging-btn"
                        data-animal-type="${escapeHtml(animal.animal_type)}"
                        data-tag-number="${escapeHtml(animal.tag_number)}">
                        Убрать из списка
                    </button>
                    <button type="button" class="btn btn-sm btn-primary open-retag-modal-btn"
                        data-animal-type="${escapeHtml(animal.animal_type)}"
                        data-tag-number="${escapeHtml(animal.tag_number)}"
                        data-display-name="${escapeHtml(animal.display_name || animal.tag_number)}"
                        data-animal-type-label="${escapeHtml(animal.animal_type_label)}">
                        Перебирковать
                    </button>
                </td>
            </tr>
        `).join("");
    } catch (error) {
        console.error("Ошибка загрузки списка перебиркования:", error);
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Ошибка загрузки</td></tr>';
    }
}

function openAddRetaggingModal() {
    selectedSearchAnimal = null;
    const searchInput = document.getElementById("retagging-animal-search");
    const results = document.getElementById("retagging-animal-search-results");
    if (searchInput) searchInput.value = "";
    if (results) {
        results.innerHTML = `
            <div class="text-muted text-center py-3">
                Введите бирку или РСХН и нажмите "Поиск" для отображения результатов
            </div>
        `;
    }

    const modal = new bootstrap.Modal(document.getElementById("addRetaggingAnimalModal"));
    modal.show();
}

async function searchRetaggingAnimals() {
    const searchInput = document.getElementById("retagging-animal-search");
    const results = document.getElementById("retagging-animal-search-results");
    const search = searchInput?.value?.trim() || "";
    selectedSearchAnimal = null;

    if (!results) return;
    if (!search) {
        results.innerHTML = '<div class="text-muted text-center py-3">Введите бирку или РСХН для поиска</div>';
        return;
    }

    results.innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Поиск...</span>
            </div>
            <div class="mt-2">Поиск животных...</div>
        </div>
    `;

    try {
        const animals = await apiRequest(`/animals/api/tags/retagging/search/?search=${encodeURIComponent(search)}`);
        if (!animals.length) {
            results.innerHTML = '<div class="text-center text-muted">Животные не найдены</div>';
            return;
        }

        results.innerHTML = "";
        typeOrder.forEach(typeName => {
            const group = animals.filter(animal => animal.animal_type_label === typeName);
            if (!group.length) return;

            const header = document.createElement("h6");
            header.className = "mt-3 mb-2 text-primary";
            header.textContent = typeName;
            results.appendChild(header);

            group.forEach(animal => {
                const item = document.createElement("div");
                item.className = "form-check mb-2";
                item.innerHTML = `
                    <input class="form-check-input retagging-animal-radio" type="radio" name="retagging-animal"
                        value="${escapeHtml(animal.tag_number)}"
                        data-animal-type="${escapeHtml(animal.animal_type)}"
                        data-display-name="${escapeHtml(animal.display_name || animal.tag_number)}">
                    <label class="form-check-label">
                        ${escapeHtml(animal.display_name || animal.tag_number)} (${escapeHtml(animal.status)} · ${escapeHtml(animal.place)})
                    </label>
                `;
                results.appendChild(item);
            });
        });

        document.querySelectorAll(".retagging-animal-radio").forEach(radio => {
            radio.addEventListener("change", () => {
                selectedSearchAnimal = {
                    animal_type: radio.dataset.animalType,
                    tag_number: radio.value,
                    display_name: radio.dataset.displayName,
                };
            });
        });
    } catch (error) {
        console.error("Ошибка поиска животных:", error);
        results.innerHTML = '<div class="text-danger text-center py-3">Ошибка поиска</div>';
    }
}

async function addSelectedAnimalToRetagging() {
    if (!selectedSearchAnimal) {
        showMessage("Выберите животное", "warning");
        return;
    }

    try {
        await apiRequest("/animals/api/tags/retagging/mark/", "POST", selectedSearchAnimal);
        bootstrap.Modal.getInstance(document.getElementById("addRetaggingAnimalModal"))?.hide();
        showMessage("Животное добавлено к перебиркованию");
        await loadRetaggingAnimals();
    } catch (error) {
        showMessage(getApiErrorMessage(error?.data || error), "warning");
    }
}

async function unmarkRetaggingAnimal(animalType, tagNumber) {
    if (!confirm(`Убрать ${tagNumber} из списка перебиркования?`)) {
        return;
    }

    try {
        await apiRequest("/animals/api/tags/retagging/unmark/", "POST", {
            animal_type: animalType,
            tag_number: tagNumber,
        });
        showMessage("Животное убрано из списка");
        await loadRetaggingAnimals();
    } catch (error) {
        showMessage(getApiErrorMessage(error?.data || error), "warning");
    }
}

function openRetagModal(button) {
    retaggingAnimal = {
        animal_type: button.dataset.animalType,
        tag_number: button.dataset.tagNumber,
        display_name: button.dataset.displayName,
        animal_type_label: button.dataset.animalTypeLabel,
    };

    const description = document.getElementById("retag-animal-description");
    const input = document.getElementById("new-tag-number-input");
    if (description) {
        description.textContent = `${retaggingAnimal.animal_type_label}: ${retaggingAnimal.display_name}`;
    }
    if (input) {
        input.value = "";
    }

    const modal = new bootstrap.Modal(document.getElementById("retagAnimalModal"));
    modal.show();
}

async function retagAnimal() {
    const input = document.getElementById("new-tag-number-input");
    const newTagNumber = input?.value?.trim() || "";

    if (!retaggingAnimal) {
        showMessage("Животное не выбрано", "warning");
        return;
    }
    if (!newTagNumber) {
        showMessage("Введите новую бирку", "warning");
        return;
    }

    try {
        const response = await apiRequest("/animals/api/tags/retagging/change/", "POST", {
            animal_type: retaggingAnimal.animal_type,
            tag_number: retaggingAnimal.tag_number,
            new_tag_number: newTagNumber,
        });
        bootstrap.Modal.getInstance(document.getElementById("retagAnimalModal"))?.hide();
        showMessage(`Бирка изменена: ${response.old_tag_number} → ${response.new_tag_number}`);
        await loadRetaggingAnimals();
    } catch (error) {
        showMessage(getApiErrorMessage(error?.data || error), "warning");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("temporary-tags-tab")?.addEventListener("click", () => setSection("temporary"));
    document.getElementById("retagging-tab")?.addEventListener("click", () => setSection("retagging"));
    document.getElementById("create-temporary-tag-btn")?.addEventListener("click", createTemporaryTag);
    document.getElementById("temporary-tag-input")?.addEventListener("keypress", event => {
        if (event.key === "Enter") createTemporaryTag();
    });
    document.getElementById("open-add-retagging-modal-btn")?.addEventListener("click", openAddRetaggingModal);
    document.getElementById("search-retagging-animal-btn")?.addEventListener("click", searchRetaggingAnimals);
    document.getElementById("retagging-animal-search")?.addEventListener("keypress", event => {
        if (event.key === "Enter") searchRetaggingAnimals();
    });
    document.getElementById("confirm-add-retagging-animal-btn")?.addEventListener("click", addSelectedAnimalToRetagging);
    document.getElementById("confirm-retag-animal-btn")?.addEventListener("click", retagAnimal);
    document.getElementById("new-tag-number-input")?.addEventListener("keypress", event => {
        if (event.key === "Enter") retagAnimal();
    });

    document.addEventListener("click", event => {
        const deleteButton = event.target.closest(".delete-temporary-tag-btn");
        if (deleteButton) {
            deleteTemporaryTag(deleteButton.dataset.id);
            return;
        }

        const unmarkButton = event.target.closest(".unmark-retagging-btn");
        if (unmarkButton) {
            unmarkRetaggingAnimal(unmarkButton.dataset.animalType, unmarkButton.dataset.tagNumber);
            return;
        }

        const retagButton = event.target.closest(".open-retag-modal-btn");
        if (retagButton) {
            openRetagModal(retagButton);
        }
    });

    setSection("temporary");
});
