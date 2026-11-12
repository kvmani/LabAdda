import { useEffect, useRef, useState } from "react";
import { api, errorMessage, errorStatus } from "../../api";
import { Button } from "../../ui";
import type { Period } from "./types";

/** Saves the page's own protected figures as CSV; the server records the export. */
export function ExportActivity({ period, onDenied }: { period: Period; onDenied: () => void }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const alive = useRef(true);
  const objectUrl = useRef<string | null>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    };
  }, []);
  async function download() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const blob = await api<Blob>("/admin/analytics/export.csv", {
        responseType: "blob",
        params: { period },
      });
      if (!alive.current) return;
      if (!blob.type.startsWith("text/csv")) throw new Error("The report could not be read. Try again.");
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl.current;
      link.download = `activity-${period}.csv`;
      link.click();
      setMessage("Report prepared. The export itself is recorded in the audit trail.");
    } catch (failure: unknown) {
      if (!alive.current) return;
      if ([401, 403].includes(errorStatus(failure) ?? 0)) onDenied();
      setError(errorMessage(failure));
    } finally {
      if (alive.current) setBusy(false);
    }
  }
  return (
    <div className="activity-export">
      <Button icon="download" busy={busy} busyLabel="Preparing report…" onClick={() => void download()}>
        Export figures
      </Button>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
    </div>
  );
}
