const PAGE_LIMIT = 300;
let listOffset = 0;
let listTotal = 0;
let sessionsTimer = null;

function buildListQuery(offset) {
  const params = new URLSearchParams();
  params.set("limit", String(PAGE_LIMIT));
  params.set("offset", String(offset));
  const exp = document.getElementById("filter-exp").value;
  if (exp) params.set("exp_id", exp);
  if (document.getElementById("filter-visualizable").checked) {
    params.set("visualizable_only", "true");
  }
  if (document.getElementById("filter-archive").checked) {
    params.set("archive", "true");
  }
  const filename = document.getElementById("filter-filename").value;
  if (filename) params.set("filename", filename);
  return params.toString();
}

function renderSessions(sessions) {
  const tbody = document.querySelector("#sessions tbody");
  tbody.innerHTML = "";
  if (!sessions.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="4" class="muted">（なし）</td>`;
    tbody.appendChild(tr);
    return;
  }
  for (const s of sessions) {
    const parts = (s.checkpoint_rel || "").split("/");
    let runDir = "";
    let filename = "";
    if (s.archive && parts.length >= 4) {
      runDir = parts[2];
      filename = parts[3];
    } else if (!s.archive && parts.length >= 3) {
      runDir = parts[1];
      filename = parts[2];
    }
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${s.pid}</td>
      <td>${s.exp_id}${s.archive ? ' <span class="muted">(archive)</span>' : ""}</td>
      <td><code>${runDir}/${filename}</code></td>
      <td>${formatJst(s.started_at_utc)}</td>
    `;
    tbody.appendChild(tr);
  }
}

function appendCheckpointRows(checkpoints, replace) {
  const tbody = document.querySelector("#checkpoints tbody");
  if (replace) tbody.innerHTML = "";

  for (const c of checkpoints) {
    const tr = document.createElement("tr");
    const canViz = c.visualizable === true;
    tr.innerHTML = `
      <td>${c.exp_id}</td>
      <td>${c.run_dir}</td>
      <td><code>${c.filename}</code></td>
      <td>${formatJst(c.mtime_utc)}</td>
      <td>${formatBytes(c.size_bytes)}</td>
      <td>${c.archive ? "yes" : ""}</td>
      <td></td>
    `;
    const actionCell = tr.lastElementChild;
    if (canViz) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "可視化";
      btn.addEventListener("click", () => launchVisualize(c.checkpoint_rel, btn));
      actionCell.appendChild(btn);
    } else {
      actionCell.textContent = c.experiment_found ? "—" : "exp なし";
      actionCell.className = "muted";
    }
    tbody.appendChild(tr);
  }
}

async function launchVisualize(checkpointRel, btn) {
  const prev = btn.textContent;
  btn.disabled = true;
  btn.textContent = "起動中…";
  try {
    await api("/api/visualize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ checkpoint_rel: checkpointRel }),
    });
    clearUiError();
    await refreshSessions();
  } catch (err) {
    showUiError(String(err));
  } finally {
    btn.disabled = false;
    btn.textContent = prev;
  }
}

function updateExpFilter(expIds, selected) {
  const sel = document.getElementById("filter-exp");
  const current = selected ?? sel.value;
  sel.innerHTML = '<option value="">（すべて）</option>';
  for (const id of expIds) {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = id;
    sel.appendChild(opt);
  }
  sel.value = current;
}

function updateCount(total, shown) {
  const el = document.getElementById("checkpoint-count");
  el.textContent = `表示 ${shown} / 全 ${total} 件`;
}

function updateLoadMore() {
  const btn = document.getElementById("load-more");
  const shown = listOffset + PAGE_LIMIT;
  if (shown < listTotal) {
    btn.classList.remove("hidden");
  } else {
    btn.classList.add("hidden");
  }
}

async function loadCheckpoints({ append }) {
  const offset = append ? listOffset : 0;
  const q = buildListQuery(offset);
  const data = await api(`/api/checkpoints?${q}`);
  listTotal = data.total ?? 0;
  listOffset = offset + (data.checkpoints?.length ?? 0);
  updateExpFilter(data.exp_ids || []);
  appendCheckpointRows(data.checkpoints || [], !append);
  updateCount(listTotal, listOffset);
  updateLoadMore();
}

async function refreshSessions() {
  try {
    const data = await api("/api/visualize/sessions");
    renderSessions(data.sessions || []);
  } catch {
    renderSessions([]);
  }
}

function scheduleSessionsPoll() {
  if (sessionsTimer != null) clearInterval(sessionsTimer);
  sessionsTimer = setInterval(refreshSessions, 5000);
}

async function refreshAll() {
  try {
    clearUiError();
    listOffset = 0;
    await loadCheckpoints({ append: false });
    await refreshSessions();
  } catch (err) {
    showUiError(String(err));
  }
}

document.getElementById("refresh").addEventListener("click", refreshAll);
document.getElementById("filter-exp").addEventListener("change", () => refreshAll());
document.getElementById("filter-visualizable").addEventListener("change", () => refreshAll());
document.getElementById("filter-archive").addEventListener("change", () => refreshAll());
document.getElementById("filter-filename").addEventListener("change", () => refreshAll());
document.getElementById("load-more").addEventListener("click", async () => {
  try {
    await loadCheckpoints({ append: true });
    clearUiError();
  } catch (err) {
    showUiError(String(err));
  }
});

refreshAll();
scheduleSessionsPoll();
