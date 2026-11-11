/**
 * Local stroke icon set on a 20-unit grid (UX-02). Each entry is SVG path data drawn with
 * `stroke="currentColor"`, so icons take the surrounding text colour. Add icons here; never load
 * icon fonts or images from outside the server.
 */
export const ICONS = {
  check: "M4 10.5l4 4 8-9",
  close: "M5 5l10 10M15 5L5 15",
  plus: "M10 4v12M4 10h12",
  minus: "M4 10h12",
  "chevron-down": "M5 8l5 5 5-5",
  "chevron-up": "M5 12l5-5 5 5",
  "chevron-right": "M8 5l5 5-5 5",
  "chevron-left": "M12 5l-5 5 5 5",
  "arrow-up": "M10 16V4M5 9l5-5 5 5",
  "arrow-down": "M10 4v12M5 11l5 5 5-5",
  search: "M8.5 3.5a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12.2 12.2L16.5 16.5",
  menu: "M3.5 5.5h13M3.5 10h13M3.5 14.5h13",
  more: "M5 10h.01M10 10h.01M15 10h.01",
  info: "M10 2.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15zM10 9v5M10 6.2v.01",
  help: "M10 2.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15zM7.8 7.8a2.2 2.2 0 1 1 3 2.1c-.6.3-.8.7-.8 1.3v.3M10 14v.01",
  warning: "M10 3l7.5 13h-15L10 3zM10 8v4M10 14.2v.01",
  error: "M10 2.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15zM7.2 7.2l5.6 5.6M12.8 7.2l-5.6 5.6",
  success: "M10 2.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15zM6.5 10.2l2.4 2.4 4.6-5",
  clock: "M10 2.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15zM10 6v4l2.8 1.8",
  calendar: "M4 5.5h12v11H4zM4 9h12M7.5 3.5v3M12.5 3.5v3",
  user: "M10 3.5a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM4 16.5c.7-3 3.1-4.5 6-4.5s5.3 1.5 6 4.5",
  users:
    "M7.5 4a2.6 2.6 0 1 0 0 5.2A2.6 2.6 0 0 0 7.5 4zM2.5 16c.6-2.7 2.6-4 5-4s4.4 1.3 5 4M13 4.3a2.5 2.5 0 0 1 0 4.8M14.5 12.3c1.6.4 2.6 1.6 3 3.7",
  unit: "M4 16.5V4.5h8v12M12 8.5h4v8M2.5 16.5h15M6.5 7.5h1.5M6.5 10.5h1.5M6.5 13.5h1.5",
  edit: "M12.5 4.5l3 3L7 16H4v-3l8.5-8.5z",
  external: "M11 4h5v5M16 4l-7 7M14 11.5V16H4V6h4.5",
  sun: "M10 6.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM10 2v1.5M10 16.5V18M2 10h1.5M16.5 10H18M4.3 4.3l1.1 1.1M14.6 14.6l1.1 1.1M4.3 15.7l1.1-1.1M14.6 5.4l1.1-1.1",
  moon: "M15.5 12.5A6.5 6.5 0 0 1 7.5 4.5a6.5 6.5 0 1 0 8 8z",
  monitor: "M3 4.5h14v9H3zM7 16.5h6M10 13.5v3",
  bell: "M5.5 13.5V9a4.5 4.5 0 0 1 9 0v4.5l1.5 2h-12l1.5-2zM8.5 17.5h3",
  filter: "M3.5 5h13M6 10h8M8.5 15h3",
  download: "M10 3.5v9M6 9l4 4 4-4M4 16.5h12",
  refresh: "M16 10a6 6 0 1 1-1.8-4.3M16 3.5v3.7h-3.7",
} as const;

export type IconName = keyof typeof ICONS;
