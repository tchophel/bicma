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

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const method = (init.method ?? (init.json !== undefined ? "POST" : "GET")).toUpperCase();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.json !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRFToken"] = cookie("csrftoken");
  const res = await fetch("/api" + path, {
    method,
    headers,
    credentials: "same-origin",
    body: init.json !== undefined ? JSON.stringify(init.json) : undefined,
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
}

export const ensureCsrf = () => api("/auth/csrf/");
