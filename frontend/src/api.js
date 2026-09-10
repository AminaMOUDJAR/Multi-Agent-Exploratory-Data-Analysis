const BASE = "/api";

async function jsonError(res) {
  let detail = "";
  try {
    const body = await res.json();
    detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
  } catch {
    /* non-JSON error body */
  }
  return new Error(detail || `Request failed (${res.status})`);
}

export async function getHealth() {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw await jsonError(res);
  return res.json();
}

export async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: fd });
  if (!res.ok) throw await jsonError(res);
  return res.json();
}

export async function askQuestion(reportId, question) {
  const res = await fetch(`${BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ report_id: reportId, question }),
  });
  if (!res.ok) throw await jsonError(res);
  return res.json();
}
