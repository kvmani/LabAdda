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

## Adding or changing a component

1. Write the component in its own file, typed props with a one-line doc comment each where the
   meaning is not obvious. Use tokens only; add a token to `tokens.css` (both themes) if needed.
2. Write its test: accessible name, keyboard operation, focus behaviour, states. Query by role
   and name (`getByRole("button", { name: "…" })`), never by class.
3. Export it from `index.ts` and add every state to the gallery.
4. Run `npm run lint && npm run typecheck && npx vitest run` and `node e2e/ui-kit.mjs`.

## Checks

```bash
cd frontend && npx vitest run src/ui        # component tests (fast)
cd .. && node e2e/ui-kit.mjs /tmp/ui-kit     # starts Vite on port 5199; set LABADDA_CHROMIUM if needed
```

`scripts/verify.sh --e2e` runs the ui-kit check after the main flows. Open
`http://127.0.0.1:5173/_ui` during `npm run dev` to compare a screen with the reference.

## Decisions and limits

- **Legacy screens stay light until U2/U4.** `styles.css` variables point at the fixed
  `--palette-*` tokens, and native colour scheme is a token applied only by ui/ components, so
  an OS dark setting does not half-restyle screens that were not designed for it. U2 (shell) and
  U4 (screens) switch each screen to the semantic tokens; delete the palette when `styles.css`
  no longer uses it.
- **The dark theme is declared twice** in `tokens.css` (explicit choice and system preference)
  because CSS cannot share the block; `theme.test.ts` fails if the two differ.
- **No native `<dialog>`**: jsdom cannot open it, so focus trapping could not be unit-tested.
  `Dialog` and `Drawer` use `useFocusTrap` with a portal and `aria-modal`.
- The gallery is removed from production builds by `import.meta.env.DEV`; check with
  `grep -l "Component gallery" frontend/dist/assets/*` (no output).
