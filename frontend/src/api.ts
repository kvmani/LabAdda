import { API, PANEL } from "./config";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields?: { field: string; message: string }[],
  ) {
    super(message);
  }
}

let csrfToken: string | null = null;
let onUnauthenticated: (() => void) | null = null;

export function setCsrf(token: string | null) {
  csrfToken = token;
}

export function setUnauthenticatedHandler(fn: () => void) {
  onUnauthenticated = fn;
}

type Options = {
  method?: string;
  body?: unknown;
  form?: FormData;
  uploadKey?: string;
  params?: Record<string, string | number | undefined | null>;
};

export async function api<T = any>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? (opts.body || opts.form ? "POST" : "GET");
  const headers: Record<string, string> = { Accept: "application/json" };
  if (opts.uploadKey) headers["Idempotency-Key"] = opts.uploadKey;
  // A panel never falls back to a desktop session that might exist in the same browser.
  if (PANEL) headers["X-LabAdda-Panel"] = "1";
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let url = API + path;
  if (opts.params) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(opts.params))
      if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    const s = qs.toString();
    if (s) url += "?" + s;
  }
  let res: Response;
  try {
    res = await fetch(url, { method, headers, body, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "offline", "Cannot reach LabAdda. Check your connection and try again.");
  }
  let data: any = null;
  try {
    if (res.headers.get("content-type")?.includes("json")) data = await res.json();
    else if (res.ok && res.status !== 204) throw new Error("Unexpected response type");
  } catch {
    throw new ApiError(
      0,
      "response_unconfirmed",
      "The server response could not be read. Check the result before trying again.",
    );
  }
  if (!res.ok) {
    const err = data?.error ?? {};
    if (
      res.status === 401 &&
      !["/auth/login", "/auth/session", "/panel/session", "/panel/claim"].includes(path)
    )
      onUnauthenticated?.();
    throw new ApiError(
      res.status,
      err.code ?? "error",
      err.message ?? `Request failed (${res.status})`,
      err.fields,
    );
  }
  return data as T;
}

export function newId(prefix = "c"): string {
  const bytes = new Uint8Array(12);
  crypto.getRandomValues(bytes);
  return prefix + "-" + Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
