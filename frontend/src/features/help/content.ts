import type { HelpEntry } from "./types";

let pendingIndex: Promise<HelpEntry[]> | null = null;

/** Loads the compiled page list once; a failed load can be retried. */
export function loadHelpIndex(): Promise<HelpEntry[]> {
  if (!pendingIndex) {
    const request = import("./generated/index.json").then((module) => module.default as HelpEntry[]);
    request.catch(() => {
      pendingIndex = null;
    });
    pendingIndex = request;
  }
  return pendingIndex;
}

/** Loads the rendered HTML of one page as its own chunk. */
export async function loadHelpPage(slug: string): Promise<string> {
  const { pageLoaders } = await import("./generated/loaders");
  const loader = pageLoaders[slug];
  if (!loader) throw new Error("No such help page");
  return (await loader()).default;
}
