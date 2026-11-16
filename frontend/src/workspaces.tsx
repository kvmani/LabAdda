import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { invalidate } from "./generation";
import { realtime } from "./realtime";
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
  const generation = useRef(0);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [homeId, setHomeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(async () => {
    const token = ++generation.current;
    try {
      const r = await api<{ workspaces: Workspace[]; home_workspace_id: string | null }>("/workspaces");
      if (token !== generation.current) return;
      setWorkspaces(r.workspaces);
      setHomeId(r.home_workspace_id);
      setError(null);
    } catch (e: unknown) {
      if (token === generation.current) setError(errorMessage(e));
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    void reload();
    return () => invalidate(generation);
  }, [reload]);
  const subscriptionIds = workspaces.map((workspace) => workspace.id).join(",");
  useEffect(() => {
    const subscriptions = subscriptionIds
      .split(",")
      .filter(Boolean)
      .map((id) =>
        realtime.subscribe(id, (event) => {
          if (event.type === "access_changed" || event.type === "revoked" || event.type === "subscribed")
            void reload();
        }),
      );
    const timer = window.setInterval(() => {
      if (!document.hidden) void reload();
    }, 30000);
    return () => {
      subscriptions.forEach((unsubscribe) => unsubscribe());
      window.clearInterval(timer);
    };
  }, [subscriptionIds, reload]);
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
