const TOKEN_KEY = "mujoco_dispatch_token";
const POLL_IDLE_MS = 15000;
const POLL_ACTIVE_MS = 5000;
let pollTimer = null;

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

/** API/SQLite の UTC 時刻を JST 表示に変換する。 */
function formatJst(value) {
  if (value == null || value === "") return "-";
  let s = String(value).trim();
  if (!s.includes("T") && s.includes(" ")) {
    s = s.replace(" ", "T") + "Z";
  } else if (!/Z|[+-]\d{2}:\d{2}$/i.test(s)) {
    s += "Z";
  }
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return String(value);
  const formatted = new Intl.DateTimeFormat("ja-JP", {
    timeZone: "Asia/Tokyo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(d);
  return `${formatted} JST`;
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
      <td>
        <button class="danger" data-cancel="${s.sweep_id}">cancel queued</button>
        <button class="danger" data-delete="${s.sweep_id}">delete</button>
      </td>
    `;
    tbody.appendChild(tr);
  }
  tbody.querySelectorAll("[data-cancel]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-cancel");
      if (!confirm(`queued ジョブを cancel しますか?\n${id}`)) return;
      await api(`/api/sweeps/${encodeURIComponent(id)}/cancel`, { method: "POST" });
      await refresh();
    });
  });
  tbody.querySelectorAll("[data-delete]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-delete");
      if (
        !confirm(
          `sweep と全ジョブを DB から削除しますか?\n${id}\n` +
            "(実行中の Worker プロセスは自動では止まりません)"
        )
      ) {
        return;
      }
      await api(`/api/sweeps/${encodeURIComponent(id)}`, { method: "DELETE" });
      await refresh();
    });
  });
}

function renderWorkers(workers) {
  const tbody = document.querySelector("#workers tbody");
  tbody.innerHTML = "";
  for (const w of workers) {
    const tr = document.createElement("tr");
    const online = w.online === true;
    const statusLabel = online ? "online" : "offline";
    const statusClass = online ? "status-succeeded" : "status-cancelled";
    tr.innerHTML = `
      <td>${w.worker_id}</td>
      <td>${w.hostname}</td>
      <td class="${statusClass}">${statusLabel}</td>
      <td>${w.max_concurrent_jobs}</td>
      <td>${w.active_jobs ?? 0}</td>
      <td>${formatJst(w.last_heartbeat_at)}</td>
    `;
    tbody.appendChild(tr);
  }
}

function jobTotalUpdates(job) {
  if (job.total_updates != null && job.total_updates > 0) {
    return job.total_updates;
  }
  const overrides = job.overrides || {};
  if (overrides.num_updates != null && overrides.num_updates > 0) {
    return Number(overrides.num_updates);
  }
  return null;
}

function renderProgress(job) {
  const total = jobTotalUpdates(job);
  const current = job.current_update;
  const active = job.status === "running" || job.status === "leased";

  if (total == null || total < 1) {
    return active ? `<span class="progress-label">—</span>` : "-";
  }

  let cur = current != null ? Math.max(0, Math.min(current, total)) : 0;
  if (job.status === "succeeded") {
    cur = total;
  }

  const pct = Math.round((cur / total) * 1000) / 10;
  const width = Math.max(0, Math.min(100, pct));
  return `
    <div class="progress-cell">
      <span class="progress-label">${cur}/${total}</span>
      <div class="progress-bar" role="progressbar" aria-valuenow="${cur}" aria-valuemin="0" aria-valuemax="${total}">
        <span style="width: ${width}%"></span>
      </div>
    </div>
  `;
}

function sortJobsForDisplay(jobs) {
  return [...jobs].sort((a, b) => {
    const sweep = String(a.sweep_id).localeCompare(String(b.sweep_id));
    if (sweep !== 0) return sweep;
    const cfgA = a.config_id ?? 999999;
    const cfgB = b.config_id ?? 999999;
    if (cfgA !== cfgB) return cfgA - cfgB;
    const seedA = a.seed_id ?? 999999;
    const seedB = b.seed_id ?? 999999;
    if (seedA !== seedB) return seedA - seedB;
    return String(a.run_id).localeCompare(String(b.run_id));
  });
}

function formatConfigValue(value) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : String(value);
  }
  return JSON.stringify(value);
}

function formatConfigOverrides(overrides) {
  if (!overrides || typeof overrides !== "object") {
    return "{}";
  }
  const lines = Object.keys(overrides)
    .sort()
    .map((key) => `${key}: ${formatConfigValue(overrides[key])}`);
  return lines.join("\n");
}

function showConfigModal(job) {
  const modal = document.getElementById("config-modal");
  const title = document.getElementById("config-modal-title");
  const meta = document.getElementById("config-modal-meta");
  const body = document.getElementById("config-modal-body");
  const configId = job.config_id ?? "-";
  title.textContent = `Config ${configId}`;
  meta.textContent = [
    `sweep: ${job.sweep_id}`,
    job.config_hash ? `hash: ${job.config_hash}` : null,
    job.seed != null ? `training seed: ${job.seed}` : null,
  ]
    .filter(Boolean)
    .join(" | ");
  body.textContent = formatConfigOverrides(job.config_overrides || {});
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
}

function hideConfigModal() {
  const modal = document.getElementById("config-modal");
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
}

function renderJobs(jobs) {
  const tbody = document.querySelector("#jobs tbody");
  tbody.innerHTML = "";
  for (const j of sortJobsForDisplay(jobs)) {
    const tr = document.createElement("tr");
    const metric =
      j.primary_metric != null
        ? `${j.primary_metric_name || ""}: ${j.primary_metric.toFixed(4)}`
        : "-";

    const cells = [
      document.createElement("td"),
      document.createElement("td"),
      document.createElement("td"),
      document.createElement("td"),
      document.createElement("td"),
      document.createElement("td"),
      document.createElement("td"),
      document.createElement("td"),
      document.createElement("td"),
      document.createElement("td"),
    ];

    cells[0].textContent = j.sweep_id;

    if (j.config_id != null) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "config-link";
      btn.textContent = String(j.config_id);
      btn.title = "クリックでコンフィグを表示";
      btn.addEventListener("click", () => showConfigModal(j));
      cells[1].appendChild(btn);
    } else {
      cells[1].textContent = "-";
    }

    cells[2].textContent = j.seed_id != null ? String(j.seed_id) : "-";
    cells[3].textContent = j.seed != null ? String(j.seed) : "-";
    cells[4].textContent = j.run_id;
    cells[5].className = statusClass(j.status);
    cells[5].textContent = j.status;
    cells[6].innerHTML = renderProgress(j);
    cells[7].textContent = j.worker_id ?? "-";
    cells[8].textContent = metric;
    cells[9].textContent = j.error_message ? j.error_message.slice(0, 80) : "";

    for (const cell of cells) {
      tr.appendChild(cell);
    }
    tbody.appendChild(tr);
  }
}

function showError(msg) {
  let el = document.getElementById("ui-error");
  if (!el) {
    el = document.createElement("p");
    el.id = "ui-error";
    el.style.color = "#f87171";
    document.querySelector("header").after(el);
  }
  el.textContent = msg;
}

async function refresh() {
  try {
    const data = await api("/api/ui/dashboard");
    showError("");
    renderSweeps(data.sweeps || []);
    renderWorkers(data.workers || []);
    const jobs = data.recent_jobs || [];
    renderJobs(jobs);
    scheduleRefresh(jobs);
  } catch (err) {
    showError(String(err));
    scheduleRefresh([]);
  }
}

function scheduleRefresh(jobs) {
  if (pollTimer != null) {
    clearTimeout(pollTimer);
  }
  const hasActive = jobs.some((j) => j.status === "running" || j.status === "leased");
  const delay = hasActive ? POLL_ACTIVE_MS : POLL_IDLE_MS;
  pollTimer = setTimeout(refresh, delay);
}

document.getElementById("refresh").addEventListener("click", refresh);
document.getElementById("config-modal-close").addEventListener("click", hideConfigModal);
document.querySelectorAll("[data-close-config-modal]").forEach((el) => {
  el.addEventListener("click", hideConfigModal);
});
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape") hideConfigModal();
});
const saved = localStorage.getItem(TOKEN_KEY);
if (saved) document.getElementById("token").value = saved;

refresh();
