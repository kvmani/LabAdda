# Pilot verification, 23 November 2026

**Hold the staff pilot. Proceed with a technical rehearsal using fictional accounts and data.**
The service handled the simulated collaboration load. Several everyday browser workflows still
lack a passing result, and the actual office installation and recovery procedure need a rehearsal.

## What ran

| Area | Result |
| --- | --- |
| Backend | 1,793 of 1,794 tests passed in one sweep across four isolated PostgreSQL databases. The 500-person directory query took 249.9 ms against a 200 ms limit. All 23 directory tests passed in isolation. Repeat the timing check on pilot hardware with concurrent users. Alembic reported no schema drift. |
| Frontend | All 272 unit tests passed across 50 files. Lint, formatting, TypeScript and the production build passed. |
| Browser | All 54 suites were attempted in Chromium through nginx. Passing suites exercised both the root and prefixed instance. The pilot walkthrough passed 60 checks, general workflows 75, alert pop-ups 14, the accessibility sweep 48, and the UI gallery 18. Individual suites can stop at their first failure. |
| Realtime | The 15-minute TLS run used 30 clients across two workspaces, with eight people drawing. It acknowledged 11,977 board edits and 1,218 chat messages. All 197,925 expected deliveries arrived, with no duplicates, revision gaps or cross-workspace delivery. Update p95 was 454.6 ms (target below 500 ms), and list p95 was 419.6 ms (target below 1,000 ms). A shorter direct TLS run recorded a disconnect and 605.4 ms update p95. |
| Dependencies and packaging | 459 dependency pins met the 30-day age rule. Advisory checks reported no known findings across 43 Python pins and the production npm dependency set. A mirror-mode kit built from 621b133 verified and installed on disposable Debian with registry access. The Python dependency consistency check passed. |
| Backup and alerts | Regression coverage includes verified backup receipt selection, compatible rollback locking, reconnect catch-up, and notification acknowledgement. Browser checks exercised enabling the chime, dismissing a reminder while preserving unread state, and marking reminders and chats as read. Perceived chime volume on office devices needs a listening check. |

## Changes made during review

- Preserved the last verified backup receipt during subsequent backup attempts. Corrected rollback
  locking and backup-timer handling, and included the lifecycle argument helper in release packaging.
- Recovered live alerts after reconnect, corrected read acknowledgement and made pop-ups fit narrow
  screens. Moved alerts away from the chat reply button. Improved chat contrast, message list semantics
  and search. Removed availability and read indicators that lacked supporting data.
- Kept attachment and emoji controls from changing a message while its send result is unknown.
  Verified that retrying after a lost response recovered a single message and attachment.
- Removed nested main landmarks in My Day, Calendar and My Whiteboard. Updated fixtures and browser
  checks to exercise the current message menu and attachment picker. The runner discovers every suite.

## Requirements before inviting staff

1. Close the outstanding browser checks below. Verify the actual workflow when a locator or fixture
   is stale, then rerun it at both URL bases. Prioritize whiteboard editing, chat, task updates,
   directory changes and administrator health visibility.
2. Install the exact candidate kit on the intended Ubuntu 24.04 host. Exercise upgrade, rollback
   and reboot, then check the service account, login persistence and backup timer.
3. Copy a verified backup off-host, restore it into an isolated instance, and have the operator
   open the restored site and check accounts, attachments and collaboration data.
4. Sign in over trusted HTTPS from a second office workstation. Check coexistence with PM if
   installed, keyboard and screen-reader workflows, mobile controls and chime audibility.
   Repeat the workload on the office network before setting a staff cohort size.

## Browser findings still open

| Suite | Observed failure |
| --- | --- |
| board-editing | The prefixed shared board did not acknowledge the simulated pointer drag before timeout. Keyboard movement, formatting persistence and the private-board checks had passed at root. |
| console-broadcast | The accessibility scan flagged a small target on the member screen with a broadcast strip. |
| console-health | The background jobs card did not show the degraded state expected by the fixture. |
| dashboard | The My Day overview did not satisfy the combined assignment, personal work and reminder assertion. |
| help | The general help shelf appeared before the steward shelf. |
| org-chart | The expected root organisation tree item could not be located. |
| people | The directory's descending-order checkbox did not retain its expected checked state. |
| people-changes | The activation slip dialog's primary button failed a contrast check. |
| people-import-excel | The template download event timed out. |
| pilot-safety | The check stopped at the private note text field. Subsequent safety checks in this suite remain unverified. |
| profile | My Profile did not occupy the expected position in the account menu. |
| task-updates | The expected refresh prompt for a shared assignment did not appear. |
