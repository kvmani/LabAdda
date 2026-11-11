# Track U — interface and design system

Contract: [ui-design-system.md](../development/ui-design-system.md) (UX-01–UX-14).
Goal of the track: one coherent, modern, accessible look, built from shared components.

### U1 · Design tokens and core components

Size L. Depends on Q2.

**Goal.** `frontend/src/ui/` exists with tokens and the components that every later package uses.

**Build.**

1. `ui/tokens.css` with every token group in UX-01, light and dark values, imported once in
   `main.tsx`. Map the existing variables in `styles.css` (`--bg`, `--panel`, `--ink` …) to
   the new tokens so current screens keep working unchanged.
2. Components, one file each plus a Vitest file, in this order (commit after each group):
   (a) `Button`, `IconButton`, `Icon` with a starter icon set; (b) `Field`, `TextInput`,
   `TextArea`, `Select`, `Checkbox`, `Switch`, `DateInput`, `SearchInput`; (c) `Card`,
   `PageHeader`, `Badge`, `Tag`, `StatusPill`, `Avatar`, `EmptyState`, `ErrorState`, `Skeleton`;
   (d) `Dialog`, `ConfirmDialog`, `Drawer`, `Menu`, `Tooltip`, `Toast`; (e) `Tabs`,
   `Breadcrumbs`, `DataTable`, `Stepper`, `TreeView`.
3. Add `@testing-library/react`, `@testing-library/user-event` and `jsdom` as dev dependencies
   for component tests (exact versions, lock file).
4. A development-only route `/_ui` (not built into production; guard with
   `import.meta.env.DEV`) that renders every component in every state, in both themes. This is
   the reference agents compare against.
5. Theme setting (System / Light / Dark) stored in `localStorage`, applied before first paint.

**Acceptance.** Each component: keyboard operation, focus management and accessible name are
unit-tested; `Dialog` and `Drawer` trap and restore focus; `DataTable` sorts and announces.
`e2e/ui-kit.mjs` opens `/_ui` on the dev build and runs axe-core in both themes at 1400 px and
390 px with zero violations. Existing browser checks still pass unchanged.

**Not in this package.** Changing any existing screen.

### U2 · Application shell refresh

Size M. Depends on U1.

**Goal.** The top bar and rail are rebuilt on `ui/` per UX-03, with a user menu and help entry.

**Build.** Rewrite `components/Shell.tsx` using `TreeView` for the workspace tree, `Menu` for
the user menu (My profile, Alert preferences, Theme, Sign out), `Breadcrumbs`, a notifications
button, a help button (links to `/help`; placeholder page until H1), and the three responsive
layouts. Keep every existing route, label that browser checks rely on, skip link and landmark.
Do not change the board-only panel (UX-13).

**Acceptance.** All existing browser checks pass (update selectors only where the accessible
name is unchanged in meaning; record each change). Accessibility audit passes at three widths.
Deep links survive refresh at `/` and `/labadda-staging`. The narrow layout does not scroll
sideways at 390 px.

**Not in this package.** Restyling page contents (U4).

### U3 · Charts kit

Size M. Depends on U1.

**Goal.** `ui/charts/` provides `Sparkline`, `LineChart`, `AreaChart`, `BarChart`, `HeatGrid`,
`Meter` per UX-09, with no charting dependency.

**Build.** Pure SVG components taking typed series (`{ label, points: { t, value | null }[] }`).
Shared `scale.ts` (linear and time scales, nice ticks) with unit tests. Gaps for `null`.
Keyboard focus moves point to point and announces label, time and value with unit. "View as
table" toggle renders a `DataTable`. Chart colours from `--chart-1…4` tokens verified for
contrast in both themes. Add every chart with sample, empty and gap data to `/_ui`.

**Acceptance.** Scale and tick unit tests; component tests for empty, single point, gaps and
many points (≥ 1 000 points must render under 50 ms — downsample). axe-core clean on `/_ui`.

**Not in this package.** Any real data wiring.

### U4 · Move existing screens onto the design system

Size L. Depends on U2. One screen per commit, in this order: Login and activation →
Noticeboard → Chat and threads → Tasks and My Tasks → My day → Notes → Members and group
settings → Storage/usage pages → Board chrome (toolbar and dialogs only; not the canvas).

**Goal.** No screen uses ad-hoc classes from `styles.css`; `styles.css` shrinks to resets.

**Build.** Replace markup with `ui/` components and UX-03/UX-04 layouts. Keep behaviour, routes
and text meaning. Where wording changes for UX-05, update the browser checks and the help page.
Delete each CSS rule when its last user is gone.

**Acceptance.** Per screen: its browser suite passes; axe-core clean at both widths and themes;
all UX-04 states reachable (show them in the suite by forcing loading, empty and error).
At the end: `styles.css` under 60 lines; UX-12 bundle budget met (`npm run build` output recorded).

**Not in this package.** New features.
