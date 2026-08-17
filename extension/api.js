// Thin authenticated fetch layer over desk.henneth.app /state/*.json.
// Same contract the dashboard uses: bearer token from the logged-in session.
const DESK_ORIGIN = "https://desk.henneth.app";

const apiCache = new Map();
const TTL_MS = 60 * 1000;

async function deskFetch(path) {
  const { desk_token } = await chrome.storage.local.get("desk_token");
  const cached = apiCache.get(path);
  if (cached && Date.now() - cached.at < TTL_MS) return cached.data;
  const res = await fetch(DESK_ORIGIN + path, {
    headers: desk_token ? { Authorization: "Bearer " + desk_token } : {},
    cache: "no-store",
  });
  if (res.status === 401) throw new Error("AUTH");
  if (!res.ok) throw new Error("HTTP " + res.status);
  const data = await res.json();
  apiCache.set(path, { at: Date.now(), data: data });
  return data;
}

async function askDesk(question, history) {
  const { desk_token } = await chrome.storage.local.get("desk_token");
  if (!desk_token) throw new Error("AUTH");
  const res = await fetch(DESK_ORIGIN + "/api/ask", {
    method: "POST",
    headers: {
      Authorization: "Bearer " + desk_token,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question: String(question || "").slice(0, 500),
      history: Array.isArray(history) ? history.slice(-4) : [],
    }),
    cache: "no-store",
  });
  if (res.status === 401) throw new Error("AUTH");
  let body = null;
  try { body = await res.json(); } catch (_) {}
  if (!res.ok || !body?.ok) throw new Error(body?.error || ("HTTP " + res.status));
  return body;
}

// State timestamps are PKT unless suffixed _utc; showing the raw date string
// avoids the UTC off-by-one trap entirely.
function pktLabel(dateStr) {
  return dateStr ? String(dateStr).slice(0, 10) : "unknown";
}

function fmtNum(n, dp) {
  if (dp === undefined) dp = 2;
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString("en-PK", { minimumFractionDigits: dp, maximumFractionDigits: dp });
}

function fmtPct(n, dp) {
  if (dp === undefined) dp = 2;
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  return (n > 0 ? "+" : "") + fmtNum(n, dp) + "%";
}

function fmtCr(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  if (n >= 1e9) return fmtNum(n / 1e9, 2) + " bn";
  if (n >= 1e6) return fmtNum(n / 1e6, 1) + " mn";
  return fmtNum(n, 0);
}

function esc(s) {
  return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

// ---- per-user notes sync ----
// Notes stay behind the desk origin. The server-side /api/notes route verifies
// the same session token and applies the Supabase RLS-scoped profile update.
async function fetchProfile() {
  const { desk_token } = await chrome.storage.local.get("desk_token");
  if (!desk_token) throw new Error("AUTH");
  const res = await fetch(DESK_ORIGIN + "/api/notes", {
    headers: { Authorization: "Bearer " + desk_token },
    cache: "no-store",
  });
  if (res.status === 401) throw new Error("AUTH");
  if (!res.ok) throw new Error("HTTP " + res.status);
  const body = await res.json();
  if (!body?.ok) throw new Error(body?.error || "Could not load notes");
  return { notes: body.notes || {} };
}

// Last-write-wins, identical to the dashboard saving from two tabs at once.
async function saveNotes(notesMap) {
  const { desk_token } = await chrome.storage.local.get("desk_token");
  if (!desk_token) throw new Error("AUTH");
  const res = await fetch(DESK_ORIGIN + "/api/notes", {
    method: "PUT",
    headers: {
      Authorization: "Bearer " + desk_token,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ notes: notesMap }),
  });
  if (res.status === 401) throw new Error("AUTH");
  if (!res.ok) {
    let body = null;
    try { body = await res.json(); } catch (_) {}
    throw new Error(body?.error || ("HTTP " + res.status));
  }
  return true;
}
