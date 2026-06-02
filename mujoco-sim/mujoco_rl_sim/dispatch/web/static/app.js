const TOKEN_KEY = "mujoco_dispatch_token";

function token() {
  const el = document.getElementById("token");
  const v = el.value.trim();
  if (v) localStorage.setItem(TOKEN_KEY, v);
  return v || localStorage.getItem(TOKEN_KEY) || "";
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const t = token();
  if (t) headers["X-Dispatch-Token"] = t;
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${path}: ${text}`);
  }
  return res.json();
}

function statusClass(s) {
  return `status-${s}`;
}

function renderSweeps(sweeps) {
  const tbody = document.querySelector("#sweeps tbody");
  tbody.innerHTML = "";
  for (const s of sweeps) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${s.sweep_id}</td>
      <td>${s.exp_id}</td>
      <td>${s.queued ?? 0}</td>
      <td>${s.running ?? 0}</td>
      <td>${s.succeeded ?? 0}</td>
      <td>${s.failed ?? 0}</td>
      <td><button class="danger" data-cancel="${s.sweep_id}">cancel queued</button></td>
    `;
    tbody.appendChild(tr);
  }
  tbody.querySelectorAll("[data-cancel]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-cancel");
      if (!confirm(`Cancel queued jobs for ${id}?`)) return;
      await api(`/api/sweeps/${id}/cancel`, { method: "POST" });
      await refresh();
    });
  });
}

function renderWorkers(workers) {
  const tbody = document.querySelector("#workers tbody");
  tbody.innerHTML = "";
  for (const w of workers) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${w.worker_id}</td>
      <td>${w.hostname}</td>
      <td>${w.max_concurrent_jobs}</td>
      <td>${w.active_jobs ?? 0}</td>
      <td>${w.last_heartbeat_at ?? "-"}</td>
    `;
    tbody.appendChild(tr);
  }
}

function renderJobs(jobs) {
  const tbody = document.querySelector("#jobs tbody");
  tbody.innerHTML = "";
  for (const j of jobs) {
    const tr = document.createElement("tr");
    const metric =
      j.primary_metric != null
        ? `${j.primary_metric_name || ""}: ${j.primary_metric.toFixed(4)}`
        : "-";
    tr.innerHTML = `
      <td>${j.run_id}</td>
      <td class="${statusClass(j.status)}">${j.status}</td>
      <td>${j.worker_id ?? "-"}</td>
      <td>${metric}</td>
      <td>${j.error_message ? j.error_message.slice(0, 80) : ""}</td>
    `;
    tbody.appendChild(tr);
  }
}

async function refresh() {
  const data = await api("/api/ui/dashboard");
  renderSweeps(data.sweeps || []);
  renderWorkers(data.workers || []);
  renderJobs(data.recent_jobs || []);
}

document.getElementById("refresh").addEventListener("click", refresh);
const saved = localStorage.getItem(TOKEN_KEY);
if (saved) document.getElementById("token").value = saved;

refresh();
setInterval(refresh, 15000);
