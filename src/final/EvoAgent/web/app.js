// 控制台交互入口：使用原生 DOM 与 fetch，按 hash 切换视图并调用后端 API。
// $ 返回首个匹配元素，$$ 将匹配集合转为数组，便于后续遍历。
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

// 视图键同时对应导航 data-view、URL hash 和页面区块 id。
const titles = {
  overview: "运行总览",
  review: "发起审查",
  tasks: "任务中心",
  skills: "Skill 注册中心",
  evolution: "演进实验室",
};

// 后端状态枚举到中文标签的映射；状态样式由 app.css 中 state-* 类提供。
const stateLabels = {
  PENDING: "等待中",
  PLANNING: "规划中",
  EXECUTING: "执行中",
  REVIEWING: "汇总中",
  PAUSED_BUDGET: "预算暂停",
  SUCCESS: "已完成",
  FAILED: "失败",
  CANCELLED: "已取消",
};

// 保存当前任务标识与完整报告，反馈表单按此关联原有问题。
let selectedTask = null;
let selectedTaskData = null;
let taskPoll = null;
let listPoll = null;
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
// 刷新页面后恢复浏览器保存的令牌，实际有效性仍由后端校验。
let accessToken = localStorage.getItem("evoagent_token") || "";
let toastTimer = null;
// 尊重系统减少动态效果偏好，页面切换时决定是否平滑滚动。
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// 通过 textContent 转义动态文本，再用于 HTML 模板，避免把仓库名和模型内容解析为标签。
function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = value ?? "";
  return node.innerHTML.replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

// 按中文月日时分展示时间；无法解析时保留原始值，缺失时显示占位。
function formatTime(value) {
  if (!value) return "时间未知";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : new Intl.DateTimeFormat("zh-CN", {
        month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
      }).format(date);
}

// 将接口对象缩进为可读 JSON，由文本节点展示。
function formatJson(value) {
  return JSON.stringify(value, null, 2);
}

// 统一附带 Bearer 令牌并解析响应；401 时显示登录层，其他失败转换为可读错误。
async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const response = await fetch(path, { ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("json") ? await response.json() : await response.text();

  // 认证失败时保留当前页面，显示登录层让用户重新登录。
  if (response.status === 401) {
    $("#login-overlay").classList.remove("hidden");
    $("#logout").classList.add("hidden");
  }
  if (!response.ok) {
    const plainText = typeof data === "string" && !/<[a-z][\s\S]*>/i.test(data) ? data.trim() : "";
    const message = typeof data === "object"
      ? data.error || data.detail
      : plainText || `请求失败 (${response.status})`;
    throw new Error(message || response.statusText || "请求失败");
  }
  return data;
}

// 显示短时操作反馈，连续调用时清除旧计时器以免提示提前消失。
function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 2600);
}

// 请求期间禁用按钮并保存原标签，完成后恢复文字和可用状态。
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

// 切换视图、导航状态和 URL hash，并按当前页面加载相应数据。
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
  if (view === "skills") loadSkills();
  if (view === "evolution") loadFailures();
  else clearTimeout(evaluationPoll);
  window.scrollTo({ top: 0, behavior: reduceMotion.matches ? "auto" : "smooth" });
}

// 导航与页内跳转共用同一视图函数，hashchange 支持浏览器地址变化。
$$(".nav-item").forEach((button) => button.addEventListener("click", () => show(button.dataset.view)));
$$("[data-jump]").forEach((button) => button.addEventListener("click", () => show(button.dataset.jump)));
window.addEventListener("hashchange", () => show(location.hash.slice(1), false));

// 将任务列表渲染为可点击行，处理空列表并转义动态字段。
function taskRows(tasks) {
  if (!tasks?.length) {
    return '<div class="empty-state"><span><b>还没有审查任务</b>提交一个 Diff 开始首次审查</span></div>';
  }
  return tasks.map((task) => {
    const state = String(task.state || "PENDING").toUpperCase();
    const repository = escapeHtml(task.repository || "未命名仓库");
    const pr = task.pull_request ? `PR #${escapeHtml(task.pull_request)}` : "手动审查";
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

// 给新渲染的任务行绑定详情入口；替换列表 HTML 后需要重新调用。
function bindTasks(root) {
  $$("[data-task]", root).forEach((row) => row.addEventListener("click", () => openTask(row.dataset.task)));
}

// 生成统计卡片模板；标签和样式由调用方的固定配置提供。
function statCard(label, value, note, style, icon) {
  return `<article class="stat ${style}">
    <div class="stat-head"><span>${label}</span><i>${icon}</i></div>
    <b>${value}</b><small>${note}</small>
  </article>`;
}

// 把模型启用、未配置或读取失败状态同步到执行链和 Skill 页面。
function renderLlmRuntime(llm = {}, runMode = {}) {
  const enabled = Boolean(llm.enabled);
  const failed = Boolean(llm.error);
  const provider = String(llm.provider || "local");
  const model = String(llm.model || "");
  const detail = failed
    ? "暂时无法读取模型配置"
    : enabled
      ? `${provider} / ${model || "默认模型"}，参与上下文审查与风险判断`
      : "未配置模型；agentic 审查暂不可用";
  const state = failed ? "读取失败" : enabled ? "已启用" : "待配置";
  const runtime = failed
    ? "运行时状态未知"
    : enabled
      ? `${provider} / ${model || "模型已配置"}`
      : "agentic / 需要模型配置";

  const chain = $("#execution-chain");
  if (chain) {
    const scanner = '<div class="agent-step"><b>01</b><span><strong>Tool / Scanner</strong><small>规则、AST 与代码搜索提供事实</small></span><em>事实</em></div>';
    const gate = '<i class="flow-line"></i><div class="agent-step"><b>03</b><span><strong>Gate</strong><small>格式、证据、置信度与发布门禁</small></span><em class="done">门禁</em></div>';
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

// 加载任务统计、最近任务和模型状态，失败时显示明确的加载错误。
async function loadDashboard() {
  try {
    const data = await api("/api/dashboard");
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
      statCard("总任务", stats.tasks_total ?? 0, "累计审查任务", "", "ALL"),
      statCard("已完成", stats.tasks_success ?? 0, "通过质量门禁", "success", "OK"),
      statCard("失败", stats.tasks_failed ?? 0, "需要进一步处理", "failed", "ERR"),
      statCard("成功率", `${rate}%`, "全部任务成功率", "rate", "RATE"),
      statCard("待处理案例", stats.unresolved_failure_cases ?? 0, "未解决反馈", "feedback", "OPEN"),
      statCard("活跃 Skills", stats.active_skill_versions ?? 0, "当前生效版本", "skills", "SK"),
    ].join("");
    $("#recent-tasks").innerHTML = taskRows((data.tasks || []).slice(0, 5));
    bindTasks($("#recent-tasks"));
  } catch (error) {
    renderLlmRuntime({ error: true }, {});
    $("#system-status").textContent = "服务连接异常";
    $("#stats").innerHTML = '<div class="empty-state"><span><b>暂时无法读取数据</b>请检查服务状态后重试</span></div>';
    $("#recent-tasks").innerHTML = '<div class="empty-state"><span>数据加载失败</span></div>';
    toast(error.message);
  }
}

// 先显示加载占位，再替换完整任务列表并绑定点击事件。
async function loadTasks(quiet = false) {
  clearTimeout(listPoll);
  const root = $("#all-tasks");
  const request = ++listRequest;
  if (!quiet) root.innerHTML = '<div class="list-loading"></div><div class="list-loading"></div>';
  try {
    const data = await api(`/api/tasks?${new URLSearchParams({ ...taskFilters, page: tasksPage })}`);
    if (request !== listRequest || currentView() !== "tasks") return;
    const tasks = data.tasks || [];
    const rows = tasks.length ? taskRows(tasks) : '<p class="muted">当前筛选条件下没有任务。</p>';
    if (root.dataset.rendered !== rows || !quiet) {
      root.innerHTML = rows;
      root.dataset.rendered = rows;
      bindTasks(root);
    }
    markActiveTask();
    $("#task-page").textContent = `第 ${data.page} 页`;
    $("#task-prev").disabled = tasksPage === 1;
    $("#task-next").disabled = !data.has_next;
    if (tasks.some((task) => runningStates.has(task.state))) {
      listPoll = setTimeout(() => loadTasks(true), 4500);
    }
  } catch (error) {
    if (quiet || request !== listRequest) return;
    root.innerHTML = '<div class="empty-state"><span>任务加载失败</span></div>';
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
  $("#task-progress").textContent = id ? "正在加载任务…" : "选择一个任务查看进度。";
  $("#task-title").textContent = "任务报告";
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
  const status = task.cancel_requested && runningStates.has(task.state) ? "正在取消" : stateLabels[task.state] || task.state;
  const meter = task.budget;
  const progress = $("#task-progress");
  const details = [status];
  if (coverage) details.push(coverage.total ? `${coverage.completed} / ${coverage.total} 批已审` : coverage.complete ? "无可审查文本" : "等待分批计划");
  else details.push("历史任务，未记录分批覆盖");
  if (meter) details.push(`${Number(meter.charged_tokens || 0).toLocaleString()} / ${Number(meter.limit).toLocaleString()} Token`);
  if (task.confirmation) details.push(`已由 ${task.confirmation.actor} 于 ${formatTime(task.confirmation.accepted_at)} 确认`);
  const errorHints = { invalid_action: "模型返回了不支持的动作，可重试本批。", invalid_action_payload: "模型返回缺少必要字段，可重试本批。",
    empty_model_content: "模型返回空内容，可重试本批。", invalid_model_json: "模型内容不是有效 JSON，可重试本批。",
    output_truncated: "模型输出被截断，可重试本批。", input_budget: "请求超出角色输入预算，需要检查模型与角色额度。" };
  if (task.error && task.state === "FAILED") details.push(errorHints[task.error_code] || task.error);
  if (task.state === "PAUSED_BUDGET") details.push("追加预算后继续审查剩余批次");
  const phases = { created: "准备中", scanned: "已扫描", delegated: "已分派", "workers-completed": "Worker 已完成", "critic-completed": "Critic 已复核", "revision-1-completed": "已返工", completed: "已汇总" };
  if (task.current?.id && runningStates.has(task.state)) details.push(`当前批次 ${task.current.id}${phases[task.current.phase] ? ` · ${phases[task.current.phase]}` : ""}`);
  if (task.stale) details.push("旧提交报告");
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
  const batchLabels = { completed: "已审", running: "审查中", failed: "失败", paused: "暂停", pending: "待审", cancelled: "已取消" };
  renderStable($("#task-coverage"), `
    ${task.versions?.model ? `<p class="muted">${escapeHtml(task.versions.model)} · Prompt ${escapeHtml(task.versions.prompt_version ?? "内置")}${Object.keys(task.versions.skill_versions || {}).length ? ` · ${Object.keys(task.versions.skill_versions).length} 个 Skill 已固定` : ""}</p>` : ""}
    ${batches.length ? `<details><summary>查看批次与未审范围</summary><ol class="workbench-list">${batches.map((batch) => `
      <li><details><summary>批次 ${escapeHtml(batch.id)} · ${batchLabels[batch.status] || escapeHtml(batch.status)} · ${escapeHtml(batch.files.join("、"))}</summary>
      <ul>${batch.ranges.map((range) => `<li>${escapeHtml(range.path)} · ${range.side === "old" ? "旧" : "新"} ${range.start}${range.end === range.start ? "" : `–${range.end}`}${range.offset ? ` · 偏移 ${range.offset}` : ""}</li>`).join("")}</ul></details></li>`).join("")}</ol></details>` : ""}
    ${fullCoverage?.metadata?.length ? `<details><summary>文件元信息及非文本变更</summary><ul>${fullCoverage.metadata.map((item) => `<li>${escapeHtml(item.detail || `${item.path} (${item.kind})`)}</li>`).join("")}</ul></details>` : ""}
    ${(task.trace || []).length ? `<details><summary>运行时间线</summary><ol class="workbench-list">${task.trace.map((event) => `<li>${escapeHtml(formatTime(event.created_at))} · ${escapeHtml(event.message)}</li>`).join("")}</ol></details>` : ""}
    ${runningStates.has(task.state) && coverage?.completed > (fullCoverage?.completed || 0) ? '<button class="button secondary" type="button" data-load-partial>载入最新部分结果</button>' : ""}`);
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

const findingStates = { pending: "待处理", accepted: "已采纳", false_positive: "误报", fixed: "已修复" };
const severityLabels = { critical: "严重", high: "高", medium: "中", low: "低" };

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
  renderStable(target, `<p><strong>修复结果</strong>${branch ? ` · ${escapeHtml(branch)}` : ""} ${githubLink(url, "查看 Draft PR")}</p>
    ${result.error ? `<p>${escapeHtml(result.error)}</p>` : ""}<details><summary>验证与修复明细</summary><pre>${escapeHtml(formatJson(result))}</pre></details>`);
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
      <span>${escapeHtml(file.label)}</span><small>${file.kind ? "元信息" : `+${file.added} −${file.removed}`}</small></button>`).join("");
  }
  $("#diff-files").innerHTML = files.length ? [...group].map(([folder, entries]) => folder
    ? `<details open><summary title="${escapeHtml(folder)}">${escapeHtml(folder)}</summary>${buttons(entries)}</details>` : buttons(entries)).join("")
    : '<p class="muted">暂时没有可显示的文件。</p>';
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
  if (!files.length) $("#diff-status").textContent = "尚未取得可显示的 Diff。";
}

function renderTaskLinks(task) {
  let publication = "";
  if (task.publication?.state === "published") publication = `已回写 GitHub${task.publication.policy === "inline" ? ` · ${task.publication.inline_posted || 0} 条行级评论` : ""}`;
  if (task.publication?.state === "failed") publication = "GitHub 回写失败，站内报告仍可查看";
  if (task.stale || task.publication?.state === "stale") publication = "报告对应旧提交";
  const versions = task.history || [];
  renderStable($("#task-pr-meta"), `<div class="task-links">${githubLink(task.github_url, "查看 GitHub PR")}
    ${task.head_sha ? `<code>${escapeHtml(task.head_sha.slice(0, 8))}</code>` : ""}${publication ? `<span>${escapeHtml(publication)}</span>` : ""}
    ${versions.length > 1 ? `<details><summary>提交记录</summary><ul>${versions.map((item) => `<li><a href="#tasks/${escapeHtml(item.id)}">${escapeHtml(item.head_sha.slice(0, 8))} · ${escapeHtml(stateLabels[item.state] || item.state)} · ${escapeHtml(formatTime(item.created_at))}</a></li>`).join("")}</ul></details>` : ""}</div>`);
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
  root.innerHTML = `<p class="muted">${task.partial ? "部分结果" : "审查发现"} · ${filtered.length} / ${all.length}</p>`
    + (filtered.length ? filtered.slice(0, findingLimit).map((item) => `<button type="button" class="finding-row" data-finding="${escapeHtml(item.id)}" aria-current="${active?.id === item.id}">
      <span><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.path)} · ${escapeHtml(item.line)}</small></span>
      <small>${escapeHtml(severityLabels[item.severity] || item.severity)} · ${escapeHtml(findingStates[item.disposition.state])}</small></button>`).join("")
      : '<p class="muted">没有符合条件的发现。</p>')
    + (filtered.length > findingLimit ? '<button class="button secondary" type="button" data-more-findings>显示更多</button>' : "");
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
    <p class="muted">${escapeHtml(finding.path)} · ${finding.line_side === "old" ? "旧行" : "新行"} ${escapeHtml(finding.line)} · ${escapeHtml(finding.rule_id)}</p>
    <p>${escapeHtml(finding.explanation)}</p><pre>${escapeHtml(finding.evidence)}</pre>
    ${!finding.file_id ? '<p class="muted">这条发现没有可定位的 Diff 行。</p>' : ""}
    ${finding.fix ? `<p><strong>修复建议</strong>　${escapeHtml(finding.fix)}</p>` : ""}
    ${finding.test ? `<p><strong>验证建议</strong>　${escapeHtml(finding.test)}</p>` : ""}
    ${(finding.evidence_refs || []).length ? `<details><summary>证据来源</summary><pre>${escapeHtml(formatJson(finding.evidence_refs))}</pre></details>` : ""}
    ${finding.disposition.actor ? `<p class="muted">${escapeHtml(findingStates[finding.disposition.state])} · ${escapeHtml(finding.disposition.actor)} · ${escapeHtml(formatTime(finding.disposition.updated_at))} ${escapeHtml(finding.disposition.note)}</p>` : ""}
    ${task.actions.review && task.has_report ? `<form id="finding-disposition" class="workbench-actions">
      <label>发现状态<select name="state">${Object.entries(findingStates).map(([key, label]) => `<option value="${key}" ${key === finding.disposition.state ? "selected" : ""}>${label}</option>`).join("")}</select></label>
      <label>备注<input name="note" maxlength="2000" value="${escapeHtml(finding.disposition.note || "")}"></label><button class="button secondary" type="submit">保存状态</button></form>` : ""}</section>`;
  $("#finding-disposition")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    setButtonBusy(button, true, "正在保存…");
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
  $("#diff-status").textContent = "正在加载代码…";
  try {
    const data = await api(`/v1/tasks/${id}/diff?${new URLSearchParams({ file, offset, side, line })}`);
    if (request !== diffRequest || selectedTask !== id || currentView() !== "tasks") return;
    diffPage = data;
    $("#diff-title").textContent = data.path;
    $("#diff-status").textContent = data.rows.length ? `变更行 ${data.offset + 1}–${data.offset + data.rows.length} / ${data.total}` : "此文件仅有元信息或非文本变更。";
    const code = $("#diff-code");
    code.innerHTML = data.rows.length ? `<div class="diff-columns"><span>旧</span><span>新</span><span>代码</span></div>${data.rows.map((row) => `<div class="diff-line ${row.kind === "+" ? "diff-added" : row.kind === "-" ? "diff-removed" : ""} ${row.id === data.anchor_id ? "diff-anchor" : ""}">
      <span>${row.old ?? ""}</span><span>${row.new ?? ""}</span><code>${escapeHtml(row.kind)}${escapeHtml(row.text)}${row.truncated ? " …（显示截断）" : ""}</code></div>`).join("")}` : "";
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
  setButtonBusy(button, true, "正在提交…");
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

// 反馈类型使用后端枚举值，显示标签集中维护以保持各页面一致。
const feedbackLabels = {
  false_positive: "误报",
  missed_issue: "漏报",
  bad_fix: "坏修复",
  accepted: "已接受",
};

// 只提供本任务实际使用过的 Agent Skill；通用 llm-review 始终可作为反馈目标。
function populateFeedbackSkills(task) {
  const assigned = task.report?.collaboration?.agent_skills || [];
  const requested = task.input?.enabled_skills || [];
  const taskSkills = [...new Set([...assigned, ...requested]
    .map((name) => String(name || "").trim().toLowerCase())
    .filter(Boolean))];
  const names = [...taskSkills, ...(!taskSkills.includes("llm-review") ? ["llm-review"] : [])];
  $("#feedback-skill").innerHTML = names.map((name) => {
    const suffix = name === "llm-review" ? "（通用审查）" : "";
    return `<option value="${escapeHtml(name)}">${escapeHtml(name + suffix)}</option>`;
  }).join("");
}

// 用报告问题的索引建立反馈选项，保留“不关联已有结论”的选择。
function populateFeedbackFindings(findings) {
  const select = $("#feedback-finding");
  select.innerHTML = '<option value="">不关联已有结论</option>' + findings.map((finding, index) => {
    const identity = `${finding.rule_id || "未命名规则"} · ${finding.path || "未知文件"}:${finding.line || "?"}`;
    return `<option value="${index}">${escapeHtml(identity)}</option>`;
  }).join("");
  $("#feedback-result").textContent = "";
}

// 展示当前任务反馈、关联问题和解决状态，动态文本统一转义。
function renderTaskFeedback(cases) {
  const root = $("#task-feedback-history");
  if (!cases.length) {
    root.innerHTML = '<p class="feedback-empty">尚无反馈。提交后，它会在这里保留并进入后续评测。</p>';
    return;
  }
  root.innerHTML = `<p class="list-section-label">本任务反馈</p>${cases.map((item) => {
    const payload = item.payload || {};
    const finding = payload.finding || {};
    const reference = finding.rule_id
      ? `${finding.rule_id}${finding.path ? ` · ${finding.path}:${finding.line || "?"}` : ""}`
      : "未关联审查结论";
    return `<div class="feedback-case">
      <span class="feedback-case-type">${escapeHtml(feedbackLabels[item.category] || item.category)}</span>
      <span class="feedback-case-copy"><b>${escapeHtml(reference)}</b><small>${escapeHtml(`归属 ${item.skill_name || "llm-review"} · ${payload.note || "未填写说明"}`)}</small></span>
      <span class="status ${item.resolved ? "state-success" : "state-pending"}">${item.resolved ? "已解决" : "待评测"}</span>
    </div>`;
  }).join("")}`;
}

// 读取任务反馈历史，响应返回后仅在仍选中该任务时更新列表。
async function loadTaskFeedback(taskId) {
  const root = $("#task-feedback-history");
  root.innerHTML = '<p class="feedback-empty">正在读取本任务反馈…</p>';
  try {
    const data = await api(`/v1/tasks/${encodeURIComponent(taskId)}/feedback`);
    // 避免较早任务的慢响应覆盖用户刚切换到的新任务反馈。
    if (selectedTask === taskId) renderTaskFeedback(data.cases || []);
  } catch (error) {
    root.innerHTML = `<p class="feedback-empty">无法读取反馈历史：${escapeHtml(error.message)}</p>`;
  }
}

// 加载注册 Skill 并同步模型状态，使用卡片展示版本、来源和描述。
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
        <p>${escapeHtml(skill.description || "暂无能力描述")}</p>
        <span class="skill-meta">v${escapeHtml(skill.version)} · ${escapeHtml(skill.source)}</span>
      </article>`).join("") : '<div class="empty-state"><span><b>尚未加载 Skill</b>扫描目录以加载可用能力</span></div>';
  } catch (error) {
    renderLlmRuntime({ error: true });
    root.innerHTML = '<div class="empty-state"><span>Skills 加载失败</span></div>';
    toast(error.message);
  }
}

let versionRequest = 0;
let evaluationPoll = null;
const versionLabels = { ready: "待发布", shadow_ready: "待发布", activated: "已通过", rejected: "未通过", deferred: "评测未完成" };
const gateLabels = { evaluation_success: "回放执行", validation_improvement: "验证集提升", validation_non_regression: "验证集非退步",
  holdout_non_regression: "保留集非退步", validation_dataset_ready: "验证集就绪", holdout_dataset_ready: "保留集就绪",
  model_configured: "模型已配置", artifact_valid: "制品有效", runtime_is_agent_skill: "Agent Skill 运行时" };
const versionProfile = () => ({ kind: $("#version-kind").value, name: $("#version-name").value.trim() });
const versionUrl = ({ kind, name }) => `/v1/versions/${kind}/${encodeURIComponent(name)}`;

async function loadFailures(selectVersion = null) {
  const profile = versionProfile();
  const request = ++versionRequest;
  const history = $("#version-history");
  $("#version-detail").classList.add("hidden");
  history.textContent = "正在加载版本…";
  if (!/^[a-z0-9_-]+$/.test(profile.name)) {
    history.textContent = "请输入有效的名称（小写字母、数字、下划线或短横线）。";
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
  const context = [active ? `生效版本 v${active.version}` : "当前使用内置版本",
    status.ready ? "可运行评测" : "评测条件未就绪",
    `验证集 ${status.validation_cases} · 保留集 ${status.holdout_cases}`];
  if (deployment?.status === "running") context.push(`v${deployment.candidate_version} 灰度 ${deployment.canary_percent}% · ${deployment.samples} 次运行 · ${deployment.errors} 次失败${deployment.samples ? ` (${(100 * deployment.errors / deployment.samples).toFixed(1)}%)` : ""}`);
  if (deployment?.status === "rolled_back") context.push(`v${deployment.candidate_version} 灰度已回滚`);
  $("#evolution-status").textContent = context.join(" · ");
  history.innerHTML = versions.length ? versions.map((version) => `<button class="task-row" type="button" data-version="${Number(version.version)}">
    <span class="task-name">v${Number(version.version)}</span>
    <span class="task-meta">${escapeHtml(formatTime(version.created_at))}</span>
    <span class="status ${version.active ? "state-success" : "status-neutral"}">${escapeHtml(releaseLabels[version.release_state] || versionLabels[version.evaluation?.decision] || "历史版本")}</span>
  </button>`).join("") : '<p class="muted">暂无候选版本。</p>';
  const openVersion = (version) => renderVersion(profile, version.version);
  $$("[data-version]", history).forEach((button) => button.addEventListener("click", () => {
    openVersion(versions.find((item) => item.version === Number(button.dataset.version)));
  }));
  const chosen = versions.find((item) => item.version === selectVersion);
  if (chosen) openVersion(chosen);

  loadEvolutionJobs(profile);
}

const releaseLabels = { active: "当前生效", historical: "历史生效版", canary: "灰度中", stale: "基线已变更", ready: "待发布", rejected: "未通过", deferred: "评测未完成", unevaluated: "待评测" };
let versionDetailRequest = 0;
let skillResources = null;

async function renderVersion(profile, number) {
  const target = $("#version-detail");
  const request = ++versionDetailRequest;
  const profileRequest = versionRequest;
  target.classList.remove("hidden");
  target.textContent = "正在加载版本详情…";
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
  const rows = [["验证集", metrics?.baseline, metrics?.candidate], ["保留集", metrics?.baseline_holdout, metrics?.candidate_holdout]];
  const score = (value) => typeof value?.score === "number" ? value.score.toFixed(3) : "—";
  const action = version.previously_released ? "回滚到此版本" : "激活此版本";
  const reproducibility = metrics?.reproducibility || {};
  const cases = metrics?.candidate?.case_results || [];
  const failedCases = cases.filter((item) => item.error || item.fp || item.fn || item.success === false);
  target.innerHTML = `<div class="panel-head"><h3>v${Number(version.version)} · ${escapeHtml(profile.name)}</h3>
    <button class="button secondary" type="button" data-use-version>用此版本创建候选</button></div>
    <p class="muted">${escapeHtml(releaseLabels[version.release_state] || version.release_state)}</p>
    ${version.baseline_changed ? '<p role="status">稳定版已变更，请重新评测后发布。</p><button class="button secondary" data-reevaluate type="button">针对当前稳定版重新评测</button>' : ""}
    ${metrics ? `<p>${escapeHtml(metrics.reason || "")}</p><table class="version-metrics">
    <thead><tr><th scope="col">数据集</th><th scope="col">基线</th><th scope="col">候选</th></tr></thead>
    <tbody>${rows.map(([label, oldScore, newScore]) => `<tr><th scope="row">${label}</th><td>${score(oldScore)}</td><td>${score(newScore)}</td></tr>`).join("")}</tbody></table>
    <ul class="workbench-list">${Object.entries(metrics.gates || {}).map(([key, value]) => `<li>${escapeHtml(gateLabels[key] || key)} · ${value === true ? "通过" : value === false ? "未通过" : "未执行"}</li>`).join("")}</ul>
    <details><summary>模型、数据集和失败样本</summary><p class="muted">模型 ${escapeHtml(detail.model?.model || "未记录")} · 验证集 ${escapeHtml(reproducibility.validation_dataset_sha256 || "未记录")} · 保留集 ${escapeHtml(reproducibility.holdout_dataset_sha256 || "未记录")}</p>
    ${failedCases.length ? `<ul>${failedCases.slice(0, 30).map((item) => `<li>${escapeHtml(item.name || item.id)} · ${escapeHtml(item.error || `误报 ${item.fp || 0} / 漏报 ${item.fn || 0}`)}</li>`).join("")}</ul>` : '<p class="muted">暂无可展示的失败样本。</p>'}
    <details><summary>完整评测指标</summary><pre>${escapeHtml(formatJson(metrics))}</pre></details></details>` : '<p class="muted">此版本没有评测记录。</p>'}
    <details open><summary>候选文字差异</summary><pre class="version-diff">${detail.changes ? detail.changes.split("\n").map((line) => `<span class="${line.startsWith("+") ? "diff-added" : line.startsWith("-") ? "diff-removed" : ""}">${escapeHtml(line)}\n</span>`).join("") : "没有文字差异。"}</pre></details>
    <details><summary>基线与候选全文</summary><div class="version-compare"><div><h4>评测基线</h4><pre>${escapeHtml(baseline)}</pre></div>
      <div><h4>候选 v${Number(version.version)}</h4><pre>${escapeHtml(content)}</pre></div></div></details>
    <details><summary>候选来源反馈（${detail.feedback.length}）</summary>${detail.feedback.length ? `<ul>${detail.feedback.map((item) => `<li><a href="#tasks/${escapeHtml(item.task_id)}">${escapeHtml(feedbackLabels[item.category] || item.category)}</a> · ${escapeHtml(item.note || "无备注")}</li>`).join("")}</ul>` : '<p class="muted">没有关联的反馈记录。</p>'}</details>
    ${version.publishable && !version.active ? `<form class="workbench-actions" data-publish>
      <label>灰度百分比<input name="canary" type="number" min="1" max="100" required value="10"></label>
      <button class="button secondary" type="submit">开始灰度</button>
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
    setButtonBusy(button, true, "正在发布…");
    try {
      await postJson(`${versionUrl(profile)}/${version.version}/publish`, { canary_percent: percent });
      toast(percent ? "灰度已配置" : `已激活 v${version.version}`);
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

// 审查提交：收集仓库与 Diff，可选异步入队；finally 中恢复按钮状态。
$("#review-source").onchange = (event) => {
  const github = event.target.value === "github";
  $("#github-review-form").classList.toggle("hidden", !github);
  $("#review-form").classList.toggle("hidden", github);
};

$("#github-review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter;
  const prUrl = new FormData(event.currentTarget).get("pr_url").trim();
  const output = $("#review-result");
  output.classList.remove("empty");
  setButtonBusy(button, true, "正在读取 PR…");
  output.textContent = "正在获取 GitHub 提交版本…";
  try {
    const result = await postJson("/v1/reviews/github", { pr_url: prUrl });
    output.textContent = result.duplicate ? "已打开同一提交的审查。" : "PR 审查已入队。";
    openTask(result.task_id);
  } catch (error) { output.textContent = error.message; }
  finally { setButtonBusy(button, false); }
});

async function configurePublication(button, save) {
  const form = $("#publication-form");
  if (!form.reportValidity()) return;
  const options = Object.fromEntries(new FormData(form));
  const status = $("#publication-result");
  setButtonBusy(button, true, "正在请求…");
  try {
    const result = save ? await postJson("/v1/review-settings", options)
      : await api(`/v1/review-settings?${new URLSearchParams({ repository: options.repository })}`);
    form.elements.publication.value = result.publication;
    status.textContent = save ? "已保存仓库回写设置。" : "已读取仓库回写设置。";
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
  output.textContent = "正在提交审查任务…";
  setButtonBusy(button, true, "正在提交…");
  try {
    const data = await api("/v1/reviews?async=true", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    output.textContent = "已入队，可在任务中心查看进度。";
    toast("审查任务已成功提交");
    openTask(data.task_id);
  } catch (error) {
    output.textContent = error.message;
  } finally {
    setButtonBusy(button, false);
  }
});

// 为当前任务请求修复；是否授权、补丁验证和 Draft PR 创建由服务端决定。
$("#create-fix").addEventListener("click", async () => {
  if (!selectedTask) return;
  const id = selectedTask;
  const button = $("#create-fix");
  setButtonBusy(button, true, "正在创建…");
  try {
    const data = await api(`/v1/tasks/${encodeURIComponent(id)}/fix`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (selectedTask === id) { renderFix(data); refreshTask(id, true); }
    toast("修复请求已完成，可查看验证结果");
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonBusy(button, false);
  }
});

// 漏报不一定对应已有结论，因此额外显示规则和源码位置字段。
$("#feedback-category").addEventListener("change", (event) => {
  const missed = event.target.value === "missed_issue";
  $("#feedback-missed-fields").classList.toggle("hidden", !missed);
  $("#feedback-hint").textContent = missed
    ? "补充规则和位置可让候选评测学习更精确的检查点。"
    : "提交后可在本任务和演进实验室查看状态。";
});

// 保存人工反馈；可引用已有问题，也可为漏报补充新位置，成功后刷新历史和总览。
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
  output.textContent = "正在保存反馈…";
  setButtonBusy(button, true, "正在提交…");
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
    output.textContent = `${feedbackLabels[data.category] || data.category}已归属 ${data.skill_name}；可等待该 Skill 的候选评测。`;
    form.reset();
    $("#feedback-missed-fields").classList.add("hidden");
    $("#feedback-hint").textContent = "提交后可在本任务和演进实验室查看状态。";
    await Promise.all([loadTaskFeedback(selectedTask), loadDashboard()]);
    toast("反馈已记录");
  } catch (error) {
    output.textContent = `提交失败：${error.message}`;
  } finally {
    setButtonBusy(button, false);
  }
});

// 触发服务端重扫 Skill 目录，完成后重新读取当前注册列表。
$("#reload-skills").addEventListener("click", async () => {
  const button = $("#reload-skills");
  setButtonBusy(button, true, "正在扫描…");
  try {
    await api("/v1/skills/reload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    await loadSkills();
    toast("Skills 已重新加载");
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
  if (!/^[a-z0-9_-]+$/.test(name)) return toast("请输入有效的版本名称");
  const endpoint = kind === "prompt" ? "evolution" : "skill-evolution";
  const options = { skill_name: name };
  if (!automatic) options[kind === "prompt" ? "prompt" : "skill_md"] = content;
  if (!automatic && kind === "skill") options.supporting_files = resources ||
    (skillResources?.profile === versionUrl({ kind, name }) ? skillResources.files : {});
  setButtonBusy(button, true, "正在提交…");
  try {
    const data = await postJson(`/v1/${endpoint}/${automatic ? "auto" : "propose"}?async=true`, options);
    submittedJob = data.job_id;
    selectedJob = data.job_id;
    $("#evolution-result").textContent = "候选已入队，可从评测运行列表查看。";
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
      <span class="task-name">${job.version ? `v${Number(job.version)}` : "候选评测"} · ${escapeHtml(formatTime(job.created_at))}</span>
      <span class="status">${escapeHtml(versionLabels[job.decision] || stateLabels[job.state])}</span></button>`).join("") : '<p class="muted">暂无评测运行。</p>');
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
  $("#version-editor-label").textContent = prompt ? "候选 Prompt" : "候选 SKILL.md";
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

// 按当前 hash 刷新对应页面数据，避免刷新按钮切换用户所在视图。
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
  toast("数据已刷新");
});

// 登录成功后保存令牌并加载总览；失败原因显示在登录表单中。
$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = $('button[type="submit"]', form);
  const values = new FormData(form);
  setButtonBusy(button, true, "正在登录…");
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

// 清除浏览器与内存中的登录令牌，并重新显示登录层。
$("#logout").addEventListener("click", () => {
  accessToken = "";
  localStorage.removeItem("evoagent_token");
  $("#login-overlay").classList.remove("hidden");
  $("#logout").classList.add("hidden");
});

const diffInput = $('textarea[name="diff"]', $("#review-form"));
const diffStats = $("#diff-stats");
// 实时统计输入行数与 JavaScript 字符串长度；服务端另按 UTF-8 字节限制请求。
function updateDiffStats() {
  const value = diffInput.value;
  const lines = value ? value.split(/\r?\n/).length : 0;
  diffStats.textContent = `${lines} 行，${value.length} 字符`;
}
diffInput.addEventListener("input", updateDiffStats);
updateDiffStats();

// 初始化页面：恢复退出按钮、选择 hash 对应视图，并读取首次总览数据。
if (accessToken) $("#logout").classList.remove("hidden");
show(location.hash.slice(1) || "overview", false);
loadDashboard();
