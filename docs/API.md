# LabAdda API contract (v1)

All endpoints are same-origin JSON under `<base>/api/v1/`. The socket is `<base>/ws/`. `<base>` is empty for a dedicated host or a prefix such as `/labadda-staging`. The server derives the actor from the session cookie and never accepts a client-supplied user ID.

## Conventions

- **Session.** `POST /auth/login` sets an HttpOnly, `SameSite=Strict` cookie scoped to the instance path and returns a `csrf_token`. Send it as `X-CSRF-Token` on every `POST`, `PUT`, `PATCH`, and `DELETE`. A browser `Origin` must match the host or `LABADDA_TRUSTED_ORIGINS`.
- **Errors.** The body is `{"error": {"code", "message", "fields?"}}`. `401` means unauthenticated or expired. `404 not_found` is identical for unknown and out-of-scope IDs. `403` is a visible but forbidden action. `409` is a conflict or idempotency mismatch. `422` is validation. `429` is rate limited.
- **Times.** Times are ISO 8601 with an offset. The server stores UTC and rejects naive values (`timezone_required`).
- **Idempotency.** Posts and replies accept an optional `client_id`, chat requires `client_id`, and board ops require `op_id`. A retry with the same content returns the committed result. Reuse with different content returns `409` (`client_id_reused` / `op_id_reused`).
- **Touch panels.** Panel requests carry `X-LabAdda-Panel: 1`. Image URLs use `?panel=1`, and the socket uses `<base>/ws/?panel=1`. A panel session works only on `GET .../board`, `POST .../board/ops` (no image placement) and `GET /files/{id}[/preview]` for images embedded on its own board. Everything else returns `401`, and another board returns `404`. Panel sockets subscribe only to their board and receive only board, presence and session events.
- **Caching.** API responses are `Cache-Control: private, no-store`.

## Endpoints

| Area | Method and path | Notes |
| --- | --- | --- |
| Auth | `POST /auth/login`, `POST /auth/logout`, `GET /auth/session` | Login is rate limited per user and per client address. |
| | `POST /auth/activate` `{token, password}` | Redeems one-time activation or reset code (min. 10 characters). |
| | `POST /auth/password` `{current_password, new_password}` | Revokes other sessions. |
| Workspaces | `GET /workspaces` | Readable spaces with `role`, `inherited`, `can_write`, `can_moderate`, `unread_chat`, `home_workspace_id`. |
| | `GET /workspaces/{id}`, `GET /workspaces/{id}/members` | Detail includes readable ancestors. |
| | `PATCH /workspaces/{id}/policy` `{posting_policy}` | Direct steward only. |
| | `PUT /me/home` `{workspace_id}` | Must be a direct grant. |
| Groups (S2.1) | `GET /directory?q=` | Active colleagues, names only. |
| | `POST /groups` `{name, description, member_ids[]}` | Creator becomes steward. `group_limit`, `group_too_large`, `unknown_member`. |
| | `PATCH /groups/{id}` `{name?, description?, archived?}` | Steward only. |
| | `POST /groups/{id}/members` `{user_ids[], role}` | Steward only. |
| | `PATCH /groups/{id}/members/{user}` `{role}`, `DELETE /groups/{id}/members/{user}` | Steward, or self to leave. `last_steward`. |
| Noticeboard | `GET /workspaces/{id}/posts?before=&limit=` | Pinned first (first page), then by sequence. Includes replies and attachments. A published board snapshot has `snapshot {source_revision, source_name, source_workspace_id}`. The source fields are null for readers who cannot read the source. |
| | `POST /workspaces/{id}/posts` `{body, kind, due_at?, remind_at?, attachment_ids[], client_id?}` | `official` needs steward. |
| | `POST /posts/{id}/replies`, `PATCH /posts/{id}`, `DELETE /posts/{id}?reason=`, `POST /posts/{id}/pin` | Removing another user's post needs steward and reason (audited). |
| | `GET /workspaces/{id}/upcoming`, `GET /workspaces/{id}/search?q=` | Scoped to the workspace only. |
| Files | `POST /uploads` (multipart `file`), `DELETE /uploads/{id}` | PDF/PNG/JPEG by signature. Size, count and quota limits. |
| | `GET /files/{id}`, `GET /files/{id}/preview` | Authorized per owning post; PDF as attachment; sanitized PNG preview. |
| Notes | `GET/POST /notes`, `GET/PUT/DELETE /notes/{id}`, `GET /notes/upcoming` | Owner only, including for administrators. |
| Notifications | `GET /notifications`, `POST /notifications/{id}/open`, `POST /notifications/read-all` | Eligibility rechecked on list and open. |
| Chat | `GET /workspaces/{id}/chat?before=\|after=&limit=`, `POST .../chat` `{body, client_id}`, `POST .../chat/read` `{seq}` | Cursor replay via `after`. |
| Board | `GET /workspaces/{id}/board?epoch=&after=` | Replay since a revision (`reset: false`), or full state (`reset: true`): the compacted `snapshot` `{revision, objects}`, if any, plus later ops. Replay below `base_revision` falls back to full state. |
| | `POST /workspaces/{id}/board/ops` `{op_id, epoch, type, object_id?, payload, base_revision?}` | `add` (stroke/text/sticky), `erase`, `move`, `undo` (own latest). `stale_epoch`, `stale_object`, `object_gone`. |
| | `POST /workspaces/{id}/board/restore` `{revision, reason?}` | Steward. Starts a new epoch. `revision_compacted` if older than retained history and not a snapshot revision. |
| | `add` with `payload.kind = "image"` `{x, y, w, h, asset_id}` | `asset_id` is the actor's provisional PNG/JPEG upload. It becomes owned by this board and readable by board readers only. |
| | `GET /workspaces/{id}/board/render?revision=&x=&y=&w=&h=` | PNG of a region at a committed revision (publish preview). |
| | `GET /workspaces/{id}/board/snapshot-destinations` | The workspace itself plus writable ancestor units. Projects and groups: themselves only. |
| | `POST /workspaces/{id}/board/snapshots` `{revision, region{x,y,w,h}, destination_id, summary, client_id, confirm_audience?}` | Creates a destination-owned post with a fixed PNG. A broader destination needs `confirm_audience` = destination ID (`confirmation_required`). An unlisted destination returns 404. |
| Touch panel | `POST /panel/pairings` `{workspace_id}` | Desktop session with read access. Returns a single-use code `XXXX-XXXX` (default lifetime 120 s). |
| | `POST /panel/claim` `{code}` | No session. Rate limited per client. Starts a board-only session bound to that board and sets the separate `<cookie>_panel` cookie. `code_invalid`. |
| | `GET /panel/session`, `POST /panel/activity`, `POST /panel/end` `{reason: ended\|idle_lock}` | Panel cookie only. Reads do not reset the idle clock; writes and `activity` do. `end` is audited (`panel.end` / `panel.lock`). |
| Admin | `GET/POST /admin/users`, `PATCH /admin/users/{id}`, `POST /admin/users/{id}/reset` | `last_admin` protection. Deactivation revokes sessions. |
| | `GET/POST /admin/workspaces`, `PATCH /admin/workspaces/{id}` `{name?, move, parent_id?, archived?}` | Cycle and single-root checks (`cycle`, `invalid_parent`). |
| | `GET/PUT /admin/workspaces/{id}/memberships`, `DELETE .../memberships/{user}` | Audited with optional reason. |
| | `GET /admin/audit` | Restricted audit trail. |
| Ops | `GET <base>/healthz`, `GET <base>/readyz` | Readiness fails on DB or schema-head mismatch. |

## Socket messages

Client to server: `subscribe` / `unsubscribe` `{workspace_id}`, `board.preview` `{workspace_id, preview_id, stroke, done?}` (transient, bounded, writers only), and `ping`.

Server to client: `hello`, `subscribed`, `subscribe_failed` (unknown and forbidden look the same), `presence`, `chat.message`, `noticeboard.changed`, `board.op`, `board.epoch`, `board.preview`, `revoked` (subscription dropped after an access change), `access_changed`, and `session_ended` (socket then closes with code 4401). Every delivery rechecks the recipient's current access. After `subscribed`, clients catch up missed committed state through the API.

## Future lifecycle and administration contract families (not implemented)

S5–S7 and [DATA-LIFECYCLE.md](DATA-LIFECYCLE.md), [ARCHIVE-FORMAT.md](ARCHIVE-FORMAT.md), [ADMIN-CONSOLE.md](ADMIN-CONSOLE.md) govern later API design. Existing routes above do not imply these capabilities. Each implementation slice must publish concrete versioned request/response schemas and authorization/error tests before exposing routes.

| Resource family | Mandatory contract |
| --- | --- |
| Effective policy / usage | Authorized scope, value/source revision, units, observation generation/time, logical/physical/reserved breakdown; no private-body metadata |
| Policy drafts / plans / approvals | Base revision, validated patch, exact candidate/version selection, plan digest, preview completeness/expiry, reviewer and capability checks; conflict rather than silent overwrite |
| Exceptions / holds / schedules | Scope, reason, effective/expiry/review dates, hard ceilings, auditable transitions and notifications |
| Export / archive view / materialization | Selection and snapshot cutoff, current grants, bounded jobs, package digest, viewer TTL, provenance mappings, destination/audience, quota reservation and idempotency key |
| Lifecycle / reconciliation jobs | Approved bounded plan, policy/inventory generation, leases/checkpoints, cancellation boundary, precise partial outcome and per-attempt failures |
| Operational metrics / events / backup status | Scope/capability, time window, freshness/completeness, stable codes/correlation, protected paginated reports, explicit unsupported state; approved storage/target aliases only |

Publish stable machine-readable reasons including `quota_exceeded`, `rate_limited`, `storage_reserve`, `policy_conflict`, `stale_plan`, `approval_required`, `held`, `archive_invalid`, `archive_unsupported`, `archive_expired`, `import_conflict` and `job_partial` when implemented. Preserve S2's 401/403/uniform-404 access semantics before returning scope-specific diagnostics; an error must not reveal an inaccessible resource. Quota errors include only authorized usage/limit/required-byte/action fields. Unsafe requests retain CSRF/origin checks. Downloads/range requests and every queued worker reauthorize; an idempotency key never substitutes for identity or current grants. No arbitrary shell command, database URL, secret or filesystem path is accepted from ordinary web policy/job inputs.

### P5.1 implemented foundation: non-enforcing proposals

`GET /admin/policy-drafts?limit=20&before=<revision>` and `POST /admin/policy-drafts` are admin-only. POST requires `{base_revision, reason, profile}`; profile schema 1 accepts only observation mode and bounded integer file/user/workspace limits, rejects unknown fields and cannot activate rules. Concurrent saves return `policy_conflict` rather than overwrite a proposal. Responses explicitly report `enforced:false`; GET separately reports environment-backed runtime limits and `activation_supported:false`. Proposal/audit commit is atomic; actor/session authorization is refreshed and locked before save. This is a partial P5.1 foundation, not implementation of the future policy activation, inheritance, dry-run or retention contracts.

`GET /usage` returns the authenticated user's own tracked original/provisional attachment counts and bytes, the environment pilot limit and an explicit list of unmeasured categories. `GET /admin/usage` adds site aggregates and filesystem free-space/inode observations without exposing paths, filenames or content. Missing filesystem measurements return `unknown` with null values. `POST /admin/usage-observations` explicitly saves a partial sample and audit; serialization keeps a maximum of 100 operational samples. `GET /admin/usage-observations` returns the latest 20. These admin-only samples do not claim full metering, reconciliation, configured site budget or new enforcement. Aggregate query timeouts return `measurement_unavailable` rather than zero.

`GET /admin/storage-inspections` returns the latest 20 operator-triggered referenced-file inspection receipts to authorized operational readers and grants no enforcement authority. The trusted-host command `labadda inspect-storage --max-files 10000 --max-bytes 1073741824 --max-seconds 30` persists a receipt and audit, verifies selected original-file sizes/hashes, and measures previews separately. It verifies preview expectations where recorded; historical previews without expectations remain unknown. It never repairs/removes files or scans unreferenced files. `--max-seconds` is a cooperative scan budget, not a hard timeout on blocking OS/database calls. Live-filesystem consistency and full accounting remain explicitly unverified. Exit code 2 means issues, incomplete budget or failure; zero means the selected reference pass completed without reported issues, not full-site readiness. A process interruption may leave a running receipt without a completion timestamp.

### P5.1 narrow operational delegation

`GET /capabilities` returns the current session's `usage.read`, `policy.draft` and `identity.admin` booleans. Existing administrators retain their existing metadata/draft rights; no default grants are added to members. An explicit unexpired `usage.read` grant permits **GET only** on site usage, observation history and inspection receipts; it does not permit policy drafts, identity administration, recording observations, audit browsing, private files or notes.

Administrators manage grants with `GET/POST /admin/usage-readers` and `POST /admin/usage-readers/revoke`. Grant body: `{user_id, hours:1..720, reason, password}`; revoke body: `{user_id, reason, password}`. Password confirmation is mandatory on each change, CSRF applies, confirmation attempts are rate-limited, failed confirmations are audited without credentials, and server-held authority is refreshed through commit. API password values are masked SecretStr fields, never returned or audited. Grants target active non-administrators only. The list returns active entries first, at most 200, with total/truncation metadata; the UI can revoke a selected account independently of the displayed rows. Every read checks current expiry/identity; no inherited organizational membership grants this capability. Revocation affects subsequent requests, not bytes already received.

User web entry: `/operations`. Site administration adds the password-confirmed grant/revoke form. Recovery deletes copied operational delegations so a revoked post-backup grant cannot reappear; verified isolated recovery requires fresh delegation. Schema 0009 refuses downgrade while grant state remains. This implements only one narrow capability, not the full future approval/capability framework.

### P5.1 pending original-byte upload admission

`POST /uploads` now reserves the measured original byte length durably under the authenticated user's identity lock before filesystem work. Active reservations plus tracked originals participate in the **existing environment pilot limit**; proposals do not activate. A successful final transaction replaces its reservation with exactly one Asset row. Pending reservations expire after 600 seconds, are excluded after expiry and are cleaned for that user on later admission. `/usage` and site observations expose `pending_upload_original_bytes` from the same SQL snapshot as originals. Other reservation classes remain unmeasured. Recovery clears copied pending reservations.

Reservation, filesystem and finalization work run sequentially in a worker rather than blocking the ASGI event loop on synchronous locks/Pillow. Storage writes use exclusive temporary/preview creation, no-clobber publication and fsync, with cleanup of this attempt's partial paths only. Definite pre-commit failures release capacity; a lost commit reply is checked through a fresh connection and current identity. A confirmed durable Asset can complete the request. An absent/unavailable confirmation returns `upload_commit_unknown` (503), retains uncertain bytes and capacity conservatively, and requires inspection rather than blind retry. A client/process crash may leave private unreferenced files; automatic orphan deletion is not implemented.

Original-byte admission covers uploads and the generated snapshot path described below. Complete site/derivative/text budgets and full quota-ledger reconciliation remain unimplemented.

Published board snapshots now use the same user-identity serialization and original-byte capacity check as uploads, including active upload reservations. Their synchronous endpoint remains in a worker. Current identity/session validity is rechecked after storage and immediately before commit, and duplicate results require current destination read access. Definite pre-commit failures remove only unpublished files; lost replies are confirmed through a fresh Post read and current access. Unconfirmed outcomes return `snapshot_commit_unknown` (503) and retain bytes. This closes the generated-original writer gap recorded in the previous slice; it does not activate site/derivative/text budgets or complete the future policy engine. Schema 0011 adds the contributor index used by original-byte admission.

### P5.1 upload request identity and recovery

`POST /uploads` accepts an optional `Idempotency-Key` header matching `[A-Za-z0-9_-]{8,64}`. Generate an unpredictable key for each intended upload and retain it while resolving that attempt. Keys are scoped to the authenticated user and valid for 24 hours from first admission. The server binds a key to a versioned fingerprint of the measured content hash/length, submitted filename and declared media type. Changing any of these under the same key returns `upload_key_reused` (409). Legacy requests without the header retain their existing behavior and have no request receipt.

Reservation and pending receipt commit together before storage. Final Asset creation, receipt completion and reservation removal commit atomically. A completed same-key request returns the original Asset (201) without writing or charging again, even at quota. Every replay checks current content access; the receipt never grants access to a previously readable workspace. Deleted results return `upload_result_unavailable` (410), and inaccessible results return the usual 404. An active pending attempt returns `upload_in_progress` (409). Failed/expired pending attempts return `upload_request_incomplete` (409); they cannot be taken over automatically. Definite failures free the reservation while retaining failed request identity. Uncertain commits retain the pending state and private bytes for inspection.

`GET /uploads/requests/{request_key}` returns `{request_key, state, created_at, expires_at, asset}` for the current user only, with `private, no-store`. States are `pending`, `complete`, `failed`, or derived `expired` when a pending lease is absent/expired. Only complete results contain Asset metadata, after current authorization. Missing/expired receipts and another user's receipt return 404; board-only sessions are denied. Admin status grants no receipt access. A removed completed Asset returns 410 rather than a new upload. Fingerprints and file bodies are never included in receipt status.

Receipts expire logically after 24 hours and are lazily removed on that user's subsequent upload admission; there is no global background receipt purge. After expiry the same key can represent a new request, so it must not be used to recover an old outcome. Pending original-byte leases still expire after 600 seconds. Isolated recovery clears all copied request receipts as well as reservations: deduplication does not survive restore. Inspect restored content before starting a new upload; do not blindly retry pre-recovery keys. Schema 0012 refuses downgrade while request history remains.

The noticeboard and desktop board file pickers now generate keys and retain bounded unresolved attempts in the current view's memory. They provide explicit Check upload result, Retry same file and Dismiss upload controls. Checks never repeat a write; retries reuse the original File and key, stop before the server identity window expires and never take over a failed/expired receipt. Unresolved attachments prevent posting; another board image is blocked until its attempt is resolved. Missing/inaccessible results fail closed; already committed assets are not silently attached/placed again. A lost or malformed response body is treated as an uncertain outcome rather than success.

File bytes and attempts are not persisted across navigation, reload or sign-out. Keep the view open until resolved; dismissing an attempt does not delete a server file. Persistent recovery, complete accounting and orphan reconciliation remain future work. No policy proposal or retention rule is activated.

### P5.1 expected preview measurements

Schema 0013 adds nullable expected `preview_size` and `preview_sha256` to Asset metadata. New uploads and generated snapshots record the exact sanitized-preview byte count/hash when created; files without a preview record zero/null. Existing rows retain null/null: migration does not read or trust historical preview files. Populated measurement metadata prevents destructive downgrade.

`GET /usage` and `/admin/usage` add `tracked_preview_bytes` (sum of known expected bytes) and `unknown_preview_files` (previews without expectations) in the same SQL snapshot as originals. These are metadata observations, not a fresh filesystem scan, a complete physical ledger or new quota charges. Original-only pilot admission is unchanged. User/site/observer web views distinguish known and unknown measurements. Historical observation payloads may omit the new fields and must display unknown rather than zero.

Inspection summaries add `verified_preview_bytes`, `verified_previews`, `selected_previews` and `unknown_previews` (unknown expectations within the bounded selection). Issues include `file_class: original|preview`. A preview with known expectations must match size/hash; mismatched files are reported and left untouched. `preview_integrity: verified_selected` requires a completed selected pass, no issues, at least one selected preview and no unknown expectations. Otherwise it remains `unverified`; `complete_for_enforcement` is always false. A completed selection is not an atomic site snapshot. Restore checks known committed-preview expectations before publication; historical-null previews retain presence/bundle-integrity checks without being silently backfilled.

Trusted-host `labadda reconcile-previews` now offers a bounded dry run and explicitly confirmed application of missing historical preview metadata. It verifies originals and requires exact regenerated-preview equality; it never changes stored bytes. Apply requires stopped writers and a recomputed reviewed plan digest; metadata, audit and completion receipt commit atomically. Protected inspection history distinguishes `scope: preview_metadata_reconciliation`, `mode: dry_run|apply`, candidate/applied counts and stopped reasons. There is no web apply endpoint. See [operator procedure, limits and interruption handling](PREVIEW-RECONCILIATION.md). The command does not provide full ledger reconciliation or activate policy.

### P5.1 text and whiteboard logical charges

`GET /usage` and `GET /admin/usage` add `logical_charges`: `methods` (`utf8-text-v1`, `board-object-json-v1`), `by_type` for `post`, `chat`, `note` and `board_object` with live and removed bytes and item counts, `live_logical_bytes`, `removed_logical_bytes`, `board_charges` (`complete` or `incomplete`) and, for site scope only, `unreconciled_boards`. User scope covers only the caller's own contributions; site scope reports aggregates, including a notes total without per-user breakdown. Responses contain metadata only and `complete_for_enforcement: false`. A query timeout returns `measurement_unavailable`, never zero. `board_history_and_snapshot_bytes` and `database_physical_size` remain in the unmeasured list. Operator reconciliation receipts appear in `GET /admin/storage-inspections` with `summary.scope = "content_charge_reconciliation"`. See [charge reconciliation](CHARGE-RECONCILIATION.md).

### P5.1 physical database storage

`GET /admin/usage` (administrators and `usage.read` observers only) adds `database`: `state` (`ready` or `unknown`), `database_bytes` (`pg_database_size`), `categories` with physical size including indexes and TOAST for `collaboration_text`, `personal_notes`, `board_history`, `file_metadata`, `identity_and_access` and `audit_and_governance`, `other_bytes` (system catalogs, bookkeeping and free space inside the database files), and `board_history` with retained operation and snapshot counts. This is shared site overhead, separate from logical charges (DL-07), and never attributed to a user or workspace. `GET /usage` does not include it. A measurement timeout returns `unknown` with null values, never zero. Board history bytes and database size are no longer in the unmeasured list.

### P5.1 workspace usage

`GET /workspaces/{workspace_id}/usage` requires a normal session with current read access to that exact workspace. Organization grants still flow upward only; no administrator or `usage.read` delegation bypasses content membership. Groups and projects use their current direct grants. Missing and inaccessible workspaces return the same 404. Panel cookies and explicit panel markers are refused, including a panel-marked request carrying a desktop cookie. Identity, session and membership are refreshed after measurement before delivery. Archived/read-only workspaces remain measurable while readable.

The response has `scope: workspace`, the requested `workspace_id`, `observed_at`, `files`, `logical_charges`, `workspace_budget`, `unmeasured` and `complete_for_enforcement: false`. All file, logical-charge and board-coverage aggregates share one SQL statement/MVCC snapshot. The measurement uses a two-second SQL statement timeout rather than a hard whole-request deadline; database failures return `measurement_unavailable` (503), never false zeroes. Responses use `private, no-store`.

`files` reports `retained_files`, `retained_original_bytes`, `recorded_preview_bytes`, `unknown_preview_files` and `removed_post_original_bytes` (a subset of retained originals). It counts committed attachments through their owning post and committed board images through their owning workspace. Removed-but-stored post attachments and board images no longer visible can still occupy retained storage. Preview expectations are metadata, not a fresh filesystem scan. Provisional files/reservations have no committed destination: `pending_upload_bytes` is null with `pending_attribution: not_attributed_before_destination_commit`, never an invented zero.

`logical_charges` uses the existing versioned ledger methods, live/removed buckets and localized board-coverage labels for `post`, `chat` and `board_object` only. Private notes have no workspace attribution and are omitted entirely. Contributor identities, content bodies, filenames, object IDs, site/filesystem/database sizes, parent/child/sibling totals and other workspaces' coverage are not returned. Parent observations cover parent-owned content only, never a subtree. `workspace_budget.bytes` is null and its state is `not_configured`; this read-only view activates no workspace limit, retention or proposed policy.

Web entry: **Storage** within each workspace (`/w/{id}/usage`), alongside Noticeboard, Whiteboard, Chat and Members. Refresh clears the previous observation before requesting current data; denied refreshes do not keep old counters. Late responses after navigation are ignored. Pending attribution, unknown previews, retained removed files and incomplete board charges are labeled separately. Complete site/derivative budgets, reference reconciliation and enforcement remain future work.

### P5.1 site capacity proposals and previews

Schema 0015 permits immutable policy profile versions 1 and 2. Existing version-one documents remain unchanged; `{profile:{}}` still creates a version-one proposal with the original shape. `GET /admin/policy-drafts` retains `supported_schema` for legacy clients and adds `supported_schemas: [1,2]` and `supported_capacity_schema`. New web proposals use version 2, adding `site_asset_budget_bytes` (null = not configured; positive integer through 10 TiB), `filesystem_reserve_bytes` (positive integer through 100 GiB; proposed default 2 GiB), and `filesystem_reserve_percent` (integer 1–50; proposed default 10). Strict validation rejects booleans, fractional integers, unknown fields and non-observation modes. A finite site asset budget must fit the proposed single-file limit. These are proposals only, not active site admission or reserve settings. Version-two history prevents downgrade to schema 0014.

`POST /admin/capacity-forecasts` accepts `{profile:<version-two capacity profile>}`. It requires an administrator's normal session and CSRF; operational readers, members and panel requests cannot use it. Asset measurement has a two-second SQL statement timeout. Identity/session/admin authority is refreshed and locked after measurement; a sanitized audit with the normalized profile digest commits before the result is returned. It creates no policy revision or content mutation. Forecast results are ephemeral; they are not approval tokens, reservations or evidence permitting later activation.

The result always reports `state: incomplete`, `complete_for_enforcement:false`, `activation_supported:false` and `admission_changed:false`. `known_asset_lower_bound_bytes` is tracked originals (including provisional originals), recorded preview sizes and active pending original-byte reservations from one SQL snapshot. `site_asset_budget.maximum_possible_headroom_bytes` is max(0, proposed budget − known lower bound), or null when not configured. It is an **upper bound**, not guaranteed available space. Unreferenced files, unknown historical previews, other derivatives, temporary/system storage and full reconciliation remain incomplete.

`filesystem` reports an independently observed timestamp and valid free/total bytes, with proposed reserve `max(floor_bytes, ceil(total_bytes × percent / 100))`, using integer arithmetic. `maximum_growth_above_reserve_bytes` and `reserve_shortfall_bytes` are nonnegative; unavailable or invalid capacity yields unknown/nulls. Warnings explain a known lower bound over budget, unknown previews, unconfigured budget, missing filesystem observation or reserve shortfall/excess. The filesystem may be shared with other services; these observations are not atomic with the asset snapshot, a future growth prediction or a safe-admission decision. Database physical size is not added to asset bytes or assumed to reside on this filesystem.

The admin form previews capacity without saving, clears results after any profile edit or observation refresh, and ignores late responses for edited inputs. Saving still uses the existing revision conflict/reason/audit rules and cannot activate limits. History labels version-one capacity fields as not recorded. Proposal/account/workspace tables support keyboard-accessible horizontal scrolling on small screens. General approval, scheduling, exception and enforcement workflows remain later gates.

## P5.1 inventory job observation

`GET /admin/inventory-jobs` requires a normal administrator session or current
`usage.read` delegation. Optional `state` filters one supported job state;
`limit` is 1–25 (default20); `before` is the previous response's `next_cursor`
job UUID. Ordering is created-at descending then ID descending. This is a live
keyset listing, not a frozen snapshot; concurrent state changes can alter filtered
pages. Missing cursor IDs return404. Counts are returned-page counts, not site totals.
Listings omit attempt history; `GET /admin/inventory-jobs/{id}` returns at most100
numbered attempts. Both routes recheck identity/session/capability after reading,
reject panel markers/cookies, omit request keys and filesystem paths, and expose
no write routes. Lease expiration is observed using the database clock; reporting
an expired running job does not mutate its state or start a retry. Accepted receipt
IDs allow correlation with inspection history. CLI `show-inventory` exposes the
same sanitized detail. These observations authorize neither enforcement nor deletion.

## C1 to-do lists

Normal sessions only; explicit panel requests are refused. Personal lists are
owner-only. Shared list scope is one immutable workspace, governed by existing
upward-only read and write/archive policy. Administrator status supplies no content
grant. No deletion, assignment, reminders or task sockets in C1.

- `GET /todos/lists?workspace_id=<uuid>&after=<uuid>&limit=25`: omit workspace for
  personal lists. `GET /todos/lists/{list}/tasks` uses the same cursor/limit.
  Results are `{items,next_cursor}`, ordered by UUID ascending, limits 1–50.
  Pages are live observations, not frozen snapshots.
- `POST /todos/lists`: `{client_id: UUID,title,workspace_id?: UUID|null}`.
- `PUT /todos/lists/{list}`: `{title,revision}`.
- `POST /todos/lists/{list}/tasks`: `{client_id: UUID,title,description?,due_date?,
  priority?,checklist?,done?}`. Date is a calendar `YYYY-MM-DD`; priority is
  low/normal/high; checklist items are `{title,done}`. Defaults: empty description,
  no due date, normal priority, empty checklist, open task.
- `GET /todos/lists/{list}/tasks/{task}`: current task after current scope checks.
- `PUT /todos/lists/{list}/tasks/{task}`: full task fields plus expected `revision`.
  `revision_conflict`409 preserves committed content; fetch/review before resaving.

Titles are trimmed, nonempty and at most200 characters, description at most10,000,
checklists at most50 entries. Bootstrap safety ceilings are100 lists per scope and
2,000 tasks per list, not an activated configurable quota policy. Unknown fields
are rejected. Creation IDs are unique per creator/resource kind and bound to the
normalized complete intent and destination: identical retries return the current
resource; changed intent returns `request_reused`409. Current write authorization
is still required on replay. Scope cannot be changed by editing.

Writes serialize identity/session changes, then shared authorization against
membership/tree/policy changes using short table SHARE locks, preceded by target
workspace KEY SHARE to avoid conflicting workspace row writers/FK cycles. Task
writers serialize through the list row; list-count admission uses a scope advisory
lock. Session time validity is checked again immediately before commits/replays.
This deliberately favours correctness for the single-process pilot; table locks
must be revisited with evidence before broader write throughput is required.
C1 task text is not included in the earlier text-charge ledger: usage marks
`todo_logical_bytes` unmeasured. Physical database totals still include these tables.

C1 list conflict recovery also provides `GET /todos/lists/{list}`. It checks the
current personal/workspace scope before and after serialization, including against
administrators and panel requests. The browser uses it only on an explicit latest
list reload; this replaces the rename draft and revision after user confirmation
through the named action.

## C2 workflow and task content history

Task create/edit accepts optional `status`: `todo`, `in_progress`, `blocked`, `done`.
The `done` projection must agree with explicitly supplied status. An omitted state
uses C1 creation semantics; on edit it preserves the current intermediate state if
completion is unchanged, sets Done on completion and To do on reopening. C1 create
fingerprints are preserved when status is omitted/null, including after migration.
Task responses include status. These changes do not add assignment or task sockets.

`GET /todos/lists/{list}/tasks/{task}/history?before=<revision>&limit=10` returns
`{items,next_cursor}` ordered by descending revision; limit 1–25, before>=1. Events
contain revision, actor_id, current actor display name, action, field before/after
values and timestamp. History is protected content: current list access applies
before/after reading, even for admin/operational readers and panels. Migration0018
creates baseline events with unknown actor/earlier changes for existing tasks;
baselines never reconstruct older edits. Normal creates/updates write history
atomically with the task revision, including failed/conflicting/replayed requests
not creating extra history. History failure aborts the edit. Populated downgrade
refuses to discard history. History has no pruning or deletion API in this slice.

## C2 assignment and My Tasks

`GET /todos/lists/{list}/assignees` returns active eligible readers, or only the
owner for a personal list. Optional literal `q` searches names/usernames (max100
characters); UUID `after` pages by user ID, limit1–50 (default25). Results are
`{items,next_cursor}` with public colleague identity only, not grant topology.
Eligibility is a point-in-time snapshot; assignment rechecks it independently.

`PUT /todos/lists/{list}/tasks/{task}/assignee` accepts
`{user_id: UUID|null,revision: positive integer}`. Current task write access is
required; an administrator without content access cannot assign. Targets must be
active readers of the actual workspace; a personal task can name only its owner.
Null clears an assignment, including a stale/inactive one. Changed assignment
increments the task revision and records named before/after values atomically.
An unchanged target with a current revision is a no-op; stale revisions conflict.
No notification or membership is created. Unknown write outcomes require reloading
the task/history before retrying, not automatic write replay.

Actor/target identities are locked in deterministic UUID order before session,
workspace authorization and list locks. Final target eligibility and session time
validity are checked under those locks. C1/C2 field edits preserve assignment;
creation payload/fingerprints have no new assignment field.

`GET /todos/mine` returns all owner-private tasks plus shared tasks assigned to the
caller in currently readable spaces. Optional `status` uses workflow states;
UUID `after` and limit1–50 (default25) page by task ID. Items add `list_title` and
`workspace_id`; task JSON adds nullable `assignee` with id/display_name/is_active.
Responses include `next_cursor` and `restart_required`. Final grant loss filters
protected rows; any visible-workspace change clears the cursor and asks the client
to restart. Pages are live observations, not frozen snapshots. Membership removal
hides a shared task without rewriting assignment/history. The caller can still
see their personal tasks. These normal-session routes reject panels and grant no
admin/operational-reader bypass. Migration0019 protects current and past assignment
evidence from a lossy downgrade.

## C2 immutable task comments

`GET /todos/lists/{list}/tasks/{task}/comments` returns `{items,next_cursor}` newest
sequence first. Optional positive `before` sequence and limit1–50 (default25)
provide bounded older pages. A comment includes id, sequence, plain-text body,
created_at and author id/current display_name. Current list/task access is checked
before and after reading; panels/admins/operational readers have no bypass.

`POST` to that path accepts `{client_id: UUID,body: string}`. Trimmed text must be
nonempty and at most4,000 characters. The author/request key binds actual task and
normalized text; identical retry returns the same comment, changed intent conflicts.
Current source write/archive/session checks apply to retries too. Per-list locking
serializes per-task append sequence; pilot ceiling1,000 comments per task. Replay
works at that ceiling. Posting is independent of the task field revision. There
are no comment edit/delete/attachment/notification/live-event endpoints in this
slice. Source read-only policy permits reading; normal write rules govern posting.
Comments and request identity survive recovery; populated downgrade refuses loss.

### C2 shared task invalidation

`tasks.changed` on the existing workspace socket contains exactly
`{"type":"tasks.changed","workspace_id":"<actual list workspace UUID>"}`.
Publication follows a new committed list create/rename, task create/edit,
assignment change or comment append. Creation replay, unchanged assignment,
rejected requests and personal mutations do not publish. No new socket command,
subscription grant, durable event cursor, schema migration or notification is added.
The hub's current delivery checks and panel whitelist apply.

Signals can be missed, duplicated or reordered; clients must read authorized HTTP
state rather than apply event deltas. Treat `subscribed` as a possible catch-up
boundary. Personal lists have no socket invalidation in this slice.
