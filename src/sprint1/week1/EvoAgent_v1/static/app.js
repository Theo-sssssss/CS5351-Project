const $ = (s) => document.querySelector(s);
const escapeHtml = (v) => { const e = document.createElement("div"); e.textContent = v ?? ""; return e.innerHTML; };
const stateText = { PENDING: "Queued", RUNNING: "Calling LLM", SUCCESS: "Completed", FAILED: "Failed" };
let timer;

function toast(text) { const node = $("#toast"); node.textContent = text; node.classList.add("show"); clearTimeout(timer); timer = setTimeout(() => node.classList.remove("show"), 2600); }
async function api(path, options) { const response = await fetch(path, options); const data = await response.json(); if (!response.ok) throw new Error(data.error || "Request failed"); return data; }
function riskClass(risk) { return `risk-${String(risk || "low").toLowerCase()}`; }

function renderStatus(data) {
  const pairs = [["GitHub Token", data.github_token_configured], ["Webhook Secret", data.webhook_secret_configured], ["LLM API", data.llm_configured], ["Auto-post review", data.auto_post_review]];
  $("#status").innerHTML = `<b>Implementation: ${escapeHtml(data.review_method)}</b><div>${pairs.map(([label, ok]) => `<span class="badge ${ok ? "ok" : "missing"}">${label}: ${ok ? "Configured" : "Missing / off"}</span>`).join("")}</div>`;
  if (!$("#public-url").value) $("#public-url").value = data.public_base_url || "";
}
function taskRow(task) { return `<button class="task" data-id="${escapeHtml(task.id)}"><span><b>${escapeHtml(task.repository)}</b><small>PR #${task.pull_request} · ${escapeHtml(task.source)}</small></span><em class="${task.state.toLowerCase()}">${stateText[task.state] || task.state}</em></button>`; }
async function loadTasks() { const data = await api("/api/tasks"); const tasks = data.tasks || []; $("#tasks").innerHTML = tasks.length ? tasks.map(taskRow).join("") : '<div class="empty">No tasks yet.</div>'; document.querySelectorAll("[data-id]").forEach((node) => node.addEventListener("click", () => loadReport(node.dataset.id))); }
function finding(item) { return `<article class="finding ${riskClass(item.severity)}"><header><b>${escapeHtml(item.title)}</b><span>${escapeHtml(item.severity)}</span></header><code>${escapeHtml(item.path)}:${escapeHtml(item.line)}</code><p>${escapeHtml(item.explanation)}</p><blockquote>${escapeHtml(item.evidence)}</blockquote><p><b>Suggested fix:</b> ${escapeHtml(item.fix)}</p><p><b>Suggested test:</b> ${escapeHtml(item.test)}</p></article>`; }
async function loadReport(id) { const task = await api(`/api/tasks/${encodeURIComponent(id)}`); if (task.state === "FAILED") { $("#report").innerHTML = `<div class="error">Review failed: ${escapeHtml(task.error)}</div>`; return; } if (!task.report) { $("#report").innerHTML = `<div class="empty">Task is ${escapeHtml(stateText[task.state] || task.state)}. Please refresh shortly.</div>`; return; }
  const r = task.report; const findings = r.findings || []; $("#report").innerHTML = `<div class="report-summary"><span class="${riskClass(r.risk)}">Risk: ${escapeHtml(r.risk)}</span><span>Model: one API call</span><span>Findings: ${findings.length}</span></div><p>${escapeHtml(r.summary)}</p>${findings.length ? findings.map(finding).join("") : '<div class="empty">No actionable findings.</div>'}`; }
async function refresh() { try { renderStatus(await api("/api/health")); await loadTasks(); } catch (e) { toast(e.message); } }
$("#refresh").addEventListener("click", refresh);
$("#review-form").addEventListener("submit", async (event) => { event.preventDefault(); const result = $("#submit-result"); result.textContent = "Creating task…"; try { const data = await api("/api/reviews/from-pr", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({pull_request_url: $("#pr-url").value})}); result.textContent = `Task created: ${data.task_id}`; await loadTasks(); } catch (e) { result.textContent = e.message; } });
$("#connect-form").addEventListener("submit", async (event) => { event.preventDefault(); const result = $("#connect-result"); result.textContent = "Creating GitHub webhook…"; try { const data = await api("/api/github/connect", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({repository: $("#connect-repo").value, public_base_url: $("#public-url").value})}); result.textContent = `Webhook #${data.webhook_id} created: ${data.url}`; } catch (e) { result.textContent = e.message; } });
refresh(); setInterval(loadTasks, 4000);
