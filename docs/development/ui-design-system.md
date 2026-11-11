# UI design system

The contract for how LabAdda looks and behaves. Requirement IDs `UX-01`–`UX-14` are normative
and are summarised in [SPECIFICATIONS.md S12](../../SPECIFICATIONS.md). Build every screen from
this document; do not design a screen from scratch.

**Character.** A calm, modern office tool: light surfaces, generous but not wasteful spacing,
one accent colour, clear type, quiet motion. It should feel as considered as a good commercial
product while staying obviously safe for long working days. No decoration for its own sake: no
gradients, hero banners, stock art, emoji in headings, or animation that does not explain a
change of state.

Every screen answers three questions without hunting: *Where am I and who can see this? What
needs my attention? What can I safely do next?*

## UX-01 Tokens

All colour, spacing, radius, shadow and type sizes come from CSS custom properties defined once
in `frontend/src/ui/tokens.css`. Components never use literal colours or pixel sizes.

| Group | Tokens | Notes |
| --- | --- | --- |
| Surface | `--surface-page`, `--surface-card`, `--surface-raised`, `--surface-sunken` | Light and dark values |
| Text | `--text`, `--text-muted`, `--text-on-accent` | Muted still meets 4.5:1 |
| Line | `--line`, `--line-strong` | |
| Accent | `--accent`, `--accent-hover`, `--accent-soft` | One brand blue; keep `#1d4ed8` family |
| Status | `--ok`, `--warn`, `--danger`, `--info`, `--neutral`, each with `-soft` background | Always paired with an icon and a word |
| Space | `--space-1` … `--space-8` = 4, 8, 12, 16, 24, 32, 48, 64 px | Only these steps |
| Radius | `--radius-sm` 6, `--radius-md` 10, `--radius-lg` 14 | |
| Shadow | `--shadow-1` (cards), `--shadow-2` (menus, dialogs) | Soft, low contrast |
| Type | `--font-ui` (system UI stack), `--font-mono`; sizes 12, 13, 14, 16, 20, 24, 32 | 14 px body, 1.5 line height |
| Motion | `--motion-fast` 120 ms, `--motion-base` 200 ms | Disabled under `prefers-reduced-motion` |

Dark theme: tokens are redefined under `@media (prefers-color-scheme: dark)` and under
`:root[data-theme="dark"]`; a user setting (System / Light / Dark) is stored per browser. Fonts
are the operating system's; no font files are downloaded or bundled.

## UX-02 Components

Shared components live in `frontend/src/ui/`, one file each, with typed props and a Vitest file.
A page may not restyle a component; add a variant to the component instead.
Components set no outer margins; the layout around them spaces them with `gap` or padding.

| Component | Purpose and required behaviour |
| --- | --- |
| `Button` | Variants primary, secondary, quiet, danger; sizes md, sm; `busy` state disables and shows progress text |
| `IconButton` | Icon plus required `label` (visible tooltip and accessible name) |
| `Field`, `TextInput`, `TextArea`, `Select`, `Checkbox`, `Switch`, `DateInput` | Label, optional hint, error text linked with `aria-describedby` |
| `SearchInput` | Debounced, clear button, announces result count |
| `Dialog` | Modal with focus trap, Escape to close, title, body, action row; `ConfirmDialog` adds a consequence summary and optional required reason |
| `Drawer` | Right-side detail panel that keeps the list visible; closes with Escape; deep-linkable |
| `Tabs` | Roving focus, each tab is a URL |
| `DataTable` | Caption, sortable headers, sticky header, row open action, pagination or "load more", column for row actions, empty and loading states, horizontal scroll inside the table only |
| `StatusPill` | Icon + word for `healthy`, `degraded`, `unavailable`, `stale`, `unknown`, `unsupported` and for person and unit states |
| `Badge`, `Tag` | Counts and labels |
| `Card`, `StatTile` | `StatTile`: label, value with unit, comparison to the previous period, freshness, link to detail |
| `PageHeader` | Title, one-line scope statement, primary action, help link |
| `EmptyState`, `ErrorState`, `Skeleton` | What this is, why it is empty or failed, the next action |
| `Toast` | Non-blocking confirmation after a durable save; errors stay inline, not in toasts |
| `Menu`, `Tooltip`, `Breadcrumbs`, `Avatar` | Avatar shows initials on a colour derived from the user ID |
| `Icon` | Inline SVG from a local set in `ui/icons/`; stroke icons, 20 px grid, `currentColor` |
| `TreeView` | Expand/collapse, arrow-key navigation, used for the rail and the organisation chart |
| `Stepper` | Multi-step dialogs (transfer, retirement, import) with a review step |

## UX-03 Layout

- **Shell.** Top bar (product name, current workspace, search, notifications, help, user menu)
  and a left rail (workspace tree, personal entries). Content area max width 1280 px for
  reading pages, full width for boards, tables and dashboards.
- **Admin console.** Its own left navigation inside the shell, grouped: *Overview* · *People* ·
  *Organisation* · *Activity* · *System health* · *Storage* · *Backups* · *Audit* · *Events* ·
  *Settings* · *Help for administrators*.
- **List + detail.** Lists open details in a `Drawer`, so the list keeps its place and filters.
- **Forms.** One column, labels above inputs, related fields grouped, primary action bottom
  right of the form, destructive action separated and styled `danger`.
- **Breakpoints.** ≥ 1200 px full layout; 900–1199 px rail collapses to icons; < 900 px rail
  becomes a labelled switcher and tables scroll inside their own region. Nothing may cause the
  page itself to scroll sideways at 390 px.

## UX-04 States

Every data region implements all of: loading (skeleton shaped like the content), empty, error
with retry, forbidden, offline, and — for forms — saving, saved, failed, conflict. Success is
shown only after the server confirms the commit. A failed save keeps what the user typed.

## UX-05 Words

- Plain English, sentence case, no jargon. Say "people" not "identities", "unit" for an
  organisation node, "steward" for the person who looks after a workspace.
- Buttons name the action and the object: "Transfer Asha Rao", not "Submit" or "OK".
- Errors say what happened and what to do next. Never show a code, ID or stack trace as the
  main message; a reference code may appear in small print for support.
- Dates show in the site time zone as "12 Nov 2026, 14:30"; relative time ("3 minutes ago") only
  for the last 24 hours, with the exact time in a tooltip. Sizes use KiB, MiB, GiB.
- Numbers always carry a unit and, on dashboards, the period they cover.

## UX-06 Accessibility

WCAG 2.1 AA. Everything works by keyboard in a logical order with a visible focus ring; a skip
link reaches the content; landmarks and headings are correct; status changes are announced with
`role="status"` or `role="alert"`; colour is never the only signal; touch targets are at least
40 px; text can zoom to 200 % without loss. Every `e2e` suite runs axe-core at 1400 px and 390 px.

## UX-07 Confirmation and consequence

Any action that changes who can see something, removes someone's access, ends a session, or
cannot be undone uses `ConfirmDialog`. The dialog lists, in words, the people and units
affected and what will change for them, and takes a reason when the API requires one. The
confirm button repeats the action ("Retire 1 person"). There is no generic "Are you sure?".

## UX-08 Help in place

Every page header has a help link to its page in the in-app help centre
([HELP-CENTER.md](../HELP-CENTER.md)). Unfamiliar terms have a short tooltip. Empty states teach
the first step. Help never blocks the task and never links outside the server.

## UX-09 Charts

Charts are local SVG React components in `frontend/src/ui/charts/` with no charting library.

| Chart | Use for |
| --- | --- |
| `Sparkline` | Trend inside a `StatTile` |
| `LineChart` / `AreaChart` | A measure over time (sessions, latency, storage) — at most 4 series |
| `BarChart` | Comparing categories or days; stacked only for parts of a whole |
| `HeatGrid` | Activity by weekday × hour |
| `Meter` | One value against a limit (disk, quota) with warn and danger thresholds |

Rules: start value axes at zero for bars; label axes with units; at most 4 categorical colours
from the `--chart-1`…`--chart-4` tokens, distinguishable without colour (shape or direct
labels); a legend only when there is more than one series; hover and keyboard focus show exact
values; every chart has a "View as table" toggle that renders the same data in a `DataTable`;
missing samples are drawn as gaps, never as zero; the chart states its period and when it was
last updated. Charts must stay readable in both themes and at 390 px.

## UX-10 Dashboards

Top to bottom: (1) an **attention list** — what is wrong or due, most serious first, each with
one action; (2) a row of 4–6 `StatTile`s; (3) two to four charts; (4) links to detail pages.
A dashboard with nothing wrong says so plainly. Every number links to the list that explains
it. Auto-refresh is at most every 15 s for health and 60 s for analytics, pauses when the tab
is hidden, and shows "Updated 12 s ago"; data older than its promised freshness is marked stale.

## UX-11 Graphical organisation management

The organisation chart and people moves follow these interaction rules:

- The chart is a `TreeView`-based diagram with collapsible branches, search that reveals and
  highlights matches, zoom, and a side panel for the selected unit.
- Dragging a person or unit **only proposes** a change. It opens the same review step as the
  button flow. Nothing is written until the user confirms the review.
- Every drag action has an equivalent button or menu action ("Move to…", "Transfer…") so the
  whole feature works by keyboard and screen reader.
- The review step shows before and after, everyone whose access changes, and warnings (for
  example, a unit left without a steward).

## UX-12 Performance budgets

First load of the shell under 2 s on the office network; route change under 300 ms; typing
never blocks; initial JavaScript under 350 KiB gzip with the admin console, board and help
content split into separate chunks loaded on demand. Lists over 100 rows are paginated or
virtualised.

## UX-13 Touch panel

The board-only panel keeps its large-control layout and is not restyled by general shell work.
Any shared component used on the panel must be verified at the panel's size.

## UX-14 Consistency check

Before finishing a screen, compare it with two existing screens built on `ui/`: same header,
spacing steps, button order, wording style and empty/error patterns. Differences need a reason.
