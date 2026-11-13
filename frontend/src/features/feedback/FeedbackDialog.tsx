import { useEffect, useRef, useState, type ClipboardEvent, type DragEvent } from "react";
import { useLocation } from "react-router-dom";
import { api, errorMessage } from "../../api";
import { fmtBytes, fmtTime } from "../../format";
import { Button, Dialog, ErrorState, Select, Skeleton, TextArea } from "../../ui";
import { ACCEPT_ATTRIBUTE, CATEGORY_OPTIONS, admitFiles, namePasted } from "./model";
import type { FeedbackCategory, FormFacts } from "./types";
import "./feedback.css";

type Phase = "editing" | "sending" | "sent";

const newRequestId = (): string =>
  typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`.padEnd(8, "0");

/** Sends a message to the administrators; the draft stays until the server confirms it saved. */
export function FeedbackDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const location = useLocation();
  const [facts, setFacts] = useState<FormFacts | null>(null);
  const [loadError, setLoadError] = useState("");
  const [category, setCategory] = useState<FeedbackCategory>("problem");
  const [message, setMessage] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [problems, setProblems] = useState<string[]>([]);
  const [phase, setPhase] = useState<Phase>("editing");
  const [error, setError] = useState("");
  const [over, setOver] = useState(false);
  const requestId = useRef(newRequestId());
  const picker = useRef<HTMLInputElement>(null);
  const page = useRef(location.pathname);

  useEffect(() => {
    if (!open) return;
    page.current = location.pathname;
    let current = true;
    setLoadError("");
    api<FormFacts>("/feedback/form")
      .then((answer) => current && setFacts(answer))
      .catch((failure: unknown) => current && setLoadError(errorMessage(failure)));
    return () => {
      current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reacts to opening only, not to later navigation
  }, [open]);

  const limits = {
    maxFiles: facts?.max_files ?? 5,
    maxFileBytes: facts?.max_file_bytes ?? 10 * 1024 * 1024,
    maxTotalBytes: facts?.max_total_bytes ?? 25 * 1024 * 1024,
  };
  const add = (chosen: File[]) => {
    const result = admitFiles(files, chosen, limits);
    setFiles(result.files);
    setProblems(result.problems);
  };
  const onPaste = (event: ClipboardEvent) => {
    const pasted = Array.from(event.clipboardData.files);
    if (pasted.length === 0) return;
    event.preventDefault();
    add(pasted.map(namePasted));
  };
  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    add(Array.from(event.dataTransfer.files));
  };

  async function send() {
    if (!message.trim()) {
      setError("Write what you want to tell the administrators.");
      return;
    }
    setPhase("sending");
    setError("");
    const form = new FormData();
    form.set("client_id", requestId.current);
    form.set("category", category);
    form.set("message", message);
    form.set("route", page.current);
    form.set("screen", `${window.innerWidth}x${window.innerHeight}`);
    for (const file of files) form.append("files", file, file.name);
    try {
      await api("/feedback", { form });
      setPhase("sent");
    } catch (failure) {
      setError(errorMessage(failure));
      setPhase("editing");
    }
  }

  function finish() {
    if (phase === "sent") {
      setMessage("");
      setFiles([]);
      setProblems([]);
      setCategory("problem");
      setPhase("editing");
      requestId.current = newRequestId();
    }
    onClose();
  }

  if (phase === "sent")
    return (
      <Dialog
        open={open}
        title="Feedback sent"
        onClose={finish}
        footer={
          <Button variant="primary" onClick={finish}>
            Close
          </Button>
        }
      >
        <p role="status">Sent to the administrators. Thank you.</p>
      </Dialog>
    );

  const sending = phase === "sending";
  return (
    <Dialog
      open={open}
      title="Send feedback"
      onClose={finish}
      footer={
        <>
          <Button onClick={finish} disabled={sending}>
            Cancel
          </Button>
          <Button variant="primary" onClick={() => void send()} disabled={sending || !facts}>
            {sending ? "Sending…" : "Send to the administrators"}
          </Button>
        </>
      }
    >
      <div className="feedback-form" onPaste={onPaste}>
        <p className="feedback-notice">
          Administrators will read this message and its attachments. Do not include passwords.
        </p>
        <Select
          label="What is this about?"
          options={CATEGORY_OPTIONS}
          value={category}
          onChange={(changed) => setCategory(changed.target.value as FeedbackCategory)}
          disabled={sending}
        />
        <TextArea
          label="Your message"
          hint="Say what you were doing and what happened. You can paste a screenshot here."
          rows={6}
          maxLength={facts?.max_message ?? 5000}
          value={message}
          required
          disabled={sending}
          onChange={(changed) => setMessage(changed.target.value)}
        />
        <div
          className={`feedback-drop${over ? " feedback-drop--over" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={onDrop}
        >
          <p>
            Drop screenshots or files here, paste a picture, or choose files. Up to {limits.maxFiles} files,
            each {fmtBytes(limits.maxFileBytes)} or smaller (pictures, PDF or text).
          </p>
          <input
            ref={picker}
            type="file"
            multiple
            hidden
            accept={ACCEPT_ATTRIBUTE}
            aria-label="Attach screenshots or files"
            onChange={(changed) => {
              add(Array.from(changed.target.files ?? []));
              changed.target.value = "";
            }}
          />
          <div>
            <Button icon="plus" onClick={() => picker.current?.click()} disabled={sending}>
              Attach screenshots or files
            </Button>
          </div>
          {files.length > 0 && (
            <ul className="feedback-files" aria-label="Files to send">
              {files.map((file) => (
                <li key={`${file.name}-${file.size}-${file.lastModified}`}>
                  <span>
                    {file.name} ({fmtBytes(file.size)})
                  </span>
                  <Button
                    size="sm"
                    variant="quiet"
                    aria-label={`Remove ${file.name}`}
                    disabled={sending}
                    onClick={() => setFiles(files.filter((other) => other !== file))}
                  >
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {problems.length > 0 && (
            <ul role="alert" className="feedback-files">
              {problems.map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
          )}
        </div>
        <section aria-label="Details sent with your message">
          <h3>Sent with your message</h3>
          {loadError ? (
            <ErrorState message={loadError} />
          ) : facts ? (
            <dl className="feedback-facts">
              <dt>Your username</dt>
              <dd>{facts.username}</dd>
              <dt>Time</dt>
              <dd>{fmtTime(facts.time)}</dd>
              <dt>Software version</dt>
              <dd>{facts.software_version}</dd>
              <dt>Commit</dt>
              <dd>{facts.commit}</dd>
              <dt>Page</dt>
              <dd>{page.current}</dd>
            </dl>
          ) : (
            <Skeleton />
          )}
        </section>
        {error && <p role="alert">{error} Your message is kept. You can send it again.</p>}
      </div>
    </Dialog>
  );
}
