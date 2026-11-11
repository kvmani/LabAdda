import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage, errorStatus } from "../../api";
import { invalidate } from "../../generation";

type Result<T> = { key: string; data: T | null; error: string };

/** Scope-bound metadata; any known authority loss clears the entire people view. */
export function usePeopleData<T>(url: string | null, onDenied: () => void) {
  const generation = useRef(0);
  const [retry, setRetry] = useState(0);
  const [result, setResult] = useState<Result<T> | null>(null);
  const key = `${url ?? ""}:${retry}`;
  useEffect(() => {
    const request = ++generation.current;
    if (url)
      void api<T>(url)
        .then((data) => {
          if (request === generation.current) setResult({ key, data, error: "" });
        })
        .catch((error: unknown) => {
          if (request !== generation.current) return;
          if ([401, 403].includes(errorStatus(error) ?? 0)) onDenied();
          setResult({ key, data: null, error: errorMessage(error) });
        });
    return () => invalidate(generation);
  }, [url, key, onDenied]);
  const current = url && result?.key === key ? result : null;
  const refresh = useCallback(() => setRetry((previous) => previous + 1), []);
  return {
    data: current?.data ?? null,
    error: current?.error ?? "",
    loading: Boolean(url && !current),
    refresh,
  };
}
