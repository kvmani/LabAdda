# Owner alert preferences

Read CT-15/T52 and the [wire contract](../API.md#c5-owner-alert-preferences).

NotificationPreference/schema0025 stores three booleans and a positive revision
under one owner User FK. No row means all-enabled revision0. alert_preferences.py
uses current normal actor, identity/session locks and optimistic revision; strict
payloads reject other-user fields and coercion. Populated downgrade refuses loss.
The synthetic reset list includes preferences; preserved demos must never be reset.

notify.create normalizes recipient UUIDs and filters known categories when processing
an occurrence. It does not delete existing alerts. Scheduler still marks a muted
occurrence processed, so re-enabling affects new occurrences, not missed reminders.
These preferences are not an access, quota, emergency-broadcast or export policy.
User choices do not change shared content or audience boundaries. Task automatic
assignment/deadline alerts remain separate; current controls cover existing post/
chat mentions, official notices and note/post scheduler reminders.

AlertPreferences.tsx retains uncertain/conflicted drafts, blocks blind repeat and
requires explicit GET reload before another PUT. Generations protect unmounted
views. Shell provides desktop and mobile routes, explicit select labeling and current
selection for My day/preferences/private-group creation. Tests cover actual alert
creation, scheduler consumption, concurrent revisions and real recovery plus web
lost replies/conflicts/ownership/mobile accessibility. Physical device and manual
screen-reader/site qualification remain open.
