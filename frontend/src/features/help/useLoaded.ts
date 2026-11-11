import { useCallback, useEffect, useState } from "react";

export type Loaded<T> = { status: "loading" } | { status: "error" } | { status: "ready"; value: T };

/** Runs a loader whenever `key` changes and ignores a result that arrives after the key changed. */
export function useLoaded<T>(load: () => Promise<T>, key: string): { state: Loaded<T>; retry: () => void } {
  const [state, setState] = useState<Loaded<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((count) => count + 1), []);

  useEffect(() => {
    let current = true;
    setState({ status: "loading" });
    load().then(
      (value) => {
        if (current) setState({ status: "ready", value });
      },
      () => {
        if (current) setState({ status: "error" });
      },
    );
    return () => {
      current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reloads only when the key or retry count changes
  }, [key, attempt]);

  return { state, retry };
}
