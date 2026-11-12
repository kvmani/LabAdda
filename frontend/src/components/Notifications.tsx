import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorCode, errorMessage } from "../api";
import type { NotificationLink, OpenedNotification } from "../types";
import { fmtTime } from "../format";
import { Button, ErrorState, Skeleton } from "../ui";
import "./notifications.css";

type Item = {
  id: string;
  kind: string;
  created_at: string;
  read: boolean;
  title: string;
  workspace: { id: string; name: string } | null;
  link: NotificationLink;
};
const kindText: Record<string, string> = {
  mention: "Mentioned you",
  reminder: "Reminder",
  official: "Official notice",
  reassign: "Tasks to reassign",
};

export function Notifications({ onClose, onChange }: { onClose: () => void; onChange: (n: number) => void }) {
  const [items, setItems] = useState<Item[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = () =>
    api<{ unread: number; items: Item[] }>("/notifications")
      .then((r) => {
        setItems(r.items);
        onChange(r.unread);
      })
      .catch((e) => setError(errorMessage(e)));
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once when the panel opens
  }, []);

  async function open(item: Item) {
    try {
      const opened = await api<OpenedNotification>(`/notifications/${item.id}/open`, { method: "POST" });
      const link = opened.link;
      onClose();
      if (link.view === "notes") navigate("/notes");
      else navigate(`/w/${link.workspace_id}/${link.view}`);
    } catch (e: unknown) {
      setError(errorCode(e) === "not_found" ? "That item is no longer available to you." : errorMessage(e));
      void load();
    }
  }

  return (
    <aside id="notifications" className="notifications" aria-label="Notifications">
      <div className="notifications__head">
        <h2 className="notifications__title">Notifications</h2>
        <div className="notifications__actions">
          <Button
            variant="quiet"
            size="sm"
            onClick={() => api("/notifications/read-all", { method: "POST" }).then(load)}
          >
            Mark all read
          </Button>
          <Button variant="quiet" size="sm" onClick={onClose} aria-label="Close notifications">
            Close
          </Button>
        </div>
      </div>
      {error && <ErrorState message={error} title="Notifications could not be updated" />}
      {items === null ? (
        <Skeleton lines={3} label="Loading…" />
      ) : items.length === 0 ? (
        <p className="notifications__empty">No notifications.</p>
      ) : (
        <ul className="notifications__list">
          {items.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                className={"notification" + (n.read ? "" : " notification--unread")}
                onClick={() => open(n)}
              >
                <strong>
                  {n.read ? "" : "Unread · "}
                  {kindText[n.kind] ?? n.kind}
                </strong>
                {n.workspace && <span className="notification__where"> in {n.workspace.name}</span>}
                <span className="notification__snippet">{n.title}</span>
                <span className="notification__time">{fmtTime(n.created_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
