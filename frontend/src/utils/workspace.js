import { reactive } from "vue";

const BASE = "/enzymind/api/workspace";
const KEY = "enzymind_workspace_access_v2";
let accessKey;
export const platformResults = reactive({});
export const workspaceNotice = reactive({ message: "" });

export function getAccessKey() {
  if (accessKey) return accessKey;
  try {
    accessKey = localStorage.getItem(KEY);
  } catch {
    /* Report unavailable persistence below. */
  }
  if (!/^[a-f0-9]{64}$/.test(accessKey || "")) {
    accessKey = Array.from(crypto.getRandomValues(new Uint8Array(32)), (n) =>
      n.toString(16).padStart(2, "0"),
    ).join("");
    try {
      localStorage.setItem(KEY, accessKey);
    } catch {
      workspaceNotice.message =
        "Browser storage is unavailable. Export your access key before closing this tab to recover saved research.";
    }
  }
  return accessKey;
}

export async function workspaceFetch(path, options = {}) {
  const response = await fetch(BASE + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Enzymind-Client": getAccessKey(),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const error = new Error(
      typeof data.detail === "string"
        ? data.detail
        : data.detail?.message || `Request failed (${response.status}). Please try again.`,
    );
    error.code = data.detail?.code;
    error.quota = data.detail?.quota;
    throw error;
  }
  return options.raw ? response : response.json();
}

export function postWorkspace(path, data = {}, headers = {}) {
  return workspaceFetch(path, { method: "POST", body: JSON.stringify(data), headers });
}

export async function streamWorkspaceTurn(id, signal, onFrame) {
  const response = await workspaceFetch(`/turns/${id}/stream`, {
    raw: true, signal, headers: { Accept: 'text/event-stream' },
  });
  if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) {
    await response.body?.cancel();
    throw new Error('Live updates are unavailable; reconnecting to saved progress.');
  }
  const reader = response.body.getReader(), decoder = new TextDecoder();
  let buffer = '', event = '', data = [];
  try {
    while (true) {
      let timer;
      const { value, done } = await Promise.race([
        reader.read(),
        new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Live connection timed out.')), 45000); }),
      ]).finally(() => clearTimeout(timer));
      buffer += decoder.decode(value, { stream: !done });
      let newline;
      while ((newline = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, newline).replace(/\r$/, '');
        buffer = buffer.slice(newline + 1);
        if (!line) {
          if (data.length) {
            await onFrame(event, JSON.parse(data.join('\n')));
            if (event === 'done') return;
          }
          event = ''; data = [];
        } else if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
      }
      if (done) throw new Error('Live connection ended before the answer finished.');
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export function newRequestId() {
  // getRandomValues also works on existing HTTP deployments where randomUUID is unavailable.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, (n) => n.toString(16).padStart(2, "0")).join(
    "",
  );
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function downloadData(value, filename, type = "application/json") {
  const blob = new Blob(
    [typeof value === "string" ? value : JSON.stringify(value, null, 2)],
    { type },
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function exportAccess() {
  downloadData(
    { application: "EnzyMind workspace", access_key: getAccessKey() },
    "enzymind-workspace-access.json",
  );
}

export function restoreAccess(value) {
  if (!/^[a-f0-9]{64}$/.test(value || ""))
    throw new Error("This is not a valid workspace access file.");
  localStorage.setItem(KEY, value);
  accessKey = value;
  Object.keys(platformResults).forEach((key) => delete platformResults[key]);
}

export const endpointForRoute = {
  "/predict/enzyme": "/recognize/enzyme",
  "/predict/ec": "/predict/ec",
  "/predict/substrate": "/predict/substrate",
  "/predict/kcat": "/predict/kcat",
  "/predict/km": "/predict/km",
  "/predict/activesite": "/predict/active-sites",
  "/predict/recommendation": "/query/enzyme-type",
  "/utility/structure": "/predict/structure",
  "/utility/parameters": "/query/protein-physchem",
  "/utility/alignment": "/query/blast",
  "/utility/enzyme-info": "/query/enzyme-full-info",
};
