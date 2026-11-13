import { fmtBytes } from "../../format";
import type { FeedbackCategory, FeedbackStatus, MailState } from "./types";

export const CATEGORY_OPTIONS: { value: FeedbackCategory; label: string }[] = [
  { value: "problem", label: "Something is wrong" },
  { value: "suggestion", label: "A suggestion" },
  { value: "question", label: "A question" },
];
export const STATUS_OPTIONS: { value: FeedbackStatus; label: string }[] = [
  { value: "new", label: "New" },
  { value: "seen", label: "Seen" },
  { value: "resolved", label: "Resolved" },
];
const CATEGORY_WORD: Record<FeedbackCategory, string> = {
  problem: "Problem",
  suggestion: "Suggestion",
  question: "Question",
};
export const categoryWord = (category: FeedbackCategory): string => CATEGORY_WORD[category];
export const statusWord = (status: FeedbackStatus): string =>
  STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status;

export const ACCEPTED_TYPES = ["image/png", "image/jpeg", "image/webp", "application/pdf", "text/plain"];
export const ACCEPT_ATTRIBUTE = ".png,.jpg,.jpeg,.webp,.pdf,.txt," + ACCEPTED_TYPES.join(",");

export type Limits = { maxFiles: number; maxFileBytes: number; maxTotalBytes: number };

/** Decide which chosen files fit; the rest come back as plain sentences, never silently dropped. */
export function admitFiles(
  current: File[],
  chosen: File[],
  limits: Limits,
): { files: File[]; problems: string[] } {
  const files = [...current];
  const problems: string[] = [];
  let total = files.reduce((sum, file) => sum + file.size, 0);
  for (const file of chosen) {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      problems.push(`${file.name} is not a picture, PDF or text file, so it was not added.`);
    } else if (file.size === 0) {
      problems.push(`${file.name} is empty, so it was not added.`);
    } else if (file.size > limits.maxFileBytes) {
      problems.push(
        `${file.name} is too large. Each file must be ${fmtBytes(limits.maxFileBytes)} or smaller.`,
      );
    } else if (files.length >= limits.maxFiles) {
      problems.push(`${file.name} was not added. You can attach up to ${limits.maxFiles} files.`);
    } else if (total + file.size > limits.maxTotalBytes) {
      problems.push(
        `${file.name} was not added. All files together must be ${fmtBytes(limits.maxTotalBytes)} or smaller.`,
      );
    } else {
      files.push(file);
      total += file.size;
    }
  }
  return { files, problems };
}

let pastedCount = 0;
/** Pictures pasted from the clipboard all arrive as "image.png"; give each a distinct name. */
export function namePasted(file: File): File {
  if (file.name && file.name !== "image.png") return file;
  pastedCount += 1;
  const extension = file.type.split("/")[1] ?? "png";
  return new File([file], `screenshot-${pastedCount}.${extension}`, { type: file.type });
}

export function mailSentence(mail: MailState, configured: boolean): string {
  if (mail.status === "sent") return "E-mailed to the administrators";
  if (mail.status === "failed") return `E-mail failed: ${mail.reason ?? "no reason recorded"}`;
  if (mail.status === "queued")
    return configured ? "E-mail waiting to be sent" : "E-mail not configured. Waiting until it is set up";
  return "No e-mail copy";
}
