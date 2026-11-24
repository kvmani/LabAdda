import { useRef } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * Filter state kept in the address. React Router's functional `setParams` builds on the
 * parameters of the last render, so a filter chosen right after "Clear" would bring the cleared
 * filters back. Every edit here starts from the newest parameters instead.
 *
 * `change` also drops the listed paging and selection keys, which no longer match new filters.
 */
export function useFilterParams(filterKeys: readonly string[], dropOnChange: readonly string[]) {
  const [params, setParams] = useSearchParams();
  const latest = useRef(params);
  latest.current = params;
  const apply = (edit: (next: URLSearchParams) => void) => {
    const next = new URLSearchParams(latest.current);
    edit(next);
    latest.current = next;
    setParams(next);
  };
  const change = (key: string, value: string) => {
    if ((latest.current.get(key) ?? "") === value) return;
    apply((next) => {
      if (value) next.set(key, value);
      else next.delete(key);
      for (const other of dropOnChange) if (other !== key) next.delete(other);
    });
  };
  const reset = () =>
    apply((next) => {
      for (const key of [...filterKeys, ...dropOnChange]) next.delete(key);
    });
  return { params, change, reset };
}
