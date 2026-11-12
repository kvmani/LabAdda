import { useEffect, useRef, useState } from "react";
import { api, errorMessage, newId } from "../api";
import { API } from "../config";
import { useWorkspaces } from "../workspaces";
import type { Workspace } from "../types";
import type { Region } from "../pages/Board";
import { Button, Checkbox, Dialog, Select, TextArea } from "../ui";

type Destination = { id: string; name: string; same_workspace: boolean };

export function PublishSnapshot({
  ws,
  region,
  revision,
  onClose,
}: {
  ws: Workspace;
  region: Region;
  revision: number;
  onClose: (done: boolean) => void;
}) {
  const { reload } = useWorkspaces();
  const [dests, setDests] = useState<Destination[]>([]);
  const [dest, setDest] = useState(ws.id);
  const [summary, setSummary] = useState("Whiteboard snapshot");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const clientId = useRef(newId("snap"));
  const r = {
    x: Math.round(region.x),
    y: Math.round(region.y),
    w: Math.max(1, Math.round(region.w)),
    h: Math.max(1, Math.round(region.h)),
  };
  const preview = `${API}/workspaces/${ws.id}/board/render?revision=${revision}&x=${r.x}&y=${r.y}&w=${r.w}&h=${r.h}`;
  const target = dests.find((d) => d.id === dest);
  const broader = dest !== ws.id;

  useEffect(() => {
    api<{ destinations: Destination[] }>(`/workspaces/${ws.id}/board/snapshot-destinations`)
      .then((x) => setDests(x.destinations))
      .catch((e) => setError(errorMessage(e)));
  }, [ws.id]);

  async function publish() {
    setBusy(true);
    setError(null);
    try {
      await api(`/workspaces/${ws.id}/board/snapshots`, {
        body: {
          revision,
          region: r,
          destination_id: dest,
          summary,
          client_id: clientId.current,
          confirm_audience: broader ? dest : null,
        },
      });
      void reload();
      onClose(true);
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open
      title="Publish snapshot"
      onClose={() => onClose(false)}
      footer={
        <>
          <Button variant="quiet" onClick={() => onClose(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={publish}
            busy={busy}
            busyLabel="Publishing…"
            disabled={!summary.trim() || (broader && !confirmed)}
          >
            {`Publish to ${target?.name ?? ws.name}`}
          </Button>
        </>
      }
    >
      <div className="board-dialog" aria-label="Publish board snapshot" role="group">
        <p className="board-dialog__muted">
          A fixed image of the selected region at revision {revision}. Later board edits, erasing, or
          restoring will not change the published copy.
        </p>
        <img className="snapshot-preview" src={preview} alt="Preview of the selected board region" />
        <Select
          label="Post to"
          value={dest}
          onChange={(e) => {
            setDest(e.target.value);
            setConfirmed(false);
          }}
          options={dests.map((d) => ({
            value: d.id,
            label: `${d.name}${d.same_workspace ? " (this workspace)" : " (parent unit)"}`,
          }))}
        />
        <TextArea
          label="Summary"
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          rows={2}
          maxLength={2000}
        />
        {broader && (
          <Checkbox
            label={`Everyone who can read ${target?.name} will see this image. That is a broader audience than ${ws.name}.`}
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
        )}
        {error && (
          <p className="board-dialog__error" role="alert">
            {error}
          </p>
        )}
      </div>
    </Dialog>
  );
}
