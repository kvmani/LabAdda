import type { HelpEntry } from "./types";

const TITLE_WEIGHT = 5;
const HEADING_WEIGHT = 3;
const SUMMARY_WEIGHT = 1;

function score(entry: HelpEntry, words: string[]): number {
  const title = entry.title.toLowerCase();
  const headings = entry.headings.join(" ").toLowerCase();
  const summary = entry.summary.toLowerCase();
  let total = 0;
  for (const word of words) {
    const found = [
      title.includes(word) ? TITLE_WEIGHT : 0,
      headings.includes(word) ? HEADING_WEIGHT : 0,
      summary.includes(word) ? SUMMARY_WEIGHT : 0,
    ];
    const points = found.reduce((sum, weight) => sum + weight, 0);
    if (points === 0) return 0;
    total += points;
  }
  return total;
}

/** Pages whose title, summary or headings contain every word typed, best match first. Runs locally. */
export function searchHelp(entries: HelpEntry[], query: string): HelpEntry[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  return entries
    .map((entry) => ({ entry, points: score(entry, words) }))
    .filter((match) => match.points > 0)
    .sort((a, b) => b.points - a.points || a.entry.title.localeCompare(b.entry.title))
    .map((match) => match.entry);
}
