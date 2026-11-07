# LabAdda API contract (v1)

All endpoints are same-origin JSON under `<base>/api/v1/`. The socket is `<base>/ws/`. `<base>` is empty for a dedicated host or a prefix such as `/labadda-staging`. The server derives the actor from the session cookie and never accepts a client-supplied user ID.

## Conventions

- **Session.** `POST /auth/login` sets an HttpOnly, `SameSite=Strict` cookie scoped to the instance path and returns a `csrf_token`. Send it as `X-CSRF-Token` on every `POST`, `PUT`, `PATCH`, and `DELETE`. A browser `Origin` must match the host or `LABADDA_TRUSTED_ORIGINS`.
- **Errors.** The body is `{"error": {"code", "message", "fields?"}}`. `401` means unauthenticated or expired. `404 not_found` is identical for unknown and out-of-scope IDs. `403` is a visible but forbidden action. `409` is a conflict or idempotency mismatch. `422` is validation. `429` is rate limited.
- **Times.** Times are ISO 8601 with an offset. The server stores UTC and rejects naive values (`timezone_required`).
- **Idempotency.** Posts and replies accept an optional `client_id`, chat requires `client_id`, and board ops require `op_id`. A retry with the same content returns the committed result. Reuse with different content returns `409` (`client_id_reused` / `op_id_reused`).
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
| Admin | `GET/POST /admin/users`, `PATCH /admin/users/{id}`, `POST /admin/users/{id}/reset` | `last_admin` protection. Deactivation revokes sessions. |
| | `GET/POST /admin/workspaces`, `PATCH /admin/workspaces/{id}` `{name?, move, parent_id?, archived?}` | Cycle and single-root checks (`cycle`, `invalid_parent`). |
| | `GET/PUT /admin/workspaces/{id}/memberships`, `DELETE .../memberships/{user}` | Audited with optional reason. |
| | `GET /admin/audit` | Restricted audit trail. |
| Ops | `GET <base>/healthz`, `GET <base>/readyz` | Readiness fails on DB or schema-head mismatch. |

## Socket messages

Client to server: `subscribe` / `unsubscribe` `{workspace_id}`, `board.preview` `{workspace_id, preview_id, stroke, done?}` (transient, bounded, writers only), and `ping`.

Server to client: `hello`, `subscribed`, `subscribe_failed` (unknown and forbidden look the same), `presence`, `chat.message`, `noticeboard.changed`, `board.op`, `board.epoch`, `board.preview`, `revoked` (subscription dropped after an access change), `access_changed`, and `session_ended` (socket then closes with code 4401). Every delivery rechecks the recipient's current access. After `subscribed`, clients catch up missed committed state through the API.
