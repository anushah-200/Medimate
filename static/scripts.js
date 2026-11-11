const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// App state — loaded from the server on startup, not localStorage
const state = {
  medicines: [],
  events: [],
  settings: { missedWindow: 60 }
};

// All DOM element references
const el = {
  sidebar:           document.querySelector("#sidebar"),
  menuButton:        document.querySelector("#menuButton"),
  navLinks:          document.querySelectorAll(".nav-link"),
  pageSections:      document.querySelectorAll(".page-section"),
  pageTitle:         document.querySelector("#pageTitle"),
  currentDate:       document.querySelector("#currentDate"),
  total:             document.querySelector("#totalReminderCount"),
  completed:         document.querySelector("#completedCount"),
  pending:           document.querySelector("#pendingCount"),
  missed:            document.querySelector("#missedCount"),
  weekly:            document.querySelector("#weeklyPlanChart"),
  ring:              document.querySelector("#adherenceRing"),
  pieCompleted:      document.querySelector("#pieCompleted"),
  piePending:        document.querySelector("#piePending"),
  pieMissed:         document.querySelector("#pieMissed"),
  progressPercent:   document.querySelector("#todayProgressPercent"),
  progressCompleted: document.querySelector("#progressCompletedCount"),
  progressPending:   document.querySelector("#progressPendingCount"),
  progressMissed:    document.querySelector("#progressMissedCount"),
  progressSummary:   document.querySelector("#todayProgressSummary"),
  nextName:          document.querySelector("#nextMedicineName"),
  nextDose:          document.querySelector("#nextMedicineDose"),
  nextTime:          document.querySelector("#nextReminderTime"),
  nextStatus:        document.querySelector("#nextReminderStatus"),
  countdown:         document.querySelector("#countdown"),
  todayList:         document.querySelector("#todayScheduleList"),
  recentEvents:      document.querySelector("#recentEventList"),
  managementList:    document.querySelector("#scheduleManagementList"),
  historyBody:       document.querySelector("#historyTableBody"),
  eventFilter:       document.querySelector("#eventFilter"),
  modal:             document.querySelector("#medicineModal"),
  modalTitle:        document.querySelector("#modalTitle"),
  medicineForm:      document.querySelector("#medicineForm"),
  medicineId:        document.querySelector("#medicineId"),
  medicineName:      document.querySelector("#medicineName"),
  medicineDose:      document.querySelector("#medicineDose"),
  medicineTime:      document.querySelector("#medicineTime"),
  closeModal:        document.querySelector("#closeModalButton"),
  cancelModal:       document.querySelector("#cancelModalButton"),
  settingsForm:      document.querySelector("#settingsForm"),
  missedWindow:      document.querySelector("#missedWindow"),
  lastRefreshed:     document.querySelector("#lastRefreshed"),
  deviceStatus:      document.querySelector("#deviceConnectionStatus"),
  lastEvent:         document.querySelector("#lastEventStatus"),
  connectionLabel:   document.querySelector("#connectionLabel"),
  connectionDot:     document.querySelector("#connectionDot"),
  toast:             document.querySelector("#toast")
};

// ── Data helpers ──────────────────────────────────────────────────────────────

function todayCode(date = new Date()) {
  return DAYS[(date.getDay() + 6) % 7];
}

function todayMedicines() {
  return state.medicines
    .filter(m => m.days.includes(todayCode()))
    .sort((a, b) => a.time.localeCompare(b.time));
}

// ── API calls ─────────────────────────────────────────────────────────────────

async function loadMedicines() {
  const res = await fetch('/api/medicines');
  if (!res.ok) throw new Error('Could not load medicines');
  state.medicines = await res.json();
}

async function loadEvents() {
  const res = await fetch('/api/events');
  if (!res.ok) throw new Error('Could not load events');
  state.events = await res.json();
}

async function loadSettings() {
  const res = await fetch('/api/settings');
  if (!res.ok) throw new Error('Could not load settings');
  state.settings = await res.json();
}

async function loadAll() {
  try {
    await Promise.all([loadMedicines(), loadEvents(), loadSettings()]);
    renderAll();
  } catch (err) {
    showToast('Could not reach server. Is Flask running?');
  }
}

async function pollStatus() {
  try {
    const res  = await fetch('/api/status');
    if (!res.ok) throw new Error('Could not load status');
    const data = await res.json();
    if (el.deviceStatus)    el.deviceStatus.textContent    = data.device_status || "Unknown";
    if (el.lastEvent)       el.lastEvent.textContent       = data.last_event    || "None";
    if (el.connectionLabel) el.connectionLabel.textContent = "Connected";
    if (el.connectionDot)   el.connectionDot.style.background = "#27ae60";
    // Refresh live reminder statuses and events together.
    await Promise.all([loadMedicines(), loadEvents()]);
    renderStats();
    renderTodaySchedule();
    renderNextReminder();
    renderEvents();
    renderHistory();
  } catch (err) {
    if (el.connectionLabel) el.connectionLabel.textContent = "Server offline";
    if (el.connectionDot)   el.connectionDot.style.background = "#e74c3c";
  }
}

// ── UI helpers ────────────────────────────────────────────────────────────────

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = String(value);
  return node.innerHTML;
}

function statusClass(status) {
  return String(status).toLowerCase().replace(/\s+/g, "-");
}

function formatTime(value) {
  if (!value) return "--:--";
  const [hours, minutes] = value.split(":").map(Number);
  const date = new Date();
  date.setHours(hours, minutes, 0, 0);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function showToast(message) {
  el.toast.textContent = message;
  el.toast.classList.add("visible");
  clearTimeout(showToast.timeout);
  showToast.timeout = setTimeout(() => el.toast.classList.remove("visible"), 2600);
}

// ── Render functions ──────────────────────────────────────────────────────────

function renderDate() {
  el.currentDate.textContent = new Date().toLocaleDateString(undefined, {
    weekday: "long", day: "numeric", month: "long", year: "numeric"
  });
}

function renderStats() {
  const medicines = todayMedicines();
  const completed = medicines.filter(m => m.status === "completed").length;
  const missed    = medicines.filter(m => m.status === "missed").length;
  const pending   = medicines.length - completed - missed;

  el.total.textContent     = medicines.length;
  el.completed.textContent = completed;
  el.pending.textContent   = pending;
  el.missed.textContent    = missed;

  const total = medicines.length;
  const rate  = total ? Math.round(completed / total * 100) : 0;
  const circumference = 2 * Math.PI * 45;
  let offset = 0;
  [[el.pieCompleted, completed], [el.piePending, pending], [el.pieMissed, missed]].forEach(([seg, count]) => {
    const length = total ? count / total * circumference : 0;
    seg.style.strokeDasharray  = `${length} ${circumference - length}`;
    seg.style.strokeDashoffset = String(-offset);
    offset += length;
  });

  el.progressPercent.textContent   = `${rate}%`;
  el.progressCompleted.textContent = completed;
  el.progressPending.textContent   = pending;
  el.progressMissed.textContent    = missed;
  el.progressSummary.textContent   = `${completed} of ${total} reminders completed`;
}

function renderWeeklyPlan() {
  const counts  = DAYS.map(day => state.medicines.filter(m => m.days.includes(day)).length);
  const maximum = Math.max(...counts, 1);
  el.weekly.innerHTML = DAYS.map((day, i) => {
    const count  = counts[i];
    const height = count ? Math.max(count / maximum * 100, 8) : 3;
    return `<div class="day-column ${day === todayCode() ? "current" : ""}">
      <span class="day-count">${count}</span>
      <div class="bar-track"><div class="bar-fill" style="height:${height}%"></div></div>
      <span class="day-label">${day}</span>
    </div>`;
  }).join("");
  el.weekly.setAttribute("aria-label", `Weekly reminders: ${DAYS.map((day, i) => `${day} ${counts[i]}`).join(", ")}`);
}

function renderNextReminder() {
  const now      = new Date();
  const upcoming = todayMedicines().find(m => {
    const [h, min] = m.time.split(":").map(Number);
    const at = new Date();
    at.setHours(h, min, 0, 0);
    return at > now && !["completed", "missed"].includes(m.status);
  });

  if (!upcoming) {
    el.nextName.textContent   = "No upcoming reminder";
    el.nextDose.textContent   = todayMedicines().length ? "You're all caught up for today." : "No medicines scheduled for today.";
    el.nextTime.textContent   = "--:--";
    el.nextStatus.textContent = "None";
    el.nextStatus.className   = "status-pill completed";
    el.countdown.textContent  = "-- : -- : --";
    return;
  }

  el.nextName.textContent   = upcoming.name;
  el.nextDose.textContent   = upcoming.dose;
  el.nextTime.textContent   = formatTime(upcoming.time);
  el.nextStatus.textContent = upcoming.status;
  el.nextStatus.className   = `status-pill ${statusClass(upcoming.status)}`;

  const [h, min] = upcoming.time.split(":").map(Number);
  const target   = new Date();
  target.setHours(h, min, 0, 0);
  let remaining  = Math.max(0, target.getTime() - Date.now());
  const hh = Math.floor(remaining / 3600000); remaining %= 3600000;
  const mm = Math.floor(remaining / 60000);
  const ss = Math.floor(remaining % 60000 / 1000);
  el.countdown.textContent = [hh, mm, ss].map(v => String(v).padStart(2, "0")).join(" : ");
}

function renderTodaySchedule() {
  const medicines = todayMedicines();
  if (!medicines.length) {
    el.todayList.innerHTML = '<div class="empty-state">No medicines scheduled for today.</div>';
    return;
  }
  el.todayList.innerHTML = medicines.map(m => `<div class="schedule-item">
    <span class="schedule-time">${escapeHtml(formatTime(m.time))}</span>
    <div class="schedule-information"><strong>${escapeHtml(m.name)}</strong><small>${escapeHtml(m.dose)}</small></div>
    <span class="status-pill ${statusClass(m.status)}">${escapeHtml(m.status)}</span>
  </div>`).join("");
}

function eventIcon(type) {
  return ({ opening: "□", acknowledged: "✓", missed: "!", triggered: "◷" })[type] || "•";
}

function renderEvents() {
  const events = state.events.slice(0, 5);
  if (!events.length) {
    el.recentEvents.innerHTML = '<div class="empty-state">No recent events.</div>';
    return;
  }
  el.recentEvents.innerHTML = events.map(evt => `<div class="event-item">
    <span class="event-icon" aria-hidden="true">${eventIcon(evt.type)}</span>
    <div class="event-information"><strong>${escapeHtml(evt.label)}</strong><small>${escapeHtml(evt.medicine)} at ${escapeHtml(formatTime(evt.time))}</small></div>
    <span class="status-pill ${statusClass(evt.status)}">${escapeHtml(evt.status)}</span>
  </div>`).join("");
}

function renderMedicineCards() {
  if (!state.medicines.length) {
    el.managementList.innerHTML = '<div class="panel empty-state">No reminders yet. Add a medicine to get started.</div>';
    return;
  }
  el.managementList.innerHTML = state.medicines.slice().sort((a, b) => a.time.localeCompare(b.time)).map(m => `<article class="medicine-card">
    <div class="medicine-card-header">
      <span class="medicine-mark" aria-hidden="true">Rx</span>
      <div class="medicine-heading"><h3>${escapeHtml(m.name)}</h3><p>${escapeHtml(m.dose)}</p></div>
      <div class="card-menu">
        <button class="small-action-button" type="button" data-edit-id="${m.id}" aria-label="Edit ${escapeHtml(m.name)}" title="Edit">✎</button>
        <button class="small-action-button delete" type="button" data-delete-id="${m.id}" aria-label="Delete ${escapeHtml(m.name)}" title="Delete">×</button>
      </div>
    </div>
    <div class="medicine-details">
      <div><span>Reminder time</span><strong>${escapeHtml(formatTime(m.time))}</strong></div>
      <div><span>Scheduled days</span><strong>${escapeHtml(m.days.join(", "))}</strong></div>
    </div>
  </article>`).join("");
}

function renderHistory() {
  const filter = el.eventFilter.value;
  const events = filter === "all" ? state.events : state.events.filter(e => e.type === filter);
  if (!events.length) {
    el.historyBody.innerHTML = '<tr><td class="empty-state" colspan="4">No events match this filter.</td></tr>';
    return;
  }
  el.historyBody.innerHTML = events.map(evt => `<tr class="history-row ${statusClass(evt.type)}">
    <td>${escapeHtml(formatTime(evt.time))}</td>
    <td>${escapeHtml(evt.medicine)}</td>
    <td><span class="history-event-label"><span class="history-marker" aria-hidden="true"></span>${escapeHtml(evt.label)}</span></td>
    <td><span class="status-pill ${statusClass(evt.status)}">${escapeHtml(evt.status)}</span></td>
  </tr>`).join("");
}

function renderAll() {
  renderDate();
  renderStats();
  renderWeeklyPlan();
  renderNextReminder();
  renderTodaySchedule();
  renderEvents();
  renderMedicineCards();
  renderHistory();
  el.missedWindow.value        = state.settings.missedWindow || 60;
  el.lastRefreshed.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ── Navigation ────────────────────────────────────────────────────────────────

function navigate(section) {
  el.navLinks.forEach(link => link.classList.toggle("active", link.dataset.section === section));
  el.pageSections.forEach(page => page.classList.toggle("active", page.id === `${section}Section`));
  const titles = { dashboard: "Dashboard", schedules: "Schedules", history: "Event History", settings: "Settings" };
  el.pageTitle.textContent = titles[section] || "MediMate";
  el.sidebar.classList.remove("open");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function openModal(medicine = null) {
  el.medicineForm.reset();
  el.medicineId.value = "";
  el.modalTitle.textContent = medicine ? "Edit reminder" : "Add medicine";
  if (medicine) {
    el.medicineId.value   = medicine.id;
    el.medicineName.value = medicine.name;
    el.medicineDose.value = medicine.dose;
    el.medicineTime.value = medicine.time;
    document.querySelectorAll(".day-selector input").forEach(input => {
      input.checked = medicine.days.includes(input.value);
    });
  }
  el.modal.hidden = false;
  document.body.style.overflow = "hidden";
  el.medicineName.focus();
}

function closeModal() {
  el.modal.hidden = true;
  document.body.style.overflow = "";
}

// ── Save / Delete via API ─────────────────────────────────────────────────────

async function saveMedicine(event) {
  event.preventDefault();
  const days = Array.from(document.querySelectorAll(".day-selector input:checked"), input => input.value);
  if (!days.length) {
    showToast("Select at least one scheduled day.");
    return;
  }

  const id = Number(el.medicineId.value) || null;
  const medicine = {
    name: el.medicineName.value.trim(),
    dose: el.medicineDose.value.trim(),
    time: el.medicineTime.value,
    days
  };

  try {
    const url    = id ? `/api/medicines/${id}` : '/api/medicines';
    const method = id ? 'PUT' : 'POST';
    const res    = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(medicine)
    });
    if (!res.ok) throw new Error('Server error');
    await loadAll();
    closeModal();
    showToast(id ? "Reminder updated." : "Reminder added.");
  } catch (err) {
    showToast("Could not save. Is the server running?");
  }
}

async function deleteMedicine(id) {
  const medicine = state.medicines.find(m => m.id === id);
  if (!medicine || !window.confirm(`Delete the reminder for "${medicine.name}"?`)) return;
  try {
    const res = await fetch(`/api/medicines/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Could not delete medicine');
    await loadAll();
    showToast("Reminder deleted.");
  } catch (err) {
    showToast("Could not delete. Is the server running?");
  }
}

// ── Event listeners ───────────────────────────────────────────────────────────

function attachEvents() {
  el.navLinks.forEach(link => link.addEventListener("click", () => navigate(link.dataset.section)));
  document.querySelectorAll("[data-navigate]").forEach(btn => btn.addEventListener("click", () => navigate(btn.dataset.navigate)));
  document.querySelectorAll("[data-open-modal]").forEach(btn => btn.addEventListener("click", () => openModal()));
  el.menuButton.addEventListener("click", () => el.sidebar.classList.toggle("open"));
  document.querySelector("#refreshButton").addEventListener("click", async () => {
    await loadAll();
    showToast("Dashboard refreshed.");
  });
  el.closeModal.addEventListener("click", closeModal);
  el.cancelModal.addEventListener("click", closeModal);
  el.modal.addEventListener("click", event => { if (event.target === el.modal) closeModal(); });
  el.medicineForm.addEventListener("submit", saveMedicine);
  el.eventFilter.addEventListener("change", renderHistory);
  el.settingsForm.addEventListener("submit", async event => {
    event.preventDefault();
    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ missedWindow: Number(el.missedWindow.value) })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Could not save settings');
      state.settings = data;
      showToast("Settings saved.");
    } catch (err) {
      showToast(err.message || "Could not save settings.");
    }
  });
  el.managementList.addEventListener("click", event => {
    const edit   = event.target.closest("[data-edit-id]");
    const remove = event.target.closest("[data-delete-id]");
    if (edit)   openModal(state.medicines.find(m => m.id === Number(edit.dataset.editId)));
    if (remove) deleteMedicine(Number(remove.dataset.deleteId));
  });
  document.addEventListener("keydown", event => { if (event.key === "Escape" && !el.modal.hidden) closeModal(); });
}

// ── Start ─────────────────────────────────────────────────────────────────────

loadAll();                              // Load data from Flask on page open
pollStatus();
attachEvents();
setInterval(renderNextReminder, 1000); // Update countdown every second
setInterval(pollStatus, 5000);         // Poll server for live device status and events
