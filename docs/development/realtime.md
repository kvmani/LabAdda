# Realtime delivery

The single-process `Hub` in `backend/labadda/realtime.py` delivers committed workspace events
in FIFO batches. It checks current sessions and workspace grants before each batch and uses
subscription generations to discard a decision made before unsubscribe or re-subscribe.
Clients catch up from committed API state after subscribing; transient previews are not saved.

`realtime_preview.py` checks the sender's current session and write permission for each stroke
preview. It then uses the same checked recipient delivery path as durable content, excluding
the sender. Cached write access alone cannot authorize a preview. Previews stay outside the
durable queue so obsolete strokes cannot fill it.

`realtime_presence.py` checks current readers before building the presence list and sending it.
Invalid sessions close; lost grants drop the subscription. Cleanup suppresses recursive presence
broadcasts while this list is being built. A generation change discards a stale delivery decision.

Session revocations from logout, activation/reset and password change notify the hub only after
the database commit. Current-access delivery checks still apply when no signal was sent, including
natural session expiry and direct database changes.

Contracts: [socket API](../API.md#socket-messages), SPECIFICATIONS S2/S4 and
[review procedure](../../REVIEW.md). Checks: `backend/tests/test_realtime.py` and
`backend/tests/test_preview_access.py`, plus `e2e/flows.mjs` at root and prefix. Preview regressions
cover expired, idle and revoked sessions, removed memberships, archived workspaces, current
readers and a sender subscription generation changing during its access check.
