const STORAGE_KEY = "betterpf.settings";
const FILTERS_KEY = "betterpf.savedFilters";
const RULES_KEY = "betterpf.rules";
const LAST_SEEN_KEY = "betterpf.lastSeen";
const REFRESH_INTERVAL_MS = 5 * 60 * 1000;

const el = (id) => document.getElementById(id);

const state = {
  settings: {
    q: "",
    dataCentre: [],
    pfCategory: [],
    joinableRole: [],
    sort: "duty",
    order: "asc",
    compact: false,
    dark: false,
  },
  rules: {
    highlights: "",
    hide: "",
    mute: "",
  },
  savedFilters: [],
};

let nextRefreshAt = null;
let refreshTicker = null;
let autoRefreshInFlight = false;

const inputIds = [
  "q",
  "data-centre",
  "pf-category",
  "joinable-role",
  "sort",
  "order",
];

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw) {
    const stored = JSON.parse(raw);
    state.settings = { ...state.settings, ...stored };
    if (typeof state.settings.dataCentre === "string") {
      state.settings.dataCentre = toList(state.settings.dataCentre);
    }
    if (typeof state.settings.pfCategory === "string") {
      state.settings.pfCategory = toList(state.settings.pfCategory);
    }
    if (typeof state.settings.joinableRole === "string") {
      state.settings.joinableRole = toList(state.settings.joinableRole);
    }
  }
  const rulesRaw = localStorage.getItem(RULES_KEY);
  if (rulesRaw) {
    state.rules = { ...state.rules, ...JSON.parse(rulesRaw) };
  }
  const filtersRaw = localStorage.getItem(FILTERS_KEY);
  if (filtersRaw) {
    state.savedFilters = JSON.parse(filtersRaw);
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.settings));
}

function saveRules() {
  localStorage.setItem(RULES_KEY, JSON.stringify(state.rules));
}

function saveFilters() {
  localStorage.setItem(FILTERS_KEY, JSON.stringify(state.savedFilters));
}

function toList(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function escapeHTML(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

function highlightText(text, terms) {
  if (!terms.length) {
    return escapeHTML(text);
  }
  let output = escapeHTML(text);
  terms.forEach((term) => {
    const safeTerm = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(`(${safeTerm})`, "gi");
    output = output.replace(regex, "<span class=\"highlight\">$1</span>");
  });
  return output;
}

function matchesRule(item, terms) {
  if (!terms.length) {
    return false;
  }
  const text = `${item.duty} ${item.creator} ${item.description}`.toLowerCase();
  return terms.some((term) => text.includes(term.toLowerCase()));
}

function applyCompactMode() {
  const cards = document.querySelectorAll(".listing-card");
  cards.forEach((card) => {
    card.classList.toggle("compact", state.settings.compact);
  });
}

function setInputsFromState() {
  el("q").value = state.settings.q;
  setCheckboxGroup("data-centre", state.settings.dataCentre);
  setCheckboxGroup("pf-category", state.settings.pfCategory);
  setCheckboxGroup("joinable-role", state.settings.joinableRole);
  el("sort").value = state.settings.sort;
  el("order").value = state.settings.order;
  el("compact").checked = state.settings.compact;
  el("dark").checked = state.settings.dark;

  el("highlights").value = state.rules.highlights;
  el("hide-rules").value = state.rules.hide;
  el("mute-rules").value = state.rules.mute;
}

function setStateFromInputs() {
  state.settings.q = el("q").value;
  state.settings.dataCentre = getCheckboxGroup("data-centre");
  state.settings.pfCategory = getCheckboxGroup("pf-category");
  state.settings.joinableRole = getCheckboxGroup("joinable-role");
  state.settings.sort = el("sort").value;
  state.settings.order = el("order").value;
  state.settings.compact = el("compact").checked;
  state.settings.dark = el("dark").checked;

  document.body.classList.toggle("dark", state.settings.dark);
}

function populateSavedFilters() {
  const select = el("saved-filters");
  select.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select saved filter";
  select.appendChild(placeholder);
  state.savedFilters.forEach((item, index) => {
    const option = document.createElement("option");
    option.value = index;
    option.textContent = item.name;
    select.appendChild(option);
  });
}

function updateRulesFromInputs() {
  state.rules.highlights = el("highlights").value;
  state.rules.hide = el("hide-rules").value;
  state.rules.mute = el("mute-rules").value;
}

function buildQueryParams() {
  const params = new URLSearchParams();
  if (state.settings.q) params.set("q", state.settings.q);
  if (state.settings.dataCentre.length) {
    params.set("data_centre", state.settings.dataCentre.join(","));
  }
  if (state.settings.pfCategory.length) {
    params.set("pf_category", state.settings.pfCategory.join(","));
  }
  if (state.settings.joinableRole.length) {
    params.set("joinable_role", state.settings.joinableRole.join(","));
  }
  if (state.settings.sort) params.set("sort", state.settings.sort);
  if (state.settings.order) params.set("order", state.settings.order);
  params.set("limit", "300");
  return params.toString();
}

async function fetchListings() {
  const params = buildQueryParams();
  const response = await fetch(`/api/listings?${params}`);
  const data = await response.json();
  renderListings(data);
}

function renderListings(data) {
  const list = el("listings");
  const template = document.getElementById("listing-template");
  list.innerHTML = "";

  const highlightTerms = toList(state.rules.highlights);
  const hideTerms = toList(state.rules.hide);
  const muteTerms = toList(state.rules.mute);

  const lastSeen = localStorage.getItem(LAST_SEEN_KEY);
  const lastSeenDate = lastSeen ? new Date(lastSeen) : null;
  const fetchedAt = data.last_updated ? new Date(data.last_updated) : null;

  let visibleCount = 0;

  data.items.forEach((item) => {
    if (matchesRule(item, hideTerms)) {
      return;
    }

    const card = template.content.cloneNode(true);
    const root = card.querySelector(".listing-card");

    root.querySelector(".listing-duty").textContent = item.duty || "Unknown duty";
    root.querySelector(".listing-creator").textContent = item.creator || "Unknown creator";

    root.querySelector(".centre").textContent = item.data_centre || "Unknown centre";
    root.querySelector(".category").textContent = item.pf_category || "Unknown category";
    root.querySelector(".parties").textContent = item.num_parties
      ? `${item.num_parties} parties`
      : "Parties N/A";
    root.querySelector(".roles").textContent = item.joinable_roles?.length
      ? item.joinable_roles.join(", ")
      : "Roles N/A";

    const desc = item.description || "No description";
    root.querySelector(".listing-desc").innerHTML = highlightText(desc, highlightTerms);

    if (matchesRule(item, muteTerms)) {
      root.classList.add("muted");
    }

    if (fetchedAt && (!lastSeenDate || fetchedAt > lastSeenDate)) {
      root.classList.add("new");
    }

    if (state.settings.compact) {
      root.classList.add("compact");
    }

    list.appendChild(card);
    visibleCount += 1;
  });

  el("results-count").textContent = visibleCount.toString();
  el("last-updated").textContent = data.last_updated || "--";
  scheduleRefreshCountdown(data.last_updated);
}

function bindEvents() {
  el("apply").addEventListener("click", () => {
    setStateFromInputs();
    saveState();
    fetchListings();
  });

  el("reset").addEventListener("click", () => {
    state.settings = {
      q: "",
      dataCentre: [],
      pfCategory: [],
      joinableRole: [],
      sort: "duty",
      order: "asc",
      compact: state.settings.compact,
      dark: state.settings.dark,
    };
    saveState();
    setInputsFromState();
    fetchListings();
  });

  el("save-filter").addEventListener("click", () => {
    setStateFromInputs();
    const name = el("save-name").value.trim();
    if (!name) return;
    const existing = state.savedFilters.find((item) => item.name === name);
    if (existing) {
      existing.settings = { ...state.settings };
    } else {
      state.savedFilters.push({ name, settings: { ...state.settings } });
    }
    saveFilters();
    populateSavedFilters();
    el("save-name").value = "";
  });

  el("delete-filter").addEventListener("click", () => {
    const select = el("saved-filters");
    const index = parseInt(select.value, 10);
    if (Number.isNaN(index)) return;
    state.savedFilters.splice(index, 1);
    saveFilters();
    populateSavedFilters();
  });

  el("saved-filters").addEventListener("change", (event) => {
    const index = parseInt(event.target.value, 10);
    if (Number.isNaN(index)) return;
    state.settings = { ...state.savedFilters[index].settings };
    saveState();
    setInputsFromState();
    fetchListings();
  });

  el("save-rules").addEventListener("click", () => {
    updateRulesFromInputs();
    saveRules();
    fetchListings();
  });


  el("compact").addEventListener("change", () => {
    state.settings.compact = el("compact").checked;
    saveState();
    applyCompactMode();
  });

  el("dark").addEventListener("change", () => {
    state.settings.dark = el("dark").checked;
    saveState();
    document.body.classList.toggle("dark", state.settings.dark);
  });
}

function init() {
  loadState();
  setInputsFromState();
  document.body.classList.toggle("dark", state.settings.dark);
  populateSavedFilters();
  bindEvents();
  setupDropdowns();
  fetchListings();
}

function getCheckboxGroup(id) {
  const container = el(id);
  return Array.from(container.querySelectorAll("input[type=\"checkbox\"]"))
    .filter((input) => input.checked)
    .map((input) => input.value);
}

function setCheckboxGroup(id, values) {
  const container = el(id);
  const selected = new Set(values || []);
  container.querySelectorAll("input[type=\"checkbox\"]").forEach((input) => {
    input.checked = selected.has(input.value);
  });
  updateSummary(container);
}

function setupDropdowns() {
  document.querySelectorAll(".dropdown").forEach((dropdown) => {
    const button = dropdown.querySelector(".dropdown-toggle");
    const menu = dropdown.querySelector(".dropdown-menu");
    let closeTimer = null;
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      closeOtherDropdowns(dropdown);
      dropdown.classList.toggle("open");
    });
    menu.addEventListener("click", (event) => event.stopPropagation());
    menu.addEventListener("change", () => updateSummary(menu));
    dropdown.addEventListener("mouseenter", () => {
      if (closeTimer) {
        clearTimeout(closeTimer);
        closeTimer = null;
      }
    });
    dropdown.addEventListener("mouseleave", () => {
      closeTimer = setTimeout(() => {
        dropdown.classList.remove("open");
        closeTimer = null;
      }, 200);
    });
    menu.addEventListener("mouseenter", () => {
      if (closeTimer) {
        clearTimeout(closeTimer);
        closeTimer = null;
      }
    });
  });

  document.addEventListener("click", () => closeOtherDropdowns());
}

function closeOtherDropdowns(active) {
  document.querySelectorAll(".dropdown").forEach((dropdown) => {
    if (!active || dropdown !== active) {
      dropdown.classList.remove("open");
    }
  });
}

function updateSummary(container) {
  const dropdown = container.closest(".dropdown");
  if (!dropdown) return;
  const summary = dropdown.querySelector("span");
  const values = Array.from(
    container.querySelectorAll("input[type=\"checkbox\"]")
  )
    .filter((input) => input.checked)
    .map((input) => input.value);
  summary.textContent = values.length ? values.join(", ") : "Any";
}

function scheduleRefreshCountdown(lastUpdated) {
  if (!lastUpdated) {
    updateRefreshUI("--", 0);
    return;
  }
  const parsed = new Date(lastUpdated);
  if (Number.isNaN(parsed.getTime())) {
    updateRefreshUI("--", 0);
    return;
  }

  nextRefreshAt = parsed.getTime() + REFRESH_INTERVAL_MS;

  if (!refreshTicker) {
    refreshTicker = setInterval(tickRefreshCountdown, 1000);
  }
  tickRefreshCountdown();
}

function tickRefreshCountdown() {
  if (!nextRefreshAt) return;
  const now = Date.now();
  let remaining = nextRefreshAt - now;

  if (remaining <= 0 && !autoRefreshInFlight) {
    autoRefreshInFlight = true;
    fetchListings().finally(() => {
      autoRefreshInFlight = false;
    });
    nextRefreshAt = Date.now() + REFRESH_INTERVAL_MS;
    remaining = nextRefreshAt - now;
  }

  const progress = Math.min(1, Math.max(0, 1 - remaining / REFRESH_INTERVAL_MS));
  const label = formatCountdown(remaining);
  updateRefreshUI(label, progress);
}

function formatCountdown(ms) {
  if (ms <= 0) return "Refreshing...";
  const totalSeconds = Math.ceil(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function updateRefreshUI(label, progress) {
  const labelEl = el("refresh-countdown");
  const barEl = el("refresh-progress");
  if (labelEl) labelEl.textContent = label;
  if (barEl) barEl.style.width = `${Math.round(progress * 100)}%`;
}

init();
