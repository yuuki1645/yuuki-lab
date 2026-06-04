const TOKEN_KEY = "mujoco_dispatch_token";

function token() {
  const el = document.getElementById("token");
  if (!el) return localStorage.getItem(TOKEN_KEY) || "";
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
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return res.json();
  }
  return res.text();
}

function parseUtcDate(value) {
  if (value == null || value === "") return null;
  let s = String(value).trim();
  if (!s.includes("T") && s.includes(" ")) {
    s = s.replace(" ", "T") + "Z";
  } else if (!/Z|[+-]\d{2}:\d{2}$/i.test(s)) {
    s += "Z";
  }
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatJst(value) {
  const d = parseUtcDate(value);
  if (d == null) return "-";
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

function formatBytes(n) {
  if (n == null || !Number.isFinite(n)) return "-";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KiB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MiB`;
}

function showUiError(msg, anchorSelector = "header") {
  let el = document.getElementById("ui-error");
  if (!el) {
    el = document.createElement("p");
    el.id = "ui-error";
    el.className = "ui-error";
    const anchor = document.querySelector(anchorSelector);
    if (anchor) anchor.after(el);
    else document.body.prepend(el);
  }
  el.textContent = msg;
}

function clearUiError() {
  const el = document.getElementById("ui-error");
  if (el) el.textContent = "";
}

function initTokenField() {
  const input = document.getElementById("token");
  if (!input) return;
  const saved = localStorage.getItem(TOKEN_KEY);
  if (saved) input.value = saved;
}

function initMainNav() {
  const nav = document.querySelector(".main-nav");
  if (!nav) return;
  const path = window.location.pathname.replace(/\/$/, "") || "/";
  nav.querySelectorAll("a").forEach((a) => {
    const href = (a.getAttribute("href") || "").replace(/\/$/, "") || "/";
    if (href === path) {
      a.classList.add("active");
      a.setAttribute("aria-current", "page");
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initTokenField();
  initMainNav();
});
