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

`GET /admin/storage-inspections` returns the latest 20 operator-triggered referenced-file inspection receipts. It is admin-only and grants no enforcement authority. The trusted-host command `labadda inspect-storage --max-files 10000 --max-bytes 1073741824 --max-seconds 30` persists a receipt and audit, verifies selected original-file sizes/hashes, and measures readable preview bytes separately. It never repairs/removes files or scans unreferenced files. `--max-seconds` is a cooperative scan budget, not a hard timeout on blocking OS/database calls. Preview integrity, live-filesystem consistency and full accounting remain explicitly unverified. Exit code 2 means issues, incomplete budget or failure; zero means the selected reference pass completed without reported issues, not full-site readiness. A process interruption may leave a running receipt without a completion timestamp.

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
