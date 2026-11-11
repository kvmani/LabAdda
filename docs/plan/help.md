# Track H — in-app help and onboarding

Contract: [HELP-CENTER.md](../HELP-CENTER.md) (HP-01–HP-11).
Writing rule for the whole track: write for a new member of staff on their first day. Use the
exact words on the screen, in bold. One task per page. No requirement IDs, phase names or
repository references in help text.

### H1 · Help centre framework and sync check

Size M. Depends on U2.

**Goal.** `/help` works offline with search and contextual entry, and a check keeps it true.

**Build.** `frontend/src/help/` with the folder structure in HP-02. A small build step
(`frontend/scripts/build-help.mjs`, run by `npm run build` and `npm run dev`) that reads the
Markdown files, validates front matter, renders to safe HTML with a vetted, bundled Markdown
library (`marked`, with raw HTML disabled; add as an exact-version dev dependency) and emits
a JSON index plus one module per page for lazy loading. `features/help/`: home with four
shelves, page view, local search (titles, summaries, headings), print stylesheet, and
`HelpLink`/help `Drawer` used by `PageHeader`. `scripts/check_help.py` implementing every
rule in HP-09, called from `scripts/verify.sh`, with tests. Seed three real pages to prove the
pipeline: "Signing in for the first time", "Finding your way around", "Glossary".

**Acceptance.** `check_help.py` fails on: missing front matter, unknown `screen`, a bold label
not found in the frontend source, a broken link (tests cover each). Help loads with the network
restricted to the server. Raw HTML or script in a help file is not rendered. axe clean.

### H2 · Help for members and stewards

Size M. Depends on H1. Content only; no code changes except help links.

**Goal.** Every existing feature has a page (see the page list). Reuse and tighten the text in
`docs/usage/*.md`, then replace those files with one-line pointers to the help pages.

**Acceptance.** `check_help.py` passes with the required-pages list for `using/` and
`stewards/` enabled. Every route in `App.tsx` outside `/admin` has a page. A reader test: follow
each page's steps on the fixture exactly as written (record the result per page in the handoff).

### H3 · Administrator handbook and setup checklist

Size M. Depends on H1, P5, A6.

**Goal.** HP-06 administrator pages and the live setup checklist (HP-07).

**Build.** All `admin/` pages in the page list and one troubleshooting page per event code and
per health item. `GET /admin/setup-checklist` computing each item from real state; the
`/admin/help/setup` page. Enable the event-code and required-page rules in `check_help.py`.

**Acceptance.** Each checklist item flips only when the real condition changes (test each).
Every event code in the code catalogue has a page and vice versa. Persona walkthrough: using
only in-app help, complete scenario steps 1–3 from [the people track](people.md#scenario).

### H4 · Operator handbook, first-use welcome, what's new

Size M. Depends on H1, D2.

**Goal.** HP-06 operator pages, HP-08 welcome, and `whats-new.md`.

**Build.** `operator/` pages distilled from `docs/DEPLOYMENT.md`, `RELEASES.md`, `RECOVERY.md`
and `COMMISSIONING.md` into task pages with exact commands (placeholders such as
`<site-name>`, never real values). First-sign-in welcome (dismissal stored per user in the
database, not the browser). "What's new" shown once per release from `whats-new.md`.

**Acceptance.** Every command in an operator page exists in the scripts (extend
`check_help.py` to verify script names and options). Welcome shows once and is keyboard
dismissible.

## Page list

`using/`: signing-in · finding-your-way · noticeboard · replies-and-official-notices ·
attaching-files · reminders-and-upcoming · whiteboard · publishing-a-snapshot · touch-panel ·
chat-and-threads · chat-files · private-groups · tasks · assigning-tasks · task-from-a-message ·
my-day · my-tasks · my-notes · notifications-and-alerts · my-storage · my-profile-and-password ·
search.

`stewards/`: what-a-steward-does · members-and-roles · read-only-and-archive · pinning-and-
official-notices · removing-a-post · handing-over-stewardship · workspace-storage.

`admin/`: setup-checklist · what-administrators-can-and-cannot-see · add-a-person ·
edit-a-record · transfer · promotion · change-of-head · acting-appointments · additional-charge ·
long-leave · retirement-and-leaving · suspend-and-reinstate · reset-a-password ·
import-a-staff-list · organisation-chart · create-move-merge-close-units · scheduled-changes ·
attention-list · unit-administrators · overview-page · system-health · status-words ·
activity-page · audit-trail · events · backups-page · site-notice · settings.

`operator/`: install · upgrade · backup · restore · certificate-renewal · site-is-down ·
status-report · disk-is-filling · moving-to-a-new-server.

`troubleshooting/`: cannot-sign-in · activation-code-expired · saving-failed · conflict-
someone-else-changed-this · upload-rejected · lost-connection · plus one per event code.
