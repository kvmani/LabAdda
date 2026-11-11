import { useEffect, useRef, useState } from "react";
import { api, asApiError, errorMessage } from "../../api";
import { invalidate } from "../../generation";
import type { ConsoleAccess } from "./console";

type Result = {
  retry: number;
  path: string;
  access: ConsoleAccess | null;
  error: string;
  forbidden: boolean;
};

/** Do not display the previous section while checking current server authority. */
export function useConsole(path: string, retry: number) {
  const generation = useRef(0);
  const [result, setResult] = useState<Result | null>(null);
  useEffect(() => {
    const request = ++generation.current;
    api<ConsoleAccess>("/admin/console")
      .then((access) => {
        if (request === generation.current) setResult({ path, retry, access, error: "", forbidden: false });
      })
      .catch((error: unknown) => {
        if (request === generation.current)
          setResult({
            path,
            retry,
            access: null,
            error: errorMessage(error),
            forbidden: asApiError(error)?.status === 403,
          });
      });
    return () => invalidate(generation);
  }, [path, retry]);
  return result?.path === path && result.retry === retry ? result : null;
}
