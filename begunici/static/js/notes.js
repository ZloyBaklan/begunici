// notes.js
// Минимальная версия: неделя текущей даты + создание заметки + отображение заметок по дням

function fmtDate(d) {
  // YYYY-MM-DD
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function startOfWeekMonday(d) {
  const dt = new Date(d);
  const day = dt.getDay(); // 0..6, 0=Sun
  const diff = (day === 0 ? -6 : 1 - day); // to Monday
  dt.setDate(dt.getDate() + diff);
  dt.setHours(0,0,0,0);
  return dt;
}

async function apiGetNotesRange(from, to) {
  const resp = await fetch(`/notes/api/notes/?from=${from}&to=${to}`, { credentials: "same-origin" });
  if (!resp.ok) throw new Error("Failed to load notes");
  return await resp.json();
}

async function apiCreateNote(text) {
  const resp = await fetch(`/notes/api/notes/`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text })
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create note");
  }
  return await resp.json();
}

function groupByDate(notes) {
  const map = new Map();
  for (const n of notes) {
    if (!map.has(n.date)) map.set(n.date, []);
    map.get(n.date).push(n);
  }
  return map;
}

function renderWeek(container, weekStart, notesByDate) {
  const days = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + i);
    days.push(d);
  }

  const html = `
    <div class="row g-2">
      ${days.map(d => {
        const key = fmtDate(d);
        const items = notesByDate.get(key) || [];
        const list = items.slice(0, 3).map(x => `<div class="small">• ${escapeHtml(x.text)}</div>`).join("");
        const more = items.length > 3 ? `<div class="small text-muted">ещё ${items.length - 3}</div>` : "";
        return `
          <div class="col">
            <div class="card h-100">
              <div class="card-body">
                <div class="fw-bold">${d.getDate()}</div>
                <div>${list}${more}</div>
              </div>
            </div>
          </div>
        `;
      }).join("")}
    </div>
  `;
  container.innerHTML = html;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.addEventListener("DOMContentLoaded", async () => {
  const cal = document.getElementById("notes-calendar");
  const btnToday = document.getElementById("btn-today");
  const btnAdd = document.getElementById("btn-add");
  const card = document.getElementById("note-form-card");
  const ta = document.getElementById("note-text");
  const btnSave = document.getElementById("note-save");
  const btnCancel = document.getElementById("note-cancel");
  const hint = document.getElementById("note-hint");

  let mode = "week";
  let anchor = new Date(); // текущая дата

  async function refresh() {
    if (mode === "week") {
      const ws = startOfWeekMonday(anchor);
      const we = new Date(ws); we.setDate(we.getDate() + 6);

      const from = fmtDate(ws);
      const to = fmtDate(we);

      const notes = await apiGetNotesRange(from, to);
      const grouped = groupByDate(notes);

      renderWeek(cal, ws, grouped);
    } else {
      cal.innerHTML = `<div class="text-muted">Режим "${mode}" подключим следующим шагом.</div>`;
    }
  }

  btnToday.addEventListener("click", async () => {
    anchor = new Date();
    await refresh();
  });

  btnAdd.addEventListener("click", () => {
    card.style.display = "block";
    hint.textContent = "Дата будет проставлена автоматически (сегодня).";
    ta.focus();
  });

  btnCancel.addEventListener("click", () => {
    card.style.display = "none";
    ta.value = "";
  });

  btnSave.addEventListener("click", async () => {
    const text = ta.value.trim();
    if (!text) return;
    await apiCreateNote(text);
    card.style.display = "none";
    ta.value = "";
    await refresh();
  });

  document.getElementById("mode-week").addEventListener("click", async () => { mode = "week"; await refresh(); });
  document.getElementById("mode-month").addEventListener("click", async () => { mode = "month"; await refresh(); });
  document.getElementById("mode-year").addEventListener("click", async () => { mode = "year"; await refresh(); });

  await refresh();
});
