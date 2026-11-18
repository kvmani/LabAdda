import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../../api";
import { realtime } from "../../realtime";
import { useSession } from "../../session";
import { useWorkspaces } from "../../workspaces";
import type { NotificationLink } from "../../types";
import { Button } from "../../ui";
import { AlertChime } from "./chime";
import "./alerts.css";

type Alert = {
  id: string;
  title: string;
  kind: string;
  read: boolean;
  link: NotificationLink;
  workspace: { id: string; name: string } | null;
};

/** Only server-authorized content enters this queue; access signals clear it immediately. */
export function AlertPopups({ onRead }: { onRead?: () => void }) {
  const { session } = useSession();
  const { workspaces, reload } = useWorkspaces();
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [sound, setSound] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const chime = useRef(new AlertChime());
  const dismissed = useRef(new Set<string>());
  const seen = useRef(new Set<string>());
  const ids = workspaces.map((w) => w.id).join(",");
  const visibleAlerts = alerts.filter(
    (alert) => !alert.workspace || workspaces.some((space) => space.id === alert.workspace?.id),
  );
  const workspaceRef = useRef(workspaces);
  workspaceRef.current = workspaces;
  const soundRef = useRef(sound);
  soundRef.current = sound;

  useEffect(() => {
    let live = true;
    let generation = 0;
    let loading = false;
    const revoked = new Set<string>();
    setAlerts((current) =>
      current.filter((item) => !item.workspace || ids.split(",").includes(item.workspace.id)),
    );
    function add(items: Alert[]) {
      if (!live) return;
      const fresh = items.filter((item) => !seen.current.has(item.id) && !item.read);
      fresh.forEach((item) => seen.current.add(item.id));
      if (fresh.length && soundRef.current) chime.current.play();
      setAlerts((current) =>
        [...current, ...fresh].filter((item) => !dismissed.current.has(item.id)).slice(-100),
      );
    }
    async function load() {
      if (loading) return;
      loading = true;
      const token = generation;
      try {
        const result = await api<{ items: Alert[] }>("/notifications", { params: { limit: 100 } });
        if (!live || token !== generation) return;
        const unread = new Set(result.items.filter((item) => !item.read).map((item) => item.id));
        setAlerts((current) => current.filter((item) => item.kind === "chat" || unread.has(item.id)));
        add(result.items);
      } catch {
        // Never retain protected snippets after an unconfirmed refresh.
        if (live) setAlerts([]);
      } finally {
        loading = false;
      }
    }
    const subscriptions = ids
      .split(",")
      .filter(Boolean)
      .map((id) =>
        realtime.subscribe(id, (event) => {
          if (event.type === "revoked" || event.type === "access_changed" || event.type === "session_ended") {
            generation += 1;
            revoked.add(id);
            setAlerts([]);
          }
          if (
            event.type === "chat.message" &&
            event.message.author?.id !== session?.user.id &&
            !revoked.has(id)
          ) {
            const message = event.message;
            add([
              {
                id: `chat:${message.id}`,
                kind: "chat",
                title: message.body || "Shared an attachment",
                read: false,
                workspace: workspaceRef.current.find((w) => w.id === id) ?? null,
                link: { view: "chat", workspace_id: id, seq: message.seq },
              },
            ]);
          }
          if (event.type === "noticeboard.changed") void load();
        }),
      );
    void load();
    const timer = window.setInterval(() => void load(), 10000);
    return () => {
      live = false;
      generation += 1;
      window.clearInterval(timer);
      subscriptions.forEach((stop) => stop());
    };
  }, [ids, session?.user.id]);

  useEffect(() => {
    const audio = chime.current;
    return () => audio.close();
  }, []);

  function dismiss(id: string) {
    dismissed.current.add(id);
    setAlerts((current) => current.filter((item) => item.id !== id));
  }

  async function acknowledge(item: Alert, open: boolean) {
    setBusy(item.id);
    setError("");
    try {
      let link = item.link;
      if (item.kind === "chat" && link.view === "chat") {
        await api(`/workspaces/${link.workspace_id}/chat/read`, { method: "POST", body: { seq: link.seq } });
        const readLink = link;
        setAlerts((current) =>
          current.filter(
            (alert) =>
              alert.link.view !== "chat" ||
              alert.link.workspace_id !== readLink.workspace_id ||
              alert.link.seq > readLink.seq,
          ),
        );
        void reload();
      } else {
        const result = await api<{ link: NotificationLink }>(`/notifications/${item.id}/open`, {
          method: "POST",
        });
        link = result.link;
        onRead?.();
      }
      dismiss(item.id);
      if (open)
        void navigate(
          link.view === "calendar"
            ? "/calendar"
            : link.view === "notes"
              ? "/notes"
              : `/w/${link.workspace_id}/${link.view}`,
        );
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  async function toggleSound() {
    if (sound) {
      setSound(false);
      return;
    }
    try {
      await chime.current.enable();
      setSound(true);
      chime.current.play();
      setError("");
    } catch {
      setError("Sound could not start. Check your browser's sound settings.");
    }
  }

  return (
    <aside className="alert-popups" aria-label="Live alerts">
      <div className="alert-popups__head">
        <span>
          {visibleAlerts.length
            ? `${visibleAlerts.length} unread alert${visibleAlerts.length === 1 ? "" : "s"}`
            : "Live alerts"}
        </span>
        <Button size="sm" variant="quiet" onClick={() => void toggleSound()} aria-pressed={sound}>
          {sound ? "Mute chime" : "Enable chime"}
        </Button>
      </div>
      {error && <p role="alert">{error}</p>}
      <div aria-live="polite" aria-relevant="additions">
        {visibleAlerts.slice(0, 3).map((item) => (
          <section
            className="alert-popup"
            key={item.id}
            aria-label={item.kind === "chat" ? "New chat message" : "New notification"}
          >
            <strong>
              {item.kind === "chat"
                ? "New chat message"
                : item.link.view === "calendar"
                  ? "Meeting starts soon"
                  : item.kind === "reminder"
                    ? "Reminder"
                    : "New notification"}
            </strong>
            {item.workspace && <span className="alert-popup__where">{item.workspace.name}</span>}
            <p>{item.title}</p>
            <div className="alert-popup__actions">
              <Button
                size="sm"
                variant="primary"
                disabled={busy !== null}
                onClick={() => void acknowledge(item, true)}
              >
                Open
              </Button>
              <Button size="sm" disabled={busy !== null} onClick={() => void acknowledge(item, false)}>
                Mark as read
              </Button>
              <Button size="sm" variant="quiet" onClick={() => dismiss(item.id)}>
                Dismiss
              </Button>
            </div>
          </section>
        ))}
      </div>
    </aside>
  );
}
