# Help centre guide

Contract: [HELP-CENTER.md](../HELP-CENTER.md) (HP-01 to HP-11). Plan: [track H](../plan/help.md).
The help centre is a set of Markdown pages compiled into the web app. It needs no network, and
`scripts/check_help.py` fails the build when a page stops matching the application.

## Where things live

| Path | Holds |
| --- | --- |
| `frontend/src/help/<shelf>/<page>.md` | The pages. Shelves are `using/`, `stewards/`, `admin/`, `operator/`, `troubleshooting/` |
| `frontend/src/help/glossary.md`, `whats-new.md` | Free-form pages: front matter only, no task template |
| `frontend/scripts/build-help.mjs` | Build step: validate, render, write `features/help/generated/` |
| `frontend/src/features/help/` | Home, page view, search, `HelpLink` and its drawer |
| `frontend/src/features/help/generated/` | Index and page modules. Git-ignored; never edit |
| `frontend/src/ui/helpEntry.ts` | Context that lets `PageHeader` show the shell's help control |
| `scripts/check_help.py`, `backend/tests/test_check_help.py` | The sync check and its tests |
| `e2e/help.mjs` | Browser check at `/` and `/labadda-staging` |

## Writing a page

Create `frontend/src/help/<shelf>/<page>.md`. Copy this template exactly; delete *Before you start*
if it is not needed. Keep to one task and two screens. Write for a new member of staff, in the
second person ("Choose **Transfer**").

```markdown
---
title: Signing in for the first time
summary: One sentence that says what the reader will be able to do.
audience: everyone
screen: /login
updated: 2026-11-11
---

## What this is for

Two sentences.

## Before you start

## Steps

1. Choose **Exact label on the screen**.

## What happens next

## If something goes wrong

## Related

- [Another page](other-page.md)
```

Front matter rules:

- `audience` is `everyone`, `steward`, `administrator` or `operator`.
- `screen` is a route written exactly as in `frontend/src/App.tsx` (for example `/w/:workspaceId/:tab`),
  or `none` for a page that explains no single screen. The page opens in the help drawer on that screen.
- `updated` is the date of the last change to the page, as `YYYY-MM-DD`.

Rules for the text:

- Bold is reserved for words that are on the screen. `check_help.py` fails if a bold label is not found
  in the frontend source, so renaming a label means updating its help page in the same commit.
- Link to other pages with a relative `.md` path. Links to the web, to `#` anchors and to application
  routes are rejected, because help never leaves the server and anchors break under the server's base path.
- Raw HTML is shown as plain text, never run. Images are not supported yet; the first page that needs
  one adds local SVG support to the build step.

## How the build works

`npm run dev`, `npm run build`, `npm run lint` and `npm run typecheck` first run
`node scripts/build-help.mjs`, which stops with a plain message on the first invalid page. Edit a page
and restart `npm run dev` (or run `npm run help`) to see it. The step writes `index.json` (title,
summary, shelf, `screen`, headings), one TypeScript module per page, and `loaders.ts`. The reader loads
the index and each page with a dynamic `import()`, so the help is a separate chunk. `marked` renders the
Markdown with its raw-HTML tokens escaped and its image tokens replaced by their alt text.

## Behaviour to keep

- Search is local: `searchHelp` scores words found in titles, then headings, then summaries. The template
  headings are left out of the index. No query leaves the browser.
- Every `PageHeader` shows the help control. With a matching `screen` it opens that page in a `Drawer`
  beside the work; without one it shows the `helpHref` link if the screen passed one, else nothing.
- The home page puts the reader's own shelf first: administrators, then anyone who is a steward, then
  everyone else. The operator shelf is never chosen automatically because the browser cannot know.
- Printing hides the navigation and prints the page on A4 (see `help.css`).

## The sync check

`python3 scripts/check_help.py` (also run by `scripts/verify.sh`) fails on:

- missing or invalid front matter, or a task page without the template sections in order;
- a `screen` that is not a route in `App.tsx` (routes inside `/admin/*` are added by H3);
- a bold label that appears nowhere in the non-test frontend source;
- a link that is not a relative path to an existing help page.

Two more rules apply to the whole help set:

- every page in `REQUIRED_PAGES` (the `using/` and `stewards/` page list; H3 adds the administrator
  pages) must exist;
- every route in `App.tsx` outside `/admin` must be the `screen` of at least one page. The routes in
  `ROUTES_WITHOUT_PAGE` (redirects, the catch-all, the help centre itself and `/activate`) are exempt.

The event-code rule (`check_event_codes`) stays off until H3 sets `EVENT_CODE_CHECK_ENABLED`.

## Checks

```bash
python3 scripts/check_help.py
cd frontend && npx vitest run scripts src/features/help
cd backend && ../.venv/bin/python -m pytest tests/test_check_help.py -q
node e2e/help.mjs /tmp/help-check      # needs the proxy stack; see the frontend instructions
```
