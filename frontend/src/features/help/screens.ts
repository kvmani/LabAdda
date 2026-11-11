import { matchPath } from "react-router-dom";
import type { HelpEntry } from "./types";

/** The page that explains the screen at `pathname`, if any. The help centre never explains itself. */
export function entryForRoute(entries: HelpEntry[], pathname: string): HelpEntry | null {
  if (pathname === "/help" || pathname.startsWith("/help/")) return null;
  return entries.find((entry) => entry.screen !== null && matchPath(entry.screen, pathname)) ?? null;
}
