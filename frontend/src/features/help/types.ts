export type ShelfId = "using" | "stewards" | "admin" | "operator" | "troubleshooting" | "reference";

/** One help page as listed in the compiled index (see scripts/build-help.mjs). */
export type HelpEntry = {
  slug: string;
  shelf: ShelfId;
  title: string;
  summary: string;
  audience: "everyone" | "steward" | "administrator" | "operator";
  /** The route this page explains, or null for a page that belongs to no single screen. */
  screen: string | null;
  updated: string;
  headings: string[];
};
