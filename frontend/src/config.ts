declare global {
  interface Window {
    __LABADD__?: { base: string; instance: string };
  }
}

const injected = typeof window === "undefined" ? undefined : window.__LABADD__;
export const BASE = injected?.base ?? "";
export const INSTANCE = injected?.instance ?? "dev";
export const API = `${BASE}/api/v1`;

export function socketUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${BASE}/ws/`;
}
