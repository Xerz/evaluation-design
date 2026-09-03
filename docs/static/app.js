const app = document.querySelector("#app");
const searchInput = document.querySelector("#global-search");
const searchResults = document.querySelector("#search-results");
const menuButton = document.querySelector("#menu-button");
const sidebarScrim = document.querySelector("#sidebar-scrim");
const toast = document.querySelector("#toast");
const editorOverlay = document.querySelector("#editor-overlay");
const editorDrawer = document.querySelector("#editor-drawer");
const editorScrim = document.querySelector("#editor-scrim");

const state = {
  currentRoute: "overview",
  erd: { scale: 0.18, x: 18, y: 18, naturalWidth: 0, naturalHeight: 0 },
  table: { name: null, offset: 0, limit: 50, query: "" },
  editor: { enabled: false, csrfToken: null, status: null, current: null },
};

const viewerConfig = Object.freeze({
  mode: "server",
  dataBase: "./data",
  ...(window.DB_VIEWER_CONFIG || {}),
});
const staticCache = new Map();

const labels = {
  prototype_now: "Прототипируем сейчас",
  conditional: "Условно",
  not_from_recording: "Не определяется по записи",
  partial: "Частично",
  indirect: "Косвенно",
  not_covered: "Не покрывается",
  reference: "Референс",
  prototype_output: "Прототипный вывод",
  not_mapped: "Связь не задана",
  validated: "Валидировано",
  unvalidated: "Не валидировано",
  not_documented: "Методика не описана",
  documented: "Методика описана",
  required: "Обязательно",
  optional: "Дополнительно",
  supplemental: "Дополняет",
  derived: "Производное",
  primary: "Основной",
  assistant: "Ассистирующий",
  baseline: "База",
  candidate: "Кандидат",
  assisted: "С ИИ",
  ablation: "Абляция",
  recording_only: "Только запись",
  boundary: "Граница",
  longitudinal: "Продольно",
  historical: "Историческая версия",
  active: "Активно",
  reference_protocol: "Референсный протокол",
  reference_protocol_status: "Референс",
  partial_methodology: "Частично описано",
  to_review: "Нужно проверить",
  source_register_checked: "Проверено в реестре",
  user_verified: "Проверено пользователем",
  partially_verified: "Проверено частично",
  not_verified: "Не подтверждено",
  confirmed: "Подтверждено",
  partially_confirmed: "Подтверждено частично",
  rejected: "Отклонено",
};

const routeNames = {
  overview: "Обзор",
  criteria: "Критерии",
  sources: "Источники",
  instruments: "Инструменты",
  conditions: "Условия",
  effects: "Эффекты",
  erd: "ERD",
  tables: "Таблицы",
};

function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function display(value, fallback = "—") {
  return value === null || value === undefined || value === "" ? fallback : escapeHTML(value);
}

function textLabel(value) {
  return labels[value] || String(value || "—").replaceAll("_", " ");
}

function badge(status, label = null) {
  const safeStatus = String(status || "gray").replace(/[^a-z0-9_-]/gi, "-");
  return `<span class="badge ${safeStatus}">${escapeHTML(label || textLabel(status))}</span>`;
}

function loading(label = "Загружаем данные…") {
  app.innerHTML = `<div class="page-loading" role="status"><span class="spinner" aria-hidden="true"></span>${escapeHTML(label)}</div>`;
}

function errorPanel(error) {
  const message = error instanceof Error ? error.message : String(error);
  app.innerHTML = `<div class="error-panel"><strong>Не удалось загрузить раздел</strong><span>${escapeHTML(message)}</span></div>`;
}

function documentUrl(relativePath) {
  return new URL(relativePath, document.baseURI).toString();
}

async function fetchJSON(relativePath) {
  const url = documentUrl(relativePath);
  if (!staticCache.has(url)) {
    staticCache.set(url, fetch(url, { headers: { Accept: "application/json" } }).then(async (response) => {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || payload.error || `HTTP ${response.status}`);
      return payload;
    }));
  }
  return staticCache.get(url);
}

function containsText(item, fields, query) {
  return fields.some((field) => String(item[field] || "").toLocaleLowerCase("ru").includes(query));
}

async function staticApi(path) {
  const request = new URL(path, window.location.origin);
  const pathname = request.pathname;
  const dataFile = (relativePath) => `${viewerConfig.dataBase.replace(/\/$/, "")}/${relativePath}`;

  if (pathname === "/health") return fetchJSON(dataFile("health.json"));
  if (pathname === "/api/editor/status") return { enabled: false, csrf_token: null };
  if (pathname === "/api/summary") return fetchJSON(dataFile("summary.json"));
  if (pathname === "/api/search") {
    const source = await fetchJSON(dataFile("search.json"));
    const query = (request.searchParams.get("q") || "").trim().slice(0, 100).toLocaleLowerCase("ru");
    if (!query) return { criteria: [], sources: [], instruments: [], conditions: [], effects: [] };
    return {
      criteria: source.criteria.filter((item) => containsText(item, ["code", "name", "block_name", "subblock_name"], query)).slice(0, 8),
      sources: source.sources.filter((item) => containsText(item, ["code", "citation_apa", "doi", "study_type", "evidence_role"], query)).slice(0, 8),
      instruments: source.instruments.filter((item) => containsText(item, ["code", "name", "provider", "description"], query)).slice(0, 8),
      conditions: source.conditions.filter((item) => containsText(item, ["code", "name", "description"], query)).slice(0, 8),
      effects: source.effects.filter((item) => containsText(item, ["code", "name", "hypothesis", "method_code", "method_name", "metrics"], query)).slice(0, 8),
    };
  }
  if (pathname === "/api/criteria") {
    const source = await fetchJSON(dataFile("criteria/index.json"));
    const query = (request.searchParams.get("q") || "").trim().toLocaleLowerCase("ru");
    const items = source.items.filter((item) => {
      if (request.searchParams.get("block") && item.block_name !== request.searchParams.get("block")) return false;
      if (request.searchParams.get("readiness") && item.readiness_status !== request.searchParams.get("readiness")) return false;
      if (request.searchParams.get("coverage") && item.platform_coverage_status !== request.searchParams.get("coverage")) return false;
      return !query || containsText(item, ["code", "name", "block_name", "subblock_name"], query);
    });
    return { items };
  }
  if (pathname.startsWith("/api/criteria/")) return fetchJSON(dataFile(`criteria/${encodeURIComponent(decodeURIComponent(pathname.split("/").pop()))}.json`));
  if (pathname === "/api/sources") {
    const source = await fetchJSON(dataFile("sources/index.json"));
    const query = (request.searchParams.get("q") || "").trim().toLocaleLowerCase("ru");
    return { items: query ? source.items.filter((item) => containsText(item, ["code", "citation_apa", "doi", "study_type", "evidence_role"], query)) : source.items };
  }
  if (pathname.startsWith("/api/sources/")) return fetchJSON(dataFile(`sources/${encodeURIComponent(decodeURIComponent(pathname.split("/").pop()))}.json`));
  if (pathname === "/api/instruments") return fetchJSON(dataFile("instruments/index.json"));
  if (pathname.startsWith("/api/instruments/")) return fetchJSON(dataFile(`instruments/${encodeURIComponent(decodeURIComponent(pathname.split("/").pop()))}.json`));
  if (pathname === "/api/conditions") return fetchJSON(dataFile("conditions/index.json"));
  if (pathname.startsWith("/api/conditions/")) return fetchJSON(dataFile(`conditions/${encodeURIComponent(decodeURIComponent(pathname.split("/").pop()))}.json`));
  if (pathname === "/api/effects") return fetchJSON(dataFile("effects/index.json"));
  if (pathname.startsWith("/api/effects/")) return fetchJSON(dataFile(`effects/${encodeURIComponent(decodeURIComponent(pathname.split("/").pop()))}.json`));
  if (pathname === "/api/tables") return fetchJSON(dataFile("tables/index.json"));
  if (pathname.startsWith("/api/tables/")) {
    const name = decodeURIComponent(pathname.split("/").pop());
    const source = await fetchJSON(dataFile(`tables/${encodeURIComponent(name)}.json`));
    const query = (request.searchParams.get("q") || "").trim().slice(0, 100).toLocaleLowerCase("ru");
    if (source.restricted) {
      return { ...source, limit: 50, offset: 0, query: "" };
    }
    const filtered = query
      ? source.rows.filter((row) => Object.values(row).some((value) => String(value ?? "").toLocaleLowerCase("ru").includes(query)))
      : source.rows;
    const limit = Math.max(1, Math.min(100, Number.parseInt(request.searchParams.get("limit") || "50", 10) || 50));
    const offset = Math.max(0, Number.parseInt(request.searchParams.get("offset") || "0", 10) || 0);
    return { ...source, rows: filtered.slice(offset, offset + limit), total: filtered.length, limit, offset, query };
  }
  throw new Error("Неизвестный статический ресурс");
}

async function api(path, options = {}) {
  const method = options.method || "GET";
  if (viewerConfig.mode === "static") {
    if (method !== "GET") throw new Error("Статическая версия доступна только для чтения");
    return staticApi(path);
  }
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && state.editor.csrfToken) headers["X-CSRF-Token"] = state.editor.csrfToken;
  const response = await fetch(path, {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.detail || payload.error || `HTTP ${response.status}`);
    error.code = payload.error;
    error.field = payload.field;
    error.status = response.status;
    throw error;
  }
  return payload;
}

function clearDataCache() {
  staticCache.clear();
}

function editorTableAction(table, key, label = "Редактировать") {
  if (!state.editor.enabled) return "";
  return `<button class="primary-button" data-edit-table="${escapeHTML(table)}" data-edit-key="${escapeHTML(JSON.stringify(key))}">${escapeHTML(label)}</button>`;
}

function editorStatusBanner() {
  if (!state.editor.enabled) return "";
  const status = state.editor.status || {};
  const publication = status.unpublished_changes
    ? "Есть изменения, не включённые в публичный снимок"
    : status.static_snapshot_known ? "Локальная база совпадает с публичным снимком" : "Состояние публичного снимка неизвестно";
  const backup = status.backup_created
    ? `Резервная копия: ${status.backup_file}`
    : "Перед первой записью будет создан локальный бэкап";
  return `<div class="edit-mode-banner"><div><strong>Редактирование включено</strong><span>${escapeHTML(publication)}. ${escapeHTML(backup)}.</span></div><a href="#/tables">Открыть таблицы →</a></div>`;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("visible"), 2200);
}

function pageHeader(eyebrow, title, description, actions = "") {
  return `<header class="page-header">
    <div><span class="eyebrow">${escapeHTML(eyebrow)}</span><h1>${escapeHTML(title)}</h1><p>${escapeHTML(description)}</p></div>
    ${actions ? `<div>${actions}</div>` : ""}
  </header>`;
}

function breadcrumb(parentHash, parentLabel, current) {
  return `<div class="breadcrumb"><a href="${parentHash}">${escapeHTML(parentLabel)}</a><span>›</span><span>${escapeHTML(current)}</span></div>`;
}

function emptyState(title, description, symbol = "○") {
  return `<div class="empty-state"><div><div class="empty-state-symbol" aria-hidden="true">${escapeHTML(symbol)}</div><strong>${escapeHTML(title)}</strong><span>${escapeHTML(description)}</span></div></div>`;
}

function setActiveNav(route) {
  const root = route.split("/")[0] || "overview";
  document.querySelectorAll(".main-nav a").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === root);
  });
  state.currentRoute = root;
  document.body.classList.remove("menu-open");
  menuButton.setAttribute("aria-expanded", "false");
}

function instrumentKind(kind) {
  return {
    llm: "LLM",
    video_analytics: "Видеоаналитика",
    audio_analytics: "Аудиоаналитика",
    human: "Эксперт",
  }[kind] || kind;
}

function statusCardClass(status) {
  if (["prototype_now", "reference", "documented"].includes(status)) return "green";
  if (["conditional", "indirect", "unvalidated"].includes(status)) return "amber";
  if (["not_from_recording", "not_covered"].includes(status)) return "red";
  return "";
}

function distributionRow(label, value, total, color) {
  const width = total ? Math.max(2, (Number(value) / total) * 100) : 0;
  return `<div class="distribution-row">
    <span class="distribution-label">${escapeHTML(label)}</span>
    <div class="distribution-track"><div class="distribution-fill ${color}" style="width:${width}%"></div></div>
    <span class="distribution-value">${escapeHTML(value)}</span>
  </div>`;
}

async function renderOverview() {
  loading("Собираем обзор пилота…");
  const [summary, conditions, effects] = await Promise.all([
    api("/api/summary"),
    api("/api/conditions"),
    api("/api/effects"),
  ]);
  const c = summary.counts;
  const operationalLabels = {
    lessons: "занятий",
    runs: "запусков",
    evaluations: "оценок",
    evidence: "фрагментов",
    results: "эффектов",
  };
  app.innerHTML = `
    ${pageHeader("Исследовательская база", summary.study.name, summary.study.objective)}
    ${editorStatusBanner()}
    <div class="warning-banner">
      <div class="warning-symbol" aria-hidden="true">!</div>
      <div><strong>Машинный сигнал — не автоматический балл преподавателю</strong><span>Результат пилота — доказательный фрагмент, источник, таймкод и неопределённость. Окончательное решение проверяет эксперт.</span></div>
    </div>
    <section class="metric-grid" aria-label="Основные количества">
      <a class="metric-card" href="#/criteria"><span class="metric-label">Критерии</span><div class="metric-value">${c.criteria}</div><div class="metric-note">${c.score_levels} описаний шкалы 0–2</div></a>
      <a class="metric-card" href="#/sources"><span class="metric-label">Источники критериев</span><div class="metric-value">${c.research_sources}</div><div class="metric-note">${c.criterion_source_links} связей с критериями</div></a>
      <a class="metric-card" href="#/instruments"><span class="metric-label">Инструменты</span><div class="metric-value">${c.instruments}</div><div class="metric-note">LLM · видео · аудио · эксперт</div></a>
      <a class="metric-card" href="#/conditions"><span class="metric-label">Условия</span><div class="metric-value">${c.conditions}</div><div class="metric-note">A0–A5</div></a>
      <a class="metric-card" href="#/effects"><span class="metric-label">Эффекты</span><div class="metric-value">${c.effects}</div><div class="metric-note">E1–E9 и методы T1–T9</div></a>
      <a class="metric-card" href="#/tables"><span class="metric-label">Структура SQLite</span><div class="metric-value">${c.tables}</div><div class="metric-note">таблиц · ${c.views} представления</div></a>
    </section>
    <section class="dashboard-grid">
      <div class="panel">
        <div class="panel-header"><div><h2>Готовность критериев</h2><p>Что технически можно проверять на текущем этапе</p></div><a href="#/criteria">Открыть критерии →</a></div>
        <div class="distribution-list">
          ${distributionRow("Прототипируем сейчас", summary.readiness.prototype_now || 0, c.criteria, "green")}
          ${distributionRow("Условно", summary.readiness.conditional || 0, c.criteria, "amber")}
          ${distributionRow("Не по записи", summary.readiness.not_from_recording || 0, c.criteria, "red")}
        </div>
      </div>
      <div class="panel">
        <div class="panel-header"><div><h2>Готовые метрики МГПУ</h2><p>Полного покрытия нет</p></div></div>
        <div class="distribution-list">
          ${distributionRow("Частично", summary.coverage.partial || 0, c.criteria, "")}
          ${distributionRow("Косвенно", summary.coverage.indirect || 0, c.criteria, "amber")}
          ${distributionRow("Не покрывается", summary.coverage.not_covered || 0, c.criteria, "gray")}
        </div>
      </div>
    </section>
    <section class="panel">
      <div class="panel-header"><div><h2>Сравниваемые условия</h2><p>От экспертного референса до эксперта с ИИ-доказательствами</p></div></div>
      <div class="condition-flow">
        ${conditions.items.map((item) => `<a class="condition-step" href="#/conditions/${encodeURIComponent(item.code)}"><strong>${escapeHTML(item.code)} · ${escapeHTML(item.name)}</strong><span>${escapeHTML(item.description)}</span></a>`).join("")}
      </div>
    </section>
    <section class="dashboard-grid">
      <div class="panel">
        <div class="panel-header"><div><h2>Дерево проверяемых эффектов</h2><p>Каждый эффект связан с методом, условиями и критериями</p></div><a href="#/effects">Все эффекты →</a></div>
        <div class="route-list">
          ${effects.items.slice(0, 5).map((item) => `<a class="route-item" href="#/effects/${item.code}"><span class="route-code">${escapeHTML(item.code)}</span><span class="route-copy"><strong>${escapeHTML(item.name)}</strong><span>${escapeHTML(item.method_code)} · ${escapeHTML(item.method_name)}</span></span><span class="route-arrow">›</span></a>`).join("")}
        </div>
      </div>
      <div class="panel">
        <div class="panel-header"><div><h2>Операционный контур</h2><p>${summary.operational_visibility === "local_only" ? "Строки и количества доступны только в локальной базе" : "Таблицы готовы для фактических данных пилота"}</p></div></div>
        <div class="operational-grid">
          ${Object.entries(summary.operational).map(([key, value]) => `<a class="operational-item" href="#/tables/${key === "runs" ? "evaluation_runs" : key === "evaluations" ? "criterion_evaluations" : key === "evidence" ? "evidence_fragments" : key === "results" ? "effect_results" : "lessons"}"><strong>${value === null ? "локально" : value}</strong><span>${operationalLabels[key]}</span></a>`).join("")}
        </div>
        <div style="margin-top:14px">${summary.operational_visibility === "local_only" ? emptyState("Данные не публикуются", "Публичный сайт показывает схему операционных таблиц без строк и реальных количеств.", "▣") : emptyState("Рабочий контур", "Отсутствие строк не интерпретируется как нулевое значение показателей.", "＋")}</div>
      </div>
    </section>`;
}

function criterionCard(item) {
  return `<a class="entity-card ${statusCardClass(item.readiness_status)}" href="#/criteria/${encodeURIComponent(item.code)}">
    <div class="card-topline"><span class="entity-code">${escapeHTML(item.code)} · № ${item.number}</span>${badge(item.readiness_status)}</div>
    <h2>${escapeHTML(item.name)}</h2>
    <p>${escapeHTML(item.subblock_name || item.block_name)}</p>
    <div class="card-meta">${badge(item.platform_coverage_status)}<span class="badge gray">${item.instrument_links_count} инструментов</span><span class="badge gray">${item.research_sources_count} источников</span></div>
  </a>`;
}

async function renderCriteria() {
  loading("Загружаем 26 критериев…");
  const response = await api("/api/criteria");
  const items = response.items;
  const blocks = [...new Set(items.map((item) => item.block_name))];
  app.innerHTML = `
    ${pageHeader("26 проверяемых гипотез", "Критерии ТюмГУ", "Шкала 0–2, готовность к автоматизации, необходимые данные и связи с инструментами и эффектами.")}
    <div class="toolbar">
      <input id="criteria-query" type="search" placeholder="Поиск по названию или коду…" aria-label="Поиск критериев">
      <select id="criteria-block" aria-label="Фильтр по блоку"><option value="">Все блоки</option>${blocks.map((block) => `<option>${escapeHTML(block)}</option>`).join("")}</select>
      <select id="criteria-readiness" aria-label="Фильтр по готовности"><option value="">Любая готовность</option><option value="prototype_now">Прототипируем сейчас</option><option value="conditional">Условно</option><option value="not_from_recording">Не по записи</option></select>
      <select id="criteria-coverage" aria-label="Фильтр по покрытию"><option value="">Любое покрытие</option><option value="partial">Частично</option><option value="indirect">Косвенно</option><option value="not_covered">Не покрывается</option></select>
      <span class="result-count" id="criteria-count">${items.length} критериев</span>
    </div>
    <section class="entity-grid" id="criteria-grid">${items.map(criterionCard).join("")}</section>`;

  const controls = ["criteria-query", "criteria-block", "criteria-readiness", "criteria-coverage"].map((id) => document.querySelector(`#${id}`));
  const filter = () => {
    const query = controls[0].value.trim().casefold?.() || controls[0].value.trim().toLocaleLowerCase("ru");
    const block = controls[1].value;
    const readiness = controls[2].value;
    const coverage = controls[3].value;
    const filtered = items.filter((item) => {
      const haystack = `${item.code} ${item.name} ${item.block_name} ${item.subblock_name || ""}`.toLocaleLowerCase("ru");
      return (!query || haystack.includes(query)) && (!block || item.block_name === block) && (!readiness || item.readiness_status === readiness) && (!coverage || item.platform_coverage_status === coverage);
    });
    document.querySelector("#criteria-count").textContent = `${filtered.length} из ${items.length}`;
    document.querySelector("#criteria-grid").innerHTML = filtered.length ? filtered.map(criterionCard).join("") : emptyState("Ничего не найдено", "Измените запрос или снимите часть фильтров.", "⌕");
  };
  controls.forEach((control) => control.addEventListener("input", filter));
}

async function renderCriterion(code) {
  loading(`Загружаем ${code}…`);
  const item = await api(`/api/criteria/${encodeURIComponent(code)}`);
  app.innerHTML = `
    ${breadcrumb("#/criteria", "Критерии", `${item.code} · ${item.name}`)}
    ${pageHeader(`${item.code} · критерий № ${item.number}`, item.name, item.subblock_name || item.block_name, `${editorTableAction("criteria", { id: item.id })}<a class="secondary-button" href="#/tables/criteria">Строка в БД</a>`)}
    <div class="card-meta" style="margin:-12px 0 22px">${badge(item.readiness_status)}${badge(item.platform_coverage_status)}</div>
    <section class="detail-layout">
      <div class="detail-column">
        <div class="detail-card">
          <div class="panel-header"><div><h2>Шкала оценки 0–2</h2><p>Точные формулировки из исходного чек-листа</p></div></div>
          <div class="score-grid">${item.levels.map((level) => `<article class="score-card" data-score="${level.score}"><div class="score-value">${level.score}</div><p>${escapeHTML(level.description)}</p></article>`).join("")}</div>
        </div>
        <div class="detail-card">
          <div class="panel-header"><div><h2>Покрытие инструментами</h2><p>Связь с конкретной версией и статусом методики</p></div></div>
          <div class="coverage-list">${item.instrument_coverage.map((coverage) => `<div class="coverage-row"><div class="coverage-head"><div><strong>${escapeHTML(coverage.instrument_name)}</strong><span>${escapeHTML(coverage.version_name)}</span></div><div>${badge(coverage.coverage_status)}</div></div><div class="card-meta">${badge(coverage.validation_status)}<span class="badge gray">${escapeHTML(instrumentKind(coverage.instrument_kind))}</span></div>${coverage.notes ? `<p>${escapeHTML(coverage.notes)}</p>` : ""}</div>`).join("")}</div>
        </div>
        <div class="detail-card">
          <div class="panel-header"><div><h2>Исследовательские источники</h2><p>Связей с публикациями: ${item.research_sources.length}</p></div><a href="#/tables/criterion_research_sources">Таблица связей →</a></div>
          ${item.research_sources.length ? `<div class="coverage-list">${item.research_sources.map((source) => `<article class="coverage-row"><div class="coverage-head"><div><a href="#/sources/${encodeURIComponent(source.code)}"><strong>${escapeHTML(source.code)}</strong></a><span>${escapeHTML(source.study_type || source.evidence_role || "Научный источник")}</span></div>${badge(source.relevance_status)}</div><p>${escapeHTML(source.citation_apa)}</p><div class="card-meta">${badge(source.verification_status)}${source.doi ? `<span class="badge gray">DOI ${escapeHTML(source.doi)}</span>` : ""}</div>${source.supported_claim ? `<p><strong>Проверяемый тезис:</strong> ${escapeHTML(source.supported_claim)}</p>` : ""}${editorTableAction("criterion_research_sources", { id: source.link_id }, "Изменить связь")}</article>`).join("")}</div>` : emptyState("Источники не связаны", "Добавьте публикацию и связь с критерием в локальном редакторе.", "§")}
        </div>
      </div>
      <aside class="detail-column">
        <div class="detail-card">
          <div class="panel-header"><div><h3>Необходимые данные</h3></div></div>
          ${item.data_requirements.length ? `<div class="data-list">${item.data_requirements.map((data) => `<div class="data-row"><div class="data-head"><div><strong>${escapeHTML(data.name)}</strong><span>${escapeHTML(data.code)}</span></div>${badge(data.requirement_role)}</div><p>${escapeHTML(data.reason)}</p></div>`).join("")}</div>` : emptyState("Специальные данные не закреплены", "Используются данные сравниваемого условия и инструмента.", "□")}
        </div>
        <div class="detail-card">
          <div class="panel-header"><div><h3>Как проверяется</h3><p>${item.effects.length} связей с эффектами</p></div></div>
          <div class="link-list">${item.effects.map((effect) => `<a class="link-row" href="#/effects/${effect.code}"><span class="route-code">${escapeHTML(effect.code)}</span><span><strong>${escapeHTML(effect.name)}</strong><span>${escapeHTML(effect.method_code)} · ${escapeHTML(effect.method_name)}</span></span><span>›</span></a>`).join("")}</div>
        </div>
        <div class="detail-card">
          <div class="panel-header"><div><h3>Происхождение</h3></div></div>
          <dl class="definition-list"><div><dt>Блок</dt><dd>${escapeHTML(item.block_name)}</dd></div><div><dt>Подблок</dt><dd>${display(item.subblock_name)}</dd></div><div><dt>Источник</dt><dd>${escapeHTML(item.source_title)}<br>${escapeHTML(item.source_path)}</dd></div></dl>
        </div>
      </aside>
    </section>`;
}

function researchSourceCard(item) {
  return `<a class="entity-card" href="#/sources/${encodeURIComponent(item.code)}">
    <div class="card-topline"><span class="entity-code">${escapeHTML(item.code)}</span>${badge(item.verification_status)}</div>
    <h2>${escapeHTML(item.study_type || "Исследовательский источник")}</h2>
    <p>${escapeHTML(item.citation_apa)}</p>
    <div class="card-meta"><span class="badge blue">Связей: ${item.criteria_count}</span>${item.doi ? `<span class="badge gray">DOI</span>` : ""}</div>
  </a>`;
}

async function renderResearchSources() {
  loading("Загружаем исследовательские источники…");
  const response = await api("/api/sources");
  const items = response.items;
  app.innerHTML = `
    ${pageHeader("Доказательная база критериев", "Исследовательские источники", "Публикации, методики и обзоры, на которых основана операционализация критериев. Связи ожидают вашей проверки.", '<a class="secondary-button" href="#/tables/research_sources">Редактировать реестр</a><a class="secondary-button" href="#/tables/criterion_research_sources">Редактировать связи</a>')}
    ${editorStatusBanner()}
    <div class="toolbar"><input id="sources-query" type="search" placeholder="Автор, DOI, тип исследования или роль…" aria-label="Поиск источников"><span class="result-count" id="sources-count">${items.length} источников</span></div>
    <section class="entity-grid" id="sources-grid">${items.map(researchSourceCard).join("")}</section>`;
  const query = document.querySelector("#sources-query");
  query.addEventListener("input", () => {
    const needle = query.value.trim().toLocaleLowerCase("ru");
    const filtered = needle ? items.filter((item) => containsText(item, ["code", "citation_apa", "doi", "study_type", "evidence_role"], needle)) : items;
    document.querySelector("#sources-count").textContent = `${filtered.length} из ${items.length}`;
    document.querySelector("#sources-grid").innerHTML = filtered.length ? filtered.map(researchSourceCard).join("") : emptyState("Ничего не найдено", "Измените поисковый запрос.", "⌕");
  });
}

async function renderResearchSource(code) {
  loading(`Загружаем ${code}…`);
  const item = await api(`/api/sources/${encodeURIComponent(code)}`);
  const url = item.url ? `<a href="${escapeHTML(item.url)}" target="_blank" rel="noopener noreferrer">Открыть публикацию ↗</a>` : "—";
  app.innerHTML = `
    ${breadcrumb("#/sources", "Источники", item.code)}
    ${pageHeader("Исследовательский источник", item.code, item.study_type || item.evidence_role || "Публикация", `${editorTableAction("research_sources", { id: item.id })}<a class="secondary-button" href="#/tables/research_sources">Строка в БД</a>`)}
    <div class="card-meta" style="margin:-12px 0 22px">${badge(item.verification_status)}<span class="badge blue">Связей: ${item.criteria.length}</span></div>
    <section class="detail-layout">
      <div class="detail-column">
        <div class="detail-card"><div class="panel-header"><div><h2>Библиографическая ссылка</h2></div></div><p>${escapeHTML(item.citation_apa)}</p><dl class="definition-list"><div><dt>DOI</dt><dd>${display(item.doi)}</dd></div><div><dt>Ссылка</dt><dd>${url}</dd></div><div><dt>Тип исследования</dt><dd>${display(item.study_type)}</dd></div></dl></div>
        <div class="detail-card"><div class="panel-header"><div><h2>Что даёт источник</h2><p>Краткая выжимка из реестра операционализации</p></div></div><p class="preserve-lines">${display(item.evidence_summary)}</p><dl class="definition-list"><div><dt>Роль доказательства</dt><dd>${display(item.evidence_role)}</dd></div><div><dt>Доступность и права</dt><dd>${display(item.access_notes)}</dd></div></dl></div>
      </div>
      <aside class="detail-column">
        <div class="detail-card"><div class="panel-header"><div><h3>Связанные критерии</h3><p>${item.criteria.length} связей</p></div><a href="#/tables/criterion_research_sources">Все связи →</a></div>${item.criteria.length ? `<div class="coverage-list">${item.criteria.map((criterion) => `<article class="coverage-row"><div class="coverage-head"><a href="#/criteria/${criterion.code}"><strong>${escapeHTML(criterion.code)} · ${escapeHTML(criterion.name)}</strong><span>${escapeHTML(criterion.block_name)}</span></a>${badge(criterion.relevance_status)}</div><p>${escapeHTML(criterion.relation_role)}</p>${criterion.supported_claim ? `<p><strong>Проверяемый тезис:</strong> ${escapeHTML(criterion.supported_claim)}</p>` : ""}${editorTableAction("criterion_research_sources", { id: criterion.link_id }, "Изменить связь")}</article>`).join("")}</div>` : emptyState("Связей пока нет", "Добавьте связь с критерием в локальном редакторе.", "§")}</div>
        <div class="detail-card"><div class="panel-header"><div><h3>Проверка и происхождение</h3></div></div><dl class="definition-list"><div><dt>Статус</dt><dd>${escapeHTML(textLabel(item.verification_status))}</dd></div><div><dt>Дата в исходном реестре</dt><dd>${display(item.registry_checked_on)}</dd></div><div><dt>Файл происхождения</dt><dd>${display(item.provenance_title)}<br>${display(item.provenance_path)}</dd></div><div><dt>Комментарий</dt><dd>${display(item.notes)}</dd></div></dl></div>
      </aside>
    </section>`;
}

function instrumentCard(item) {
  return `<a class="entity-card ${item.instrument_kind === "human" ? "green" : item.instrument_kind === "llm" ? "purple" : ""}" href="#/instruments/${encodeURIComponent(item.code)}">
    <div class="card-topline"><span class="entity-code">${escapeHTML(item.code)}</span><span class="badge gray">${escapeHTML(instrumentKind(item.instrument_kind))}</span></div>
    <h2>${escapeHTML(item.name)}</h2><p>${escapeHTML(item.description)}</p>
    <div class="card-meta"><span class="badge blue">${item.criteria_count} критериев</span><span class="badge gray">${item.versions_count} версия</span></div>
  </a>`;
}

async function renderInstruments() {
  loading("Загружаем инструменты…");
  const response = await api("/api/instruments");
  app.innerHTML = `${pageHeader("Измерительный контур", "Инструменты", "Исторический LLM-прототип, два модуля МГПУ и экспертный референс.")}
    <section class="entity-grid">${response.items.map(instrumentCard).join("")}</section>`;
}

async function renderInstrument(code) {
  loading(`Загружаем ${code}…`);
  const item = await api(`/api/instruments/${encodeURIComponent(code)}`);
  const historicalWarning = code === "LLM_EVAL" ? `<div class="warning-banner"><div class="warning-symbol">!</div><div><strong>Eval-2024 — исторический неподтверждённый прототип</strong><span>Он использовал только первые 3000 символов транскрипта, не выдавал таймкоды и мог записывать 0 при технической ошибке. Существующие персональные результаты в БД не импортированы.</span></div></div>` : "";
  app.innerHTML = `
    ${breadcrumb("#/instruments", "Инструменты", item.name)}
    ${pageHeader(item.code, item.name, item.description, `${editorTableAction("instruments", { id: item.id })}<a class="secondary-button" href="#/tables/instruments">Строка в БД</a>`)}
    ${historicalWarning}
    <section class="detail-layout">
      <div class="detail-column">
        <div class="detail-card"><div class="panel-header"><div><h2>Версии</h2><p>Конфигурация, происхождение и ограничения</p></div></div><div class="version-list">${item.versions.map((version) => `<div class="version-row"><div class="version-head"><div><strong>${escapeHTML(version.version_name)}</strong><span>${escapeHTML(version.version_code)}</span></div>${badge(version.lifecycle_status, textLabel(version.lifecycle_status))}</div><div class="card-meta">${badge(version.methodology_status)}${version.model_name ? `<span class="badge gray">${escapeHTML(version.model_name)}</span>` : ""}</div><p>${escapeHTML(version.config_summary || "Конфигурация не документирована.")}</p>${version.limitations ? `<p><strong>Ограничения:</strong> ${escapeHTML(version.limitations)}</p>` : ""}</div>`).join("")}</div></div>
        <div class="detail-card"><div class="panel-header"><div><h2>Покрытие критериев</h2><p>${item.coverage.length} явно заданных связей</p></div></div>${item.coverage.length ? `<div class="coverage-list">${item.coverage.map((coverage) => `<a class="coverage-row" href="#/criteria/${coverage.code}"><div class="coverage-head"><div><strong>${escapeHTML(coverage.code)} · ${escapeHTML(coverage.name)}</strong><span>Критерий № ${coverage.number}</span></div>${badge(coverage.coverage_status)}</div>${coverage.notes ? `<p>${escapeHTML(coverage.notes)}</p>` : ""}</a>`).join("")}</div>` : emptyState("Покрытие не зафиксировано", "Для версии нет явных связей с критериями.", "○")}</div>
      </div>
      <aside class="detail-column">
        <div class="detail-card"><div class="panel-header"><div><h3>Входы и производные данные</h3></div></div><div class="data-list">${item.inputs.map((input) => `<div class="data-row"><div class="data-head"><div><strong>${escapeHTML(input.name)}</strong><span>${escapeHTML(input.code)}</span></div>${badge(input.requirement_role)}</div><p>${escapeHTML(input.purpose)}</p></div>`).join("")}</div></div>
        <div class="detail-card"><dl class="definition-list"><div><dt>Поставщик</dt><dd>${escapeHTML(item.provider)}</dd></div><div><dt>Тип</dt><dd>${escapeHTML(instrumentKind(item.instrument_kind))}</dd></div><div><dt>Режим</dt><dd>${state.editor.enabled ? "Локальное редактирование включено" : "Только чтение существующих данных"}</dd></div></dl></div>
      </aside>
    </section>`;
}

function conditionCard(item) {
  const primary = item.instruments.filter((instrument) => instrument.role === "primary" || instrument.role === "reference");
  const required = item.data_types.filter((data) => data.requirement_role === "required");
  return `<a class="entity-card" href="#/conditions/${encodeURIComponent(item.code)}">
    <div class="card-topline"><span class="entity-code">${escapeHTML(item.code)}</span><span class="badge blue">шаг ${item.condition_order}</span></div>
    <h2>${escapeHTML(item.name)}</h2><p>${escapeHTML(item.description)}</p>
    <div class="card-meta"><span class="badge gray">${primary.length} основных</span><span class="badge gray">${required.length} обязательных входа</span></div>
  </a>`;
}

async function renderConditions() {
  loading("Загружаем A0–A5…");
  const response = await api("/api/conditions");
  app.innerHTML = `${pageHeader("Экспериментальные ветви", "Сравниваемые условия A0–A5", "Парные сравнения на одних занятиях показывают вклад данных и роль ИИ.")}
    <section class="condition-flow" style="margin-bottom:18px">${response.items.map((item) => `<a class="condition-step" href="#/conditions/${item.code}"><strong>${item.code} · ${escapeHTML(item.name)}</strong><span>${escapeHTML(item.description)}</span></a>`).join("")}</section>
    <section class="entity-grid">${response.items.map(conditionCard).join("")}</section>`;
}

async function renderCondition(code) {
  loading(`Загружаем ${code}…`);
  const item = await api(`/api/conditions/${encodeURIComponent(code)}`);
  app.innerHTML = `
    ${breadcrumb("#/conditions", "Условия A0–A5", `${item.code} · ${item.name}`)}
    ${pageHeader(`Условие ${item.code}`, item.name, item.description, `${editorTableAction("comparison_conditions", { id: item.id })}<a class="secondary-button" href="#/tables/comparison_conditions">Строка в БД</a>`)}
    <section class="detail-layout">
      <div class="detail-column">
        <div class="detail-card"><div class="panel-header"><div><h2>Инструменты</h2><p>Роль каждого участника измерительного контура</p></div></div><div class="coverage-list">${item.instruments.map((instrument) => `<a class="coverage-row" href="#/instruments/${instrument.code}"><div class="coverage-head"><div><strong>${escapeHTML(instrument.name)}</strong><span>${escapeHTML(instrumentKind(instrument.instrument_kind))}</span></div>${badge(instrument.role)}</div>${instrument.notes ? `<p>${escapeHTML(instrument.notes)}</p>` : ""}</a>`).join("")}</div></div>
        <div class="detail-card"><div class="panel-header"><div><h2>Использование в проверках</h2><p>Эффекты, где условие выступает базой, референсом или кандидатом</p></div></div><div class="link-list">${item.effect_checks.map((check) => `<a class="link-row" href="#/effects/${check.effect_code}"><span class="route-code">${escapeHTML(check.effect_code)}</span><span><strong>${escapeHTML(check.effect_name)}</strong><span>${escapeHTML(check.method_code)} · ${escapeHTML(check.method_name)}</span></span>${badge(check.role)}</a>`).join("")}</div></div>
      </div>
      <aside class="detail-column"><div class="detail-card"><div class="panel-header"><div><h3>Данные условия</h3></div></div><div class="data-list">${item.data_types.map((data) => `<div class="data-row"><div class="data-head"><div><strong>${escapeHTML(data.name)}</strong><span>${escapeHTML(data.code)}</span></div>${badge(data.requirement_role)}</div><p>${escapeHTML(data.purpose)}</p></div>`).join("")}</div></div></aside>
    </section>`;
}

function effectCard(item) {
  return `<a class="entity-card effect-card purple" href="#/effects/${encodeURIComponent(item.code)}">
    <div class="card-topline"><span class="entity-code">${escapeHTML(item.code)}</span><span class="badge purple">${escapeHTML(item.method_code)}</span></div>
    <h2>${escapeHTML(item.name)}</h2><p>${escapeHTML(item.hypothesis)}</p>
    <div class="method-box"><strong>${escapeHTML(item.method_name)}</strong><br>${escapeHTML(item.metrics)}</div>
  </a>`;
}

async function renderEffects() {
  loading("Загружаем E1–E9…");
  const response = await api("/api/effects");
  app.innerHTML = `${pageHeader("Дерево эффектов", "Проверяемые эффекты E1–E9", "Что именно должно измениться, каким методом это измеряется и какие условия сравниваются.")}
    <section class="entity-grid">${response.items.map(effectCard).join("")}</section>`;
}

async function renderEffect(code) {
  loading(`Загружаем ${code}…`);
  const item = await api(`/api/effects/${encodeURIComponent(code)}`);
  app.innerHTML = `
    ${breadcrumb("#/effects", "Эффекты E1–E9", `${item.code} · ${item.name}`)}
    ${pageHeader(`${item.code} · ${item.method_code}`, item.name, item.hypothesis, `${editorTableAction("effects", { id: item.id })}<a class="secondary-button" href="#/tables/effects">Строка в БД</a>`)}
    <section class="detail-layout">
      <div class="detail-column">
        <div class="detail-card"><div class="panel-header"><div><h2>${escapeHTML(item.method_name)}</h2><p>Способ проверки ${escapeHTML(item.method_code)}</p></div></div><p>${escapeHTML(item.method_description)}</p><dl class="definition-list" style="margin-top:18px"><div><dt>Метрики</dt><dd>${escapeHTML(item.metrics)}</dd></div><div><dt>Процедура</dt><dd>${escapeHTML(item.procedure)}</dd></div><div><dt>Единица анализа</dt><dd>${escapeHTML(item.unit_of_analysis)}</dd></div><div><dt>Сравнение</dt><dd>${escapeHTML(item.comparison_description)}</dd></div><div><dt>Правило успеха</dt><dd>${escapeHTML(item.success_rule)}</dd></div></dl></div>
        <div class="detail-card"><div class="panel-header"><div><h2>Критерии</h2><p>${item.criteria.length} связанных критериев</p></div></div><div class="card-meta">${item.criteria.map((criterion) => `<a class="badge ${criterion.scope_role}" href="#/criteria/${criterion.code}">${escapeHTML(criterion.code)} · ${escapeHTML(criterion.name)}</a>`).join("")}</div></div>
      </div>
      <aside class="detail-column">
        <div class="detail-card"><div class="panel-header"><div><h3>Сравниваемые условия</h3></div></div><div class="link-list">${item.conditions.map((condition) => `<a class="link-row" href="#/conditions/${condition.code}"><span class="route-code">${escapeHTML(condition.code)}</span><span><strong>${escapeHTML(condition.name)}</strong><span>${escapeHTML(condition.notes || "Роль в сравнении")}</span></span>${badge(condition.role)}</a>`).join("")}</div></div>
        <div class="detail-card"><div class="panel-header"><div><h3>Данные проверки</h3></div></div><div class="data-list">${item.data_types.map((data) => `<div class="data-row"><div class="data-head"><div><strong>${escapeHTML(data.name)}</strong><span>${escapeHTML(data.code)}</span></div>${badge(data.role)}</div>${data.notes ? `<p>${escapeHTML(data.notes)}</p>` : ""}</div>`).join("")}</div></div>
      </aside>
    </section>`;
}

async function renderERD() {
  app.innerHTML = `${pageHeader("Структура данных", "ERD базы пилота", "Перетаскивайте схему мышью или трекпадом и изменяйте масштаб. SQLite и SQL-схема остаются источником истины.")}
    <section class="erd-shell">
      <div class="erd-toolbar">
        <button class="icon-button" id="erd-minus" aria-label="Уменьшить">−</button>
        <span class="zoom-value" id="erd-zoom">18%</span>
        <button class="icon-button" id="erd-plus" aria-label="Увеличить">＋</button>
        <button class="secondary-button" id="erd-fit">Вписать</button>
        <button class="secondary-button" id="erd-reset">100%</button>
        <a href="${documentUrl("./assets/erd.mmd")}" target="_blank" rel="noopener">Открыть MMD ↗</a>
      </div>
      <div class="erd-viewport" id="erd-viewport"><img class="erd-image" id="erd-image" src="${documentUrl("./assets/erd.svg")}" alt="ERD базы пилота автоматизации критериев ТюмГУ" draggable="false"></div>
    </section>`;
  setupERD();
}

function setupERD() {
  const viewport = document.querySelector("#erd-viewport");
  const image = document.querySelector("#erd-image");
  const zoomLabel = document.querySelector("#erd-zoom");
  let dragging = false;
  let startX = 0;
  let startY = 0;
  let originX = 0;
  let originY = 0;

  const apply = () => {
    image.style.transform = `translate(${state.erd.x}px, ${state.erd.y}px) scale(${state.erd.scale})`;
    zoomLabel.textContent = `${Math.round(state.erd.scale * 100)}%`;
  };
  const setScale = (next, centerX = viewport.clientWidth / 2, centerY = viewport.clientHeight / 2) => {
    const previous = state.erd.scale;
    const scale = Math.min(1.5, Math.max(0.06, next));
    const ratio = scale / previous;
    state.erd.x = centerX - (centerX - state.erd.x) * ratio;
    state.erd.y = centerY - (centerY - state.erd.y) * ratio;
    state.erd.scale = scale;
    apply();
  };
  const fit = () => {
    if (!image.naturalWidth || !image.naturalHeight) return;
    const scale = Math.min((viewport.clientWidth - 36) / image.naturalWidth, (viewport.clientHeight - 36) / image.naturalHeight);
    state.erd.scale = scale;
    state.erd.x = (viewport.clientWidth - image.naturalWidth * scale) / 2;
    state.erd.y = (viewport.clientHeight - image.naturalHeight * scale) / 2;
    apply();
  };
  image.addEventListener("load", () => {
    state.erd.naturalWidth = image.naturalWidth;
    state.erd.naturalHeight = image.naturalHeight;
    fit();
  });
  document.querySelector("#erd-plus").addEventListener("click", () => setScale(state.erd.scale * 1.25));
  document.querySelector("#erd-minus").addEventListener("click", () => setScale(state.erd.scale / 1.25));
  document.querySelector("#erd-fit").addEventListener("click", fit);
  document.querySelector("#erd-reset").addEventListener("click", () => {
    state.erd.scale = 1;
    state.erd.x = 18;
    state.erd.y = 18;
    apply();
  });
  viewport.addEventListener("wheel", (event) => {
    event.preventDefault();
    const box = viewport.getBoundingClientRect();
    setScale(state.erd.scale * (event.deltaY > 0 ? 0.9 : 1.1), event.clientX - box.left, event.clientY - box.top);
  }, { passive: false });
  viewport.addEventListener("pointerdown", (event) => {
    dragging = true;
    startX = event.clientX;
    startY = event.clientY;
    originX = state.erd.x;
    originY = state.erd.y;
    viewport.classList.add("dragging");
    viewport.setPointerCapture(event.pointerId);
  });
  viewport.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    state.erd.x = originX + event.clientX - startX;
    state.erd.y = originY + event.clientY - startY;
    apply();
  });
  const stop = () => { dragging = false; viewport.classList.remove("dragging"); };
  viewport.addEventListener("pointerup", stop);
  viewport.addEventListener("pointercancel", stop);
  apply();
}

function tableIndex(items, selected) {
  const groups = {
    table: items.filter((item) => item.kind === "table"),
    view: items.filter((item) => item.kind === "view"),
  };
  return Object.entries(groups).map(([kind, rows]) => `<div class="table-index-group"><div class="table-index-title">${kind === "table" ? "Таблицы" : "Представления"}</div>${rows.map((row) => `<a class="${row.name === selected ? "active" : ""}" href="#/tables/${encodeURIComponent(row.name)}"><span>${escapeHTML(row.name)}</span><span>${row.row_count === null ? "локально" : row.row_count}</span></a>`).join("")}</div>`).join("");
}

function formatCell(value) {
  if (value === null || value === undefined) return `<span class="null-value">NULL</span>`;
  if (typeof value === "object") return escapeHTML(JSON.stringify(value));
  return escapeHTML(value);
}

async function renderTables(name = null) {
  loading("Читаем sqlite_schema…");
  const index = await api("/api/tables");
  const selected = name || index.items.find((item) => item.name === "criteria")?.name || index.items[0]?.name;
  if (!selected) {
    app.innerHTML = emptyState("В базе нет таблиц", "sqlite_schema не вернула доступных объектов.", "▦");
    return;
  }
  state.table.name = selected;
  if (name !== state.table.lastName) {
    state.table.offset = 0;
    state.table.query = "";
    state.table.lastName = name;
  }
  const params = new URLSearchParams({ limit: String(state.table.limit), offset: String(state.table.offset) });
  if (state.table.query) params.set("q", state.table.query);
  const selectedMeta = index.items.find((item) => item.name === selected);
  const editable = Boolean(state.editor.enabled && selectedMeta?.kind === "table");
  const data = await api(`${editable ? "/api/editor/tables/" : "/api/tables/"}${encodeURIComponent(selected)}?${params}`);
  state.editor.currentTableData = editable ? data : null;
  const pageStart = data.total ? data.offset + 1 : 0;
  const pageEnd = data.total === null ? null : Math.min(data.offset + data.rows.length, data.total);
  const rowEntries = editable
    ? data.rows
    : data.rows.map((values) => ({ values, key: null, etag: null }));
  const tableBody = data.restricted
    ? emptyState("Доступно только в локальной базе", "Публичный снимок показывает структуру таблицы, но не экспортирует строки или реальные количества.", "▣")
    : rowEntries.length
      ? `<div class="data-table-wrap"><table class="data-table"><thead><tr>${data.columns.map((column) => `<th title="${escapeHTML(column.type || "")}">${escapeHTML(column.name)}</th>`).join("")}${editable ? "<th>Действия</th>" : ""}</tr></thead><tbody>${rowEntries.map((entry, indexValue) => `<tr>${data.columns.map((column) => `<td title="${escapeHTML(entry.values[column.name] ?? "NULL")}">${formatCell(entry.values[column.name])}</td>`).join("")}${editable ? `<td class="row-actions"><button class="table-action" data-row-edit="${indexValue}">Изменить</button><button class="table-action danger" data-row-delete="${indexValue}">Удалить</button></td>` : ""}</tr>`).join("")}</tbody></table></div>`
      : emptyState("В таблице пока нет строк", "Структура готова для будущих данных пилота. Пустота не интерпретируется как нулевое значение.", "▦");
  app.innerHTML = `${pageHeader("Технический режим", "Таблицы и представления", state.editor.enabled ? "Локальные формы изменяют SQLite транзакционно; произвольный SQL недоступен." : "Универсальный просмотр SQLite без SQL-консоли и операций записи.")}
    ${editorStatusBanner()}
    <section class="tables-layout">
      <aside class="table-index">${tableIndex(index.items, selected)}</aside>
      <div class="table-panel">
        <div class="table-panel-header"><div><h2>${escapeHTML(data.name)}</h2><p>${data.kind === "view" ? "Представление · только чтение" : "Таблица"} · ${data.total === null ? "строки скрыты" : `${data.total} строк`} · ${data.columns.length} колонок</p></div><div class="table-header-actions"><div class="table-filter"><input id="table-query" value="${escapeHTML(state.table.query)}" placeholder="Фильтр по значениям…" aria-label="Фильтр строк таблицы" ${data.restricted ? "disabled" : ""}></div>${editable ? '<button class="primary-button" id="table-add">＋ Добавить</button>' : ""}</div></div>
        ${tableBody}
        ${data.restricted ? "" : `<div class="table-pagination"><span>Показано ${pageStart}–${pageEnd} из ${data.total}</span><div class="pagination-actions"><button class="secondary-button" id="table-prev" ${data.offset <= 0 ? "disabled" : ""}>← Назад</button><button class="secondary-button" id="table-next" ${pageEnd >= data.total ? "disabled" : ""}>Далее →</button></div></div>`}
      </div>
    </section>`;
  const queryInput = document.querySelector("#table-query");
  let timer;
  queryInput.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      state.table.query = queryInput.value.trim();
      state.table.offset = 0;
      renderTables(selected).catch(errorPanel);
    }, 280);
  });
  document.querySelector("#table-prev")?.addEventListener("click", () => {
    state.table.offset = Math.max(0, state.table.offset - state.table.limit);
    renderTables(selected).catch(errorPanel);
  });
  document.querySelector("#table-next")?.addEventListener("click", () => {
    state.table.offset += state.table.limit;
    renderTables(selected).catch(errorPanel);
  });
  document.querySelector("#table-add")?.addEventListener("click", () => openEditorForm(data.schema));
  document.querySelectorAll("[data-row-edit]").forEach((button) => button.addEventListener("click", () => {
    openEditorForm(data.schema, data.rows[Number(button.dataset.rowEdit)]);
  }));
  document.querySelectorAll("[data-row-delete]").forEach((button) => button.addEventListener("click", () => {
    openDeleteDialog(data.schema, data.rows[Number(button.dataset.rowDelete)]).catch(showEditorError);
  }));
}

function closeEditor() {
  editorOverlay.hidden = true;
  editorDrawer.innerHTML = "";
  state.editor.current = null;
  document.body.classList.remove("editor-open");
}

function editorFieldInput(column, value, mode) {
  const id = `editor-field-${column.cid}`;
  const readonly = mode === "edit" && column.pk;
  const isNull = value === null || (mode === "create" && column.nullable && column.dflt_value === null);
  const useDefault = mode === "create" && column.dflt_value !== null;
  const enumValues = column.enum_options || [];
  const numericType = /INT|REAL|FLOA|DOUB|NUM/i.test(column.type || "");
  const booleanType = enumValues.length === 2 && enumValues.includes(0) && enumValues.includes(1);
  const longText = column.json || /description|notes|rationale|procedure|summary|limitations|purpose|hypothesis|rule|excerpt|metadata|configuration|output|citation|claim|evidence|access/i.test(column.name);
  let input;
  if (column.generated && mode === "create") {
    input = `<div class="generated-value">Будет назначено SQLite автоматически</div>`;
  } else if (column.foreign_key) {
    const targetColumn = column.foreign_key.to || "id";
    input = `<div class="foreign-control"><input type="search" class="foreign-search" data-target="${id}" placeholder="Найти связанное значение…" ${readonly || isNull || useDefault ? "disabled" : ""}><select id="${id}" data-editor-input data-foreign-table="${escapeHTML(column.foreign_key.table)}" data-foreign-column="${escapeHTML(targetColumn)}" data-current-value="${escapeHTML(JSON.stringify(value))}" ${readonly || isNull || useDefault ? "disabled" : ""}><option value="${escapeHTML(JSON.stringify(value))}">${escapeHTML(value ?? "Выберите значение")}</option></select></div>`;
  } else if (booleanType) {
    input = `<label class="boolean-control"><input id="${id}" data-editor-input data-boolean="true" type="checkbox" ${Number(value) === 1 ? "checked" : ""} ${readonly || isNull || useDefault ? "disabled" : ""}><span>Включено</span></label>`;
  } else if (enumValues.length) {
    input = `<select id="${id}" data-editor-input ${readonly || isNull || useDefault ? "disabled" : ""}>${enumValues.map((option) => `<option value="${escapeHTML(JSON.stringify(option))}" ${Object.is(option, value) ? "selected" : ""}>${escapeHTML(option)}</option>`).join("")}</select>`;
  } else if (longText) {
    input = `<textarea id="${id}" data-editor-input rows="${column.json ? 7 : 4}" ${readonly || isNull || useDefault ? "disabled" : ""}>${escapeHTML(value ?? "")}</textarea>`;
  } else {
    input = `<input id="${id}" data-editor-input type="${numericType ? "number" : "text"}" ${numericType ? 'step="any"' : ""} value="${escapeHTML(value ?? "")}" ${readonly || isNull || useDefault ? "disabled" : ""}>`;
  }
  return `<div class="editor-field" data-field-name="${escapeHTML(column.name)}" data-column-type="${escapeHTML(column.type || "TEXT")}" data-json="${column.json ? "true" : "false"}" data-generated="${column.generated ? "true" : "false"}" data-primary-key="${column.pk ? "true" : "false"}">
    <div class="editor-field-head"><label for="${id}">${escapeHTML(column.name)}${column.notnull ? " *" : ""}</label><span>${escapeHTML(column.type || "TEXT")}${column.pk ? " · PK" : ""}${column.foreign_key ? ` · FK → ${escapeHTML(column.foreign_key.table)}.${escapeHTML(column.foreign_key.to || "PK")}` : ""}</span></div>
    ${input}
    <div class="field-options">
      ${column.nullable && !readonly ? `<label><input type="checkbox" data-null-toggle ${isNull ? "checked" : ""}> NULL</label>` : ""}
      ${useDefault ? `<label><input type="checkbox" data-default-toggle checked> По умолчанию: ${escapeHTML(column.dflt_value)}</label>` : ""}
    </div>
    <div class="field-error" aria-live="polite"></div>
  </div>`;
}

async function loadForeignSelect(select, query = "") {
  const currentRaw = select.dataset.currentValue;
  let current;
  try { current = JSON.parse(currentRaw); } catch { current = currentRaw; }
  const params = new URLSearchParams({ column: select.dataset.foreignColumn });
  if (query) params.set("q", query);
  const response = await api(`/api/editor/options/${encodeURIComponent(select.dataset.foreignTable)}?${params}`);
  const options = [...response.items];
  if (current !== null && current !== undefined && !options.some((item) => Object.is(item.value, current))) {
    options.unshift({ value: current, label: String(current) });
  }
  select.innerHTML = `<option value="">— выберите —</option>${options.map((item) => `<option value="${escapeHTML(JSON.stringify(item.value))}" ${Object.is(item.value, current) ? "selected" : ""}>${escapeHTML(item.label)}</option>`).join("")}`;
}

function setupEditorFieldControls() {
  editorDrawer.querySelectorAll(".editor-field").forEach((field) => {
    const input = field.querySelector("[data-editor-input]");
    const nullToggle = field.querySelector("[data-null-toggle]");
    const defaultToggle = field.querySelector("[data-default-toggle]");
    const updateDisabled = () => {
      const immutable = field.dataset.primaryKey === "true" && state.editor.current?.mode === "edit";
      const generated = field.dataset.generated === "true" && state.editor.current?.mode === "create";
      const disabled = immutable || generated || Boolean(nullToggle?.checked) || Boolean(defaultToggle?.checked);
      if (input) input.disabled = disabled;
      const search = field.querySelector(".foreign-search");
      if (search) search.disabled = disabled;
    };
    nullToggle?.addEventListener("change", updateDisabled);
    defaultToggle?.addEventListener("change", updateDisabled);
    updateDisabled();
  });
  editorDrawer.querySelectorAll("select[data-foreign-table]").forEach((select) => {
    loadForeignSelect(select).catch((error) => {
      select.innerHTML = `<option value="">${escapeHTML(error.message)}</option>`;
    });
    const search = editorDrawer.querySelector(`.foreign-search[data-target="${select.id}"]`);
    let timer;
    search?.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => loadForeignSelect(select, search.value.trim()).catch(showEditorError), 250);
    });
  });
}

function collectEditorValues() {
  const values = {};
  editorDrawer.querySelectorAll(".editor-field").forEach((field) => {
    field.classList.remove("has-error");
    field.querySelector(".field-error").textContent = "";
    if (field.dataset.generated === "true" && state.editor.current.mode === "create") return;
    if (field.dataset.primaryKey === "true" && state.editor.current.mode === "edit") return;
    if (field.querySelector("[data-default-toggle]")?.checked) return;
    const name = field.dataset.fieldName;
    if (field.querySelector("[data-null-toggle]")?.checked) {
      values[name] = null;
      return;
    }
    const input = field.querySelector("[data-editor-input]");
    if (input.dataset.boolean === "true") {
      values[name] = input.checked ? 1 : 0;
    } else if (input.tagName === "SELECT") {
      if (input.value === "") values[name] = "";
      else values[name] = JSON.parse(input.value);
    } else {
      values[name] = input.value;
    }
    if (field.dataset.json === "true" && values[name] !== "" && values[name] !== null) {
      try { JSON.parse(values[name]); }
      catch {
        field.classList.add("has-error");
        field.querySelector(".field-error").textContent = "Введите корректный JSON";
        throw new Error(`Поле ${name} содержит некорректный JSON`);
      }
    }
  });
  return values;
}

function showEditorError(error) {
  const panel = editorDrawer.querySelector("#editor-error");
  if (panel) {
    panel.textContent = error.message || String(error);
    panel.hidden = false;
  } else {
    showToast(error.message || String(error));
  }
  if (error.field) {
    const field = editorDrawer.querySelector(`.editor-field[data-field-name="${CSS.escape(error.field)}"]`);
    field?.classList.add("has-error");
    const message = field?.querySelector(".field-error");
    if (message) message.textContent = error.message;
  }
}

function openEditorForm(schema, row = null) {
  const mode = row ? "edit" : "create";
  state.editor.current = { mode, schema, row };
  const values = row?.values || {};
  editorDrawer.innerHTML = `<header class="editor-header"><div><span>${mode === "create" ? "Новая строка" : "Редактирование строки"}</span><h2 id="editor-title">${escapeHTML(schema.name)}</h2></div><button class="icon-button" data-editor-close aria-label="Закрыть">×</button></header>
    <form id="editor-form" novalidate>
      <div class="editor-error" id="editor-error" hidden></div>
      <div class="editor-fields">${schema.columns.map((column) => editorFieldInput(column, values[column.name] ?? null, mode)).join("")}</div>
      <footer class="editor-footer"><button type="button" class="secondary-button" data-editor-close>Отмена</button><button type="submit" class="primary-button">${mode === "create" ? "Добавить строку" : "Сохранить изменения"}</button></footer>
    </form>`;
  editorOverlay.hidden = false;
  document.body.classList.add("editor-open");
  editorDrawer.querySelectorAll("[data-editor-close]").forEach((button) => button.addEventListener("click", closeEditor));
  setupEditorFieldControls();
  editorDrawer.querySelector("#editor-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = event.submitter;
    submit.disabled = true;
    try {
      const formValues = collectEditorValues();
      const path = `/api/editor/tables/${encodeURIComponent(schema.name)}/rows`;
      if (mode === "create") {
        await api(path, { method: "POST", body: { values: formValues } });
      } else {
        await api(path, { method: "PATCH", body: { key: row.key, values: formValues, etag: row.etag } });
      }
      closeEditor();
      clearDataCache();
      await checkEditorStatus();
      await renderTables(schema.name);
      showToast(mode === "create" ? "Строка добавлена" : "Изменения сохранены");
    } catch (error) {
      showEditorError(error);
    } finally {
      submit.disabled = false;
    }
  });
  setTimeout(() => editorDrawer.querySelector("input:not(:disabled), textarea:not(:disabled), select:not(:disabled)")?.focus(), 0);
}

async function openDeleteDialog(schema, row) {
  const preview = await api(`/api/editor/tables/${encodeURIComponent(schema.name)}/delete-preview`, {
    method: "POST",
    body: { key: row.key, etag: row.etag },
  });
  state.editor.current = { mode: "delete", schema, row, preview };
  const references = preview.references.length
    ? `<div class="delete-references">${preview.references.map((item) => `<div><strong>${escapeHTML(item.table)}</strong><span>${item.count} строк · ON DELETE ${escapeHTML(item.on_delete)}</span></div>`).join("")}</div>`
    : `<p>Связанных строк не найдено.</p>`;
  editorDrawer.innerHTML = `<header class="editor-header"><div><span>Удаление строки</span><h2 id="editor-title">${escapeHTML(schema.name)}</h2></div><button class="icon-button" data-editor-close aria-label="Закрыть">×</button></header>
    <div class="delete-dialog"><div class="editor-error" id="editor-error" hidden></div><div class="danger-panel"><strong>Это изменение попадёт непосредственно в рабочую SQLite.</strong><span>Перед первой записью текущего запуска создаётся резервная копия.</span></div>${references}
      ${preview.requires_typed_confirmation ? `<label class="typed-confirmation">Введите <code>${escapeHTML(schema.name)}</code>, чтобы подтвердить удаление связанных строк<input id="delete-confirmation" autocomplete="off"></label>` : ""}
      <footer class="editor-footer"><button class="secondary-button" data-editor-close>Отмена</button><button class="danger-button" id="confirm-delete">Удалить</button></footer></div>`;
  editorOverlay.hidden = false;
  document.body.classList.add("editor-open");
  editorDrawer.querySelectorAll("[data-editor-close]").forEach((button) => button.addEventListener("click", closeEditor));
  editorDrawer.querySelector("#confirm-delete").addEventListener("click", async (event) => {
    event.currentTarget.disabled = true;
    try {
      await api(`/api/editor/tables/${encodeURIComponent(schema.name)}/rows`, {
        method: "DELETE",
        body: {
          key: row.key,
          etag: row.etag,
          confirmation_token: preview.confirmation_token,
          confirmation_text: editorDrawer.querySelector("#delete-confirmation")?.value || "",
        },
      });
      closeEditor();
      clearDataCache();
      await checkEditorStatus();
      await renderTables(schema.name);
      showToast("Строка удалена");
    } catch (error) {
      showEditorError(error);
      event.currentTarget.disabled = false;
    }
  });
}

async function openEditorForKey(table, key) {
  const firstValue = Object.values(key)[0];
  const params = new URLSearchParams({ limit: "100", offset: "0", q: String(firstValue ?? "") });
  const data = await api(`/api/editor/tables/${encodeURIComponent(table)}?${params}`);
  const row = data.rows.find((candidate) => Object.entries(key).every(([name, value]) => Object.is(candidate.key[name], value)));
  if (!row) throw new Error("Строка для редактирования не найдена");
  openEditorForm(data.schema, row);
}

async function route() {
  const hash = location.hash.replace(/^#\/?/, "") || "overview";
  const parts = hash.split("/").filter(Boolean).map(decodeURIComponent);
  const section = parts[0] || "overview";
  const id = parts[1] || null;
  setActiveNav(section);
  document.title = `${routeNames[section] || "Навигатор"} · Пилот ТюмГУ`;
  try {
    if (section === "overview") await renderOverview();
    else if (section === "criteria") await (id ? renderCriterion(id) : renderCriteria());
    else if (section === "sources") await (id ? renderResearchSource(id) : renderResearchSources());
    else if (section === "instruments") await (id ? renderInstrument(id) : renderInstruments());
    else if (section === "conditions") await (id ? renderCondition(id) : renderConditions());
    else if (section === "effects") await (id ? renderEffect(id) : renderEffects());
    else if (section === "erd") await renderERD();
    else if (section === "tables") await renderTables(id);
    else {
      location.hash = "#/overview";
      return;
    }
    app.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  } catch (error) {
    errorPanel(error);
  }
}

function setupSearch() {
  let timer;
  const close = () => { searchResults.hidden = true; };
  searchInput.addEventListener("input", () => {
    clearTimeout(timer);
    const query = searchInput.value.trim();
    if (!query) { close(); return; }
    timer = setTimeout(async () => {
      try {
        const result = await api(`/api/search?q=${encodeURIComponent(query)}`);
        const groups = [
          ["Критерии", result.criteria, (item) => `#/criteria/${item.code}`],
          ["Источники", result.sources, (item) => `#/sources/${item.code}`],
          ["Инструменты", result.instruments, (item) => `#/instruments/${item.code}`],
          ["Условия", result.conditions, (item) => `#/conditions/${item.code}`],
          ["Эффекты", result.effects, (item) => `#/effects/${item.code}`],
        ].filter(([, items]) => items.length);
        searchResults.innerHTML = groups.length ? groups.map(([title, items, href]) => `<div class="search-group"><div class="search-group-title">${title}</div>${items.map((item) => `<a class="search-result" href="${href(item)}"><span class="search-result-code">${escapeHTML(item.code)}</span><span>${escapeHTML(item.name)}</span></a>`).join("")}</div>`).join("") : `<div class="search-empty">Совпадений не найдено</div>`;
        searchResults.hidden = false;
      } catch {
        close();
      }
    }, 220);
  });
  searchResults.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      searchInput.value = "";
      close();
    }
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".search-wrap")) close();
  });
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      searchInput.focus();
    }
    if (event.key === "Escape") {
      close();
      searchInput.blur();
      document.body.classList.remove("menu-open");
      if (!editorOverlay.hidden) closeEditor();
    }
  });
}

async function checkEditorStatus() {
  const status = await api("/api/editor/status");
  state.editor.enabled = Boolean(status.enabled);
  state.editor.csrfToken = status.csrf_token || null;
  state.editor.status = status;
  const pill = document.querySelector("#mode-pill");
  const pillLabel = document.querySelector("#mode-pill-label");
  const modeLabel = document.querySelector("#db-mode-label");
  pill.classList.toggle("editable-pill", state.editor.enabled);
  pillLabel.textContent = state.editor.enabled ? "Редактирование" : "Read-only";
  modeLabel.textContent = state.editor.enabled ? "Запись включена локально" : "Только чтение";
  document.body.classList.toggle("edit-mode", state.editor.enabled);
  return status;
}

async function checkHealth() {
  const dot = document.querySelector("#db-status-dot");
  const label = document.querySelector("#db-status-label");
  try {
    const health = await api("/health");
    dot.classList.add(health.status === "ok" ? "ok" : "error");
    label.textContent = health.database.file;
  } catch {
    dot.classList.add("error");
    label.textContent = "База недоступна";
  }
}

menuButton.addEventListener("click", () => {
  const open = !document.body.classList.contains("menu-open");
  document.body.classList.toggle("menu-open", open);
  menuButton.setAttribute("aria-expanded", String(open));
});
sidebarScrim.addEventListener("click", () => {
  document.body.classList.remove("menu-open");
  menuButton.setAttribute("aria-expanded", "false");
});
editorScrim.addEventListener("click", closeEditor);
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-edit-table]");
  if (!button) return;
  event.preventDefault();
  let key;
  try { key = JSON.parse(button.dataset.editKey); }
  catch { showToast("Некорректный ключ строки"); return; }
  openEditorForKey(button.dataset.editTable, key).catch(showEditorError);
});
window.addEventListener("hashchange", route);
window.addEventListener("error", (event) => showToast(event.message || "Ошибка интерфейса"));

async function boot() {
  setupSearch();
  try { await checkEditorStatus(); }
  catch { state.editor.enabled = false; }
  await checkHealth();
  if (!location.hash) location.hash = "#/overview";
  else await route();
}

boot().catch(errorPanel);
