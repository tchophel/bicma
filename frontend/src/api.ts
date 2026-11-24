export class ApiError extends Error {
  status: number;
  fields: Record<string, string>;
  body: unknown; // raw error response, for endpoints that return structured errors (e.g. per-row)
  constructor(message: string, status: number, fields: Record<string, string> = {}, body: unknown = null) {
    super(message);
    this.status = status;
    this.fields = fields;
    this.body = body;
  }
}

function cookie(name: string): string {
  return document.cookie.split("; ").find((c) => c.startsWith(name + "="))?.split("=")[1] ?? "";
}

function flatten(data: unknown): { message: string; fields: Record<string, string> } {
  const fields: Record<string, string> = {};
  const parts: string[] = [];
  if (data && typeof data === "object") {
    for (const [k, v] of Object.entries(data as Record<string, unknown>)) {
      const text = Array.isArray(v) ? v.join(" ") : String(v);
      if (k === "rows") continue; // structured per-row errors are read from ApiError.body
      if (k === "detail" || k === "non_field_errors") parts.push(text);
      else {
        fields[k] = text;
        parts.push(`${k.replace(/_/g, " ")}: ${text}`);
      }
    }
  }
  return { message: parts.join(" ") || "Something went wrong. Please try again.", fields };
}

let pending = 0;
const listeners = new Set<() => void>();
export const pendingCount = () => pending;
export function subscribePending(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn); }; }
const track = (delta: number) => { pending += delta; listeners.forEach((l) => l()); };

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown; form?: FormData } = {}): Promise<T> {
  const method = (init.method ?? (init.json !== undefined || init.form ? "POST" : "GET")).toUpperCase();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.json !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRFToken"] = cookie("csrftoken");
  const quiet = path.startsWith("/notifications/") || path === "/complaints/?page_size=1"; // background polling (the bell, the sidebar count): no spinner for that
  if (!quiet) track(1);
  try {
    const res = await fetch("/api" + path, {
      method,
      headers,
      credentials: "same-origin",
      body: init.form ?? (init.json !== undefined ? JSON.stringify(init.json) : undefined),
    });
    if (res.status === 204) return undefined as T;
    let data: unknown = null;
    try {
      data = await res.json();
    } catch {
      /* non-JSON body */
    }
    if (!res.ok) {
      const { message, fields } = flatten(data);
      throw new ApiError(res.status === 429 ? "Too many requests. Please wait and try again." : message, res.status, fields, data);
    }
    return data as T;
  } finally {
    if (!quiet) track(-1);
  }
}

/** Uploads a form with progress (fetch cannot report upload progress). Errors come back the same way as from `api`. */
export function uploadWithProgress<T = unknown>(path: string, form: FormData, onProgress: (percent: number) => void): Promise<T> {
  track(1);
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api" + path);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.setRequestHeader("X-CSRFToken", cookie("csrftoken"));
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(Math.min(100, Math.round((e.loaded / e.total) * 100))); };
    xhr.onerror = () => reject(new ApiError("The upload could not be completed. Check your connection and try again.", 0));
    xhr.onabort = () => reject(new ApiError("The upload was cancelled.", 0));
    xhr.onload = () => {
      let data: unknown = null;
      try { data = JSON.parse(xhr.responseText); } catch { /* non-JSON body */ }
      if (xhr.status >= 200 && xhr.status < 300) { resolve(data as T); return; }
      const { message, fields } = flatten(data);
      reject(new ApiError(xhr.status === 429 ? "Too many requests. Please wait and try again." : message, xhr.status, fields, data));
    };
    xhr.send(form);
  }).finally(() => track(-1));
}

export const ensureCsrf = () => api("/auth/csrf/");
