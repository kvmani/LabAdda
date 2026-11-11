import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, errorMessage } from "./api";
import type { Workspace } from "./types";

type Ctx = {
  workspaces: Workspace[];
  homeId: string | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
};
const WorkspaceContext = createContext<Ctx | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [homeId, setHomeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(async () => {
    try {
      const r = await api<{ workspaces: Workspace[]; home_workspace_id: string | null }>("/workspaces");
      setWorkspaces(r.workspaces);
      setHomeId(r.home_workspace_id);
      setError(null);
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    reload();
  }, [reload]);
  return (
    <WorkspaceContext.Provider value={{ workspaces, homeId, loading, error, reload }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspaces(): Ctx {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("WorkspaceProvider missing");
  return ctx;
}

/** Order org units depth-first so the rail shows indentation. */
export function treeOrder(list: Workspace[]): { ws: Workspace; depth: number }[] {
  const orgs = list.filter((w) => w.kind === "org");
  const ids = new Set(orgs.map((w) => w.id));
  const children = new Map<string | null, Workspace[]>();
  for (const w of orgs) {
    const key = w.parent_id && ids.has(w.parent_id) ? w.parent_id : null;
    children.set(key, [...(children.get(key) ?? []), w]);
  }
  const out: { ws: Workspace; depth: number }[] = [];
  const walk = (parent: string | null, depth: number) => {
    for (const w of (children.get(parent) ?? []).sort((a, b) => a.name.localeCompare(b.name))) {
      out.push({ ws: w, depth });
      walk(w.id, depth + 1);
    }
  };
  walk(null, 0);
  return out;
}
