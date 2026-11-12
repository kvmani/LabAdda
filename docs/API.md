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
| Auth | `POST /auth/login`, `POST /auth/logout`, `GET /auth/session` | Login is rate limited per user and per client address. The session payload also carries `release`, `welcome_pending` (normal sessions only, until the caller dismisses the welcome) and `whats_new_pending` (welcome already dismissed and the caller has not seen this release's notes). |
| | `POST /auth/activate` `{token, password}` | Redeems one-time activation or reset code (min. 10 characters). |
| | `POST /auth/password` `{current_password, new_password}` | Revokes other sessions. |
| My account | `GET /me/profile` | `{record, access}`: the caller's own staff record (same fields as the administrator profile, including contacts) and retained grants with upward-only inheritance. Read-only. |
| | `POST /me/password` `{current_password, new_password}` | Normal session and CSRF. Rate limited per person (shares the sign-in window; `429 rate_limited`). `invalid_credentials` (audited with outcome `denied`), `weak_password` (min. 10 characters), `password_unchanged` (all `400`). Revokes every other session and closes their sockets (`session_ended`); keeps the caller's. Returns `{ok, sessions_ended}`; audited as `auth.password_changed` with the count. |
| | `POST /me/welcome/dismiss` | H4, schema 0032. Normal session and CSRF; signed out and panel sessions get `401`. Stores `welcome_dismissed_at` for the caller, marks the running release's notes as seen, returns `{ok: true}`. Idempotent. |
| | `POST /me/whats-new/seen` | H4. Same rules. Stores the server's current release as the caller's `whats_new_seen_release`; the client sends nothing, so it cannot claim another release. Returns `{ok: true}`. |
| | `GET /me/sessions` | `{items:[{id, browser, started_at, last_seen_at, current}]}`, current first, then newest. `id` is a public identifier, never the cookie token or its stored digest. `browser` is a short label such as `Firefox on Linux`, derived at sign-in; the raw User-Agent is not stored. |
| | `DELETE /me/sessions/{id}` | Ends another of the caller's sessions and closes its socket; audited as `auth.session_ended`. Another person's, unknown or already-ended id returns the uniform `404`. The current session returns `409 current_session` (use sign out). |
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
| | `GET /admin/audit` | Audit explorer (A2, below). |
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

### C3 conversation-to-task

`POST /todos/lists/{list_id}/from-conversation` accepts the C1 TaskCreate fields plus
`source_kind` (`post` or `chat`), `source_id` (UUID) and strict boolean
`confirm_audience` (default false). Posts must be readable, undeleted top-level
posts; chats must be readable actual messages. Destination uses actual current
list scope/write policy. Any different shared workspace requires confirmation
(`422 audience_confirmation_required`); a personal destination is owner-only.
Title/description are the user's reviewed copy, not server-expanded source text.

Response201 uses the compatible task representation. `has_source` is a generic
provenance boolean visible to task readers; it conveys no source IDs/names/body.
Old task create fingerprints are unchanged. Conversion identity additionally binds
source kind/ID, confirmation, destination and normalized task fields. Identical
replay returns the same task after current-authority checks; changed intent or
reuse across the old create endpoint returns409. New shared conversions emit the
existing content-free task hint only after atomic task/history/reference commit.

`GET /todos/lists/{list_id}/tasks/{task_id}/source` requires actual task/list access
and independently current source read access. Success returns kind, source ID,
workspace ID/name, current body and creation time. This explicit protected view
never grants source access. No reference/missing/removed/purged/out-of-scope source
uses uniform404. Task content/history never receives this protected payload.
No panel access, attachment copying, edit synchronization or source permission
changes. Source physical purge sets reference FKs null and retains the task copy.

### C3 protected whiteboard context

`POST /todos/lists/{list_id}/from-board` accepts TaskCreate plus
`source_workspace_id`, strict `source_epoch` (>=1), strict `source_revision` (>=0)
and strict `confirm_audience` (default false). The source must be a readable
existing Board row. Same/personal/different workspace audiences follow CT-10;
different shared workspaces require explicit confirmation. Fields describe the
user's task, never copied board strokes/images/names. Task/history/reference commit
atomically; only a new shared task emits the existing content-free update hint.

New requests compare the reviewed tuple to the current board under FOR SHARE.
Mismatch returns409 `board_context_changed`; no task/history/reference is stored.
Committed receipt lookup precedes this comparison: an identical authorized retry
returns the same task after ink/restore, with its original recorded tuple. Changed
intent/source/context/destination with the same request ID returns409. C1 and
conversation fingerprints remain unchanged.

`GET /todos/board-context/{workspace_id}` returns only `{epoch, revision}` for a
currently readable existing board, rechecking current access before return. It
serves deliberate context refresh without fetching strokes/images.

The existing protected task `/source` endpoint returns `kind:board`, workspace
ID/name, recorded `epoch`/`revision` and `current_epoch`/`current_revision` only to
current task AND board readers. It does not return a historical render or image.
Missing/purged/inaccessible source uses uniform404. Ordinary task/history responses
retain only generic `has_source`, never board context. Board purge clears its FK
but keeps recorded context stored; populated context downgrade is refused even
when the source FK is null. Both endpoints reject panel sessions.

### C4 chat threads

Chat creation accepts optional `parent_id` (default null). It must name a top-level
message in the actual destination workspace; replies to replies return422. Same
client ID binds workspace, body and parent. Existing flat history and socket chat
messages include parent_id and retain every message, including replies. Sends
serialize per workspace before sequence allocation; acknowledgements/fanout follow
commit. Current source write/session policy applies to replay.

`GET /workspaces/{workspace_id}/chat/{message_id}/replies` returns root, ascending
messages (latest page) and next_before. Optional positive before and limit1–100
(default25) page older replies. Both actual root scope and final read authority
are checked. No panel access. Unread remains per workspace, not per-thread.

### C4 validated chat attachments

Chat creation additionally accepts `attachment_ids` (up to20 submitted IDs and the
configured per-message limit after deduplication). Intent binds the canonical set,
body, root and workspace. Body may be empty when files are present; empty/whitespace
without files returns422. Only the sender's provisional uploads can bind; used or
foreign files return422. Claims lock files in UUID order and commit with the chat.

Chat stream/thread/socket messages include `attachments` with same-origin URLs,
validated metadata and previews. File/preview authorization resolves the actual
chat workspace each request; removed members, unrelated admins/siblings and panels
cannot retrieve them. No rebind to posts/boards/another message. Workspace retained
file/preview observations include chat-owned assets. Storage caps remain the existing
upload/configuration controls; this does not activate future P5 quota proposals.

### C5 daily overview

`GET /dashboard` returns current actor data: up to25 active personal/shared-assigned
tasks (due then priority),10 earliest dated private notes,10 recent visible updates
and10 unread accessible conversations. tasks_more/notes_more/chats_more describe
bounded windows; no site-wide totals. Source permissions apply to every item;
final grant changes filter data, suppress shared more flags and set restart_required.
Includes today/timezone/observed_at. Calendar date follows valid configured
LABADDA_TIMEZONE. Administrators get only their own/current-source content; panels
are refused. Notification open still uses its existing current-source API.

### C5 owner alert preferences

`GET /notification-preferences` returns mentions, official_notices, reminders and
revision for the current owner only; absent storage means all true, revision0.
`PUT` accepts exactly these fields with strict booleans and expected revision.
A current identity lock serializes saves, stale revisions return409 and a successful
save increments revision. No target-user field or administrator override exists.
Panels/unsafe requests without CSRF are refused. New queued mention/official/
reminder occurrences follow the recipient's choices. Previously queued alerts
remain visible; re-enabling never replays consumed muted reminder occurrences.
This does not add task assignment/due reminders or change source permissions.

## A1 · Console access and navigation (AD-01–02)

`GET /admin/console` returns `{sections: string[], read_only: boolean}` for the
current normal session. Sections are `overview`, `people`, `org`, `activity`,
`health`, `storage`, `backups`, `audit`, `events`, `settings`, `help`, in that order.
Administrators receive all sections; an active, unexpired `usage.read` observer
receives only overview/activity/health/storage/backups/events, read-only. No unit
administrator role is introduced in A1. Ordinary members receive403
`usage_read_required`; signed-out, deactivated and board-only/explicit panel
requests receive401. No content is returned. Each request re-evaluates authority.

Existing admin/usage endpoint rights and errors are preserved through the shared
`deps.require_console(section, admin_only=...)` dependency. Delegation never permits
identity, policy, audit, settings or write access. Legacy `/operations` web links
redirect to `/admin/storage`; backend URLs and payloads remain compatible.

## P1 · Staff-state foundation (schema0026)

Existing identity/authentication response shapes and permission gates are unchanged.
Legacy account creation records invited status; activation records active status.
Legacy enable/disable keeps the employment state and access switch consistent,
without adding any new administration right. Successful normal sign-in observes
only the site-local date; no new timestamp/history endpoint is exposed. Staff
changes advance the record revision; sign-in observations do not.

The read-only people list/profile/timeline/export APIs are the next P1 slice and
are not exposed yet. [Implementation/limits](development/people.md).

### P1 directory reads

`GET /admin/people` (normal current administrators only): `q` literal case-insensitive
name/username/employee-number search (max120 characters); `status` one employment
state; `unit_id` an organisation unit; `include_children` defaults true (home-unit
filter); `role` admin/member/steward (direct membership, within selected units when
filtered); `sort` name/username/employee_no/status/last_seen_on; `descending`
defaults false; `limit`1..100 defaults50; `cursor` max1024 characters.
Returns `{people:[{id,username,display_name,employee_no,designation,status,revision,
sign_in_enabled,is_admin,home_unit:{id,name}|null,last_seen_on:date|null}],next_cursor}`.
Null sort values remain last in both directions; ID breaks ties. Cursors are bound
to the filters/sort; malformed or mismatched cursors return422 `invalid_cursor`.
Unknown/non-unit filters return404. No staff contacts, credentials, content or
exact sign-in times in the directory. Metadata authority is refreshed before
returning; ordinary members/operational readers get403, panel/signed-out get401.
Timed-out/unavailable database reads return503 `people_unavailable`, never empty
success. The additional reads are described below.

### P1 profile, access, timeline and report

All routes below use the same current-administrator/normal-session gates and final
read checks as the directory. Missing people return404 only after that gate.
`GET /admin/people/{id}` adds contact_email/contact_phone and status_effective_on,
expected_return_on/joined_on dates to the directory record. No credential/session
fields or content. Missing staff values are null, not invented defaults.

`GET /admin/people/{id}/access?limit=50&cursor=WORKSPACE_UUID` returns
`{memberships:[{workspace:{id,name,kind,archived},role,inherited,sign_in_enabled}],next_cursor}`.
Limit1..100; stable workspace-ID order. Includes retained grants for departed
people; `sign_in_enabled` distinguishes a recorded grant from usable sign-in.
Inherited organisational access goes upward only and carries member authority;
home-unit pointers and administrator status do not create grants. Projects/groups
remain direct. These are scope names/roles, never workspace contents.

`GET /admin/people/{id}/timeline?limit=50&before=AUDIT_ID` returns
`{items:[{id,occurred_on,actor:{id,display_name}|null,summary,reason,outcome}],next_cursor}`.
Only person-targeted identity/membership/authority history; dates use the site
calendar, including sign-ins. No exact sign-in times, raw audit details, file names,
request/search terms or credential values. Summaries are controlled plain sentences;
unrecognised activity has a generic summary and no free-form detail/reason.

`GET /admin/people/export.csv` accepts the directory filters/sort (no page cursor),
returns a UTF-8 CSV report (with BOM for office spreadsheets) of the list columns, with blank cells for unknown fields.
Spreadsheet formula prefixes (including leading whitespace/control characters) are
escaped. At most10,000 rows; a larger result returns422 `export_limit` with guidance
to narrow filters. It audits `people.export` as report preparation with row count,
never the query or row data. Authority is rechecked after audit commit; no content
or private contacts in this bulk report. Filename is the fixed `people.csv`.
This is a directory report, not the future staff-import template or a content archive.


### P2 internal plan format

`changes/plan.py` defines the internal
metadata contract for the later preview/apply service: `format_version:1`, `kind`
(`add_person|edit_person|transfer`), `actor_id`, normalized `request`, positive
record `revisions`, ordered `steps`, `warnings`, `blockers`, nonnegative
`affected_people` and `digest`. Each step has `target_type` (`identity|workspace`),
`target_id`, a plain `summary`, and structured `before`/`after`. Issues have `code`,
`message`, and nullable `target_id`. Object keys sort lexically; arrays retain order;
strings retain exact Unicode; compact UTF-8 JSON excludes the digest itself before
SHA-256. Floats and implicit Python-to-JSON conversions are refused.

These are immutable server-built snapshots, with detached response copies. The
digest is a change detector, **not authorization or a signature**. No future apply
route may accept client-provided steps: it must reauthorize, lock and rebuild from
the validated original request and current state. Builders must select only staff
metadata and never insert credentials or private collaboration content into plans.
The first executable slice below supports reviewed staff edits. Add/transfer
remain P2 work. P2 remains in progress.

### P2 reviewed edits (first executable slice)

Normal site administrators only; members and operational readers receive403,
board-only intent and signed-out sessions401. POST requests require same-origin
and the normal session's CSRF token. No content access is granted.

- `POST /admin/changes/preview`: `{request:{kind:"edit_person",person_id,fields}}`.
  Fields permit only display_name(1–120), designation(120), employee_no(64),
  contact_email(254), contact_phone(64). Unknown keys, empty edits, controls and
  invalid Unicode are rejected422. Strings are trimmed; blank optional fields
  become null. Display name cannot be cleared. Preview returns the version1
  plan above, including current revisions, ordered before/after steps, blockers,
  warnings and digest. A duplicate employee number and no effective change are
  blocking problems. No staff or audit rows are written by preview.
- `POST /admin/changes/apply`: same `request`, `digest`(64 lowercase hex),
  `revisions`(at most100 UUID keys with positive32-bit integers) and a trimmed
  `reason`(3–500). Returns `{applied:true,person_id,revision,digest}` after commit.
  The actor/session is refreshed under locks; current plans are rebuilt, never
  supplied by clients.409 `plan_stale` means re-preview;422 `plan_blocked` means
  fix the request. Missing target404.503 `changes_unavailable` means the database
  could not complete the operation; reload the record before retrying.

Apply takes the shared admin-role lock, actor identity/session locks and target
identity lock, rechecks authority, matches the complete digest/revision map and
writes the edit, revision and parent/per-step audits in one transaction. A retry
of an applied plan returns409. Audit steps retain structured staff before/after;
no request bodies or credentials are logged. Live identity revalidation follows
commit. Once committed, the receipt is returned even if the actor's session or
authority ends immediately afterwards: the change is durable and a retry could only
return409. Every receipt carries `kind`; the request is a discriminated union on `kind`.

### P2 add a person (PO-10)

`request:{kind:"add_person",username,display_name,fields?,home_unit_id,role,joined_on?}`.
`username` is trimmed, lowercased and must match the shared rule (2–63 of
`a-z0-9._-`, starting with a letter or digit); `display_name` 1–120; `fields`
permits designation, employee_no, contact_email, contact_phone (same bounds as
edits); `role` is `member|steward`; `joined_on` is an ISO date (default: today in
the site zone). Unknown keys, including `is_admin` and `status`, are rejected422.
New accounts are never administrators.

Steps: create the invited account (step target `new:<username>`; audits record the
real identity), make the home unit with the role, issue a one-time activation code.
Blockers: `username_taken`, `duplicate_employee`, `unit_unavailable` (project,
group or archived unit). Warning `similar_name` (target: the existing person) when
another display name is very similar; it never blocks. A missing unit returns404.
`revisions` is `{}`. The receipt adds `activation:{code,expires_at}`: the only time
the code is returned (only its hash is stored, never in audits). Concurrent identical
confirmations create one person; the other gets409.

`POST /admin/changes/activation-code` `{person_id,reason}` (reason 3–500): for a person
still `invited` and not yet activated, marks every unused code of theirs as used,
issues a fresh activation code and audits `identity.activation_reissued` with the
reason (never the code) in one transaction. Returns `{person_id,code,expires_at}`.
409 `not_invited` otherwise; missing person404; same denial matrix as apply.

### P2 transfer (PO-12)

`request:{kind:"transfer",person_id,to_unit_id,role,keep_previous?,leave_workspace_ids?,acknowledge_no_steward?}`.
`role` is `member|steward`; booleans are strict (default false);
`leave_workspace_ids` lists at most100 of the person's projects/groups to leave
(all others are kept). Steps, in order: change the home unit (before/after
`home_unit_id`,`home_unit` name); the membership in the new unit; then each
membership removed (the previous home unit unless `keep_previous`, and each listed
project/group), each with before/after `role`. `revisions` holds the person.

Warnings (names and counts only): `access_gained`/`access_lost` per workspace the
person can newly read or no longer read, computed from current and proposed grants
with the upward-only rule; `open_tasks` per lost workspace with `count` of open
shared tasks assigned to the person (no titles); `unit_without_steward` when
acknowledged. Blockers: `person_inactive` (suspended, retired or left),
`unit_unavailable` (not an open organisation unit), `same_unit`, `not_a_member`
(a listed id is not one of their projects/groups), `group_needs_steward` (leaving
would leave a project/group with members but no steward), `unit_without_steward`
(not acknowledged; checked for the old unit, and for the new unit when the person's
steward role there is lowered). Missing person or unit404. A handover period is not offered.

Apply locks the admin roles, the actor, the role locks of every workspace in scope
(sorted), then the person row; it rebuilds, compares digest and revision, writes
home unit, revision, memberships (with their `membership.set`/`membership.remove`
audits), the parent/step audits and steward notices in one transaction. The receipt
adds `stewards_notified` (a count). After commit the person's live subscriptions are
revalidated: old-unit subscriptions receive `revoked`, and later reads return404.

Steward notice: `GET /notifications` item `kind:"reassign"` for each active direct
steward (other than the person) of a lost workspace with open assigned tasks:
`title` names the person and the current open count; `link:{view:"todos",workspace_id}`.
It is hidden once the recipient can no longer read that workspace.

## P3 · Positions, authority, leave, retirement, suspension (schema 0033)

Same endpoints, authority and protocol as P2 (`POST /admin/changes/preview` and `/apply`,
digest + revisions + reason, 409 `plan_stale`, 422 `plan_blocked`, 404 for a missing person,
unit or position). Members, stewards and usage readers 403; signed-out and panel sessions 401.
Every plan carries names, roles, dates and counts only. Dates are site-calendar ISO dates; an
end or return date must be after today and within five years (blocker `invalid_date`).

Table `unit_positions(id, workspace_id, user_id, position head|deputy|charge, acting,
starts_on, ends_on, revert_role member|steward|none, covers_id, ended_at, end_reason
expired|ended, created_by, created_at)`. A partial unique index allows one current Head per
unit, plus at most one *acting* Head while that Head is away. A Head or Deputy is always a
steward: any membership write (reviewed or legacy) that removes or demotes the holder ends the
position (`position.end`). `charge` records an additional charge. Rows are never deleted; the
0033 downgrade refuses while any exist. Audits: `position.appoint`, `position.end`,
`position.expire` (actor null).

`GET /admin/people` rows and `GET /admin/people/{id}` add `positions:[{id,workspace:{id,name},
position,acting,starts_on,ends_on}]` (current only).

Kinds (`request` bodies; all forbid unknown keys):

- `promote {person_id, designation?, workspace_id?, role?, position?}`: designation and/or the
  role in a workspace they already belong to, optionally a vacant `head|deputy` (role must be
  `steward`). Warnings `moderation_gained|moderation_lost`. Blockers `not_a_member`,
  `holds_position` (demoting a holder), `unit_without_steward`/`group_needs_steward`,
  `unit_has_head`, `already_holds`, `person_inactive`, `no_changes`.
- `change_authority {workspace_id, position, successor_id, acting?, ends_on?,
  replace_person_id?, outgoing_role?}`: `ends_on` is required exactly when `acting`. For Head the
  current Head is replaced automatically (an acting Head covers instead while the Head is away);
  a current acting Head ends and returns to its recorded role. Deputies are replaced only when
  `replace_person_id` names one. The outgoing holder keeps `outgoing_role` (default steward);
  the successor becomes steward; an acting row records `revert_role`. Blockers
  `holder_inactive`, `holder_outside_unit` (home not in the unit's branch and no membership),
  `unit_unavailable`, `already_holds`, `not_a_deputy`, `invalid_date`. `revisions` holds the
  successor; the receipt's `person_id` is the successor.
- `additional_charge {person_id, workspace_id, role, position?, ends_on?}`: a membership in a
  second open unit and a `charge` (or position) row; on `ends_on` it is removed automatically.
  Warnings `access_gained`, `ends_automatically`. Blockers `same_unit`, `already_member`,
  `unit_unavailable`, `unit_has_head`, `person_inactive`.
- `leave {person_id, expected_return_on, block_sign_in?, acting?:[{position_id,
  successor_id}]}` (≤ 20): status `on_leave`; blocking sign-in ends sessions at once. Each cover
  is an acting appointment ending on the return date. Warning `position_uncovered`. Blockers
  `person_unavailable`, `not_their_position`, `unit_has_acting_head`, `last_admin`, `self_change`.
- `return {person_id}`: status `active`; acting appointments covering the person end and revert.
  Blocker `not_on_leave`.
- `retire {person_id, status retired|left, keep_workspace_ids?, successors?:[{workspace_id,
  successor_id, acting?, ends_on?}], acknowledge_no_steward?}`: ends every position, appoints
  successors, removes memberships not kept, sets the status and ends sign-in and sessions.
  Warnings `last_steward` (each workspace where they are the last active steward),
  `open_tasks` (`count` per readable workspace), `position_vacant`, `unit_without_steward`.
  Blockers `position_needs_successor` (Head/Deputy without successor or acknowledgement),
  `group_needs_steward` and `successor_not_member` (a project/group successor must be one of its
  active members), `unit_without_steward`, `successor_not_needed`, `not_a_member`,
  `already_departed`, `last_admin`, `self_change`. The receipt adds `stewards_notified`; the
  notice is `kind:"reassign"` with title "<name> has retired or left. N open shared tasks…".
- `suspend {person_id}`: immediate; positions end, memberships are kept but give no access,
  sessions end and live sockets receive `session_ended`. Warning `no_active_steward`. Blockers
  `person_unavailable`, `last_admin`, `self_change`.
- `reinstate {person_id}`: from suspended/retired/left to `invited`: removes every retained
  membership and position, never restores the administrator role, clears the password, voids
  older unused codes and issues a new activation code (receipt `activation:{code,expires_at}`,
  only here). Warning `last_placement` lists the earlier workspaces and roles (from retained
  grants and the last departure's audit steps). Blocker `not_departed`.

Transfer (P2) now also ends positions in a unit the person leaves or stops stewarding (identity
steps after the home-unit step) and warns `unit_without_head`.

Scheduler step `positions.expire_due(now)` (each reminder tick, idempotent, at most 100 per
pass): at the start of `ends_on` in the site zone it ends the row (`end_reason:"expired"`),
applies `revert_role` and writes `position.expire`. The P5 attention list reads those rows.

## P4 · Organisation chart and unit changes (schema 0034)

`workspaces.code` (organisation units only): 2-24 characters, uppercase letters, digits and
dashes, unique among units (archived ones included); null for projects and groups. Existing
units were given a code from the initials of their name. `workspace_json` adds `code`. The 0034
downgrade refuses while any code was chosen rather than derived from the unit's name.

`GET /admin/org/tree` (current administrators; members, stewards and usage readers 403; signed
out and panel sessions 401) returns names, roles and counts only:
`{units:[{id,code,name,archived,parent_id,head:{id,name}|null,acting_head:{id,name}|null,
stewards:[{id,name}],people,members}], spaces:[{id,kind project|group,name,archived,
stewards:[{id,name}],members}]}`. `people` counts home-unit people; `members` counts direct
memberships; stewards are active people only. Projects and groups are not part of the tree.

Unit kinds use the same `POST /admin/changes/preview` and `/apply` (digest, `revisions:{}`,
reason, 409 `plan_stale`, 422 `plan_blocked`). A unit has no revision counter, so staleness is
the digest over the unit's reviewed before/after state. Steps use `target_type:"workspace"`
(a unit about to be created is `new:unit`). The receipt is `{applied,kind,unit_id,digest}`.
The audit parent row has `scope_type:"workspace"`, `scope_id` = the unit; each step is a
`people.change_step`. After commit every live socket is revalidated. Units are never deleted.

- `unit_create {parent_id, name, code, head_id?}`: an optional Head becomes steward of the new
  unit with a `head` position. Warnings `unit_without_steward` (no Head), `access_gained`.
  Blockers `unit_unavailable` (parent not an open unit), `duplicate_code`, `holder_inactive`.
- `unit_rename {unit_id, name?, code?}`: at least one. Ids do not change. Blockers `no_change`,
  `duplicate_code`.
- `unit_move {unit_id, new_parent_id}`: with its sub-units. Warnings `access_gained` and
  `access_lost`, one per unit, with `target_id` and `count` of people (counts only). Blockers
  `cycle` (beneath itself or a sub-unit), `root_fixed`, `same_parent`, `unit_unavailable`.
- `unit_merge {unit_id, into_unit_id}`: sub-units move under the target; every person whose
  home is the source gets the target as home and a `member` membership there (an existing
  membership is kept); positions in the source end; the source is archived. Members keep their
  memberships in the source, so they still read its history. Warnings `history_kept`,
  `access_gained`, `access_lost`. Blockers `root_fixed`, `same_unit`, `cycle`,
  `unit_unavailable`, `too_many_people` (over 500).
- `unit_split {unit_id, name, code, person_ids[1..200], acknowledge_no_steward?}`: creates a
  sibling under the source's parent and moves the chosen people (home must be the source) with
  their role; their source memberships and positions end. Warnings `access_lost`, `open_tasks`
  (a count; the stewards of the source are not notified), `unit_without_steward`. Blockers
  `root_fixed`, `duplicate_code`, `person_not_in_unit`, `unit_without_steward` (for the source
  or the new unit unless acknowledged).
- `unit_close {unit_id}`: archives. Blockers `unit_has_people` (any person's home),
  `unit_has_subunits` (open ones), `root_fixed`, `no_change`. Positions end; warning
  `history_kept`.
- `unit_reopen {unit_id}`: unarchives. Blockers `no_change`, `parent_closed`.

## A2 · Audit explorer (AD-09)

Administrators only: usage readers and members get 403, signed-out 401, board-only panel sessions 401.
Responses carry names, times, outcomes, reasons and recorded before/after values; never message text, note
titles, file names or board images. Projects and groups are named by kind only ("a project").

`GET /admin/audit?start=&end=&actor_id=&person_id=&unit_id=&group=&outcome=&q=&limit=&cursor=`

- `start`, `end`: inclusive calendar dates in the site time zone. `end` before `start` returns 422 `invalid_range`.
- `actor_id`: who did it. `person_id`: the person acted on. `unit_id`: the unit or workspace the entry is about.
- `group`: `people | access | organisation | authority | sign_in | settings | exports`
  (422 `invalid_group` otherwise). `outcome`: exact value (`success`, `denied`, `failed`, ...).
- `q`: case-insensitive text in the stated reason only (never searched in recorded detail).
- `limit` 1-500 (default 100). Order is newest first with `id` as tie-break. `cursor` is opaque, bound to the
  filters that produced it (422 `invalid_cursor` otherwise); rows inserted meanwhile never shift later pages.
- Response `{events: [{id, created_at, actor_id, actor, action, group, group_label, sentence, scope_type,
  scope_id, target_id, target, unit, outcome, reason, changes: [{field, before, after}], detail}],
  next_cursor}`. `sentence` comes from `audit_catalog.py`; contact fields are removed from `detail`.
- 503 `audit_unavailable` when the 2 s statement bound is exceeded.

`GET /admin/audit/export.csv?...same filters...` streams `text/csv` (UTF-8 with BOM; columns time, who, group,
what happened, outcome, reason, action; cells beginning `=`, `+`, `-`, `@` or hidden characters are prefixed
with `'`). More than 10 000 matching entries returns 422 `export_limit` with no file and no record. A
successful export is audited as `audit.export` (`rows` and the names of the filters used, never their values)
in the same request, before the first byte, after re-checking administrator authority.


## A3 · Metrics foundation (AD-08, schema 0027)

Collection is internal: no endpoint writes metrics. API requests (not `/healthz`, `/readyz`,
static assets, the web shell or sockets) are counted by route group taken from the route
template; feature counters are recorded only after the commit, so an idempotent retry counts
once. Normal-session requests record one `activity_days` row per person per site-local day;
board-only panels record nothing. No response shape changes.

`GET /admin/metrics/series?metric=&dimension=&resolution=&from=&to=` — administrators and
current usage readers (console section `activity`, read-only). Members without a grant 403
`usage_read_required`; signed-out, deactivated and board-only/explicit panel requests 401.

- `metric`: a stored series from `metrics/catalog.py` (`http.requests`, `http.errors`,
  `http.latency_p50`, `http.latency_p95`, `auth.signin_ok`, `auth.signin_failed`,
  `sessions.active`, `sockets.connected`, `posts.created`, `replies.created`, `chat.messages`,
  `board.operations`, `tasks.created`, `tasks.completed`, `uploads.count`, `uploads.bytes`,
  `notifications.created`, `uploads.size_band`, `db.size_bytes`, `assets.bytes`,
  `disk.free_bytes`); otherwise
  422 `unknown_metric`.
- `dimension` (default empty): a route group for `http.*` (`all` only for latency), `org`,
  `project` or `group` for feature counters, `under_100kb | under_1mb | under_10mb |
  10mb_or_more` for `uploads.size_band`, empty for the rest; otherwise 422
  `unknown_dimension`. Per-unit values (`unit:<id>`, `unit:other`) are stored but never served
  here (422 `unit_series_not_available`): they need the small-group protection of the
  Activity summaries.
- `resolution`: `minute | hour | day`. Hours and days are site-local buckets.
- `from`, `to`: ISO 8601 with a time zone (422 `invalid` without one); `to` must be after
  `from` (422 `invalid_range`); at most 48 hours of minutes, 35 days of hours, 731 days of days
  (422 `range_too_long`).
- 200 `{metric, dimension, resolution, kind: counter|gauge|histogram, unit: count|bytes|ms,
  from, to, points: [{bucket_start, value, samples}]}`, oldest first, buckets in `[from, to)`.
  A missing bucket means nothing was recorded or collection was not running: show it as a gap,
  never as zero. Only complete hours and days are rolled up; the current hour and day exist at
  minute resolution only.
- 503 `metrics_unavailable` when the 2 s statement bound is exceeded.


## A4 · System health and operational events (AD-06, AD-07, schema 0030)

A background sampler measures the ten health items every `LABADDA_HEALTH_SAMPLE_SECONDS`
(15) and keeps the latest results in memory; the endpoint never measures on request (except on
an instance with the scheduler turned off). Console sections `health` and `events`: administrators
and current usage readers read; members without a grant 403 `usage_read_required`; signed-out,
deactivated and board-only requests 401. Responses hold times, counts, sizes and status words only.

`GET /admin/health` — 200 `{overall, generated_at, interval_seconds, items: [{key, label,
status, value, unit, detail, checked_at, age_seconds, help, chart}]}`. `status` is one of
`healthy | degraded | unavailable | stale | unknown | unsupported` (AD-03); `overall` is the worst
item ignoring `unsupported`, with `unknown` and `stale` ranked above healthy. `value` is a
number, text or null with its `unit`; `detail` is one plain sentence. A result older than
`LABADDA_HEALTH_STALE_SECONDS` (60) is served as `stale`. `key` is `application | database |
file_storage | connections | jobs | response_time | sign_in | backups | server | certificate`.
`help` is the help page below `troubleshooting/` (`troubleshooting/health-<item>`). `chart`
is null or `{metric, dimension, unit}` for `GET /admin/metrics/series`.

`GET /admin/events?state=&severity=&component=&cursor=&limit=` — newest activity first by
`(last_at, id)`; `limit` 1-100 (default 25); 422 on an unknown `state`
(`open | acknowledged | resolved`), `severity` or a bad `cursor` (`invalid_cursor`). 200
`{events: [{id, code, component, component_label, severity, summary, detail, first_at, last_at,
count, state, acknowledged_by, acknowledged_at, note, resolved_at, help}], next_cursor}`. A code
is `<item>.<status>` (for example `database.unavailable`). The same code and component while one
is open raise `count` and `last_at` instead of adding a row. 503 `events_unavailable` past the 2 s bound.

`POST /admin/events/{id}/acknowledge` `{note}` (1-500 characters, required) — administrators only
(usage readers 403 `admin_required`). Open -> acknowledged, records who and why, audited as
`ops_event.acknowledge`. It never changes the item: a failing item stays failing and keeps its
event. 409 `event_acknowledged` or `event_resolved` when it is not open; 404 for an unknown id.

`POST /admin/events/{id}/resolve` `{note?}` — administrators only, audited as
`ops_event.resolve`. 409 `still_failing` while the item behind the event is still degraded,
unavailable or stale (it resolves itself when the check passes); 409 `event_resolved`.

Events are raised only for `degraded | unavailable | stale` and are resolved automatically when
the item reads `healthy`; `unknown` and `unsupported` neither raise nor resolve.

## A5 · Usage analytics (AD-08)

Console section `activity`: administrators and current usage readers (read-only; the export is
a GET). Members without a grant 403 `usage_read_required`; signed-out, deactivated and
board-only/explicit panel requests 401. Computed only from `metric_samples`, `activity_days`
and the people and unit tables; results are cached for 60 s and every query runs under a 2 s
statement bound (503 `analytics_unavailable`). Authorization is checked before and after
reading, also for cached results. No response contains content, project or group names.

`period` is `7d | 30d | 90d | 12m` (default `30d`; 422 otherwise): whole site-local days
ending today (`12m` = 365 days), compared with the equal-length period just before.
`current` and `previous` are `{first_day, last_day}`.

`GET /admin/analytics/summary?period=` — 200 `{period, timezone, generated_at, current,
previous, state, tiles, charts}`. `state` is `unknown` (with `tiles: []`, `charts: null`) when
the period has no activity day and no metric sample; never zeros.
Site figures are floored as well: a people figure below 5 (including 0) is `suppressed` with
`value: null`, so a small site cannot show one person's activity.
- `tiles[]`: `{key, label, unit, state, value, previous_state, previous}` with `state` and
  `previous_state` one of `measured | unknown | suppressed`, for `active_day`, `active_week`,
  `active_month` (distinct people on the last 1/7/30 days of the period), `active_share` (unit
  `fraction`, plus `active` (null unless measured) and `accounts`: people active in the period
  over accounts that may sign in now), `peak_connections` (highest `sockets.connected`, never
  suppressed), `items_created` (posts, replies, chat messages, tasks created and files added;
  suppressed when fewer than 5 people were active in that period). A figure without data is
  `unknown`; `value`/`previous` are null unless `measured`.
- `charts.active_per_day[]` `{day, state, value}`; `charts.features` `{bucket: day|week|month,
  series[{key,label}], points[{start, state, values}]}` (`values` only when the bucket had at
  least 5 active people); `charts.items_by_kind[]` and `charts.upload_sizes[]` `{key, label,
  state, value}` (suppressed when fewer than 5 people were active in the period) — projects and
  groups only as the `project`/`group` totals; `charts.weekday_hour` `{state, from,
  cells[{weekday 1-7 (Monday 1), hour 0-23, value}], suppressed_weekdays[]}` from API request
  counts over the hours still kept (35 days); a weekday with fewer than 5 active people on its
  days has null cells, all seven make `state: suppressed`; `charts.storage[]` `{day,
  files_bytes, database_bytes}` (daily peaks, null when not read).

`GET /admin/analytics/units?period=` — 200 `{period, timezone, generated_at, current,
previous, minimum_group: 5, rounded_to: 5, state, units[], no_home_unit, chart[]}`. One row per
organisation unit `{id, name, parent_id, archived, active_people, items_created,
previous_active_people}`; `no_home_unit` has the same figures (`items_created` null). A figure
is `{state: "shown", value}` (rounded to the nearest 5) or `{state: "suppressed"}` (no number is
sent; shown as "fewer than 5"), or `{state: "unknown"}` for items when nothing was collected.
Item counts are published only for rows whose people are shown and only while the items of all
hidden units (including units that are nobody's home, and the overflow bucket) total at least 5
and are spread over at least two units; otherwise more item counts are hidden. Small-group protection,
on the server: a row is shown only when at least 5 of its home people were active in that
period; while suppressed rows together hold fewer than 5 active people, the smallest shown row
is suppressed too (so total minus shown units cannot reveal them); shown people counts are
rounded to the nearest 5 (so overlapping periods cannot be subtracted); a unit counts only its
own home people, never its sub-units. `chart[]` `{label, value}`: top 10 shown units by active
people plus "Other units"; suppressed rows are left out. `state` is `unknown` when the period
has no activity day.

`GET /admin/analytics/export.csv?period=` — the same protected figures as CSV (`section, item,
this period, previous period`; UTF-8 with BOM, formula-escaped; suppressed figures read "fewer
than 5", missing ones "not measured"). Audited as `analytics.export` (period words and row
count) before delivery.

## A7 · Backups page, settings and site notice (AD-10, AD-11)

All errors use the common envelope. Board-only sessions get 401 on every route here.

`GET /admin/backups/status` (administrators and usage readers). Reads and strictly validates the
operator status file in `LABADDA_STATUS_DIR` (`backup_status.py`: exact fields, 4 KiB limit,
patterned text). Never 500. Returns `status` (one AD-03 word), `headline`, `guidance` (or null),
`checked_at`, `healthy_within_hours` (26), `stale_after_hours` (50), `next_run` and
`restore_rehearsal` (both null: the receipt does not carry them), `setup_guide`, and
`last_backup` (null when unknown): `finished_at`, `age_seconds`, `result`, `size_bytes`,
`verification`, `destination` (short alias), `schema`, `release`. Words: missing, oversized,
malformed or future-dated receipt is `unknown`; a failed backup or failed verification is
`unavailable`; a good one older than 26 h is `degraded`, older than 50 h `stale`; otherwise
`healthy`. No path, host name or secret is ever returned.

`GET /admin/settings` (administrators only; usage readers 403 `admin_required`). Returns
`groups[]` of `{key, title, summary, items[]}`, each item `{key, label, value, unit, explanation,
changed_by}` with `changed_by` always "Changed by the operator in the site configuration file.",
the current `banner` (or null) and `banner_max_length` (280). Only an explicit list of non-secret
limits is returned; paths, hosts, cookie names and database addresses never are.

`PUT /admin/settings/banner` (administrators only; CSRF required). Body `{message, level
("info"|"warning"), starts_at (optional, default now), ends_at, expected_revision}`; times carry a
zone. The message is plain text on one line, 1 to 280 characters after whitespace is collapsed; an
empty message removes the notice (`level` and `ends_at` then optional). `expected_revision` is the
revision last read (0 when there is no notice). Returns `{banner}` with `revision` or `{banner:
null}`. Errors: 422 `banner_too_long`, `invalid_banner`, `invalid_banner_times` (must end after it
starts and in the future), 409 `banner_changed`. Audited as `site.banner_set` (level, times and
length, not the text) and `site.banner_clear` in the same transaction.

`GET /site/banner` (any signed-in person). Returns `{banner: {message, level, starts_at,
ends_at} | null}` for the notice whose window contains now. Clients render the text as text.

## H3 · Setup checklist (HP-07)

`GET /admin/setup-checklist` (console section `help`: administrators only; usage readers and other
members 403 `admin_required`; signed-out, deactivated and board-only/explicit panel requests 401).
No content: states, counts and sentences about counts. 200: `{checked_at, done, total, items[]}`
where each item is `{key, label, state (done|not_done|unknown), detail, screen, help}`, in the
order `second_admin`, `units`, `people`, `stewards`, `backups`, `time_zone`, `test_restore`. `screen`
is the console route that fixes it and `help` the help page below `/help/`. Every state is derived
on each request: two or more active administrators; an open unit below the top; an active person
who is not an administrator; no open unit without an active steward or Head; the Backups report
is `healthy` (`unknown` when no report exists); the operator set `LABADDA_TIMEZONE`; a test restore
is recorded, which is `unknown` until the backup report can carry one. Nothing can be ticked.

## A6 · Console overview (AD-12)

`GET /admin/overview` (console section `overview`: administrators and current usage readers;
members without a grant 403 `usage_read_required`; signed-out, deactivated and board-only/explicit
panel requests 401). One request, no content: statuses, counts, sizes, times and unit names. Health
is the sampler's latest result (measured now when no scheduler runs); the 7-day summary is the
Activity page's own cached result, so its small-group floor applies once and a figure that page
suppresses is never sent here. Queries run under a 2 s bound (503 `overview_unavailable`); authority
is rechecked after reading. 200:

- `generated_at`, `timezone`, `period` `{first_day, last_day}` (the last 7 site-local days) and
  `overall`: the worst health word, ignoring `unsupported` (AD-03).
- `attention[]`, most severe first, then health, events, people: `{id, kind (health|event|people),
  severity (critical|error|warning|info), status (health word or null), title, detail, route, help,
  at}`. `route` is the console page that fixes it. Health items that are not `healthy` or
  `unsupported` (`unavailable` is `error`, `degraded` and `stale` `warning`, `unknown` `info`; the
  Backups item links to `/admin/backups`); open events (not those about an item already listed;
  at most 10, then one "N more" entry); one entry for units without an active steward or Head.
  Empty means nothing needs attention.
- `tiles[]` in the order `active_today`, `signed_in_now`, `connected_now`, `storage_used`,
  `last_backup`, `open_events`: `{key, label, unit, link, state, value, trend, updated_at}`.
  `state` is `measured | unknown | stale | suppressed`, or a health word for `last_backup`. People
  figures (`active_today`, `signed_in_now`, and the days of their `trend`) below 5 are
  `suppressed` with `value: null`. `trend` is seven daily values (null where not measured), or null
  for `last_backup`. `last_backup.value` is the age in seconds and adds `finished_at`;
  `open_events.value` counts open events and adds `by_severity`. `storage_used` is files plus the
  database in bytes.
- `charts.activity` `{state, points[{day, state, value}]}` (people active per day, as on the
  Activity page) and `charts.response_time` `{state, unit: "ms", points[{day, state, value}]}`
  (the slowest hourly 95th percentile of each day). Missing days are `unknown` with `value: null`.

## P6 staff list import and bulk changes

All endpoints are administrator-only (`people` console section): members, stewards and unit
heads 403; signed out and board-only panel sessions 401. Metadata only; the file is parsed in
memory and never stored.

- `GET /admin/changes/import/template`: `text/csv` download, UTF-8 with BOM, columns
  `employee_no,username,display_name,designation,unit_code,role,status,effective_on` and one
  fictional example row.
- `POST /admin/changes/import/preview`: the request body is the raw CSV with
  `Content-Type: text/csv` (UTF-8, BOM tolerated; up to 1 MiB and 2 000 rows). Writes nothing.
  Returns `{rows:[{line,group add|change|transfer|errors,username,display_name,summary[],
  errors[],warnings[],requests[]}],counts:{add,change,transfer,errors,unchanged},
  absent:[{username,display_name}],absent_total,digest}`. `requests` are ordinary
  `add_person`, `edit_person`, `transfer` or `suspend` requests (empty for error rows). A blank
  cell leaves the stored value alone. `unit_code` finds an open unit; a different code moves
  the person (`transfer`, role from `role`, default member). `status: suspended` suspends;
  leave, retirement and departure are refused with advice to use the profile. `effective_on`
  is the joining date of a new person. People missing from the file are listed in `absent`
  (capped at 500, `absent_total` is the full count) and never changed. Cells starting with
  `= + - @` are kept as plain text and carry a warning. Errors: 422 `import_not_csv` (wrong
  content type, binary data, unreadable CSV), `import_encoding`, `import_empty`,
  `import_header`; 413 `import_too_large` (over 1 MiB or 2 000 rows).
- `POST /admin/changes/bulk/preview`: `{requests:[1..2000]}` of kind `add_person`,
  `edit_person`, `transfer` or `suspend` (the same bodies as `/admin/changes/preview`; one per
  kind per person, else 422). Returns the merged plan `{kind:"bulk",count,steps,warnings,
  blockers,revisions,affected_people,digest}`; blocker messages begin with the person's name.
- `POST /admin/changes/bulk/apply`: the same `requests` plus `digest`, `revisions` and
  `reason` (3-500). Every request is rebuilt under the usual locks; 409 `plan_stale` when any
  record or consequence changed, 422 `plan_blocked` when any request is blocked, in both
  cases nothing is written. One transaction, one `people.change` audit parent and its steps
  per request. Receipt `{applied,kind:"bulk",digest,count,added:[{person_id,username,
  display_name,activation:{code,expires_at}}],site_date}`; codes appear only here.

## P5 scheduled changes and attention list (schema 0035)

Administrators with the People section only; signed out 401, members and panel sessions 403/401
as for every `/admin/changes` route. Plans, notes and lists hold names, dates and counts only.

- `POST /admin/changes/preview` and `/apply` accept an optional `effective_on` (`YYYY-MM-DD`).
  Preview then builds the plan as of that day. Apply with `effective_on` checks the digest and
  revisions exactly as a live apply, applies nothing, stores the change and returns
  `{scheduled: true, id, kind, effective_on, digest}`. Errors: `422 invalid_date` (not after today,
  or more than five years ahead), `422 not_schedulable` (`add_person` and `reinstate` issue a
  one-time activation code), plus the usual `409 plan_stale` and `422 plan_blocked`.
- `GET /admin/changes/scheduled?person_id=` returns `{items[{id, kind, effective_on, state:
  pending|needs_review, note, reason, subject_id, steps[], created_by, created_at}]}`, soonest first,
  at most 200. `steps` are the sentences that were reviewed; `note` explains `needs_review`.
- `DELETE /admin/changes/scheduled/{id}?reason=` (3-500 characters) cancels a pending or
  needs-review change: `{cancelled: true, id}`. `404` for an unknown id, `409 not_pending` once
  applied or cancelled. Audited as `people.schedule_cancel`.
- Scheduler step `changes.run_due` (every tick): for each pending change whose day has started it
  takes the live locks, rebuilds the plan as of `effective_on` for the original actor, and applies it
  only if the digest is identical and there are no blockers and the actor is still an administrator.
  Otherwise the change becomes `needs_review` with a plain note and nothing is written. Running
  twice applies once. Audit: `people.schedule`, `people.schedule_apply` (and the usual
  `people.change` rows with the original actor and reason), `people.schedule_review`.
- `GET /admin/org/attention` returns `{items[{id, kind:"people", severity, status:null, title,
  detail, route, help:null, at:null}]}` for the PO-22 items: `units-without-steward`,
  `no-home-unit`, `activation-pending`, `acting-ending`, `acting-expired`, `overdue-leave`,
  `scheduled-review`, `groups-without-steward`, `never-signed-in`. The same entries are merged into
  `GET /admin/overview` `attention`. Each is one bounded query; `detail` names at most three units
  or people.
- `positions.expire_due` now revalidates the holder's sockets and the unit's subscribers after
  commit, like a live apply.
- `change_authority` with `outgoing_role: "member"` lists, as its own step, every other position the
  outgoing holder has in that unit that the demotion ends.
