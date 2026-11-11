import { useEffect, useRef, useState } from "react";
import { api, errorMessage, errorStatus } from "../../api";
import { Button } from "../../ui";

/** The report is saved only while its original filter scope is still on screen. */
export function ExportAudit({ url, onDenied }: { url: string; onDenied: () => void }) {
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
      const blob = await api<Blob>(url, { responseType: "blob" });
      if (!alive.current) return;
      if (!blob.type.startsWith("text/csv")) throw new Error("The report could not be read. Try again.");
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl.current;
      link.download = "audit.csv";
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
    <div>
      <Button icon="download" busy={busy} busyLabel="Preparing report…" onClick={() => void download()}>
        Export matching entries
      </Button>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
    </div>
  );
}
