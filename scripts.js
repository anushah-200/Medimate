const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const STORAGE_KEYS = {
  medicines: "medimateMedicines",
  events: "medimateEvents",
  settings: "medimateSettings"
};

const defaultMedicines = [
  { id: 1, name: "Vitamin D", dose: "1 tablet after breakfast", time: "09:00", days: [...DAYS], status: "completed" },
  { id: 2, name: "Blood Pressure Tablet", dose: "1 tablet", time: "14:30", days: [...DAYS], status: "pending" },
  { id: 3, name: "Calcium Supplement", dose: "1 tablet after dinner", time: "20:00", days: ["Mon", "Wed", "Fri", "Sun"], status: "pending" }
];
const defaultEvents = [
  { id: 1, time: "09:02", medicine: "Vitamin D", type: "opening", label: "Compartment opened", status: "Opening detected" },
  { id: 2, time: "09:00", medicine: "Vitamin D", type: "triggered", label: "Reminder activated", status: "Due" },
  { id: 3, time: "08:58", medicine: "Vitamin D", type: "acknowledged", label: "Button pressed", status: "Acknowledged" }
];

function loadData(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch (error) {
    console.warn(`Could not load ${key}:`, error);
    return fallback;
  }
}

const state = {
  medicines: loadData(STORAGE_KEYS.medicines, defaultMedicines),
  events: loadData(STORAGE_KEYS.events, defaultEvents),
  settings: loadData(STORAGE_KEYS.settings, { missedWindow: 60 })
};

const el = {
  sidebar: document.querySelector("#sidebar"),
  menuButton: document.querySelector("#menuButton"),
  navLinks: document.querySelectorAll(".nav-link"),
  pageSections: document.querySelectorAll(".page-section"),
  pageTitle: document.querySelector("#pageTitle"),
  currentDate: document.querySelector("#currentDate"),
  total: document.querySelector("#totalReminderCount"),
  completed: document.querySelector("#completedCount"),
  pending: document.querySelector("#pendingCount"),
  missed: document.querySelector("#missedCount"),
  weekly: document.querySelector("#weeklyPlanChart"),
  ring: document.querySelector("#adherenceRing"),
  pieCompleted: document.querySelector("#pieCompleted"),
  piePending: document.querySelector("#piePending"),
  pieMissed: document.querySelector("#pieMissed"),
  progressPercent: document.querySelector("#todayProgressPercent"),
  progressCompleted: document.querySelector("#progressCompletedCount"),
  progressPending: document.querySelector("#progressPendingCount"),
  progressMissed: document.querySelector("#progressMissedCount"),
  progressSummary: document.querySelector("#todayProgressSummary"),
  nextName: document.querySelector("#nextMedicineName"),
  nextDose: document.querySelector("#nextMedicineDose"),
  nextTime: document.querySelector("#nextReminderTime"),
  nextStatus: document.querySelector("#nextReminderStatus"),
  countdown: document.querySelector("#countdown"),
  todayList: document.querySelector("#todayScheduleList"),
  recentEvents: document.querySelector("#recentEventList"),
  managementList: document.querySelector("#scheduleManagementList"),
  historyBody: document.querySelector("#historyTableBody"),
  eventFilter: document.querySelector("#eventFilter"),
  modal: document.querySelector("#medicineModal"),
  modalTitle: document.querySelector("#modalTitle"),
  medicineForm: document.querySelector("#medicineForm"),
  medicineId: document.querySelector("#medicineId"),
  medicineName: document.querySelector("#medicineName"),
  medicineDose: document.querySelector("#medicineDose"),
  medicineTime: document.querySelector("#medicineTime"),
  closeModal: document.querySelector("#closeModalButton"),
  cancelModal: document.querySelector("#cancelModalButton"),
  settingsForm: document.querySelector("#settingsForm"),
  missedWindow: document.querySelector("#missedWindow"),
  lastRefreshed: document.querySelector("#lastRefreshed"),
  toast: document.querySelector("#toast")
};

function saveData() {
  localStorage.setItem(STORAGE_KEYS.medicines, JSON.stringify(state.medicines));
  localStorage.setItem(STORAGE_KEYS.events, JSON.stringify(state.events));
  localStorage.setItem(STORAGE_KEYS.settings, JSON.stringify(state.settings));
}

function todayCode(date = new Date()) {
  return DAYS[(date.getDay() + 6) % 7];
}

function todayMedicines() {
  return state.medicines
    .filter(medicine => medicine.days.includes(todayCode()))
    .sort((a, b) => a.time.localeCompare(b.time));
}

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

function renderDate() {
  el.currentDate.textContent = new Date().toLocaleDateString(undefined, {
    weekday: "long", day: "numeric", month: "long", year: "numeric"
  });
}

function renderStats() {
  const medicines = todayMedicines();
  const completed = medicines.filter(item => item.status === "completed").length;
  const missed = medicines.filter(item => item.status === "missed").length;
  const pending = medicines.length - completed - missed;
  el.total.textContent = medicines.length;
  el.completed.textContent = completed;
  el.pending.textContent = pending;
  el.missed.textContent = missed;

  const total = medicines.length;
  const completionRate = total ? Math.round(completed / total * 100) : 0;
  const circumference = 2 * Math.PI * 45;
  let offset = 0;
  [[el.pieCompleted, completed], [el.piePending, pending], [el.pieMissed, missed]].forEach(([segment, count]) => {
    const length = total ? count / total * circumference : 0;
    segment.style.strokeDasharray = `${length} ${circumference - length}`;
    segment.style.strokeDashoffset = String(-offset);
    offset += length;
  });
  el.ring.setAttribute("aria-label", `Today's reminders: ${completed} completed, ${pending} pending, ${missed} missed`);
  el.progressPercent.textContent = `${completionRate}%`;
  el.progressCompleted.textContent = completed;
  el.progressPending.textContent = pending;
  el.progressMissed.textContent = missed;
  el.progressSummary.textContent = `${completed} of ${total} reminders completed`;
}

function renderWeeklyPlan() {
  const counts = DAYS.map(day => state.medicines.filter(item => item.days.includes(day)).length);
  const maximum = Math.max(...counts, 1);
  el.weekly.innerHTML = DAYS.map((day, index) => {
    const count = counts[index];
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
  const now = new Date();
  const upcoming = todayMedicines().find(item => {
    const [hours, minutes] = item.time.split(":").map(Number);
    const at = new Date();
    at.setHours(hours, minutes, 0, 0);
    return at > now && !["completed", "missed"].includes(item.status);
  });
  if (!upcoming) {
    el.nextName.textContent = "No upcoming reminder";
    el.nextDose.textContent = todayMedicines().length ? "You're all caught up for today." : "No medicines scheduled for today.";
    el.nextTime.textContent = "--:--";
    el.nextStatus.textContent = "None";
    el.nextStatus.className = "status-pill completed";
    el.countdown.textContent = "-- : -- : --";
    return;
  }
  el.nextName.textContent = upcoming.name;
  el.nextDose.textContent = upcoming.dose;
  el.nextTime.textContent = formatTime(upcoming.time);
  el.nextStatus.textContent = upcoming.status;
  el.nextStatus.className = `status-pill ${statusClass(upcoming.status)}`;
  const [hours, minutes] = upcoming.time.split(":").map(Number);
  const target = new Date();
  target.setHours(hours, minutes, 0, 0);
  let remaining = Math.max(0, target.getTime() - Date.now());
  const hh = Math.floor(remaining / 3600000);
  remaining %= 3600000;
  const mm = Math.floor(remaining / 60000);
  const ss = Math.floor(remaining % 60000 / 1000);
  el.countdown.textContent = [hh, mm, ss].map(value => String(value).padStart(2, "0")).join(" : ");
}

function renderTodaySchedule() {
  const medicines = todayMedicines();
  if (!medicines.length) {
    el.todayList.innerHTML = '<div class="empty-state">No medicines scheduled for today.</div>';
    return;
  }
  el.todayList.innerHTML = medicines.map(item => `<div class="schedule-item">
    <span class="schedule-time">${escapeHtml(formatTime(item.time))}</span>
    <div class="schedule-information"><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.dose)}</small></div>
    <span class="status-pill ${statusClass(item.status)}">${escapeHtml(item.status)}</span>
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
  el.recentEvents.innerHTML = events.map(event => `<div class="event-item">
    <span class="event-icon" aria-hidden="true">${eventIcon(event.type)}</span>
    <div class="event-information"><strong>${escapeHtml(event.label)}</strong><small>${escapeHtml(event.medicine)} at ${escapeHtml(formatTime(event.time))}</small></div>
    <span class="status-pill ${statusClass(event.status)}">${escapeHtml(event.status)}</span>
  </div>`).join("");
}

function renderMedicineCards() {
  if (!state.medicines.length) {
    el.managementList.innerHTML = '<div class="panel empty-state">No reminders yet. Add a medicine to get started.</div>';
    return;
  }
  el.managementList.innerHTML = state.medicines.slice().sort((a, b) => a.time.localeCompare(b.time)).map(item => `<article class="medicine-card">
    <div class="medicine-card-header">
      <span class="medicine-mark" aria-hidden="true">Rx</span>
      <div class="medicine-heading"><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(item.dose)}</p></div>
      <div class="card-menu">
        <button class="small-action-button" type="button" data-edit-id="${item.id}" aria-label="Edit ${escapeHtml(item.name)}" title="Edit">✎</button>
        <button class="small-action-button delete" type="button" data-delete-id="${item.id}" aria-label="Delete ${escapeHtml(item.name)}" title="Delete">×</button>
      </div>
    </div>
    <div class="medicine-details">
      <div><span>Reminder time</span><strong>${escapeHtml(formatTime(item.time))}</strong></div>
      <div><span>Scheduled days</span><strong>${escapeHtml(item.days.join(", "))}</strong></div>
    </div>
  </article>`).join("");
}

function renderHistory() {
  const filter = el.eventFilter.value;
  const events = filter === "all" ? state.events : state.events.filter(event => event.type === filter);
  if (!events.length) {
    el.historyBody.innerHTML = '<tr><td class="empty-state" colspan="4">No events match this filter.</td></tr>';
    return;
  }
  el.historyBody.innerHTML = events.map(event => `<tr class="history-row ${statusClass(event.type)}">
    <td>${escapeHtml(formatTime(event.time))}</td>
    <td>${escapeHtml(event.medicine)}</td>
    <td><span class="history-event-label"><span class="history-marker" aria-hidden="true"></span>${escapeHtml(event.label)}</span></td>
    <td><span class="status-pill ${statusClass(event.status)}">${escapeHtml(event.status)}</span></td>
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
  el.missedWindow.value = state.settings.missedWindow || 60;
  el.lastRefreshed.textContent = "Just now";
}

function navigate(section) {
  el.navLinks.forEach(link => link.classList.toggle("active", link.dataset.section === section));
  el.pageSections.forEach(page => page.classList.toggle("active", page.id === `${section}Section`));
  const titles = { dashboard: "Dashboard", schedules: "Schedules", history: "Event History", settings: "Settings" };
  el.pageTitle.textContent = titles[section] || "MediMate";
  el.sidebar.classList.remove("open");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function openModal(medicine = null) {
  el.medicineForm.reset();
  el.medicineId.value = "";
  el.modalTitle.textContent = medicine ? "Edit reminder" : "Add medicine";
  if (medicine) {
    el.medicineId.value = medicine.id;
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

function showToast(message) {
  el.toast.textContent = message;
  el.toast.classList.add("visible");
  clearTimeout(showToast.timeout);
  showToast.timeout = setTimeout(() => el.toast.classList.remove("visible"), 2600);
}

function addEvent(medicine, type, label, status) {
  const now = new Date();
  state.events.unshift({
    id: Date.now(),
    time: `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`,
    medicine, type, label, status, createdAt: now.toISOString()
  });
  state.events = state.events.slice(0, 100);
}

function saveMedicine(event) {
  event.preventDefault();
  const days = Array.from(document.querySelectorAll(".day-selector input:checked"), input => input.value);
  if (!days.length) {
    showToast("Select at least one scheduled day.");
    return;
  }
  const id = Number(el.medicineId.value) || Date.now();
  const existing = state.medicines.find(item => item.id === id);
  const medicine = {
    id,
    name: el.medicineName.value.trim(),
    dose: el.medicineDose.value.trim(),
    time: el.medicineTime.value,
    days,
    status: existing?.status || "pending"
  };
  const index = state.medicines.findIndex(item => item.id === id);
  if (index >= 0) state.medicines[index] = medicine;
  else state.medicines.push(medicine);
  addEvent(medicine.name, "triggered", index >= 0 ? "Reminder updated" : "Reminder added", "Scheduled");
  saveData();
  renderAll();
  closeModal();
  showToast(index >= 0 ? "Reminder updated." : "Reminder added.");
}

function deleteMedicine(id) {
  const medicine = state.medicines.find(item => item.id === id);
  if (!medicine || !window.confirm(`Delete the reminder for "${medicine.name}"?`)) return;
  state.medicines = state.medicines.filter(item => item.id !== id);
  addEvent(medicine.name, "missed", "Reminder removed", "Removed");
  saveData();
  renderAll();
  showToast("Reminder deleted.");
}

function attachEvents() {
  el.navLinks.forEach(link => link.addEventListener("click", () => navigate(link.dataset.section)));
  document.querySelectorAll("[data-navigate]").forEach(button => button.addEventListener("click", () => navigate(button.dataset.navigate)));
  document.querySelectorAll("[data-open-modal]").forEach(button => button.addEventListener("click", () => openModal()));
  el.menuButton.addEventListener("click", () => el.sidebar.classList.toggle("open"));
  document.querySelector("#refreshButton").addEventListener("click", () => {
    el.lastRefreshed.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    renderAll();
    showToast("Dashboard refreshed.");
  });
  el.closeModal.addEventListener("click", closeModal);
  el.cancelModal.addEventListener("click", closeModal);
  el.modal.addEventListener("click", event => { if (event.target === el.modal) closeModal(); });
  el.medicineForm.addEventListener("submit", saveMedicine);
  el.eventFilter.addEventListener("change", renderHistory);
  el.settingsForm.addEventListener("submit", event => {
    event.preventDefault();
    state.settings.missedWindow = Number(el.missedWindow.value);
    saveData();
    showToast("Settings saved.");
  });
  el.managementList.addEventListener("click", event => {
    const edit = event.target.closest("[data-edit-id]");
    const remove = event.target.closest("[data-delete-id]");
    if (edit) openModal(state.medicines.find(item => item.id === Number(edit.dataset.editId)));
    if (remove) deleteMedicine(Number(remove.dataset.deleteId));
  });
  document.addEventListener("keydown", event => { if (event.key === "Escape" && !el.modal.hidden) closeModal(); });
}

renderAll();
attachEvents();
setInterval(renderNextReminder, 1000);
