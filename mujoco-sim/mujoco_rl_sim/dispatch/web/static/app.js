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
      <td>${j.sweep_id}</td>
      <td>${j.run_id}</td>
      <td class="${statusClass(j.status)}">${j.status}</td>
      <td>${j.worker_id ?? "-"}</td>
      <td>${metric}</td>
      <td>${j.error_message ? j.error_message.slice(0, 80) : ""}</td>
    `;
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
    renderJobs(data.recent_jobs || []);
  } catch (err) {
    showError(String(err));
  }
}

document.getElementById("refresh").addEventListener("click", refresh);
const saved = localStorage.getItem(TOKEN_KEY);
if (saved) document.getElementById("token").value = saved;

refresh();
setInterval(refresh, 15000);
