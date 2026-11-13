import { useEffect, useRef, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../../api";
import { Notifications } from "../../components/Notifications";
import { realtime, type ConnState } from "../../realtime";
import { useSession } from "../../session";
import { Banner, HelpEntryContext } from "../../ui";
import { useWorkspaces } from "../../workspaces";
import { HelpLink } from "../help/HelpLink";
import { BuildFooter } from "./BuildFooter";
import { FirstUse } from "./FirstUse";
import { RailNav } from "./RailNav";
import { TopBar } from "./TopBar";
import { useSiteBanner } from "./useSiteBanner";
import "./shell.css";

/** Refresh the unread count this often while a page stays open. */
const UNREAD_POLL_MILLISECONDS = 30_000;

/** The signed-in frame around every page: skip link, top bar, rail and main region (UX-03). */
export function Shell({ children }: { children: ReactNode }) {
  const { session } = useSession();
  const { workspaces, reload, error } = useWorkspaces();
  const location = useLocation();
  const [connection, setConnection] = useState<ConnState>(realtime.state);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [operations, setOperations] = useState(false);
  const [unitAdmin, setUnitAdmin] = useState(false);
  const [unread, setUnread] = useState(0);
  const notice = useSiteBanner();
  const currentId = /^\/w\/([^/]+)/.exec(location.pathname)?.[1];
  const currentRef = useRef(currentId);
  currentRef.current = currentId;

  useEffect(() => {
    let live = true;
    api<{ "usage.read": boolean; "unit.admin"?: boolean }>("/capabilities")
      .then((capabilities) => {
        if (!live) return;
        setOperations(capabilities["usage.read"]);
        setUnitAdmin(capabilities["unit.admin"] === true);
      })
      .catch(() => {
        if (!live) return;
        setOperations(false);
        setUnitAdmin(false);
      });
    return () => {
      live = false;
    };
  }, [location.pathname]);

  useEffect(() => realtime.onState(setConnection) as () => void, []);

  useEffect(() => {
    const load = () =>
      api<{ unread: number }>("/notifications", { params: { limit: 1 } })
        .then((result) => setUnread(result.unread))
        .catch(() => undefined);
    void load();
    const timer = window.setInterval(() => void load(), UNREAD_POLL_MILLISECONDS);
    return () => window.clearInterval(timer);
  }, [location.pathname]);

  useEffect(() => {
    // Membership changes arrive as access signals; unread chat elsewhere refreshes rail counts.
    const unsubscribe = workspaces.map((workspace) =>
      realtime.subscribe(workspace.id, (event) => {
        if (event.type === "revoked" || event.type === "access_changed") void reload();
        if (
          event.type === "chat.message" &&
          event.message.author?.id !== session?.user.id &&
          currentRef.current !== workspace.id
        )
          void reload();
      }),
    );
    return () => unsubscribe.forEach((stop) => stop());
    // eslint-disable-next-line react-hooks/exhaustive-deps -- resubscribe only when the set of workspace IDs changes
  }, [workspaces.map((workspace) => workspace.id).join(",")]);

  return (
    <HelpEntryContext.Provider value={HelpLink}>
      <div className={notice ? "shell shell--notice" : "shell"}>
        {/* Moves focus programmatically: a "#main" href would resolve against <base href> under a prefix. */}
        <a
          href="#main"
          className="shell-skip-link"
          onClick={(event) => {
            event.preventDefault();
            document.getElementById("main")?.focus();
          }}
        >
          Skip to main content
        </a>
        <TopBar
          workspaces={workspaces}
          currentId={currentId}
          operations={operations}
          unitAdmin={unitAdmin}
          connection={connection}
          unread={unread}
          notificationsOpen={notificationsOpen}
          onToggleNotifications={() => setNotificationsOpen((open) => !open)}
        />
        {notice && (
          <div className="shell-notice">
            <Banner level={notice.level}>{notice.message}</Banner>
          </div>
        )}
        {notificationsOpen && (
          <Notifications onClose={() => setNotificationsOpen(false)} onChange={setUnread} />
        )}
        <RailNav workspaces={workspaces} currentId={currentId} operations={operations} error={error} />
        <main className="shell-main" id="main" tabIndex={-1}>
          <FirstUse />
          {children}
        </main>
        <div className="shell-footer">
          <BuildFooter />
        </div>
      </div>
    </HelpEntryContext.Provider>
  );
}
