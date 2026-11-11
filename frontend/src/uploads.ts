import { api, ApiError, newId } from "./api";
import type { Attachment } from "./types";

export type UploadedAsset = Attachment & { status: string };
type Receipt = { state: "pending" | "complete" | "failed" | "expired"; asset: UploadedAsset | null };
export type UploadAttempt = {
  key: string;
  file: File;
  started: number;
  busy: boolean;
  message: string;
  retryable: boolean;
};
const RETRY_WINDOW_MS = 23 * 60 * 60 * 1000; // Conservative margin inside server's 24h identity window.

/** Bounded, in-memory attempts. Never persist file bytes or automatically repeat a write. */
export class UploadQueue {
  private attempts: UploadAttempt[] = [];
  private listeners = new Set<() => void>();
  private closed = false;
  constructor(
    private maxBytes: number,
    private completed: (asset: UploadedAsset) => void,
  ) {}
  snapshot = () => this.attempts;
  open() {
    this.closed = false;
  }
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  close() {
    this.closed = true;
    this.attempts = [];
    this.listeners.clear();
  }
  private update(key: string, changes: Partial<UploadAttempt>) {
    if (this.closed) return;
    this.attempts = this.attempts.map((a) => (a.key === key ? { ...a, ...changes } : a));
    this.listeners.forEach((f) => f());
  }
  dismiss(key: string) {
    if (this.attempts.find((a) => a.key === key)?.busy) return;
    this.attempts = this.attempts.filter((a) => a.key !== key);
    this.listeners.forEach((f) => f());
  }
  add(files: File[], slots: number) {
    if (this.closed) return;
    const room = Math.max(0, slots - this.attempts.length);
    const selected = files.slice(0, room);
    if (files.length > room)
      throw new Error(`Choose up to ${room} more files, including unresolved uploads.`);
    if (selected.some((f) => f.size > this.maxBytes))
      throw new Error(`Each file must be ${this.maxBytes / 1048576} MiB or smaller.`);
    // Reserve every slot synchronously before starting any asynchronous work.
    const added = selected.map((file) => ({
      key: newId("upload"),
      file,
      started: Date.now(),
      busy: false,
      message: "",
      retryable: true,
    }));
    this.attempts = [...this.attempts, ...added];
    for (const attempt of added) void this.send(attempt.key);
  }
  private eligible(key: string) {
    const attempt = this.attempts.find((a) => a.key === key);
    if (this.closed || !attempt || attempt.busy) return;
    if (Date.now() - attempt.started >= RETRY_WINDOW_MS || Date.now() < attempt.started) {
      this.update(key, {
        retryable: false,
        message:
          "This upload is too old to retry safely. Inspect your storage and original destination before uploading again.",
      });
      return;
    }
    return attempt;
  }
  private accept(key: string, asset: UploadedAsset) {
    if (this.closed) return;
    if (asset.status !== "provisional") {
      this.update(key, {
        busy: false,
        retryable: false,
        message: "This file has already been used. Check its original destination.",
      });
      return;
    }
    this.update(key, { busy: false });
    this.dismiss(key);
    this.completed(asset);
  }
  async send(key: string) {
    const attempt = this.eligible(key);
    if (!attempt || !attempt.retryable) return;
    this.update(key, { busy: true, message: "Uploading…" });
    const form = new FormData();
    form.append("file", attempt.file);
    try {
      this.accept(key, await api<UploadedAsset>("/uploads", { form, uploadKey: key }));
    } catch (error) {
      const e = error as ApiError;
      const retryable =
        e.code === "offline" ||
        e.code === "response_unconfirmed" ||
        e.status >= 500 ||
        e.code === "upload_in_progress";
      this.update(key, {
        busy: false,
        retryable,
        message: retryable
          ? "Upload outcome is unconfirmed. Check the result or retry this same file; do not select another copy."
          : e.message,
      });
    }
  }
  async check(key: string) {
    const attempt = this.eligible(key);
    if (!attempt) return;
    this.update(key, { busy: true, message: "Checking upload…" });
    try {
      const receipt = await api<Receipt>(`/uploads/requests/${key}`);
      if (receipt.state === "complete" && receipt.asset) return this.accept(key, receipt.asset);
      this.update(key, {
        busy: false,
        retryable: receipt.state === "pending",
        message:
          receipt.state === "pending"
            ? "This upload is still pending. Wait, then check again."
            : "This attempt did not complete. Inspect your storage before starting another upload.",
      });
    } catch (error) {
      const e = error as ApiError;
      this.update(key, {
        busy: false,
        retryable:
          attempt.retryable && (e.code === "offline" || e.code === "response_unconfirmed" || e.status >= 500),
        message:
          e.status === 404 || e.status === 410
            ? "No accessible upload result was found. Inspect your storage and original destination before uploading again."
            : e.message,
      });
    }
  }
}
