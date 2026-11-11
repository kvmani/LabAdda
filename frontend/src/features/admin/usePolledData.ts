import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage, errorStatus } from "../../api";
import { invalidate } from "../../generation";

type State<T> = { path: string; data: T | null; error: string; at: number | null };

/**
 * Read a console endpoint now and then again every `intervalMs` while the tab is visible (UX-10).
 * A poll that fails keeps the last good data and reports the error, so the page can say its
 * figures are old instead of blanking. An answer for an older path never replaces a newer one.
 */
export function usePolledData<T>(path: string | null, intervalMs: number, onDenied?: () => void) {
  const generation = useRef(0);
  const [state, setState] = useState<State<T> | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!path) return;
    const load = () => {
      const request = ++generation.current;
      api<T>(path)
        .then((data) => {
          if (request === generation.current) setState({ path, data, error: "", at: Date.now() });
        })
        .catch((failure: unknown) => {
          if (request !== generation.current) return;
          if ([401, 403].includes(errorStatus(failure) ?? 0)) onDenied?.();
          setState((previous) => ({
            path,
            data: previous?.path === path ? previous.data : null,
            error: errorMessage(failure),
            at: previous?.path === path ? previous.at : null,
          }));
        });
    };
    const whenVisible = () => {
      if (document.visibilityState === "visible") load();
    };
    load();
    const timer = intervalMs > 0 ? window.setInterval(whenVisible, intervalMs) : undefined;
    document.addEventListener("visibilitychange", whenVisible);
    return () => {
      if (timer !== undefined) window.clearInterval(timer);
      document.removeEventListener("visibilitychange", whenVisible);
      invalidate(generation);
    };
  }, [path, intervalMs, attempt, onDenied]);
  const current = path && state?.path === path ? state : null;
  const reload = useCallback(() => setAttempt((count) => count + 1), []);
  return {
    data: current?.data ?? null,
    error: current?.error ?? "",
    fetchedAt: current?.at ?? null,
    loading: Boolean(path && !current),
    reload,
  };
}

/** The current time, refreshed every `ms` while the tab is visible, for "checked 8 s ago" text. */
export function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = () => {
      if (document.visibilityState === "visible") setNow(Date.now());
    };
    const timer = window.setInterval(tick, ms);
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [ms]);
  return now;
}
