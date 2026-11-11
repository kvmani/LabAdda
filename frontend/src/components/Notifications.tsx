import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorCode, errorMessage } from "../api";
import type { NotificationLink, OpenedNotification } from "../types";
import { fmtTime } from "../format";

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
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function open(item: Item) {
    try {
      const opened = await api<OpenedNotification>(`/notifications/${item.id}/open`, { method: "POST" });
      const link = opened.link;
      onClose();
      if (link.view === "notes") navigate("/notes");
      else navigate(`/w/${link.workspace_id}/${link.view}`);
    } catch (e: unknown) {
      setError(errorCode(e) === "not_found" ? "That item is no longer available to you." : errorMessage(e));
      load();
    }
  }

  return (
    <aside id="notifications" className="notifications card" aria-label="Notifications">
      <div className="row between">
        <h2>Notifications</h2>
        <div className="row">
          <button
            className="ghost"
            onClick={() => api("/notifications/read-all", { method: "POST" }).then(load)}
          >
            Mark all read
          </button>
          <button className="ghost" onClick={onClose} aria-label="Close notifications">
            Close
          </button>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {items === null ? (
        <p className="muted">Loading…</p>
      ) : items.length === 0 ? (
        <p className="muted">No notifications.</p>
      ) : (
        <ul className="plain">
          {items.map((n) => (
            <li key={n.id}>
              <button className={"notification" + (n.read ? "" : " unread")} onClick={() => open(n)}>
                <strong>
                  {n.read ? "" : "Unread · "}
                  {kindText[n.kind] ?? n.kind}
                </strong>
                {n.workspace && <span className="muted"> in {n.workspace.name}</span>}
                <span className="snippet">{n.title}</span>
                <span className="muted small">{fmtTime(n.created_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
