let activeShiftTextareaId = null;

function openEditShiftNoteModal(noteId, noteDate, noteText) {
    const noteIdInput = document.getElementById("edit-note-id");
    const noteDateInput = document.getElementById("edit-note-date");
    const noteTextInput = document.getElementById("edit-note-text");

    if (!noteIdInput || !noteDateInput || !noteTextInput) {
        return;
    }

    noteIdInput.value = noteId;
    noteDateInput.value = noteDate;
    noteTextInput.value = noteText || "";

    const modalElement = document.getElementById("editShiftNoteModal");
    if (!modalElement) {
        return;
    }

    const modal = new bootstrap.Modal(modalElement);
    modal.show();
}

function showShiftTagModal(targetTextareaId) {
    activeShiftTextareaId = targetTextareaId;

    const searchInput = document.getElementById("shiftTagSearchInput");
    const tagsList = document.getElementById("shiftTagsList");

    if (searchInput) {
        searchInput.value = "";
    }
    if (tagsList) {
        tagsList.innerHTML = `
            <div class="text-muted text-center py-3">
                Введите номер бирки и нажмите «Поиск»
            </div>
        `;
    }

    const modalElement = document.getElementById("shiftTagModal");
    if (!modalElement) {
        return;
    }
    const modal = new bootstrap.Modal(modalElement);
    modal.show();
}

function insertShiftTag(tagNumber) {
    if (!activeShiftTextareaId) {
        return;
    }

    const textarea = document.getElementById(activeShiftTextareaId);
    if (!textarea) {
        return;
    }

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const source = textarea.value;
    const textToInsert = tagNumber;

    textarea.value = source.slice(0, start) + textToInsert + source.slice(end);
    textarea.selectionStart = start + textToInsert.length;
    textarea.selectionEnd = start + textToInsert.length;
    textarea.focus();

    const modalElement = document.getElementById("shiftTagModal");
    const modal = bootstrap.Modal.getInstance(modalElement);
    if (modal) {
        modal.hide();
    }
}

function renderShiftTags(tags) {
    const tagsList = document.getElementById("shiftTagsList");
    if (!tagsList) {
        return;
    }

    if (!tags || tags.length === 0) {
        tagsList.innerHTML = `<div class="text-center text-muted py-3">Бирки не найдены</div>`;
        return;
    }

    tagsList.innerHTML = "";
    tags.forEach((tag) => {
        const item = document.createElement("div");
        item.className = "shift-tag-item";
        item.innerHTML = `
            <div><strong>${tag.tag_number}</strong></div>
            ${tag.is_active ? "" : '<small class="text-muted">(архив)</small>'}
        `;
        item.addEventListener("click", () => insertShiftTag(tag.tag_number));
        tagsList.appendChild(item);
    });
}

async function searchShiftTags() {
    const searchInput = document.getElementById("shiftTagSearchInput");
    const tagsList = document.getElementById("shiftTagsList");
    if (!searchInput || !tagsList) {
        return;
    }

    const searchValue = searchInput.value.trim();
    if (!searchValue) {
        tagsList.innerHTML = `<div class="text-center text-muted py-3">Введите номер бирки для поиска</div>`;
        return;
    }

    tagsList.innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm" role="status"></div>
            <div class="mt-2">Поиск...</div>
        </div>
    `;

    try {
        const response = await fetch(`/animals/api/all-tags/?search=${encodeURIComponent(searchValue)}`);
        const data = await response.json();
        if (!Array.isArray(data)) {
            tagsList.innerHTML = `<div class="text-center text-danger py-3">Ошибка поиска</div>`;
            return;
        }
        renderShiftTags(data.slice(0, 50));
    } catch (error) {
        tagsList.innerHTML = `<div class="text-center text-danger py-3">Ошибка соединения</div>`;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const searchBtn = document.getElementById("shiftTagSearchBtn");
    const searchInput = document.getElementById("shiftTagSearchInput");

    if (searchBtn) {
        searchBtn.addEventListener("click", searchShiftTags);
    }

    if (searchInput) {
        searchInput.addEventListener("keypress", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                searchShiftTags();
            }
        });
    }
});

window.openEditShiftNoteModal = openEditShiftNoteModal;
window.showShiftTagModal = showShiftTagModal;
