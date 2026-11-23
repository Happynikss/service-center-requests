const API_BASE = "";

const CATEGORY_LABELS = {
  diagnostics: "Діагностика",
  hardware: "Апаратний ремонт",
  software: "Програмне забезпечення",
  maintenance: "Обслуговування та апгрейд",
};

const PRIORITY_LABELS = {
  low: "Низький",
  normal: "Звичайний",
  high: "Високий",
  urgent: "Терміновий",
};

const STATUS_LABELS = {
  new: "Нова",
  diagnostics: "Діагностика",
  in_progress: "У роботі",
  waiting_parts: "Очікує запчастини",
  ready: "Готово до видачі",
  completed: "Виконано",
  cancelled: "Скасовано",
};

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function getToken() {
  return localStorage.getItem("sc_access_token");
}

function getStoredUser() {
  try {
    const raw = localStorage.getItem("sc_user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveAuth(authData) {
  localStorage.setItem("sc_access_token", authData.access_token);
  localStorage.setItem("sc_user", JSON.stringify(authData.user));
}

function clearAuth() {
  localStorage.removeItem("sc_access_token");
  localStorage.removeItem("sc_user");
}

async function apiRequest(path, options = {}) {
  const headers = {
    Accept: "application/json, application/problem+json",
    ...(options.headers || {}),
  };

  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!response.ok) {
    if (response.status === 401 && token) {
      clearAuth();
    }
    const err = new Error(data?.detail || data?.title || `Помилка HTTP ${response.status}`);
    err.status = response.status;
    err.problem = data;
    throw err;
  }

  return data;
}

function renderAlert(container, type, message, fieldErrors = null) {
  if (!container) return;
  if (!message) {
    container.innerHTML = "";
    return;
  }
  const cls = type === "error" ? "alert-error" : type === "success" ? "alert-success" : "alert-info";
  let listHtml = "";
  if (Array.isArray(fieldErrors) && fieldErrors.length > 0) {
    const items = fieldErrors
      .map((e) => `<li><strong>${escapeHtml(e.field)}:</strong> ${escapeHtml(e.message)}</li>`)
      .join("");
    listHtml = `<ul>${items}</ul>`;
  }
  container.innerHTML = `<div class="alert ${cls}" role="alert">${escapeHtml(message)}${listHtml}</div>`;
}

function formatDateTime(isoString) {
  if (!isoString) return "—";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return escapeHtml(isoString);
  return d.toLocaleString("uk-UA", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function toLocalInputValue(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatSlaBadge(item) {
  const state = item.sla_state || "unset";
  const mins = item.remaining_minutes;

  if (state === "closed") {
    return `<span class="badge sla-closed">Завершено</span>`;
  }
  if (state === "unset" || mins === null || mins === undefined) {
    return `<span class="badge sla-unset">Дедлайн не задано</span>`;
  }

  const absMins = Math.abs(mins);
  const hours = Math.floor(absMins / 60);
  const remMins = absMins % 60;
  const humanTime = hours > 0 ? `${hours} год ${remMins} хв` : `${remMins} хв`;

  if (state === "overdue") {
    return `<span class="badge sla-overdue">Прострочено на ${escapeHtml(humanTime)}</span>`;
  }
  if (state === "warning") {
    return `<span class="badge sla-warning">Залишилось ${escapeHtml(humanTime)}</span>`;
  }
  return `<span class="badge sla-ok">В межах SLA (${escapeHtml(humanTime)})</span>`;
}

function initNavigation(activePage) {
  const nav = document.getElementById("main-nav");
  if (!nav) return;

  const user = getStoredUser();
  const links = [
    { id: "index", href: "/", label: "Послуги та головна" },
    { id: "create", href: "/create-request", label: "Подати заявку" },
    { id: "track", href: "/track", label: "Відстежити статус" },
  ];

  if (!user) {
    links.push({ id: "login", href: "/login", label: "Вхід / Реєстрація" });
  } else if (user.role === "manager") {
    links.push({ id: "manager", href: "/manager", label: "Панель менеджера" });
  } else {
    links.push({ id: "client", href: "/client", label: "Мої заявки" });
  }

  let html = links
    .map(
      (link) =>
        `<a href="${link.href}" ${link.id === activePage ? 'aria-current="page"' : ""}>${escapeHtml(link.label)}</a>`
    )
    .join("");

  if (user) {
    html += `<button type="button" id="logout-btn" title="${escapeHtml(user.email)}">Вийти (${escapeHtml(
      user.full_name.split(" ")[0]
    )})</button>`;
  }

  nav.innerHTML = html;

  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      clearAuth();
      window.location.href = "/login";
    });
  }
}