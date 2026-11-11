# Frontend instructions

Read the [repository instructions](../AGENTS.md) first. This file adds only what is specific to
`frontend/` and `e2e/`. Full recipes: [standards.md §4](../docs/development/standards.md#4-frontend-react-18-typescript-vite).
Look and behaviour: [ui-design-system.md](../docs/development/ui-design-system.md).

## Where things go

- Shared components and tokens in `src/ui/` (charts in `src/ui/charts/`). Use these first; add
  a variant there rather than restyling in a page.
- New feature code in `src/features/<feature>/` (components, hooks, `types.ts`). `src/pages/`
  holds one thin file per route.
- All requests go through `api<Type>(...)` in `src/api.ts`. Never call `fetch` directly.
- In-app help pages in `src/help/`. Browser checks in `../e2e/<feature>.mjs`.

## Always

- Type every response to mirror `docs/API.md`. No `any`; caught errors are `unknown`.
- Implement every state: loading, empty, error, forbidden, offline, saving, saved, conflict.
  Show success only after the server confirms. Keep the user's draft when a save fails.
- Discard responses that arrive after the scope changed or access was revoked (generation
  counter pattern).
- Keyboard and screen-reader operation for every control; icon + word for every status; a
  confirmation dialog that names who and what is affected for any access-changing action.
- Plain English on screen. Buttons name the action and the object.
- Add or update the help page and the browser check in the same commit as a screen change.

## Never

- No inline styles, literal colours or pixel sizes outside `src/ui/tokens.css`.
- No new runtime dependency unless the work-package card names it. No charting library.
- No request, font, image or script from outside the server.
- No compressed style (several statements per line, one-letter names). See standards §1.
- Do not restyle the board-only touch panel as part of general interface work.

## Commands

```bash
cd frontend
npm run typecheck && npx vitest run && npm run build
npm run dev                         # hot reload; proxies /api and /ws to port 8000
cd .. && scripts/verify.sh --e2e    # browser checks at / and /labadda-staging
```
