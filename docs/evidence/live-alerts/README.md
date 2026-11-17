# Live alerts: synthetic browser evidence

Captured from Chromium against real FastAPI/PostgreSQL servers on 17 November 2026.
Only fictional fixture accounts and locally created example content were used.

`e2e/alert-popups.mjs` exercises both root and `/labadda-staging` instances:
calendar creation and scheduled reminder delivery, enabling the local chime,
dismissal preserving unread state, read acknowledgement persistence, live chat
from a second account, and saving the private whiteboard drawing. Screenshot pairs
use `root-` and `prefix-` names. No mocked routes or injected pop-up markup.

Calendar and chat pop-up screenshots show the new controls. The other images show
existing whiteboards, chat, noticeboard, tasks and notes; those applications were
not redesigned. Browser automation verifies audio context activation, not human
perception of sound. Chime loudness should also be checked on office speakers.

Validation: 264 frontend tests, 20 focused backend/migration tests and browser
checks at both paths passed. Feature lint/build and docs/help checks passed.
Repository-wide verification stops at existing Python formatting violations;
frontend lint has 11 existing errors and Alembic reports the existing
`ix_join_requests_created_at` drift. Independent delivery review remains pending.
