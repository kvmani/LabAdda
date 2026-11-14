export type StickyShape = "rectangle" | "circle" | "hexagon" | "diamond" | "cloud" | "star";
export type StickySize = "small" | "medium" | "large";
export type DrawMode = "pen" | "pencil" | "brush" | "line" | "arrow" | "rect" | "circle";

export type StickyConfig = {
  shape: StickyShape;
  size: StickySize;
  color: string;
  text: string;
};

export const STICKY_COLORS = [
  "#fff59d", // Pastel Yellow
  "#b3e5fc", // Pastel Sky Blue
  "#c8e6c9", // Pastel Mint Green
  "#ffccbc", // Pastel Coral
  "#e1bee7", // Pastel Lavender
  "#ffe082", // Pastel Amber
] as const;

export const PEN_COLORS = [
  "#1f2933", // Charcoal/Black
  "#c62828", // Crimson Red
  "#1565c0", // Cobalt Blue
  "#2e7d32", // Forest Green
  "#ef6c00", // Amber Orange
  "#6a1b9a", // Deep Purple
  "#00838f", // Teal
  "#d81b60", // Rose Pink
  "#757575", // Graphite Grey
] as const;
