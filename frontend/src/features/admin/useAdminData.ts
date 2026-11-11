import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../../api";
import { invalidate } from "../../generation";

type Loaded<T> = { data: T | null; error: string; reload: () => void };

/** Load one console read endpoint; an older answer never replaces a newer one. */
export function useAdminData<T>(path: string): Loaded<T> {
  const [state, setState] = useState<{ data: T | null; error: string }>({ data: null, error: "" });
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);
  useEffect(() => {
    const request = ++generation.current;
    setState({ data: null, error: "" });
    api<T>(path)
      .then((data) => {
        if (request === generation.current) setState({ data, error: "" });
      })
      .catch((failure: unknown) => {
        if (request === generation.current) setState({ data: null, error: errorMessage(failure) });
      });
    return () => invalidate(generation);
  }, [path, attempt]);
  const reload = useCallback(() => setAttempt((count) => count + 1), []);
  return { ...state, reload };
}
