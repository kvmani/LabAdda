# LabAdda specification

## S1. Product and pilot scope

LabAdda gives research groups a common noticeboard, a live writing surface, and a group message stream. One sign-in gives an employee access to their home workspace and eligible parent units. Personal notes have their own entry in the shell. The intranet runtime runs on a single Ubuntu VM and serves desktop browsers and an office touch panel.

Pilot with a fictional root, group, division, and two sibling sections, plus an invite-only project space and a user-created collaborative group spanning both sections. Then rehearse with two real sibling sections and their parent division after the site gates in [Deployment](docs/DEPLOYMENT.md) pass. The pilot includes local accounts, membership administration, user-created collaborative groups, posts and replies, approved attachments, dated reminders, live whiteboards, board snapshots, group chat, personal notes, and touch sessions. Internal identity federation is optional until the site confirms a provider. Later scope includes the P5 data lifecycle and administration contracts in S5–S7, direct messages, recurring reminders, rich collaborative document editing, full-text indexing across workspaces, SMTP delivery, and cross-site federation.

## S2. Workspace, identity, and permissions

An organizational workspace is a node with an immutable ID, display name, nullable parent, archived status, and posting policy. Use a single-root tree with configurable names and arbitrary depth. Reject cycles and invalid parents. Model invite-only projects separately with direct grants and no inherited organization access. User-created collaborative groups (S2.1) follow the same flat, direct-grant model. An active account has zero or more direct workspace grants and may choose an eligible home workspace. Resolve all grants by stable IDs. If home is lost, choose an accessible direct workspace or show a clear empty state. Audit membership and hierarchy changes with actor, scope, action, outcome, timestamp, and reason where applicable.

| Actor in the target workspace | Read content | Post, reply, draw, chat | Pin, issue official notice, moderate, restore |
| --- | --- | --- | --- |
| Direct member | Yes | Yes under the workspace posting policy | No |
| Direct member or steward in a descendant | Yes, as an inherited member | Yes under the workspace posting policy | No, unless also a direct steward in the target |
| Direct steward | Yes | Yes | Yes, in the target only |
| Org administrator without a content grant | No | No | No. Can administer identities and the tree with audit |
| Member of only a sibling, ancestor, or unrelated project or group | No | No | No |
| Board-only session | Selected board and images embedded on it | Selected board tools | No |

Normal workspaces start in open mode. A steward may switch a workspace to read-only for ordinary members and switch it back. Posting policy covers all shared content mutations, including replies, board edits, chat, and uploads. Archive freezes shared mutations including touch sessions and retains reads for eligible members. Users edit and remove their own posts/replies while writable. Stewards can remove items with an audited reason. Attribution uses immutable user IDs and survives moves and deactivation. Admin privileges do not grant personal-note access through the app. Role administration must protect against removing the last active org admin.

Use explicit, administrator-provisioned accounts in the pilot. Support one-time activation/reset credentials with expiry and forced password setup, a maintained password hasher, rate limits, and no self-registration. Prefer a stable external issuer/subject mapping if adding internal federation. Use opaque server-side revocable sessions in secure HttpOnly cookies, with explicit idle and absolute expiries, CSRF protection for unsafe HTTP requests, and trusted origins on socket upgrades. Deactivation invalidates all sessions. Membership changes invalidate affected workspace subscriptions and authorization caches. Recheck current membership before delivering queued protected content and before applying edits; once the access change commits, stale clients may receive a revocation signal but cannot fetch or receive new protected content. Bytes already delivered remain in the user's possession. Denied unauthenticated requests use 401, out-of-scope resource requests use a uniform 404, and a visible but forbidden action uses 403. Avoid revealing existence through metadata, counts, errors, or suggestions.

### S2.1 Collaborative groups

Any active user can create a **collaborative group**: a self-organized workspace for chosen colleagues from any section, division, or project. A group has the same features as a section or division (noticeboard with replies, pins, official notices, attachments and reminders; whiteboard; chat; workspace search; upcoming; notifications), but no hierarchy controls.

- **Flat and private.** A group has no parent and no children and is never part of the organization tree. Only direct members can read it. Membership elsewhere, including stewardship of a parent unit, grants nothing. Administrators without a grant cannot read group content, the same as any other workspace. Group content never appears in parent-unit search, counts, notifications or feeds.
- **Roles.** The creator becomes the first steward. Stewards add active colleagues, remove members, change roles, rename, set the posting policy, and archive or unarchive the group. They pin and issue official notices and moderate within the group only. Any member can leave. The last active steward cannot leave or step down until another member is a steward, and stewardship can be handed over at any time.
- **Choosing colleagues.** A directory lookup returns active colleagues' display names and usernames only, never memberships or home units. Invitations add members immediately. Before adding, the UI states that new members can read the group's existing history. Inactive accounts are refused.
- **Limits and audit.** Configurable defaults cap active groups created per user (20) and members per group (200). Group creation, membership, role and archive changes go to the audit trail with actor and scope. Administrators can see group names and member counts and can repair membership, for example, after a steward leaves the organization, without gaining content access.
- **Lifecycle.** Archive keeps reads for members and blocks all shared mutations, as for any workspace. Group data is retained like other workspace data. A schema downgrade refuses to run while groups exist.

## S3. Desktop shell and workflows

Use the accepted workspace-first layout. A left rail shows the accessible hierarchy, with clear indentation, current unit, and shortcuts to nearest ancestors. Selecting a unit changes the content scope without mixing sibling activity. Keep Noticeboard, Whiteboard, and Chat as feature tabs within that scope, and pin My Notes outside it. Use the desktop noticeboard's centre column for the feed and composer, and a secondary rail for Upcoming and a small board preview. Stack the secondary rail below the feed on narrow screens. The board opens as a dedicated workspace view with a prominent drawing toolbar and a visible save indicator. On narrow screens, collapse the rail to a labeled workspace switcher. Workspace and feature deep links must survive refresh and sign-in at a configured URL prefix. Use text alongside color for access, unread, and connection states. Support keyboard navigation, visible focus, and accessible forms. Provide a list view for typed board objects. Use fictional lab examples in demos.

### Noticeboard, files, and reminders

- Paginate posts by stable creation order, show pinned notices first, and distinguish discussion posts from official notices. Provide replies, edit/delete for authors, moderated removal, clear errors, and success state only after persistence. Show `Post to <workspace>` and the audience beside the composer. An open draft stays scoped to its original workspace if the user navigates.
- Attach up to five PDF, PNG, or JPEG files per post, 20 MiB each as configurable pilot defaults. Enforce limits before storing and validate allowed signatures and media types. Use generated storage keys, protected same-origin downloads, safe display names, attachment disposition for PDFs, and sanitized raster previews. Never serve uploads directly from a public static directory. Apply resource authorization to files, preview derivatives, and file metadata. Enforce storage quotas and clean failed uploads without touching referenced files. An upload becomes readable to its target audience only after the owning item commits. Use approved internal links for large datasets and avoid fetching link previews from remote URLs.
- Give an announcement or personal reminder a due time and optional reminder time. Store UTC, display in a configured local time zone, and expose upcoming items in the selected workspace or My Notes. Generate an in-app notification once per occurrence and recipient using a durable uniqueness key. Recheck eligibility when creating and opening notifications. Enable mentions, reminders, and official notices by default. Show routine activity as unread rather than pushing it to everyone.
- Provide workspace-local text filtering/search over posts and chat with scoped counts and results. Search never indexes unapproved workspace content into a public or global endpoint. Hide deleted items and inaccessible hits.

### Live whiteboard and touch

- Provide one persistent active board per workspace, with a large canvas, pen, eraser, typed notes, stickies, approved embedded raster images, pan, zoom, fit, and undo of the actor's most recent eligible operation. Erasing another person's stroke is a distinct mutation, while Undo reverses only the current actor's work. Desktop and touch users see active edits and presence. Use the canvas-first layout when opening the board and on the touch panel.
- Use immutable object IDs and an ordered board revision for the authoritative state. Commit mutations as sequenced, idempotent operations. Stage the sender's drawing locally and relay bounded transient stroke previews to other viewers. Commit complete strokes or bounded segments with stable IDs. Disconnect discards uncommitted remote previews. Stored strokes replace their previews on delivery without duplication.
- Clients subscribe with their latest sequence and board epoch. On reconnect, replay missed operations or fetch the latest durable snapshot if replay has been compacted. Resend pending operations with the same IDs. Unacknowledged edits survive a brief network interruption within the open tab. Show `Saving`, `Saved`, `Reconnecting`, and conflicts accurately. A closed tab does not guarantee unsaved edit recovery. A stale object edit is rejected with the current revision. A restore creates a new board epoch and invalidates old pending mutations. Keep enough version history to undo or restore without rewriting an already published snapshot.
- Offer `Publish snapshot` from the desktop board. Capture a selected region at a specific committed revision as an immutable image with a typed summary. Default destination to the same workspace. For a parent destination, require current read access to the source, write access to the destination, preview of the captured region, and explicit confirmation naming the broader audience. Create a separately owned destination artifact, never a protected source link. Copy additional allowed attachments only when individually selected. Removing a source item does not remove a published copy. Show that in confirmation. Editing the canvas does not change the copy. The server renders the copy from committed state. Destinations are the source workspace or a writable ancestor unit. Projects and collaborative groups publish only within themselves. Readers of the destination who cannot read the source see the copy without the source's name. Images embedded on a board become owned by that board. They are served only to its readers and are never reused as post attachments. Board history older than a configurable window (500 revisions by default) is compacted into a durable snapshot. Undo and restore reach back to the window or to a stored snapshot revision.
- A shared panel uses an individually authorized, short-lived board-only session. Open only the selected board in a separate browser profile or dedicated kiosk context, using a separately named session cookie. Grant only board actions, board-safe presence, and embedded images. Do not expose the notice feed, general file picker, other spaces, chat, notes, administration, or publishing. Use large controls, prominent `End session`, lock after a configurable idle time (five minutes by default in staging), and require reauthorization. Clear the board and discard transient input on lock/end. Use site-configured absolute expiry and record initiator and termination. A signed-in user authorizes a panel from their desktop: "Open on touch panel" issues a single-use code that expires in two minutes. Entering it on the panel starts the board-only session as that user, so attribution and own-undo stay personal and no password is typed on a shared screen. Only interactions reset the idle clock, and the server enforces the same idle limit as the panel. Ending or locking discards the board from the panel. A new code is needed to continue.

### Chat and My Notes

- Provide one text chat stream per workspace with bounded history pagination, server-side attribution, unread state, and optional mentions. Deliver new messages live and replay from the last received cursor after reconnect. Allow publishing a concise summary to the noticeboard. The composer opens with a selected excerpt and a visible destination, and broader sharing uses the same explicit audience confirmation as a snapshot.
- My Notes supports create, edit, delete, personal reminders, and owner-only access from normal sessions. Notes never appear in workspace search, notifications to colleagues, export to a touch panel, or an admin content browser. Privileged backup handling is an operator responsibility under site policy.

## S4. Implementation contracts

Use Python 3.12, FastAPI with ASGI, SQLAlchemy 2, Alembic, PostgreSQL, and React with TypeScript and Vite. Build static assets ahead of deployment. Use PostgreSQL for authoritative sessions, revisions, and durable data. Begin with one ASGI process and bounded in-memory fanout; reconnect catches up from committed state. Use a native web canvas and pointer events or a vetted, fully bundled component after the first drawing spike. Maintain separation between identity, workspace policy, content, realtime transport, and operations. A broker or additional application workers require a subsequent design and proof of revocation and ordered delivery across processes.

- Use a versioned same-origin JSON API under `<base>/api/v1/` and a socket endpoint under `<base>/ws/`. Root and prefixed instances use the same code. Publish request/response schemas and error codes alongside implementation. Derive the actor from the session, never a client-supplied user ID.
- Persist users, workspaces, memberships, sessions, posts/replies, assets and ownership, reminder occurrences/notifications, boards and immutable revisions, chat messages, and personal notes. Use foreign keys, server timestamps, and DB constraints for idempotency and uniqueness. Keep binary assets outside the code tree. Back up database and assets at a consistent recovery point.
- Durable realtime mutations have an operation ID, resource ID, expected revision where applicable, and bounded validated payload. Sequence per resource under a database transaction. Uniqueness covers the resource, epoch where relevant, actor, and operation ID. A retry with identical intent returns the committed result. Reuse with different content fails explicitly. Acknowledgement and fanout happen after commit. Catch up missed committed events even if a process restarts before fanout. Serialize authorization-sensitive writes against revocation and recheck permissions on delivery.
- Define loading, empty, forbidden, offline, reconnect, save failure, and stale-write states. Use stable pagination and timeouts. Escape user text, use parameterized queries, and enforce upload and realtime rate and payload limits. Keep tokens, message bodies, board content, and personal notes out of operational logs.
- No internet-bound scripts, font requests, telemetry, external image loads, authentication, or API calls from the installed application. Optional internal services must fail clearly and independently of the core workflows.

Provisional rehearsal targets on a representative VM are 30 signed-in clients, 8 simultaneous drawers on one board, and 2 active sibling workspaces for 15 minutes. Measure the 95th percentile local-to-remote committed update under 500 ms and 95th percentile ordinary list response under 1 s, and confirm no missing or duplicate committed edits. Record VM sizing, network path, browser, board size, workload, and observed results. Reassess targets with the site owner before any organization-wide rollout.

## S5. Data ownership, usage and lifecycle (future)

[DATA-LIFECYCLE.md](docs/DATA-LIFECYCLE.md), requirements DL-01–DL-28, is the normative P5 contract for user/workspace/site quotas, accounting, admission, retention, preservation holds, downloads, temporary archive viewing and selected materialization. It specifies a proposed lightweight profile, not a change to today's pilot settings. Admin-reviewed versioned policy must govern all product limits and lifecycle actions through the web UI; host safety ceilings remain explicit operator constraints. Roll out measurement and archive escape paths before hard enforcement or deletion. A frozen workspace retains authorized reads and is not a retention hold or a downloaded archive.

## S6. Portable archives and offline recovery of user content (future)

[ARCHIVE-FORMAT.md](docs/ARCHIVE-FORMAT.md), requirements AF-01–AF-11, governs a versioned standard ZIP containing offline-readable static views, UTF-8 JSON/JSONL records, original permitted files, portable board geometry and complete integrity indexes. Export requires current content access; admin privilege alone never supplies it. Re-upload defaults to a bounded isolated read-only viewer. Selected materialization creates newly authorized destination records with provenance, current quotas and explicit audience confirmation, never restores source memberships, sessions or admin roles. These packages are distinct from operator database recovery under RECOVERY.md.

## S7. Administrative control and operational observability (future)

[ADMIN-CONSOLE.md](docs/ADMIN-CONSOLE.md), requirements AC-01–AC-21, governs web policy configuration, safe dry runs/approval/activation, privacy-conscious site-wide usage/resource analytics, health, searchable actionable events and backup/recovery visibility. Operational completeness must not become a private-content access bypass. Destructive actions require current bounded plans, review, notice, verified prerequisites and auditable execution. Stale, unknown and unsupported observations must remain visibly distinct from healthy/zero. The acceptance matrix in TESTING.md and P5 delivery order in ROADMAP.md are mandatory release gates; this specification does not assert these features exist today.

## S8. Collaboration priority and tasks

The owner-approved C1–C5 track in ROADMAP.md now precedes unfinished P5 work.

**CT-01 (C1).** Provide multiple named personal and shared workspace to-do lists.
Personal lists are owner-only, including against administrators and colleagues.
Shared lists belong to exactly one workspace (any org level, project or group)
and inherit the existing upward-only read and workspace write policy. Division
membership grants no access to child sections; assignment never grants access.
Scope is immutable in C1: no moving a personal list into a shared audience.

**CT-02 (C1).** Tasks have a title, plain-text description, optional calendar due
date, priority (low/normal/high), ordered checklists, and open/done state with
completion/reopening. Users can edit list names and task fields. C1 excludes
assignment, comments, automatic reminders, file attachments and deletion; those
require later explicit contracts. Workspace writers collaborate on shared lists;
archived/read-only policy applies. Personal lists remain independent of workspaces.

**CT-03 (C1).** Use bounded payloads/pages, stable ordering, durable operation IDs
for creation and optimistic revisions for updates. Identical create retries return
the original resource; changed intent with the same ID conflicts. Updates never
silently overwrite concurrent edits. Show scope, pending/failed saves and conflict
recovery without discarding the user's draft. Revalidate current identity/grants
at authorization-sensitive write boundaries. No task access via panel sessions.
Persist migrations and backup/restore data without exposing task bodies in logs.

**CT-04 (C2–C3).** Add eligible-member assignment, task comments/history/live
updates and My Tasks, then conversion from conversations and protected links.
Cross-level sharing requires an explicit audience decision. Division dashboards
aggregate only currently authorised content. Links never grant source access.

**CT-05 (C4–C5).** Add threaded chat, validated chat attachments and private
colleague conversations using private groups, followed by a daily collaboration
dashboard and configurable notification controls. Preserve durable retry, current
content permissions and browser/offline-asset invariants throughout.

**CT-06 (C2 workflow/history slice).** Add To do/In progress/Blocked/Done task
states, with done as a compatible completion projection. Preserve C1 create request
fingerprints and omitted-state edits; an old client editing an incomplete task
must not reset its intermediate state. State and completion supplied together must
agree. Persist one content-history event atomically per committed revision, including
actor attribution and field changes. Replay/conflict/failure creates no duplicate
event. History is content, read only through current task/list permissions; no admin
or operational-reader bypass. Migration records an explicit baseline with unknown
earlier authors/history, not invented reconstruction. Bound history pages and
protect stored history against lossy downgrade. Web changes use the existing draft,
revision and revoked-refresh rules. Assignment/comments/live updates/My Tasks are
separate C2 slices.

**CT-07 (C2 assignment/My Tasks).** Shared task assignment may name only an active
current reader of the task's actual workspace; personal tasks may name only their
owner. Assignment never creates membership or broadens an audience. Use expected
revision and atomic content history; current write/session authority and target
eligibility must hold at commit. Reciprocal assignments must use deterministic
identity lock ordering. Unassigning stale/deactivated assignees remains possible.

Provide a bounded searchable eligible-colleague picker and My Tasks containing
owner-private tasks plus shared assignments with current source read access. Apply
hierarchy/project/group policy without an admin bypass. Revalidate read grants
before returning; do not expose stale content/cursors when grants change during
measurement. Membership loss hides shared assignments without silently rewriting
responsibility/history. Old task field edits must preserve assignment; create
request fingerprints stay compatible. Web refresh/conflicts/uncertain writes must
retain useful drafts and discard stale results. No assignment notifications or
live delivery are implied by this slice.

**CT-08 (C2 initial comments).** Provide immutable plain-text task discussion under
the actual list audience: owner-only for personal lists, current source readers for
shared lists. Posting follows current write/archive/session policy, including retry.
Creation UUIDs bind author, task and normalized text; identical retries return the
same comment, changed intent conflicts. Serialize monotonic per-task append sequence
and capacity under the list lock; comments do not change the task field revision.
Bound payloads/pages, preserve authorship/Unicode/newlines and escape text in the
browser. Recheck source access before returning a page. Use explicit same-request
recovery after uncertain creation; stale responses cannot populate another task.
Keep drafts during same-list refresh/field edits. Initial delivery adds no comment
editing/deletion, notifications, attachments or live events; refresh loads discussion.

**CT-09 (C2 shared task invalidation).** After a new shared list/task/assignment/
comment mutation commits, send a content-free `tasks.changed` hint in the actual
list's workspace. Include only event type and workspace ID; never personal list,
task, comment, author or assignee metadata. Replays, no-op assignment and rejected/
rolled-back writes send no hint. Delivery uses current session/grant checks and
excludes board-only sessions. Hints are lossy and may arrive out of order; HTTP
state remains authoritative. A new subscription/reconnect must signal possible
missed changes. Preserve drafts until explicit review/replacement; do not silently
adopt a new task revision for an unsaved assignment. Personal cross-session live
updates and assignment notifications remain separate work.

**CT-10 (C3 conversation-to-task).** Convert a readable top-level post or chat
message into a task in an owner-private or currently writable shared list. The user
reviews editable title/description and destination. Every different workspace
requires explicit audience confirmation, even if audiences overlap; personal copies
need no broader-audience confirmation. Never implicitly copy attachments, source
names, authors or subsequent edits into a task. Task creation, initial history and
one protected reference commit atomically with durable same-intent request identity.
Replays require current source-read and destination-write authority; source edits/
removal serialize with acceptance. Preserve C1 task fingerprints and field edits.

A generic `has_source` flag is destination-visible provenance only, including after
source removal; task/history payloads contain no protected source identifier, name
or body. Resolve the reference through a separate endpoint requiring current task
and source read access, rechecking before return. Missing, removed, purged and
inaccessible sources return uniform404 without deleting the reviewed task copy.
Source purge clears foreign keys, not tasks. Protect references against lossy
schema downgrade and preserve them through recovery. Web uncertain writes freeze
original intent/audience, and revoked scopes invalidate delayed source/create
responses. This slice excludes reply conversion, board references and automatic
assignment/reminders; those remain subsequent C3/C5 work.

**CT-11 (C3 research-plan board context).** Create a task from a readable existing
whiteboard, using the same reviewed task fields, destination policy, audience
confirmation and protected-source boundary as CT-10. Record an immutable epoch/
revision tuple, not a copied image, rendered historical board or access grant.
Accept a new task only if the reviewed tuple matches the current board under its
row lock. A stale tuple requires explicit context review without discarding draft
text; a committed same-intent retry retains its original context after later ink or
restore. Source read and destination write must hold under metadata/identity locks.

Task/history/events expose no board IDs, names or revision context; generic source
provenance remains destination-visible. Authorized source inspection shows recorded
and current tuples separately and links to the live board with an explicit saved-
image distinction. Compaction/restore does not rewrite recorded context; source
purge makes the link unavailable while retaining the task copy. Guard populated
context downgrade and preserve references through recovery. No task controls or
endpoints are available to board-only sessions. Empty never-written boards must
have plan content before creation; no implicit board write on a reader's behalf.
This slice does not provide per-object/region references or historical rendering.
