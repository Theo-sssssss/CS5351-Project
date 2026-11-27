// Console entry point: vanilla DOM + fetch, switching views by hash and calling backend APIs.
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

// View keys map to nav data-view, URL hash, and section element ids.
const titles = {
  overview: "Overview",
  review: "New Review",
  tasks: "Tasks",
  skills: "Skill Registry",
  evolution: "Evolution Lab",
};

// Backend task state enum to display labels; CSS styling uses state-* classes.
const stateLabels = {
  PENDING: "Pending",
  PLANNING: "Planning",
  EXECUTING: "Executing",
  REVIEWING: "Reviewing",
  PAUSED_BUDGET: "Paused (Budget)",
  SUCCESS: "Completed",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

// Selected task and report state for workbench and feedback form.
let selectedTask = null;
let selectedTaskData = null;
let taskPoll = null;
let listPoll = null;
let dashboardRequest = 0;
let taskRequest = 0;
let listRequest = 0;
let tasksPage = 1;
let taskFilters = {};
let selectedFinding = null;
let activeFile = null;
let diffPage = null;
let diffRequest = 0;
let findingLimit = 30;
const currentView = () => location.hash.slice(1).split("/")[0] || "overview";
const taskHash = () => `#tasks${selectedTask ? `/${selectedTask}${selectedFinding ? `/${selectedFinding}` : ""}` : ""}`;
const runningStates = new Set(["PENDING", "PLANNING", "EXECUTING", "REVIEWING"]);
const postJson = (path, body = {}) => api(path, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});
// Restore saved bearer token across reloads; server still validates it.
let accessToken = localStorage.getItem("evoagent_token") || "";
let toastTimer = null;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = value ?? "";
  return node.innerHTML.replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function formatTime(value) {
  if (!value) return "Unknown time";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : new Intl.DateTimeFormat("en-US", {
        month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
      }).format(date);
}

function formatJson(value) {
  return JSON.stringify(value, null, 2);
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const response = await fetch(path, { ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("json") ? await response.json() : await response.text();

  if (response.status === 401) {
    $("#login-overlay").classList.remove("hidden");
    $("#logout").classList.add("hidden");
  }
  if (!response.ok) {
    const plainText = typeof data === "string" && !/<[a-z][\s\S]*>/i.test(data) ? data.trim() : "";
    const message = typeof data === "object"
      ? data.error || data.detail
      : plainText || `Request failed (${response.status})`;
    throw new Error(message || response.statusText || "Request failed");
  }
  return data;
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 2600);
}

function setButtonBusy(button, busy, busyText) {
  if (!button) return;
  button.setAttribute("aria-busy", String(busy));
  if (busy) {
    button.dataset.label = button.innerHTML;
    button.disabled = true;
    button.textContent = busyText;
  } else {
    button.disabled = false;
    if (button.dataset.label) button.innerHTML = button.dataset.label;
  }
}

function show(view, updateHash = true) {
  const [section, id, finding] = view.split("/");
  view = section;
  if (view === "tasks" && !updateHash) {
    const next = /^[a-f0-9-]+$/.test(id || "") ? id : null;
    if (next !== selectedTask) resetTask(next);
    selectedFinding = /^[a-f0-9]{32}$/.test(finding || "") ? finding : null;
  }
  if (!titles[view]) {
    view = "overview";
    history.replaceState(null, "", "#overview");
  }
  $$(".view").forEach((element) => element.classList.remove("active"));
  $$(".nav-item").forEach((element) => {
    const active = element.dataset.view === view;
    element.classList.toggle("active", active);
    element.setAttribute("aria-current", active ? "page" : "false");
  });
  $(`#view-${view}`).classList.add("active");
  $("#page-title").textContent = titles[view];
  document.title = `${titles[view]} · EvoAgent`;
  if (updateHash) history.replaceState(null, "", view === "tasks" ? taskHash() : `#${view}`);

  if (view === "tasks") {
    loadTasks();
    if (selectedTask) refreshTask(selectedTask);
  } else {
    clearTimeout(taskPoll);
    clearTimeout(listPoll);
  }
  if (view === "overview") loadDashboard();
  if (view === "skills") loadSkills();
  if (view === "evolution") loadFailures();
  else clearTimeout(evaluationPoll);
  window.scrollTo({ top: 0, behavior: reduceMotion.matches ? "auto" : "smooth" });
}

$$(".nav-item").forEach((button) => button.addEventListener("click", () => show(button.dataset.view)));
$$("[data-jump]").forEach((button) => button.addEventListener("click", () => show(button.dataset.jump)));
window.addEventListener("hashchange", () => show(location.hash.slice(1), false));

function taskRows(tasks) {
  if (!tasks?.length) {
    return '<div class="empty-state"><span><b>No review tasks yet</b>Submit a Diff to start your first review</span></div>';
  }
  return tasks.map((task) => {
    const state = String(task.state || "PENDING").toUpperCase();
    const repository = escapeHtml(task.repository || "Untitled Repository");
    const pr = task.pull_request ? `PR #${escapeHtml(task.pull_request)}` : "Manual Review";
    return `
      <button class="task-row" data-task="${escapeHtml(task.id)}" type="button">
        <span class="task-main">
          <span class="task-glyph">PR</span>
          <span class="task-copy">
            <span class="task-name">${repository}</span>
            <span class="task-meta"><span>${pr}</span><span>${escapeHtml(formatTime(task.created_at))}</span></span>
          </span>
        </span>
        <span class="status state-${state.toLowerCase()}">${stateLabels[state] || escapeHtml(state)}</span>
      </button>`;
  }).join("");
}

function bindTasks(root) {
  $$("[data-task]", root).forEach((row) => row.addEventListener("click", () => openTask(row.dataset.task)));
}

function statCard(label, value, note, style, icon) {
  return `<article class="stat ${style}">
    <div class="stat-head"><span>${label}</span><i>${icon}</i></div>
    <b>${value}</b><small>${note}</small>
  </article>`;
}

function renderLlmRuntime(llm = {}, runMode = {}) {
  const enabled = Boolean(llm.enabled);
  const failed = Boolean(llm.error);
  const provider = String(llm.provider || "local");
  const model = String(llm.model || "");
  const detail = failed
    ? "Unable to read model configuration"
    : enabled
      ? `${provider} / ${model || "default model"} — context-aware review & risk analysis`
      : "No model configured; agentic review unavailable";
  const state = failed ? "Error" : enabled ? "Enabled" : "Not Configured";
  const runtime = failed
    ? "Runtime status unknown"
    : enabled
      ? `${provider} / ${model || "Model configured"}`
      : "agentic / model required";

  const chain = $("#execution-chain");
  if (chain) {
    const scanner = '<div class="agent-step"><b>01</b><span><strong>Tool / Scanner</strong><small>Rules, AST, and repository search provide factual evidence</small></span><em>Facts</em></div>';
    const gate = '<i class="flow-line"></i><div class="agent-step"><b>03</b><span><strong>Gate</strong><small>Format, evidence, confidence, and release gates</small></span><em class="done">Gate</em></div>';
    const llmStep = `<i class="flow-line"></i><div class="agent-step is-active" id="llm-agent-step"><b>02</b><span><strong>4-role LLM Agents</strong><small id="llm-agent-detail">${escapeHtml(detail)}</small></span><em id="llm-agent-state">${escapeHtml(state)}</em></div>`;
    chain.innerHTML = scanner + llmStep + gate;
  }

  const step = $("#llm-agent-step");
  if (step) {
    step.classList.remove("is-pending");
    step.classList.toggle("is-active", enabled);
    step.classList.toggle("is-disabled", !enabled && !failed);
    step.classList.toggle("is-error", failed);
    const detailNode = $("#llm-agent-detail");
    const stateNode = $("#llm-agent-state");
    if (detailNode) detailNode.textContent = detail;
    if (stateNode) stateNode.textContent = state;
  }

  const status = $("#llm-runtime-status");
  status.className = `runtime-status ${failed ? "is-error" : enabled ? "is-active" : "is-disabled"}`;
  status.textContent = state;
  const capability = $("#llm-capability");
  capability.classList.toggle("is-active", enabled);
  capability.classList.toggle("is-disabled", !enabled && !failed);
  capability.classList.toggle("is-error", failed);
  $("#llm-capability-detail").textContent = detail;
  $("#llm-runtime-model").textContent = runtime;
}

async function loadDashboard() {
  const request = ++dashboardRequest;
  try {
    const data = await api("/api/dashboard", { cache: "no-store" });
    if (request !== dashboardRequest) return;
    renderLlmRuntime(data.llm, data.run_mode);
    const modeSelect = $("#review-mode");
    if (modeSelect) {
      modeSelect.value = "agentic";
      modeSelect.disabled = !data.llm?.enabled;
    }
    $("#system-status").textContent = `${data.queue} · ${data.orchestrator}`;
    const stats = data.stats || {};
    const rate = Math.round(Number(stats.success_rate || 0) * 100);
    $("#stats").innerHTML = [
      statCard("Total Tasks", stats.tasks_total ?? 0, "Cumulative reviews", "", "ALL"),
      statCard("Completed", stats.tasks_success ?? 0, "Passed quality gates", "success", "OK"),
      statCard("Failed", stats.tasks_failed ?? 0, "Requires attention", "failed", "ERR"),
      statCard("Success Rate", `${rate}%`, "Overall completion rate", "rate", "RATE"),
      statCard("Open Feedback", stats.unresolved_failure_cases ?? 0, "Unresolved cases", "feedback", "OPEN"),
      statCard("Active Skills", stats.active_skill_versions ?? 0, "Active versions", "skills", "SK"),
    ].join("");
    $("#recent-tasks").innerHTML = taskRows((data.tasks || []).slice(0, 5));
    bindTasks($("#recent-tasks"));
  } catch (error) {
    if (request !== dashboardRequest) return;
    renderLlmRuntime({ error: true }, {});
    $("#system-status").textContent = "Service Disconnected";
    $("#stats").innerHTML = '<div class="empty-state"><span><b>Unable to load dashboard data</b>Check service status and retry</span></div>';
    $("#recent-tasks").innerHTML = '<div class="empty-state"><span>Failed to load tasks</span></div>';
    toast(error.message);
  }
}

async function loadTasks(quiet = false) {
  clearTimeout(listPoll);
  const root = $("#all-tasks");
  const request = ++listRequest;
  if (!quiet) root.innerHTML = '<div class="list-loading"></div><div class="list-loading"></div>';
  try {
    const data = await api(`/api/tasks?${new URLSearchParams({ ...taskFilters, page: tasksPage })}`);
    if (request !== listRequest || currentView() !== "tasks") return;
    const tasks = data.tasks || [];
    const rows = tasks.length ? taskRows(tasks) : '<p class="muted">No tasks match the current filters.</p>';
    if (root.dataset.rendered !== rows || !quiet) {
      root.innerHTML = rows;
      root.dataset.rendered = rows;
      bindTasks(root);
    }
    markActiveTask();
    $("#task-page").textContent = `Page ${data.page}`;
    $("#task-prev").disabled = tasksPage === 1;
    $("#task-next").disabled = !data.has_next;
    if (tasks.some((task) => runningStates.has(task.state))) {
      listPoll = setTimeout(() => loadTasks(true), 4500);
    }
  } catch (error) {
    if (quiet || request !== listRequest) return;
    root.innerHTML = '<div class="empty-state"><span>Failed to load tasks</span></div>';
    toast(error.message);
  }
}

function markActiveTask() {
  $$("#all-tasks [data-task]").forEach((row) => row.setAttribute("aria-current", row.dataset.task === selectedTask ? "true" : "false"));
}

function resetTask(id) {
  selectedTask = id;
  selectedTaskData = selectedFinding = activeFile = diffPage = null;
  findingLimit = 30;
  ++diffRequest;
  $("#task-progress").textContent = id ? "Loading task…" : "Select a task to view progress.";
  $("#task-title").textContent = "Task Report";
  for (const name of ["task-report", "task-pr-meta", "task-coverage", "diff-code", "fix-result"]) {
    $(`#${name}`).textContent = "";
    delete $(`#${name}`).dataset.rendered;
  }
  for (const name of ["feedback-panel", "create-fix", "confirm-review", "cancel-review", "resume-review",
    "download-review", "resume-budget", "review-workspace", "fix-result"]) $(`#${name}`).classList.add("hidden");
  markActiveTask();
}

function openTask(id) {
  if (selectedTask !== id) resetTask(id);
  if (location.hash !== taskHash()) history.pushState(null, "", taskHash());
  show(taskHash().slice(1), false);
}

async function refreshTask(id, forceContent = false) {
  clearTimeout(taskPoll);
  const request = ++taskRequest;
  try {
    const endpoint = `/v1/tasks/${encodeURIComponent(id)}`;
    const progress = await api(`${endpoint}/progress`);
    if (request !== taskRequest || selectedTask !== id || currentView() !== "tasks") return;
    const previous = selectedTaskData;
    const needsContent = forceContent || !previous?.content || previous.state !== progress.state;
    selectedTaskData = { ...previous, ...progress };
    renderTaskProgress(selectedTaskData);
    if (needsContent) {
      const content = await api(`${endpoint}/workbench`);
      if (request !== taskRequest || selectedTask !== id || currentView() !== "tasks") return;
      const task = selectedTaskData = { ...progress, ...content, coverage: progress.coverage, content };
      renderReviewWorkspace(task);
      renderTaskProgress(task);
      const feedbackReady = task.state === "SUCCESS" && task.report && task.actions.review;
      $("#feedback-panel").classList.toggle("hidden", !feedbackReady);
      if (feedbackReady && (!previous?.report || previous.report_revision !== task.report_revision)) {
        populateFeedbackSkills(task);
        populateFeedbackFindings(task.report.findings || []);
        loadTaskFeedback(id);
      }
    } else if (selectedFinding !== previous?.visibleFinding) {
      renderFindingList(true);
    }
    if (previous?.state !== progress.state) loadTasks(true);
    if (runningStates.has(progress.state) || progress.cancel_requested && progress.state === "PAUSED_BUDGET") {
      taskPoll = setTimeout(() => refreshTask(id), document.hidden ? 12000 : 2300);
    }
  } catch (error) {
    if (request !== taskRequest || selectedTask !== id) return;
    $("#task-progress").textContent = error.message;
    if (runningStates.has(selectedTaskData?.state)) taskPoll = setTimeout(() => refreshTask(id), 5000);
  }
}

$("#task-filters").addEventListener("submit", (event) => {
  event.preventDefault();
  taskFilters = Object.fromEntries([...new FormData(event.currentTarget)].map(([key, value]) => [key, value.trim()]));
  tasksPage = 1;
  loadTasks();
});
$("#task-filters").addEventListener("reset", () => { taskFilters = {}; tasksPage = 1; loadTasks(); });
$("#task-prev").addEventListener("click", () => { if (tasksPage > 1) { tasksPage--; loadTasks(); } });
$("#task-next").addEventListener("click", () => { tasksPage++; loadTasks(); });

function renderTaskProgress(task) {
  const report = task.report || task.partial_report;
  const coverage = task.coverage;
  const status = task.cancel_requested && runningStates.has(task.state) ? "Cancelling" : stateLabels[task.state] || task.state;
  const meter = task.budget;
  const progress = $("#task-progress");
  const details = [status];
  if (coverage) details.push(coverage.total ? `${coverage.completed} / ${coverage.total} batches reviewed` : coverage.complete ? "No reviewable text" : "Awaiting batch plan");
  else details.push("Legacy task (batch coverage not recorded)");
  if (meter) details.push(`${Number(meter.charged_tokens || 0).toLocaleString()} / ${Number(meter.limit).toLocaleString()} tokens`);
  if (task.confirmation) details.push(`Accepted by ${task.confirmation.actor} at ${formatTime(task.confirmation.accepted_at)}`);
  const errorHints = { invalid_action: "Model returned an unsupported action; retry this batch.", invalid_action_payload: "Model response missed required fields; retry this batch.",
    empty_model_content: "Model returned empty content; retry this batch.", invalid_model_json: "Model response was not valid JSON; retry this batch.",
    output_truncated: "Model output was truncated; retry this batch.", input_budget: "Request exceeded role input budget; check model and role limits." };
  if (task.error && task.state === "FAILED") details.push(errorHints[task.error_code] || task.error);
  if (task.state === "PAUSED_BUDGET") details.push("Add token budget to resume remaining batches");
  const phases = { created: "Preparing", scanned: "Scanned", delegated: "Delegated", "workers-completed": "Workers Done", "critic-completed": "Critic Reviewed", "revision-1-completed": "Revised", completed: "Finalized" };
  if (task.current?.id && runningStates.has(task.state)) details.push(`Batch ${task.current.id}${phases[task.current.phase] ? ` · ${phases[task.current.phase]}` : ""}`);
  if (task.stale) details.push("Stale commit report");
  const text = details.join(" · ");
  if (progress.textContent !== text) progress.textContent = text;

  $("#confirm-review").classList.toggle("hidden", !task.actions?.accept);
  $("#cancel-review").classList.toggle("hidden", !task.actions?.cancel);
  $("#resume-review").classList.toggle("hidden", !task.actions?.resume || task.state === "PAUSED_BUDGET");
  $("#resume-budget").classList.toggle("hidden", !task.actions?.resume || task.state !== "PAUSED_BUDGET");
  $("#download-review").classList.toggle("hidden", !report && !task.has_report);
  $("#create-fix").classList.toggle("hidden", !task.actions?.fix || !!task.fix_result);
  $("#task-title").textContent = `${task.repository}${task.pull_request ? ` #${task.pull_request}` : ""}`;
  if (task.fix_result) renderFix(task.fix_result);
  if (task.content) renderTaskLinks(task);

  const fullCoverage = task.content?.coverage;
  const batches = fullCoverage?.batches || [];
  const batchLabels = { completed: "Reviewed", running: "Reviewing", failed: "Failed", paused: "Paused", pending: "Pending", cancelled: "Cancelled" };
  renderStable($("#task-coverage"), `
    ${task.versions?.model ? `<p class="muted">${escapeHtml(task.versions.model)} · Prompt ${escapeHtml(task.versions.prompt_version ?? "Built-in")}${Object.keys(task.versions.skill_versions || {}).length ? ` · ${Object.keys(task.versions.skill_versions).length} Skills pinned` : ""}</p>` : ""}
    ${batches.length ? `<details><summary>Coverage & Pending Scope</summary><ol class="workbench-list">${batches.map((batch) => `
      <li><details><summary>Batch ${escapeHtml(batch.id)} · ${batchLabels[batch.status] || escapeHtml(batch.status)} · ${escapeHtml(batch.files.join(", "))}</summary>
      <ul>${batch.ranges.map((range) => `<li>${escapeHtml(range.path)} · ${range.side === "old" ? "Old" : "New"} lines ${range.start}${range.end === range.start ? "" : `–${range.end}`}${range.offset ? ` · offset ${range.offset}` : ""}</li>`).join("")}</ul></details></li>`).join("")}</ol></details>` : ""}
    ${fullCoverage?.metadata?.length ? `<details><summary>File Metadata & Non-Text Changes</summary><ul>${fullCoverage.metadata.map((item) => `<li>${escapeHtml(item.detail || `${item.path} (${item.kind})`)}</li>`).join("")}</ul></details>` : ""}
    ${(task.trace || []).length ? `<details><summary>Execution Timeline</summary><ol class="workbench-list">${task.trace.map((event) => `<li>${escapeHtml(formatTime(event.created_at))} · ${escapeHtml(event.message)}</li>`).join("")}</ol></details>` : ""}
    ${runningStates.has(task.state) && coverage?.completed > (fullCoverage?.completed || 0) ? '<button class="button secondary" type="button" data-load-partial>Load Latest Partial Results</button>' : ""}`);
  const partial = $("[data-load-partial]");
  if (partial) partial.onclick = () => refreshTask(task.id, true);
}

function renderStable(element, html) {
  if (element.dataset.rendered === html) return;
  const open = [...element.querySelectorAll("details")].map((item) => item.open);
  element.innerHTML = html;
  element.dataset.rendered = html;
  element.querySelectorAll("details").forEach((item, index) => { item.open = !!open[index]; });
}

const findingStates = { pending: "Pending", accepted: "Accepted", false_positive: "False Positive", fixed: "Fixed" };
const severityLabels = { critical: "Critical", high: "High", medium: "Medium", low: "Low" };

function githubLink(value, label) {
  try {
    const url = new URL(value);
    if (url.origin === "https://github.com" && !url.username && !url.password) {
      return `<a href="${escapeHtml(url.href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
    }
  } catch { /* A missing provider URL is valid for manually supplied diffs. */ }
  return "";
}

function renderFix(result) {
  const target = $("#fix-result");
  target.classList.remove("hidden");
  const branch = result.branch || result.fix_branch;
  const url = result.draft_pr_url || result.pull_request?.html_url || result.draft_pull_request?.url;
  renderStable(target, `<p><strong>Fix Result</strong>${branch ? ` · ${escapeHtml(branch)}` : ""} ${githubLink(url, "View Draft PR")}</p>
    ${result.error ? `<p>${escapeHtml(result.error)}</p>` : ""}<details><summary>Verification & Repair Details</summary><pre>${escapeHtml(formatJson(result))}</pre></details>`);
}

function renderReviewWorkspace(task) {
  const files = task.files || [];
  $("#review-workspace").classList.remove("hidden");
  $("#diff-file-count").textContent = files.length;
  const group = new Map();
  for (const file of files) {
    const slash = file.path.lastIndexOf("/");
    const folder = slash < 0 ? "" : file.path.slice(0, slash);
    if (!group.has(folder)) group.set(folder, []);
    group.get(folder).push({ ...file, label: file.path.slice(slash + 1) });
  }
  function buttons(entries) {
    return entries.map((file) => `<button type="button" class="code-file" data-file="${escapeHtml(file.id)}" title="${escapeHtml(file.path)}">
      <span>${escapeHtml(file.label)}</span><small>${file.kind ? "Metadata" : `<span class="stat-add">+${file.added}</span><span class="stat-del">−${file.removed}</span>`}</small></button>`).join("");
  }
  $("#diff-files").innerHTML = files.length ? [...group].map(([folder, entries]) => folder
    ? `<details open><summary title="${escapeHtml(folder)}">${escapeHtml(folder)}</summary>${buttons(entries)}</details>` : buttons(entries)).join("")
    : '<p class="muted">No displayable files yet.</p>';
  $$("[data-file]", $("#diff-files")).forEach((button) => button.addEventListener("click", () => {
    selectedFinding = null;
    history.replaceState(null, "", taskHash());
    renderFindingList(false);
    openDiff(button.dataset.file);
  }));
  renderTaskLinks(task);
  if (selectedFinding) {
    renderFindingList(true);
    if (!activeFile && files.length) openDiff(files[0].id);
  } else {
    renderFindingList(false);
    if (!activeFile && files.length) openDiff(files[0].id);
  }
  if (!files.length) $("#diff-status").textContent = "Diff is not available yet.";
}

function renderTaskLinks(task) {
  let publication = "";
  if (task.publication?.state === "published") publication = `Published to GitHub${task.publication.policy === "inline" ? ` · ${task.publication.inline_posted || 0} inline comments` : ""}`;
  if (task.publication?.state === "failed") publication = "GitHub publish failed; in-app report remains available";
  if (task.stale || task.publication?.state === "stale") publication = "Report corresponds to an older commit";
  const versions = task.history || [];
  renderStable($("#task-pr-meta"), `<div class="task-links">${githubLink(task.github_url, "View GitHub PR")}
    ${task.head_sha ? `<code>${escapeHtml(task.head_sha.slice(0, 8))}</code>` : ""}${publication ? `<span>${escapeHtml(publication)}</span>` : ""}
    ${versions.length > 1 ? `<details><summary>Commit History</summary><ul>${versions.map((item) => `<li><a href="#tasks/${escapeHtml(item.id)}">${escapeHtml(item.head_sha.slice(0, 8))} · ${escapeHtml(stateLabels[item.state] || item.state)} · ${escapeHtml(formatTime(item.created_at))}</a></li>`).join("")}</ul></details>` : ""}</div>`);
}

function renderFindingList(openAnchor) {
  const task = selectedTaskData;
  if (!task?.content) return;
  const all = task.report?.findings || [];
  const severity = $("#finding-severity").value;
  const state = $("#finding-state").value;
  const filtered = all.filter((item) => (!severity || severity === item.severity) && (!state || state === item.disposition.state));
  const active = all.find((item) => item.id === selectedFinding);
  const root = $("#finding-list");
  root.innerHTML = `<p class="muted">${task.partial ? "Partial Findings" : "Review Findings"} · ${filtered.length} / ${all.length}</p>`
    + (filtered.length ? filtered.slice(0, findingLimit).map((item) => `<button type="button" class="finding-row" data-finding="${escapeHtml(item.id)}" aria-current="${active?.id === item.id}">
      <span><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.path)} · Line ${escapeHtml(item.line)}</small></span>
      <small>${escapeHtml(severityLabels[item.severity] || item.severity)} · ${escapeHtml(findingStates[item.disposition.state])}</small></button>`).join("")
      : '<p class="muted">No matching findings.</p>')
    + (filtered.length > findingLimit ? '<button class="button secondary" type="button" data-more-findings>Show More</button>' : "");
  $$("[data-finding]", root).forEach((button) => button.addEventListener("click", () => {
    selectedFinding = button.dataset.finding;
    if (location.hash !== taskHash()) history.pushState(null, "", taskHash());
    renderFindingList(true);
    $("[data-finding][aria-current=true]", root)?.focus({ preventScroll: true });
  }));
  if ($("[data-more-findings]", root)) $("[data-more-findings]", root).onclick = () => { findingLimit += 30; renderFindingList(false); };
  task.visibleFinding = selectedFinding;
  renderFindingDetail(task, active);
  if (openAnchor && active?.file_id) openDiff(active.file_id, 0, active.line_side || "new", active.line, true);
}

function renderFindingDetail(task, finding) {
  const target = $("#task-report");
  if (!finding) {
    target.innerHTML = task.report?.summary ? `<p class="muted">${escapeHtml(task.report.summary)}</p>` : "";
    return;
  }
  target.innerHTML = `<section class="finding-detail"><h4>${escapeHtml(finding.title)}</h4>
    <p class="muted">${escapeHtml(finding.path)} · ${finding.line_side === "old" ? "Old Line" : "New Line"} ${escapeHtml(finding.line)} · ${escapeHtml(finding.rule_id)}</p>
    <p>${escapeHtml(finding.explanation)}</p><pre>${escapeHtml(finding.evidence)}</pre>
    ${!finding.file_id ? '<p class="muted">This finding does not have an anchorable diff line.</p>' : ""}
    ${finding.fix ? `<p><strong>Recommended Fix</strong> — ${escapeHtml(finding.fix)}</p>` : ""}
    ${finding.test ? `<p><strong>Verification</strong> — ${escapeHtml(finding.test)}</p>` : ""}
    ${(finding.evidence_refs || []).length ? `<details><summary>Evidence Sources</summary><pre>${escapeHtml(formatJson(finding.evidence_refs))}</pre></details>` : ""}
    ${finding.disposition.actor ? `<p class="muted">${escapeHtml(findingStates[finding.disposition.state])} · ${escapeHtml(finding.disposition.actor)} · ${escapeHtml(formatTime(finding.disposition.updated_at))} ${escapeHtml(finding.disposition.note)}</p>` : ""}
    ${task.actions.review && task.has_report ? `<form id="finding-disposition" class="workbench-actions">
      <label>Disposition<select name="state">${Object.entries(findingStates).map(([key, label]) => `<option value="${key}" ${key === finding.disposition.state ? "selected" : ""}>${label}</option>`).join("")}</select></label>
      <label>Note<input name="note" maxlength="2000" value="${escapeHtml(finding.disposition.note || "")}"></label><button class="button secondary" type="submit">Save Status</button></form>` : ""}</section>`;
  $("#finding-disposition")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    setButtonBusy(button, true, "Saving…");
    try {
      await postJson(`/v1/tasks/${task.id}/findings/${finding.id}`, Object.fromEntries(new FormData(event.currentTarget)));
      if (selectedTask === task.id) await refreshTask(task.id, true);
    } catch (error) { toast(error.message); }
    finally { setButtonBusy(button, false); }
  });
}

async function openDiff(file, offset = 0, side = "new", line = 0, jump = false) {
  if (!selectedTask) return;
  const id = selectedTask;
  const request = ++diffRequest;
  activeFile = file;
  $$("[data-file]", $("#diff-files")).forEach((button) => button.setAttribute("aria-current", button.dataset.file === file ? "true" : "false"));
  $("#diff-prev").disabled = $("#diff-next").disabled = true;
  $("#diff-status").textContent = "Loading code…";
  try {
    const data = await api(`/v1/tasks/${id}/diff?${new URLSearchParams({ file, offset, side, line })}`);
    if (request !== diffRequest || selectedTask !== id || currentView() !== "tasks") return;
    diffPage = data;
    $("#diff-title").textContent = data.path;
    $("#diff-status").textContent = data.rows.length ? `Lines ${data.offset + 1}–${data.offset + data.rows.length} / ${data.total}` : "This file contains only metadata or non-text changes.";
    const code = $("#diff-code");
    code.innerHTML = data.rows.length ? `<div class="diff-columns"><span>Old</span><span>New</span><span>Code</span></div>${data.rows.map((row) => `<div class="diff-line ${row.kind === "+" ? "diff-added" : row.kind === "-" ? "diff-removed" : ""} ${row.id === data.anchor_id ? "diff-anchor" : ""}">
      <span>${row.old ?? ""}</span><span>${row.new ?? ""}</span><code>${escapeHtml(row.kind)}${escapeHtml(row.text)}${row.truncated ? " … (truncated)" : ""}</code></div>`).join("")}` : "";
    $("#diff-prev").disabled = data.offset === 0;
    $("#diff-next").disabled = data.next_offset === null;
    code.scrollTop = 0;
    const anchor = $(".diff-anchor", code);
    if (anchor) code.scrollTop = Math.max(0, anchor.offsetTop - code.offsetTop - 90);
    if (jump && matchMedia("(max-width: 760px)").matches) $(".diff-pane").scrollIntoView({ block: "nearest" });
  } catch (error) {
    if (request !== diffRequest) return;
    $("#diff-code").textContent = "";
    $("#diff-status").textContent = error.message;
  }
}

$("#finding-severity").onchange = $("#finding-state").onchange = () => { findingLimit = 30; renderFindingList(false); };
$("#diff-prev").onclick = () => { if (activeFile && diffPage) openDiff(activeFile, Math.max(0, diffPage.offset - 100)); };
$("#diff-next").onclick = () => { if (activeFile && diffPage?.next_offset != null) openDiff(activeFile, diffPage.next_offset); };

async function performTaskAction(button, action, data = {}) {
  if (!selectedTask) return;
  const id = selectedTask;
  setButtonBusy(button, true, "Submitting…");
  try {
    await postJson(`/v1/tasks/${encodeURIComponent(id)}/${action}`, data);
    if (selectedTask === id) await refreshTask(id);
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonBusy(button, false);
  }
}

$("#confirm-review").addEventListener("click", (event) => {
  performTaskAction(event.currentTarget, "accept", { report_revision: selectedTaskData?.report_revision });
});
$("#cancel-review").addEventListener("click", (event) => performTaskAction(event.currentTarget, "cancel"));
$("#resume-review").addEventListener("click", (event) => performTaskAction(event.currentTarget, "resume"));
$("#resume-budget").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  performTaskAction($("button", form), "resume", { additional_tokens: Number(new FormData(form).get("additional_tokens")) });
});
$("#download-review").addEventListener("click", async () => {
  const id = selectedTask;
  try {
    const markdown = await api(`/v1/tasks/${encodeURIComponent(id)}/report`);
    const href = URL.createObjectURL(new Blob([markdown], { type: "text/markdown" }));
    const link = Object.assign(document.createElement("a"), { href, download: `evoagent-${id}.md` });
    link.click();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  } catch (error) { toast(error.message); }
});

const feedbackLabels = {
  false_positive: "False Positive",
  missed_issue: "Missed Issue",
  bad_fix: "Bad Fix",
  accepted: "Accepted",
};

function populateFeedbackSkills(task) {
  const assigned = task.report?.collaboration?.agent_skills || [];
  const requested = task.input?.enabled_skills || [];
  const taskSkills = [...new Set([...assigned, ...requested]
    .map((name) => String(name || "").trim().toLowerCase())
    .filter(Boolean))];
  const names = [...taskSkills, ...(!taskSkills.includes("llm-review") ? ["llm-review"] : [])];
  $("#feedback-skill").innerHTML = names.map((name) => {
    const suffix = name === "llm-review" ? " (General Review)" : "";
    return `<option value="${escapeHtml(name)}">${escapeHtml(name + suffix)}</option>`;
  }).join("");
}

function populateFeedbackFindings(findings) {
  const select = $("#feedback-finding");
  select.innerHTML = '<option value="">Not linked to an existing finding</option>' + findings.map((finding, index) => {
    const identity = `${finding.rule_id || "Unnamed Rule"} · ${finding.path || "Unknown File"}:${finding.line || "?"}`;
    return `<option value="${index}">${escapeHtml(identity)}</option>`;
  }).join("");
  $("#feedback-result").textContent = "";
}

function renderTaskFeedback(cases) {
  const root = $("#task-feedback-history");
  if (!cases.length) {
    root.innerHTML = '<p class="feedback-empty">No feedback yet. Submitted feedback will appear here and enter future evaluation runs.</p>';
    return;
  }
  root.innerHTML = `<p class="list-section-label">Task Feedback</p>${cases.map((item) => {
    const payload = item.payload || {};
    const finding = payload.finding || {};
    const reference = finding.rule_id
      ? `${finding.rule_id}${finding.path ? ` · ${finding.path}:${finding.line || "?"}` : ""}`
      : "Unlinked feedback";
    return `<div class="feedback-case">
      <span class="feedback-case-type">${escapeHtml(feedbackLabels[item.category] || item.category)}</span>
      <span class="feedback-case-copy"><b>${escapeHtml(reference)}</b><small>${escapeHtml(`Skill: ${item.skill_name || "llm-review"} · ${payload.note || "No notes"}`)}</small></span>
      <span class="status ${item.resolved ? "state-success" : "state-pending"}">${item.resolved ? "Resolved" : "Pending Eval"}</span>
    </div>`;
  }).join("")}`;
}

async function loadTaskFeedback(taskId) {
  const root = $("#task-feedback-history");
  root.innerHTML = '<p class="feedback-empty">Loading feedback history…</p>';
  try {
    const data = await api(`/v1/tasks/${encodeURIComponent(taskId)}/feedback`);
    if (selectedTask === taskId) renderTaskFeedback(data.cases || []);
  } catch (error) {
    root.innerHTML = `<p class="feedback-empty">Unable to load feedback history: ${escapeHtml(error.message)}</p>`;
  }
}

async function loadSkills() {
  const root = $("#skill-list");
  root.innerHTML = '<div class="skill-card loading"></div><div class="skill-card loading"></div>';
  try {
    const data = await api("/api/skills");
    renderLlmRuntime(data.llm);
    const skills = (data.skills || []).filter((skill) => skill.name !== "llm-review");
    root.innerHTML = skills.length ? skills.map((skill) => `
      <article class="skill-card">
        <span class="skill-label">${skill.sandboxed ? "SANDBOXED SKILL" : "ACTIVE SKILL"}</span>
        <h3>${escapeHtml(skill.name)}</h3>
        <p>${escapeHtml(skill.description || "No description provided")}</p>
        <span class="skill-meta">v${escapeHtml(skill.version)} · ${escapeHtml(skill.source)}</span>
      </article>`).join("") : '<div class="empty-state"><span><b>No Skills loaded</b>Reload directory to discover skills</span></div>';
  } catch (error) {
    renderLlmRuntime({ error: true });
    root.innerHTML = '<div class="empty-state"><span>Failed to load Skills</span></div>';
    toast(error.message);
  }
}

let versionRequest = 0;
let evaluationPoll = null;
const versionLabels = { ready: "Ready to Publish", shadow_ready: "Ready to Publish", activated: "Passed", rejected: "Rejected", deferred: "Deferred" };
const gateLabels = { evaluation_success: "Replay Execution", validation_improvement: "Validation Improvement", validation_non_regression: "Validation Non-Regression",
  holdout_non_regression: "Holdout Non-Regression", validation_dataset_ready: "Validation Set Ready", holdout_dataset_ready: "Holdout Set Ready",
  model_configured: "Model Configured", artifact_valid: "Artifact Valid", runtime_is_agent_skill: "Agent Skill Runtime" };
const versionProfile = () => ({ kind: $("#version-kind").value, name: $("#version-name").value.trim() });
const versionUrl = ({ kind, name }) => `/v1/versions/${kind}/${encodeURIComponent(name)}`;

async function loadFailures(selectVersion = null) {
  const profile = versionProfile();
  const request = ++versionRequest;
  const history = $("#version-history");
  $("#version-detail").classList.add("hidden");
  history.textContent = "Loading versions…";
  if (!/^[a-z0-9_-]+$/.test(profile.name)) {
    history.textContent = "Enter a valid name (lowercase letters, digits, underscores, or hyphens).";
    return;
  }
  const [catalogResult] = await Promise.allSettled([api(`${versionUrl(profile)}?summary=1`)]);
  const live = versionProfile();
  if (request !== versionRequest || live.kind !== profile.kind || live.name !== profile.name) return;
  const submit = $('#evolution-form button[type="submit"]');
  submit.disabled = $("#auto-evolve").disabled = catalogResult.status !== "fulfilled";
  if (catalogResult.status !== "fulfilled") {
    history.textContent = catalogResult.reason.message;
    $("#evolution-status").textContent = "";
    return;
  }
  const catalog = catalogResult.value;
  const { versions, status, deployment } = catalog;
  const active = versions.find((item) => item.active);
  const context = [active ? `Active v${active.version}` : "Using built-in version",
    status.ready ? "Ready for evaluation" : "Evaluation prerequisites unmet",
    `Validation ${status.validation_cases} · Holdout ${status.holdout_cases}`];
  if (deployment?.status === "running") context.push(`v${deployment.candidate_version} Canary ${deployment.canary_percent}% · ${deployment.samples} runs · ${deployment.errors} errors${deployment.samples ? ` (${(100 * deployment.errors / deployment.samples).toFixed(1)}%)` : ""}`);
  if (deployment?.status === "rolled_back") context.push(`v${deployment.candidate_version} Canary rolled back`);
  $("#evolution-status").textContent = context.join(" · ");
  history.innerHTML = versions.length ? versions.map((version) => `<button class="task-row" type="button" data-version="${Number(version.version)}">
    <span class="task-name">v${Number(version.version)}</span>
    <span class="task-meta">${escapeHtml(formatTime(version.created_at))}</span>
    <span class="status ${version.active ? "state-success" : "status-neutral"}">${escapeHtml(releaseLabels[version.release_state] || versionLabels[version.evaluation?.decision] || "Historical")}</span>
  </button>`).join("") : '<p class="muted">No candidate versions yet.</p>';
  const openVersion = (version) => renderVersion(profile, version.version);
  $$("[data-version]", history).forEach((button) => button.addEventListener("click", () => {
    openVersion(versions.find((item) => item.version === Number(button.dataset.version)));
  }));
  const chosen = versions.find((item) => item.version === selectVersion);
  if (chosen) openVersion(chosen);

  loadEvolutionJobs(profile);
}

const releaseLabels = { active: "Active", historical: "Previously Active", canary: "Canary", stale: "Baseline Changed", ready: "Ready to Publish", rejected: "Rejected", deferred: "Deferred", unevaluated: "Unevaluated" };
let versionDetailRequest = 0;
let skillResources = null;

async function renderVersion(profile, number) {
  const target = $("#version-detail");
  const request = ++versionDetailRequest;
  const profileRequest = versionRequest;
  target.classList.remove("hidden");
  target.textContent = "Loading version details…";
  let detail;
  try { detail = await api(`${versionUrl(profile)}/${number}`); }
  catch (error) { if (request === versionDetailRequest) target.textContent = error.message; return; }
  if (request !== versionDetailRequest || profileRequest !== versionRequest || currentView() !== "evolution") return;
  const version = detail.version;
  const run = version.evaluation;
  const metrics = run?.metrics;
  const content = detail.candidate_text;
  const baseline = detail.baseline_text;
  const resources = Object.fromEntries(Object.entries(version.artifact?.files || {}).filter(([path]) => path !== "SKILL.md"));
  const rows = [["Validation", metrics?.baseline, metrics?.candidate], ["Holdout", metrics?.baseline_holdout, metrics?.candidate_holdout]];
  const score = (value) => typeof value?.score === "number" ? value.score.toFixed(3) : "—";
  const action = version.previously_released ? "Rollback to This Version" : "Activate Version";
  const reproducibility = metrics?.reproducibility || {};
  const cases = metrics?.candidate?.case_results || [];
  const failedCases = cases.filter((item) => item.error || item.fp || item.fn || item.success === false);
  target.innerHTML = `<div class="panel-head"><h3>v${Number(version.version)} · ${escapeHtml(profile.name)}</h3>
    <button class="button secondary" type="button" data-use-version>Create Candidate from This</button></div>
    <p class="muted">${escapeHtml(releaseLabels[version.release_state] || version.release_state)}</p>
    ${version.baseline_changed ? '<p role="status">Stable baseline has changed; please re-evaluate before publishing.</p><button class="button secondary" data-reevaluate type="button">Re-evaluate Against Stable</button>' : ""}
    ${metrics ? `<p>${escapeHtml(metrics.reason || "")}</p><table class="version-metrics">
    <thead><tr><th scope="col">Dataset</th><th scope="col">Baseline</th><th scope="col">Candidate</th></tr></thead>
    <tbody>${rows.map(([label, oldScore, newScore]) => `<tr><th scope="row">${label}</th><td>${score(oldScore)}</td><td>${score(newScore)}</td></tr>`).join("")}</tbody></table>
    <ul class="workbench-list">${Object.entries(metrics.gates || {}).map(([key, value]) => `<li>${escapeHtml(gateLabels[key] || key)} · ${value === true ? "Passed" : value === false ? "Failed" : "Not Run"}</li>`).join("")}</ul>
    <details><summary>Model, Datasets & Failed Cases</summary><p class="muted">Model ${escapeHtml(detail.model?.model || "Unrecorded")} · Validation ${escapeHtml(reproducibility.validation_dataset_sha256 || "Unrecorded")} · Holdout ${escapeHtml(reproducibility.holdout_dataset_sha256 || "Unrecorded")}</p>
    ${failedCases.length ? `<ul>${failedCases.slice(0, 30).map((item) => `<li>${escapeHtml(item.name || item.id)} · ${escapeHtml(item.error || `FP ${item.fp || 0} / FN ${item.fn || 0}`)}</li>`).join("")}</ul>` : '<p class="muted">No failed cases to display.</p>'}
    <details><summary>Full Evaluation Metrics</summary><pre>${escapeHtml(formatJson(metrics))}</pre></details></details>` : '<p class="muted">No evaluation record for this version.</p>'}
    <details open><summary>Candidate Text Diff</summary><pre class="version-diff">${detail.changes ? detail.changes.split("\n").map((line) => `<span class="${line.startsWith("+") ? "diff-added" : line.startsWith("-") ? "diff-removed" : ""}">${escapeHtml(line)}\n</span>`).join("") : "No text differences."}</pre></details>
    <details><summary>Baseline vs Candidate Full Text</summary><div class="version-compare"><div><h4>Baseline</h4><pre>${escapeHtml(baseline)}</pre></div>
      <div><h4>Candidate v${Number(version.version)}</h4><pre>${escapeHtml(content)}</pre></div></div></details>
    <details><summary>Source Feedback (${detail.feedback.length})</summary>${detail.feedback.length ? `<ul>${detail.feedback.map((item) => `<li><a href="#tasks/${escapeHtml(item.task_id)}">${escapeHtml(feedbackLabels[item.category] || item.category)}</a> · ${escapeHtml(item.note || "No note")}</li>`).join("")}</ul>` : '<p class="muted">No linked feedback records.</p>'}</details>
    ${version.publishable && !version.active ? `<form class="workbench-actions" data-publish>
      <label>Canary %<input name="canary" type="number" min="1" max="100" required value="10"></label>
      <button class="button secondary" type="submit">Start Canary</button>
      <button class="button" data-activate type="button">${action}</button></form>` : ""}`;
  target.classList.remove("hidden");
  $("[data-use-version]", target).addEventListener("click", () => {
    const input = $('#evolution-form textarea');
    input.value = content;
    skillResources = { profile: versionUrl(profile), files: resources };
    input.focus();
  });
  $("[data-reevaluate]", target)?.addEventListener("click", (event) => startEvaluation(event.currentTarget, false, content, resources));
  const form = $("[data-publish]", target);
  if (!form) return;
  async function publish(button, percent) {
    setButtonBusy(button, true, "Publishing…");
    try {
      await postJson(`${versionUrl(profile)}/${version.version}/publish`, { canary_percent: percent });
      toast(percent ? "Canary configured" : `Activated v${version.version}`);
      await loadFailures(version.version);
    } catch (error) { toast(error.message); }
    finally { setButtonBusy(button, false); }
  }
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    publish(event.submitter, Number(new FormData(form).get("canary")));
  });
  $("[data-activate]", form).addEventListener("click", (event) => publish(event.currentTarget, 0));
}

$("#review-source").onchange = (event) => {
  const github = event.target.value === "github";
  $("#github-review-form").classList.toggle("hidden", !github);
  $("#review-form").classList.toggle("hidden", github);
};

function resetReviewSubmission(form) {
  form.reset();
  updateDiffStats();
  const output = $("#review-result");
  output.classList.add("empty");
  output.textContent = "Review submission status will appear here";
}

$("#github-review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = event.submitter;
  const prUrl = new FormData(form).get("pr_url").trim();
  const output = $("#review-result");
  output.classList.remove("empty");
  setButtonBusy(button, true, "Fetching PR…");
  output.textContent = "Fetching GitHub commit revision…";
  try {
    const result = await postJson("/v1/reviews/github", { pr_url: prUrl });
    resetReviewSubmission(form);
    toast(result.duplicate ? "Opened existing review for this commit." : "PR review queued.");
    openTask(result.task_id);
  } catch (error) { output.textContent = error.message; }
  finally { setButtonBusy(button, false); }
});

async function configurePublication(button, save) {
  const form = $("#publication-form");
  if (!form.reportValidity()) return;
  const options = Object.fromEntries(new FormData(form));
  const status = $("#publication-result");
  setButtonBusy(button, true, "Loading…");
  try {
    const result = save ? await postJson("/v1/review-settings", options)
      : await api(`/v1/review-settings?${new URLSearchParams({ repository: options.repository })}`);
    form.elements.publication.value = result.publication;
    status.textContent = save ? "Repository publication settings saved." : "Repository publication settings loaded.";
  } catch (error) { status.textContent = error.message; }
  finally { setButtonBusy(button, false); }
}

$("#load-publication").onclick = (event) => configurePublication(event.currentTarget, false);
$("#publication-form").onsubmit = (event) => { event.preventDefault(); configurePublication(event.submitter, true); };

$("#review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = $('button[type="submit"]', form);
  const values = new FormData(form);
  const body = { repository: values.get("repository"), diff: values.get("diff"), mode: values.get("mode") };
  if (values.get("pull_request")) body.pull_request = Number(values.get("pull_request"));
  const output = $("#review-result");
  output.classList.remove("empty");
  output.textContent = "Submitting review task…";
  setButtonBusy(button, true, "Submitting…");
  try {
    const data = await api("/v1/reviews?async=true", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    resetReviewSubmission(form);
    toast("Review task submitted");
    openTask(data.task_id);
  } catch (error) {
    output.textContent = error.message;
  } finally {
    setButtonBusy(button, false);
  }
});

$("#create-fix").addEventListener("click", async () => {
  if (!selectedTask) return;
  const id = selectedTask;
  const button = $("#create-fix");
  setButtonBusy(button, true, "Creating…");
  try {
    const data = await api(`/v1/tasks/${encodeURIComponent(id)}/fix`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (selectedTask === id) { renderFix(data); refreshTask(id, true); }
    toast("Fix request finished; inspect verification results");
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonBusy(button, false);
  }
});

$("#feedback-category").addEventListener("change", (event) => {
  const missed = event.target.value === "missed_issue";
  $("#feedback-missed-fields").classList.toggle("hidden", !missed);
  $("#feedback-hint").textContent = missed
    ? "Provide rule ID and source location to guide candidate learning."
    : "Once submitted, feedback can be tracked here and in the Evolution Lab.";
});

$("#feedback-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedTask || !selectedTaskData?.report) return;
  const form = event.currentTarget;
  const button = $('button[type="submit"]', form);
  const values = new FormData(form);
  const category = String(values.get("category"));
  const selectedIndex = values.get("finding_index");
  const findings = selectedTaskData.report.findings || [];
  const finding = selectedIndex === "" ? {} : { ...(findings[Number(selectedIndex)] || {}) };
  if (category === "missed_issue") {
    const ruleId = String(values.get("rule_id") || "").trim();
    const path = String(values.get("path") || "").trim();
    const line = Number(values.get("line"));
    if (ruleId) finding.rule_id = ruleId;
    if (path) finding.path = path;
    if (Number.isInteger(line) && line > 0) finding.line = line;
  }
  const output = $("#feedback-result");
  output.textContent = "Saving feedback…";
  setButtonBusy(button, true, "Submitting…");
  try {
    const data = await api(`/v1/tasks/${encodeURIComponent(selectedTask)}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category,
        skill_name: String(values.get("skill_name") || "llm-review"),
        finding: Object.keys(finding).length ? finding : null,
        note: String(values.get("note") || "").trim(),
      }),
    });
    output.textContent = `${feedbackLabels[data.category] || data.category} attributed to ${data.skill_name}; ready for candidate evaluation.`;
    form.reset();
    $("#feedback-missed-fields").classList.add("hidden");
    $("#feedback-hint").textContent = "Once submitted, feedback can be tracked here and in the Evolution Lab.";
    await Promise.all([loadTaskFeedback(selectedTask), loadDashboard()]);
    toast("Feedback recorded");
  } catch (error) {
    output.textContent = `Submission failed: ${error.message}`;
  } finally {
    setButtonBusy(button, false);
  }
});

$("#reload-skills").addEventListener("click", async () => {
  const button = $("#reload-skills");
  setButtonBusy(button, true, "Reloading…");
  try {
    await api("/v1/skills/reload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    await loadSkills();
    toast("Skills reloaded");
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonBusy(button, false);
  }
});

let selectedJob = null;
let submittedJob = null;
let jobsRequest = 0;

async function startEvaluation(button, automatic, content = "", resources = null) {
  const { kind, name } = versionProfile();
  if (!/^[a-z0-9_-]+$/.test(name)) return toast("Enter a valid version name");
  const endpoint = kind === "prompt" ? "evolution" : "skill-evolution";
  const options = { skill_name: name };
  if (!automatic) options[kind === "prompt" ? "prompt" : "skill_md"] = content;
  if (!automatic && kind === "skill") options.supporting_files = resources ||
    (skillResources?.profile === versionUrl({ kind, name }) ? skillResources.files : {});
  setButtonBusy(button, true, "Submitting…");
  try {
    const data = await postJson(`/v1/${endpoint}/${automatic ? "auto" : "propose"}?async=true`, options);
    submittedJob = data.job_id;
    selectedJob = data.job_id;
    $("#evolution-result").textContent = "Candidate queued; track progress in Evaluation Runs.";
    loadEvolutionJobs({ kind, name });
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonBusy(button, false);
  }
}

async function loadEvolutionJobs(profile) {
  clearTimeout(evaluationPoll);
  const request = ++jobsRequest;
  const history = $("#evolution-jobs");
  try {
    const { jobs } = await api(`/v1/evolution/jobs?${new URLSearchParams(profile)}`);
    if (request !== jobsRequest || currentView() !== "evolution" || versionUrl(profile) !== versionUrl(versionProfile())) return;
    const pending = jobs.some((job) => runningStates.has(job.state));
    const justFinished = jobs.find((job) => job.id === submittedJob && !runningStates.has(job.state));
    renderStable(history, jobs.length ? jobs.map((job) => `<button class="task-row" type="button" data-job="${escapeHtml(job.id)}" aria-current="${job.id === selectedJob}">
      <span class="task-name">${job.version ? `v${Number(job.version)}` : "Candidate Eval"} · ${escapeHtml(formatTime(job.created_at))}</span>
      <span class="status">${escapeHtml(versionLabels[job.decision] || stateLabels[job.state])}</span></button>`).join("") : '<p class="muted">No evaluation runs yet.</p>');
    $$("[data-job]", history).forEach((button) => button.onclick = () => {
      selectedJob = button.dataset.job;
      $$("[data-job]", history).forEach((row) => row.setAttribute("aria-current", String(row === button)));
      showEvaluationJob(selectedJob);
    });
    if (selectedJob && jobs.some((job) => job.id === selectedJob)) showEvaluationJob(selectedJob, false);
    if (justFinished) {
      submittedJob = null;
      $("#evolution-result").textContent = justFinished.error || versionLabels[justFinished.decision] || stateLabels[justFinished.state];
      if (justFinished.version) { loadFailures(Number(justFinished.version)); return; }
    }
    if (pending) evaluationPoll = setTimeout(() => loadEvolutionJobs(profile), document.hidden ? 12000 : 3000);
  } catch (error) { if (request === jobsRequest) history.textContent = error.message; }
}

async function showEvaluationJob(id, openVersion = true) {
  const output = $("#evolution-job-detail");
  try {
    const detail = await api(`/v1/evolution/jobs/${id}`);
    if (selectedJob !== id || currentView() !== "evolution") return;
    output.textContent = [versionLabels[detail.result?.decision] || stateLabels[detail.state],
      detail.model?.model, detail.error || detail.result?.reason].filter(Boolean).join(" · ");
    if (openVersion && detail.result?.version?.version) renderVersion(versionProfile(), detail.result.version.version);
  } catch (error) { if (selectedJob === id) output.textContent = error.message; }
}

$("#version-kind").addEventListener("change", (event) => {
  const prompt = event.currentTarget.value === "prompt";
  $("#version-name").readOnly = prompt;
  $("#version-name").value = prompt ? "llm-review" : "evolved-review";
  $("#version-editor-label").textContent = prompt ? "Candidate Prompt" : "Candidate SKILL.md";
  $('#evolution-form textarea').value = "";
  skillResources = null;
  selectedJob = null;
  $("#evolution-job-detail").textContent = "";
  loadFailures();
});
$("#load-versions").addEventListener("click", () => loadFailures());
$("#version-name").addEventListener("change", () => {
  selectedJob = skillResources = null;
  $("#evolution-job-detail").textContent = "";
  loadFailures();
});
$("#evolution-form").addEventListener("submit", (event) => {
  event.preventDefault();
  startEvaluation(event.submitter, false, new FormData(event.currentTarget).get("prompt"));
});
$("#auto-evolve").addEventListener("click", (event) => startEvaluation(event.currentTarget, true));

$("#refresh").addEventListener("click", async () => {
  const view = currentView();
  if (view === "overview") await loadDashboard();
  else if (view === "tasks") {
    await loadTasks();
    if (selectedTask) await refreshTask(selectedTask, true);
  }
  else if (view === "skills") await loadSkills();
  else if (view === "evolution") await loadFailures();
  else await loadDashboard();
  toast("Data refreshed");
});

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = $('button[type="submit"]', form);
  const values = new FormData(form);
  setButtonBusy(button, true, "Signing in…");
  try {
    const data = await api("/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: values.get("username"),
        password: values.get("password"),
        tenant_id: values.get("tenant_id"),
      }),
    });
    accessToken = data.access_token;
    localStorage.setItem("evoagent_token", accessToken);
    $("#login-overlay").classList.add("hidden");
    $("#logout").classList.remove("hidden");
    $("#login-error").textContent = "";
    await loadDashboard();
  } catch (error) {
    $("#login-error").textContent = error.message;
  } finally {
    setButtonBusy(button, false);
  }
});

$("#logout").addEventListener("click", () => {
  accessToken = "";
  localStorage.removeItem("evoagent_token");
  $("#login-overlay").classList.remove("hidden");
  $("#logout").classList.add("hidden");
});

const diffInput = $('textarea[name="diff"]', $("#review-form"));
const diffStats = $("#diff-stats");
function updateDiffStats() {
  const value = diffInput.value;
  const lines = value ? value.split(/\r?\n/).length : 0;
  diffStats.textContent = `${lines} lines, ${value.length} chars`;
}
diffInput.addEventListener("input", updateDiffStats);
updateDiffStats();

if (accessToken) $("#logout").classList.remove("hidden");
show(location.hash.slice(1) || "overview", false);
if (currentView() !== "overview") loadDashboard();
