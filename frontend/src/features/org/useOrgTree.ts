import { useCallback, useMemo, useState } from "react";
import { usePeopleData } from "../people/usePeopleData";
import { reveal } from "./layout";
import type { OrgTree } from "./types";

/** The chart's data plus what the person chose to see: selection, collapsed units, closed units. */
export function useOrgTree(onDenied: () => void) {
  const data = usePeopleData<OrgTree>("/admin/org/tree", onDenied);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const [showClosed, setShowClosed] = useState(false);
  const all = useMemo(() => data.data?.units ?? [], [data.data]);
  const units = showClosed ? all : all.filter((unit) => !unit.archived);
  const selected = all.find((unit) => unit.id === selectedId) ?? null;

  const toggle = useCallback((id: string) => {
    setCollapsed((previous) => {
      const next = new Set(previous);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }, []);
  const collapseAll = useCallback(
    (collapse: boolean) => {
      const parents = new Set(all.map((unit) => unit.parent_id).filter(Boolean) as string[]);
      const tops = new Set(all.filter((unit) => !unit.parent_id).map((unit) => unit.id));
      setCollapsed(collapse ? new Set([...parents].filter((id) => !tops.has(id))) : new Set());
    },
    [all],
  );
  const show = useCallback(
    (id: string) => {
      const target = all.find((unit) => unit.id === id);
      if (target?.archived) setShowClosed(true);
      setCollapsed((previous) => reveal(previous, all, id));
      setSelectedId(id);
    },
    [all],
  );
  return {
    ...data,
    units,
    all,
    selected,
    selectedId,
    collapsed,
    showClosed,
    setShowClosed,
    toggle,
    collapseAll,
    show,
  };
}
