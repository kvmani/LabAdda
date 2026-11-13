import { Brand } from "../home/Brand";
import "../home/home.css";
import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { INSTANCE } from "../../config";
import type { ConnState } from "../../realtime";
import { useSession } from "../../session";
import {
  Badge,
  Icon,
  Menu,
  StatusPill,
  Tag,
  readThemeChoice,
  saveThemeChoice,
  type IconName,
  type ThemeChoice,
  type Tone,
} from "../../ui";
import { FeedbackDialog } from "../feedback/FeedbackDialog";
import { WorkspaceSwitcher } from "./WorkspaceSwitcher";
import type { Workspace } from "../../types";

const CONNECTION: Record<ConnState, { word: string; tone: Tone; icon: IconName }> = {
  online: { word: "Live", tone: "ok", icon: "success" },
  connecting: { word: "Connecting…", tone: "warn", icon: "clock" },
  reconnecting: { word: "Reconnecting…", tone: "warn", icon: "refresh" },
  offline: { word: "Offline", tone: "danger", icon: "error" },
};

const THEMES: { choice: ThemeChoice; label: string; icon: IconName }[] = [
  { choice: "system", label: "Follow the system", icon: "monitor" },
  { choice: "light", label: "Light", icon: "sun" },
  { choice: "dark", label: "Dark", icon: "moon" },
];

type TopBarProps = {
  workspaces: Workspace[];
  currentId: string | undefined;
  operations: boolean;
  /** A unit administrator reaches People and Organisation only. */
  unitAdmin: boolean;
  connection: ConnState;
  unread: number;
  notificationsOpen: boolean;
  onToggleNotifications: () => void;
};

/** Product name, site, live status, notifications, help, administration and the account menu. */
export function TopBar({
  workspaces,
  currentId,
  operations,
  unitAdmin,
  connection,
  unread,
  notificationsOpen,
  onToggleNotifications,
}: TopBarProps) {
  const { session, signOut } = useSession();
  const navigate = useNavigate();
  const [theme, setTheme] = useState<ThemeChoice>(readThemeChoice);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const status = CONNECTION[connection];
  const name = session?.user.display_name ?? "";
  return (
    <header className="shell-topbar">
      <Link to="/" className="shell-topbar__brand" aria-label="LabAdda home">
        <Brand />
      </Link>
      {INSTANCE !== "pilot" && (
        <span className="shell-topbar__instance">
          <Tag tone="warn">{INSTANCE}</Tag>
        </span>
      )}
      <WorkspaceSwitcher workspaces={workspaces} currentId={currentId} operations={operations} />
      <div className="shell-topbar__end">
        <span role="status" className="shell-topbar__connection">
          <StatusPill tone={status.tone} icon={status.icon} label={status.word} />
        </span>
        <button
          type="button"
          className="ui-button ui-button--quiet ui-button--md shell-topbar__notifications"
          onClick={onToggleNotifications}
          aria-expanded={notificationsOpen}
          aria-controls="notifications"
        >
          <Icon name="bell" />
          <span className="shell-topbar__label">Notifications</span>
          <Badge count={unread} label="unread" />
        </button>
        <button
          type="button"
          className="ui-button ui-button--quiet ui-button--md shell-topbar__notifications"
          onClick={() => setFeedbackOpen(true)}
        >
          <Icon name="edit" />
          <span className="shell-topbar__label">Feedback</span>
        </button>
        <Link to="/help" className="shell-topbar__link">
          <Icon name="help" />
          <span className="shell-topbar__label">Help</span>
        </Link>
        {(session?.user.is_admin || operations || unitAdmin) && (
          <NavLink to="/admin" className="shell-topbar__link">
            <Icon name="unit" />
            <span className="shell-topbar__label">Administration</span>
          </NavLink>
        )}
        <Menu
          label={`Account menu for ${name}`}
          visibleLabel={name}
          items={[
            { label: "My profile", icon: "user", onSelect: () => navigate("/profile") },
            { label: "Alert preferences", icon: "bell", onSelect: () => navigate("/preferences") },
            ...THEMES.map(({ choice, label, icon }) => ({
              label: `Theme: ${label}${theme === choice ? " (selected)" : ""}`,
              icon,
              onSelect: () => {
                saveThemeChoice(choice);
                setTheme(choice);
              },
            })),
            { label: "Sign out", icon: "external", onSelect: () => void signOut() },
          ]}
        />
      </div>
      <FeedbackDialog open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
    </header>
  );
}
