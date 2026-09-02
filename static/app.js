const app = document.querySelector("#app");
const searchInput = document.querySelector("#global-search");
const searchResults = document.querySelector("#search-results");
const menuButton = document.querySelector("#menu-button");
const sidebarScrim = document.querySelector("#sidebar-scrim");
const toast = document.querySelector("#toast");

const state = {
  currentRoute: "overview",
  erd: { scale: 0.18, x: 18, y: 18, naturalWidth: 0, naturalHeight: 0 },
  table: { name: null, offset: 0, limit: 50, query: "" },
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
};

const routeNames = {
  overview: "Обзор",
  criteria: "Критерии",
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
  if (pathname === "/api/summary") return fetchJSON(dataFile("summary.json"));
  if (pathname === "/api/search") {
    const source = await fetchJSON(dataFile("search.json"));
    const query = (request.searchParams.get("q") || "").trim().slice(0, 100).toLocaleLowerCase("ru");
    if (!query) return { criteria: [], instruments: [], conditions: [], effects: [] };
    return {
      criteria: source.criteria.filter((item) => containsText(item, ["code", "name", "block_name", "subblock_name"], query)).slice(0, 8),
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
    const filtered = query
      ? source.rows.filter((row) => Object.values(row).some((value) => String(value ?? "").toLocaleLowerCase("ru").includes(query)))
      : source.rows;
    const limit = Math.max(1, Math.min(100, Number.parseInt(request.searchParams.get("limit") || "50", 10) || 50));
    const offset = Math.max(0, Number.parseInt(request.searchParams.get("offset") || "0", 10) || 0);
    return { ...source, rows: filtered.slice(offset, offset + limit), total: filtered.length, limit, offset, query };
  }
  throw new Error("Неизвестный статический ресурс");
}

async function api(path) {
  if (viewerConfig.mode === "static") return staticApi(path);
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || `HTTP ${response.status}`);
  }
  return payload;
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
    <div class="warning-banner">
      <div class="warning-symbol" aria-hidden="true">!</div>
      <div><strong>Машинный сигнал — не автоматический балл преподавателю</strong><span>Результат пилота — доказательный фрагмент, источник, таймкод и неопределённость. Окончательное решение проверяет эксперт.</span></div>
    </div>
    <section class="metric-grid" aria-label="Основные количества">
      <a class="metric-card" href="#/criteria"><span class="metric-label">Критерии</span><div class="metric-value">${c.criteria}</div><div class="metric-note">${c.score_levels} описаний шкалы 0–2</div></a>
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
        <div class="panel-header"><div><h2>Операционный контур</h2><p>Таблицы готовы, фактические данные ещё не загружены</p></div></div>
        <div class="operational-grid">
          ${Object.entries(summary.operational).map(([key, value]) => `<a class="operational-item" href="#/tables/${key === "runs" ? "evaluation_runs" : key === "evaluations" ? "criterion_evaluations" : key === "evidence" ? "evidence_fragments" : key === "results" ? "effect_results" : "lessons"}"><strong>${value}</strong><span>${operationalLabels[key]}</span></a>`).join("")}
        </div>
        <div style="margin-top:14px">${emptyState("Пилот ещё не запущен", "Занятия, запуски инструментов и доказательные фрагменты появятся здесь после начала сбора данных.", "＋")}</div>
      </div>
    </section>`;
}

function criterionCard(item) {
  return `<a class="entity-card ${statusCardClass(item.readiness_status)}" href="#/criteria/${encodeURIComponent(item.code)}">
    <div class="card-topline"><span class="entity-code">${escapeHTML(item.code)} · № ${item.number}</span>${badge(item.readiness_status)}</div>
    <h2>${escapeHTML(item.name)}</h2>
    <p>${escapeHTML(item.subblock_name || item.block_name)}</p>
    <div class="card-meta">${badge(item.platform_coverage_status)}<span class="badge gray">${item.instrument_links_count} связей</span></div>
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
    ${pageHeader(`${item.code} · критерий № ${item.number}`, item.name, item.subblock_name || item.block_name, `<a class="secondary-button" href="#/tables/criteria">Строка в БД</a>`)}
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
    ${pageHeader(item.code, item.name, item.description, `<a class="secondary-button" href="#/tables/instruments">Строка в БД</a>`)}
    ${historicalWarning}
    <section class="detail-layout">
      <div class="detail-column">
        <div class="detail-card"><div class="panel-header"><div><h2>Версии</h2><p>Конфигурация, происхождение и ограничения</p></div></div><div class="version-list">${item.versions.map((version) => `<div class="version-row"><div class="version-head"><div><strong>${escapeHTML(version.version_name)}</strong><span>${escapeHTML(version.version_code)}</span></div>${badge(version.lifecycle_status, textLabel(version.lifecycle_status))}</div><div class="card-meta">${badge(version.methodology_status)}${version.model_name ? `<span class="badge gray">${escapeHTML(version.model_name)}</span>` : ""}</div><p>${escapeHTML(version.config_summary || "Конфигурация не документирована.")}</p>${version.limitations ? `<p><strong>Ограничения:</strong> ${escapeHTML(version.limitations)}</p>` : ""}</div>`).join("")}</div></div>
        <div class="detail-card"><div class="panel-header"><div><h2>Покрытие критериев</h2><p>${item.coverage.length} явно заданных связей</p></div></div>${item.coverage.length ? `<div class="coverage-list">${item.coverage.map((coverage) => `<a class="coverage-row" href="#/criteria/${coverage.code}"><div class="coverage-head"><div><strong>${escapeHTML(coverage.code)} · ${escapeHTML(coverage.name)}</strong><span>Критерий № ${coverage.number}</span></div>${badge(coverage.coverage_status)}</div>${coverage.notes ? `<p>${escapeHTML(coverage.notes)}</p>` : ""}</a>`).join("")}</div>` : emptyState("Покрытие не зафиксировано", "Для версии нет явных связей с критериями.", "○")}</div>
      </div>
      <aside class="detail-column">
        <div class="detail-card"><div class="panel-header"><div><h3>Входы и производные данные</h3></div></div><div class="data-list">${item.inputs.map((input) => `<div class="data-row"><div class="data-head"><div><strong>${escapeHTML(input.name)}</strong><span>${escapeHTML(input.code)}</span></div>${badge(input.requirement_role)}</div><p>${escapeHTML(input.purpose)}</p></div>`).join("")}</div></div>
        <div class="detail-card"><dl class="definition-list"><div><dt>Поставщик</dt><dd>${escapeHTML(item.provider)}</dd></div><div><dt>Тип</dt><dd>${escapeHTML(instrumentKind(item.instrument_kind))}</dd></div><div><dt>Режим</dt><dd>Только чтение существующих данных</dd></div></dl></div>
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
    ${pageHeader(`Условие ${item.code}`, item.name, item.description, `<a class="secondary-button" href="#/tables/comparison_conditions">Строка в БД</a>`)}
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
    ${pageHeader(`${item.code} · ${item.method_code}`, item.name, item.hypothesis, `<a class="secondary-button" href="#/tables/effects">Строка в БД</a>`)}
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
  return Object.entries(groups).map(([kind, rows]) => `<div class="table-index-group"><div class="table-index-title">${kind === "table" ? "Таблицы" : "Представления"}</div>${rows.map((row) => `<a class="${row.name === selected ? "active" : ""}" href="#/tables/${encodeURIComponent(row.name)}"><span>${escapeHTML(row.name)}</span><span>${row.row_count}</span></a>`).join("")}</div>`).join("");
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
  const data = await api(`/api/tables/${encodeURIComponent(selected)}?${params}`);
  const pageStart = data.total ? data.offset + 1 : 0;
  const pageEnd = Math.min(data.offset + data.rows.length, data.total);
  app.innerHTML = `${pageHeader("Технический режим", "Таблицы и представления", "Универсальный просмотр SQLite без SQL-консоли и операций записи.")}
    <section class="tables-layout">
      <aside class="table-index">${tableIndex(index.items, selected)}</aside>
      <div class="table-panel">
        <div class="table-panel-header"><div><h2>${escapeHTML(data.name)}</h2><p>${data.kind === "view" ? "Представление" : "Таблица"} · ${data.total} строк · ${data.columns.length} колонок</p></div><div class="table-filter"><input id="table-query" value="${escapeHTML(state.table.query)}" placeholder="Фильтр по значениям…" aria-label="Фильтр строк таблицы"></div></div>
        ${data.rows.length ? `<div class="data-table-wrap"><table class="data-table"><thead><tr>${data.columns.map((column) => `<th title="${escapeHTML(column.type || "")}">${escapeHTML(column.name)}</th>`).join("")}</tr></thead><tbody>${data.rows.map((row) => `<tr>${data.columns.map((column) => `<td title="${escapeHTML(row[column.name] ?? "NULL")}">${formatCell(row[column.name])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : emptyState("В таблице пока нет строк", "Структура готова для будущих данных пилота. Пустота не интерпретируется как нулевое значение.", "▦")}
        <div class="table-pagination"><span>Показано ${pageStart}–${pageEnd} из ${data.total}</span><div class="pagination-actions"><button class="secondary-button" id="table-prev" ${data.offset <= 0 ? "disabled" : ""}>← Назад</button><button class="secondary-button" id="table-next" ${pageEnd >= data.total ? "disabled" : ""}>Далее →</button></div></div>
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
  document.querySelector("#table-prev").addEventListener("click", () => {
    state.table.offset = Math.max(0, state.table.offset - state.table.limit);
    renderTables(selected).catch(errorPanel);
  });
  document.querySelector("#table-next").addEventListener("click", () => {
    state.table.offset += state.table.limit;
    renderTables(selected).catch(errorPanel);
  });
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
    }
  });
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
window.addEventListener("hashchange", route);
window.addEventListener("error", (event) => showToast(event.message || "Ошибка интерфейса"));

setupSearch();
checkHealth();
if (!location.hash) location.hash = "#/overview";
else route();
