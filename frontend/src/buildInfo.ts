/** Which software this is: the version, commit and date stamped into this build. */
export const CREDIT = "Software conceived and developed by Dr. K. V. Mani Krishna, Materials Group.";

const SHORT_COMMIT = /^[0-9a-f]{7,40}$/i;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** "0.0.1-beta" is shown to people as "0.0.1 beta". */
export function versionLabel(version: string): string {
  return version.replace(/-/g, " ");
}

/**
 * "Version 0.0.1 beta · commit 7a94edc · 2026-11-13". An unknown commit says so and is never made up;
 * an unknown date is left out.
 */
export function formatBuildLine(version: string, commit: string, commitDate: string): string {
  const parts = [`Version ${versionLabel(version)}`];
  const id = commit.trim();
  parts.push(SHORT_COMMIT.test(id) ? `commit ${id.slice(0, 7).toLowerCase()}` : "commit unknown");
  if (DATE.test(commitDate.trim())) parts.push(commitDate.trim());
  return parts.join(" · ");
}

export const APP_VERSION = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "0.0.0";
export const APP_COMMIT = typeof __APP_COMMIT__ !== "undefined" ? __APP_COMMIT__ : "";
export const APP_COMMIT_DATE = typeof __APP_COMMIT_DATE__ !== "undefined" ? __APP_COMMIT_DATE__ : "";
export const BUILD_LINE = formatBuildLine(APP_VERSION, APP_COMMIT, APP_COMMIT_DATE);
