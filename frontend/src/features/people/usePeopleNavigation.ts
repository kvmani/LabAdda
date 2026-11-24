import { useFilterParams } from "../../useFilterParams";
import { FILTER_KEYS } from "./model";

/** URL navigation preserves search focus and drops cursors and the open profile when filters change. */
export function usePeopleNavigation() {
  const { params, change, reset, apply } = useFilterParams(FILTER_KEYS, ["cursor", "person", "view"]);
  const profile = (key: string, value?: string) =>
    apply((next) => {
      if (value) next.set(key, value);
      else next.delete(key);
      if (key === "person") next.delete("view");
    });
  return { params, change, reset, profile };
}
