import type { BoardDocument, BoardObject } from "./types";

type Draft = { key: string; document: BoardDocument; objects: BoardObject[] };
const drafts = new Map<string, Draft>();
let identity: string | null = null;

function sessionKey(key: string) {
  return key.split(":").slice(0, 2).join(":");
}

/** Drafts survive route changes only in this tab and authenticated session, never browser storage. */
export function boardDraft(key: string): Draft | null {
  if (identity !== sessionKey(key)) {
    drafts.clear();
    identity = sessionKey(key);
  }
  return drafts.get(key) ?? null;
}
export function rememberBoard(value: Draft) {
  if (identity !== sessionKey(value.key)) drafts.clear();
  identity = sessionKey(value.key);
  drafts.set(value.key, value);
}
export function clearBoardDraft(key?: string) {
  if (key) drafts.delete(key);
  else {
    drafts.clear();
    identity = null;
  }
}

/** A late save from an old identity must never mutate another session's cache. */
export function clearSavedBoard(key: string, objects: BoardObject[]) {
  if (drafts.get(key)?.objects === objects) drafts.delete(key);
}
export function hasBoardDrafts() {
  return drafts.size > 0;
}
