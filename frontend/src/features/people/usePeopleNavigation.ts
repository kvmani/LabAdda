import { useSearchParams } from "react-router-dom";
import { FILTER_KEYS } from "./model";

/** URL navigation preserves search focus and drops cursors when filters change. */
export function usePeopleNavigation() {
  const [params, setParams] = useSearchParams();
  const change = (key: string, value: string) => {
    if ((params.get(key) ?? "") === value) return;
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value);
      else next.delete(key);
      if (key !== "cursor") next.delete("cursor");
      next.delete("person");
      next.delete("view");
      return next;
    });
  };
  const reset = () =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      for (const key of [...FILTER_KEYS, "cursor", "person", "view"]) next.delete(key);
      return next;
    });
  const profile = (key: string, value?: string) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value);
      else next.delete(key);
      if (key === "person") next.delete("view");
      return next;
    });
  return { params, change, reset, profile };
}
