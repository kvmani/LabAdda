import type { HelpEntry, ShelfId } from "./types";

export type Shelf = { id: ShelfId; title: string; audience: string };

const STANDARD_SHELVES: Shelf[] = [
  { id: "using", title: "Using LabAdda", audience: "For everyone" },
  { id: "stewards", title: "Looking after a workspace", audience: "For stewards" },
  { id: "admin", title: "Administering LabAdda", audience: "For administrators and unit administrators" },
  { id: "operator", title: "Running the server", audience: "For the person who looks after the server" },
];

/** Glossary and troubleshooting pages share one shelf on the home page. */
export const REFERENCE_SHELF: Shelf = { id: "reference", title: "Words and fixes", audience: "For everyone" };

export function shelfFor(entry: HelpEntry): ShelfId {
  return entry.shelf === "troubleshooting" ? "reference" : entry.shelf;
}

/** The four shelves with the reader's own first (HP-02). */
export function orderShelves(own: ShelfId): Shelf[] {
  return [...STANDARD_SHELVES].sort((a, b) => Number(b.id === own) - Number(a.id === own));
}
