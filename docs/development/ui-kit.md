# UI kit guide

How to use and extend the shared component library in `frontend/src/ui/`. The contract for how
things look and behave is [ui-design-system.md](ui-design-system.md) (UX-01–UX-14); this guide
says where the code is and how to work with it. Delivered by package U1.

## Where things are

| Path | Holds |
| --- | --- |
| `frontend/src/ui/tokens.css` | Every design token, light and dark (UX-01). The only place literal colours and sizes may appear |
| `frontend/src/ui/theme.ts` | System / Light / Dark choice in `localStorage`; `index.html` applies it before first paint |
| `frontend/src/ui/index.ts` | Public entry point. Import components from `../ui`, not from their files |
| `frontend/src/ui/<Component>.tsx` | One component per file, `ui-` prefixed classes, typed props |
| `frontend/src/ui/*.css` | Styles by group: `button`, `field`, `display`, `overlay`, `navigation`, `table`, `base` |
| `frontend/src/ui/focus.ts` | `useFocusTrap` for modal surfaces; `focusableWithin` |
| `frontend/src/ui/*.test.ts(x)` | Vitest + Testing Library tests; each file starts with `// @vitest-environment jsdom` |
| `frontend/src/ui/charts/` | Chart components, `scale.ts`, `downsample.ts` and `charts.css` (see Charts below) |
| `frontend/src/ui/gallery/Gallery.tsx` | Development-only page at `/_ui` showing every component and state |
| `e2e/ui-kit.mjs` | Browser check of the gallery: axe-core in both themes at 1400 px and 390 px, dialog focus |

## Using components

```tsx
import { Button, DataTable, PageHeader, type Column } from "../ui";
```

- Build screens from these components; do not restyle them in a page. If one lacks a variant you
  need, add the variant to the component (with a test and a gallery entry).
- Components set no outer margins. Space them with the layout: `gap`, padding, or a wrapper.
- Every form control is a complete labelled field (`TextInput label="…"`). Pass `error` to mark
  it invalid and announce the message; pass `hint` for help text.
- Buttons default to `type="button"`. Use `type="submit"` only for the form's main action.
- Use `ConfirmDialog` for anything that changes access or cannot be undone, with consequences in
  plain sentences and `requireReason` when the API takes a reason.
- Success after a save: `useToast()("Note saved.")` inside `ToastProvider`. Errors stay inline.

`SearchInput` accepts an optional controlled `value` for URL-driven filters. It
updates the existing input, preserving focus; `initialValue` remains the
uncontrolled starting value. Keep `onSearch` idempotent for unchanged queries.

## Adding or changing a component

1. Write the component in its own file, typed props with a one-line doc comment each where the
   meaning is not obvious. Use tokens only; add a token to `tokens.css` (both themes) if needed.
2. Write its test: accessible name, keyboard operation, focus behaviour, states. Query by role
   and name (`getByRole("button", { name: "…" })`), never by class.
3. Export it from `index.ts` and add every state to the gallery.
4. Run `npm run lint && npm run typecheck && npx vitest run` and `node e2e/ui-kit.mjs`.

## Charts

Pure SVG components in `frontend/src/ui/charts/` (UX-09, package U3); no charting library.
Import `Sparkline`, `LineChart`, `AreaChart`, `BarChart`, `HeatGrid` and `Meter` from `../ui`.

```tsx
<LineChart
  title="Sessions"
  series={[{ label: "Sessions", points: [{ t: 1_762_646_400_000, value: 31 }, { t: 1_762_650_000_000, value: null }] }]}
  unit="sessions"
  period="Last 24 hours"
  updated="Updated 12 s ago"
/>
```

- Data is `{ label, points: { t, value | null }[] }` with `t` in epoch milliseconds. `null` is a gap
  (a broken line, an empty cell, no bar), never zero. Pass at most four series.
- `period` is required; `updated` is shown as "Update time unknown" when you do not have it.
- Line, area and bar charts and the heat grid have one tab stop: arrow keys read each point (up and
  down change series or row), Home and End jump, Escape stops. The reading is shown under the
  chart and announced with label, time and value with unit ("no data" for a gap).
- "View as table" shows the same data in a `DataTable`; every chart except `Sparkline` and
  `Meter` has it. `Sparkline` is a summary inside a `StatTile` and `Meter` prints its numbers.
- Series colours are `--chart-1` to `--chart-4`; series also differ by mark shape and line dash
  (bars by fill pattern), and a legend appears only with more than one series.
- Line and area series above 400 points are downsampled to each bucket's lowest and highest real
  sample, so peaks and gaps survive; the table view keeps every sample. Bar charts are for tens of
  categories, not thousands.
- `Meter` takes a limit and optional `warnAt` and `dangerAt` and shows a word and icon with the
  colour; `value={null}` shows "Not measured".
- Shared maths is in `charts/scale.ts` (linear and time scales, nice ticks) with unit tests.

## Checks

```bash
cd frontend && npx vitest run src/ui        # component tests (fast)
cd .. && node e2e/ui-kit.mjs /tmp/ui-kit     # starts Vite on port 5199; set LABADDA_CHROMIUM if needed
```

`scripts/verify.sh --e2e` runs the ui-kit check after the main flows. Open
`http://127.0.0.1:5173/_ui` during `npm run dev` to compare a screen with the reference.

## Decisions and limits

- **Every screen follows the theme.** U4 moved the last screens onto the semantic tokens, so the
  app no longer forces light. People choose Follow the system, Light or Dark in the account menu
  (`features/shell/TopBar.tsx`); `styles.css` holds resets only. The whiteboard canvas stays white
  in both themes because pen colours are chosen for white. `e2e/accessibility.mjs` runs in either
  theme with `LABADDA_E2E_THEME=dark`.
- **The dark theme is declared twice** in `tokens.css` (explicit choice and system preference)
  because CSS cannot share the block; `theme.test.ts` fails if the two differ.
- **No native `<dialog>`**: jsdom cannot open it, so focus trapping could not be unit-tested.
  `Dialog` and `Drawer` use `useFocusTrap` with a portal and `aria-modal`.
- The gallery is removed from production builds by `import.meta.env.DEV`; check with
  `grep -l "Component gallery" frontend/dist/assets/*` (no output).
