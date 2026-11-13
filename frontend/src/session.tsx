import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setCsrf, setUnauthenticatedHandler } from "./api";
import { setSiteTimeZone } from "./format";
import { realtime } from "./realtime";
import type { SessionInfo } from "./types";

type Ctx = {
  session: SessionInfo | null;
  loading: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  activate: (token: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** Update the cached session after the server confirmed a change, such as a dismissed welcome. */
  patch: (changes: Partial<SessionInfo>) => void;
  expired: boolean;
};

const SessionContext = createContext<Ctx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [expired, setExpired] = useState(false);

  const accept = useCallback((s: SessionInfo | null) => {
    setCsrf(s?.csrf_token ?? null);
    setSiteTimeZone(s?.timezone);
    setSession(s);
    if (s) {
      setExpired(false);
      realtime.start();
    } else realtime.stop();
  }, []);

  useEffect(() => {
    setUnauthenticatedHandler(() => {
      setExpired(true);
      accept(null);
    });
    api<SessionInfo>("/auth/session")
      .then(accept)
      .catch(() => accept(null))
      .finally(() => setLoading(false));
  }, [accept]);

  const value: Ctx = {
    session,
    loading,
    expired,
    patch: (changes) => setSession((current) => (current ? { ...current, ...changes } : current)),
    signIn: async (username, password) =>
      accept(await api<SessionInfo>("/auth/login", { body: { username, password } })),
    activate: async (token, password) =>
      accept(await api<SessionInfo>("/auth/activate", { body: { token, password } })),
    signOut: async () => {
      try {
        await api("/auth/logout", { method: "POST" });
      } finally {
        accept(null);
      }
    },
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Ctx {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("SessionProvider missing");
  return ctx;
}
