# In-app help and guidance — contract

Status: **normative for v1.0; not yet implemented.** Delivered by track H of
[the plan](plan/help.md). Summarised in [SPECIFICATIONS.md S11](../SPECIFICATIONS.md).

**Purpose.** Nobody at the site should need the source repository, a consultant or the internet
to use or look after LabAdda. Everything a member, a steward, an administrator or the person
who looks after the server needs is inside the application, in plain language, and is kept
correct by automated checks.

## Requirements

**HP-01. Offline and built in.** Help pages are Markdown files in `frontend/src/help/`, compiled
into the application at build time and loaded on demand as a separate chunk. No help content is
fetched from outside the server. Images are local SVG or PNG with fictional data only.

**HP-02. Structure.** `/help` has four shelves, each a folder:

| Shelf | Audience | Folder |
| --- | --- | --- |
| Using LabAdda | Everyone | `help/using/` |
| Looking after a workspace | Stewards | `help/stewards/` |
| Administering LabAdda | Administrators and unit administrators | `help/admin/` |
| Running the server | The operator (the person with server access) | `help/operator/` |

Plus `help/glossary.md`, `help/troubleshooting/` (one page per error and event code family) and
`help/whats-new.md`. Everyone can read every shelf; the home page puts the reader's own shelf first.

**HP-03. Page shape.** Each page has front matter (`title`, `summary`, `audience`, `screen` —
the route it explains, `updated`) and follows one template: *What this is for* (two sentences) →
*Before you start* (only if needed) → numbered *Steps* using the exact words on the screen in
bold → *What happens next* → *If something goes wrong* → *Related*. One task per page. A page
fits on two screens. Reading level: a new member of staff on their first day.

**HP-04. Contextual entry.** Every page header in the application has a help link that opens
the page whose `screen` matches the current route, in a side drawer so the user's work stays
visible. Forms with unfamiliar fields have short inline hints. Error messages that have a
troubleshooting page link to it.

**HP-05. Search.** A local search over titles, summaries and headings, built at compile time.
No query is sent anywhere or recorded.

**HP-06. Required pages.** The minimum set is listed in [the plan](plan/help.md#page-list).
It must include, for administrators: a **setup checklist** for a new site; add a person;
transfer; promotion and change of authority; long leave; retirement and leaving; reinstating;
reorganising units; importing a staff list; resetting a password; reading the overview, health
and activity pages; what each status word means; what to do for every event code; reading the
audit trail. For the operator: installing, upgrading, backing up, restoring, renewing the
certificate, what to check when the site is down, and how to get a status report.

**HP-07. Setup checklist.** `/admin/help/setup` shows a live checklist for a new installation:
second administrator created; organisation units created; people added or imported; stewards
or Heads assigned for every unit; backups reporting healthy; site name and time zone confirmed;
a test restore recorded. Each item shows done / not done from real system state and links to
the screen and the help page. It never marks an item done from a tick box alone.

**HP-08. First use.** A person's first sign-in shows a short, dismissible welcome that names
their home unit, what the three tabs are for, and where help is. Empty states teach the first
action. No forced tour.

**HP-09. Kept true by checks.** `scripts/check_help.py` (run by `scripts/verify.sh`) fails when:
a page lacks required front matter or sections; a `screen` route does not exist in `App.tsx`;
a **bold on-screen label** quoted in a page does not occur in the frontend source; an event or
error code documented in troubleshooting does not exist in the code, or a code in the code's
catalogue has no page; a required page from the plan list is missing; a link is broken.
A change to a screen label, route, error code or workflow updates its help page in the same
commit ([AGENTS.md](../AGENTS.md), definition of done).

**HP-10. Printable.** Each page prints cleanly on A4 (print stylesheet), so guides can be handed
to staff. The activation slip (PO-10) links to "Signing in for the first time".

**HP-11. Language.** English, plain, sentence case, second person ("Choose **Transfer**").
No internal identifiers, phase names, requirement IDs or references to this repository.

## Acceptance

Tests T67–T68 in [TESTING.md](../TESTING.md): the help check passes; every route has a matching
page; help opens without network access beyond the server; an administrator persona completes
"add a person", "transfer", "retire" and "read system health" using only in-app help.
