import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * Filter state kept in the address.
 *
 * Two React Router behaviours make URL-driven filters misbehave on their own:
 * - its functional `setParams` builds on the parameters of the last render, so a filter chosen
 *   right after "Clear" would bring the cleared filters back; every edit here starts from the
 *   newest parameters instead;
 * - it applies navigation as a low-priority transition, so a controlled check box or select would
 *   snap back to its old value until the address updates; the new parameters are shown at once
 *   and handed back to the address as soon as it has caught up (or the reader goes back).
 *
 * `change` also drops the listed paging and selection keys, which no longer match new filters.
 */
export function useFilterParams(filterKeys: readonly string[], dropOnChange: readonly string[]) {
  const [routed, setParams] = useSearchParams();
  const [pending, setPending] = useState<URLSearchParams | null>(null);
  const routedKey = routed.toString();
  useEffect(() => setPending(null), [routedKey]);
  const params = pending ?? routed;
  const latest = useRef(params);
  latest.current = params;
  const apply = (edit: (next: URLSearchParams) => void) => {
    const next = new URLSearchParams(latest.current);
    edit(next);
    latest.current = next;
    setPending(next);
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
  return { params, change, reset, apply };
}
