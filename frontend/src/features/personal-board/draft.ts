import type { BoardDocument, BoardObject } from "./types";

type Draft = { key: string; document: BoardDocument; objects: BoardObject[] };
let current: Draft | null = null;

/** Drafts survive route changes only in this tab and authenticated session, never browser storage. */
export function boardDraft(key: string): Draft | null {
  if (current?.key !== key) current = null;
  return current;
}
export function rememberBoard(value: Draft) {
  current = value;
}
export function clearBoardDraft(key?: string) {
  if (!key || current?.key === key) current = null;
}
