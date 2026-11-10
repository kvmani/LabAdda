# LabAdda test plan

Use generated fixtures and disposable PostgreSQL databases and asset directories. Seed the same recognizable synthetic tree across API and browser suites. Keep credentials test-only and supply them through the harness. Record exact commands, commit, environment, pass/fail/skip totals, and evidence paths or CI links. Add runnable commands to README in P1 and evolve the same entry points for CI and staging. Use pytest for policy, API, migrations and concurrency, frontend unit/component tests for state, and Playwright for browser flows. PostgreSQL-backed transaction and race cases are release gates.

| ID | Scenario | Expected result | Phase |
| --- | --- | --- | --- |
| T01 | Tree and grants across four levels, sibling, invited project, archive, direct steward, administrator, disabled account, attempted cycle | Only eligible scopes resolve. Steward authority stays direct. Admin cannot browse content without a grant. Invalid tree mutations fail and existing grants remain intact. | P1 |
| T02 | Session lifecycle, CSRF, expiry, origin validation, last-admin race, transfer and offboarding | Invalid requests cannot mutate. Revocation removes old access and retains attribution. Concurrent admin changes preserve at least one active administrator. | P1, repeat sockets in P3 |
| T03 | Root and prefixed deployments side by side through a real proxy | Deep links and refresh work. Assets, API, redirects, cookie names and paths, uploads and socket upgrade stay within the correct instance. Logout or clear cookies for one leaves the other intact. | P1, repeat in P3–P4 |
| T04 | Create, edit, delete, reply, pin, official notices and read-only transition | Confirm persistence on reload; role, workspace and author restrictions hold on direct requests. Failed writes show an actionable error and retain unsaved input. | P2 |
| T05 | Raw IDs, URLs and metadata for posts, notes, files, previews, unread counts and search | Authorized resource succeeds. Other-workspace direct URL returns the same absence behavior as an unknown ID. Search and counts reveal no hidden content. | P2, repeat in P3–P4 |
| T06 | Forged MIME, file name traversal, oversized and concurrent uploads, failed save, malicious HTML and active image payload | Rejected content is never public or executable. No over-quota commit, exposed provisional asset, dangling reference, or deletion of a referenced file. | P2 |
| T07 | Reminder timing, duplicate scheduler ticks and restart, timezone boundaries, membership removed before delivery, two note owners | One eligible notification per occurrence. No stale content delivery. Each user's notes and reminders remain private. | P2 |
| T08 | Parallel drawing, same-object edits, retries before and after ack, socket drop, duplicate or changed operation ID, missed fanout, server restart | One durable result per intended operation. Replayed state converges. Stale edits show conflicts and missed previews disappear. | P3 |
| T09 | Board undo, restore, pending edit against old epoch, selected-region snapshot, chat summary and parent publish | Own undo only. Old epoch is rejected. Published copy stays fixed and target-owned. Parent share needs explicit confirmation and fresh authorization. | P3 |
| T10 | Socket subscription and live delivery after membership change, deactivation, expiry, workspace archive or cross-space ID spoofing | Old subscriptions close or stop delivering inaccessible content. Reconnect and writes reauthorize. Rejected connections and events disclose no protected data. | P3 |
| T11 | Physical panel and browser-simulated touch, screen lock/end, scoped cookie, touch-only access and expired sessions | Pen and finger input are usable. Large controls, undo and fit work. Board clears and session is unusable after lock/end. Direct personal and admin URLs remain denied. | P4 |
| T12 | Cold offline install, blocked external DNS/HTTP, real proxy, restart, migrations, preflight/health failure, recovery | No public network dependency or outbound attempt. Bad releases are rejected or safely reverted according to schema compatibility. Restore recovers a consistent database and assets and invalidates sessions. | P4 |
| T13 | Load rehearsal using S4 targets, accessibility and visual review | Report workload and percentiles, no lost/duplicated edits, keyboard focus and text alternatives, clear scope and error states, and workable desktop and panel layouts. | P4 |
| T14 | Collaborative group created by a section member with a sibling-section colleague and a project guest; division steward, admin and non-members probe it; leave, role change, archive, limits | All workspace features work for members. Non-members, parent stewards and admins get the uniform 404 and no search/notification leakage. Last steward is protected. Archive freezes writes. Changes are audited. | P2, repeat sockets in P3 |

For changed workflows, inspect normal, empty, slow, and failure states. Use separate browser contexts for each actor. Test denied cases directly through APIs and sockets as well as through the UI. Exercise an actual pen/finger and the target browser on the panel before pilot approval. Synthetic touch automation supplies regression coverage but cannot establish device acceptance.

CI runs deterministic tests and the production build on pinned dependencies using fictional data. Deployment rehearsal installs the release without public network, uses a fresh browser cache, and inspects client requests and VM egress. Save sanitized results separately from live data. Failed authorization, data durability, restore, or offline install checks block a pilot. A skipped mandatory gate leaves it unverified.

## Offline release checks (T12)

`backend/tests/test_release.py` runs in the normal `scripts/verify.sh` suite. It covers unsafe and duplicate archive paths, links and special members, resource limits, digest/payload/platform/manifest failures, transfer replacement isolation, install cleanup, pip environment isolation, optimized preflight, and atomic activation/rollback with schema mismatch, tampering and external-state preservation. The real target-platform build, no-network install and installed root/prefix functional checks are recorded in [release evidence](docs/RELEASE-EVIDENCE.md). Site TLS, recovery and pilot acceptance remain separate gates.

For T12 backup/restore, run `LABADDA_RECOVERY_TESTS=1 scripts/verify.sh` with PostgreSQL 16 clients on PATH and CREATEDB permission on the disposable test role. The integration test verifies content, asset hashes, board replay, session/token invalidation and negative authorization after a real dump/restore; its target is uniquely named and cleaned up. Without the flag it is explicitly skipped. See [recovery procedure](docs/RECOVERY.md).

For T13 local regression, use `scripts/soak.py --drawers 8 --seconds 120 --enforce-targets` against a fresh synthetic test stack. The process fails on missing/duplicate edits, gaps, incomplete observer delivery, zero operations, errors or breached p95 targets. See [qualification evidence and remaining site workload](docs/P4-QUALIFICATION.md).

For a realistic five-person fixture with handwritten native ink, sibling sections, parent division and a private colleague handoff, see [research-day scenario](fixtures/research-day/README.md). `e2e/research-day.mjs` runs only against an explicitly selected local synthetic instance; it saves real screenshots and fails on permission/replay/upload-boundary regressions. SVG sources and native-object JSON are deterministic and covered by `test_research_fixture.py`.

## Future data lifecycle/admin acceptance matrix (S5–S7)

These are **requirements for future tests**, not checks claimed to have passed or features currently present. Each implementation slice must add real positive/negative, race/restart and browser evidence as applicable. Reference the stable requirement IDs in the three normative documents; record schema/commit, environment, metrics, counts, skips and limitations. Reuse the five-person research-day fixture for two siblings, their division, a five-member group, private two-person sharing and personal notes.

| ID | Required scenarios and observable exit | Requirement coverage | First delivery |
| --- | --- | --- | --- |
| T15 | Effective policy resolves deterministically across site/tree/workspace/user and locked exceptions; moves and stale revisions cannot silently relax it; explicit units and bootstrap ceilings shown | DL-01–DL-06; AC-04–AC-05 | P5.1/P5.3 |
| T16 | Parallel uploads/attachments/snapshots reserve and commit once; burst/daily limits survive retry/logout/delete; overflow, measured bytes and provisional expiry enforced | DL-07–DL-09 | P5.1/P5.3 |
| T17 | Shared contributor accounting, physical dedup totals, trash/held/temp bytes and reconcilers agree after crash, deactivation and audited transfer; no referenced-file deletion or cross-scope oracle | DL-07–DL-09, DL-11; AC-09 | P5.1/P5.3 |
| T18 | Over-quota user still reads/exports/cleans; one small file handoff succeeds within limits; denial names exact constraint; draft preserved; lower limit/expired exception does not evict data; disk/inode reserve protected | DL-10–DL-12; AC-19–AC-20 | P5.3 |
| T19 | Class clocks, UTC/DST boundaries, notice/grace, edit/freeze/move behavior, parent/reply expiry, shorter attachment lifetimes with explicit placeholders, and expired queued deliveries match policy; no accidental clock renewal | DL-13–DL-14, DL-17 | P5.5 |
| T20 | Dry-run candidate sets, holds, reference graph, board compaction/images and crash-at-every-purge-boundary retain required bytes; changed candidates skipped; standing authorizations cannot exceed scope/budgets/expiry or approve retroactive deletion; retry/cancel safe; audit failure blocks irreversible action | DL-15–DL-18, DL-24–DL-25 | P5.5/P5.6 |
| T21 | Partial/whole/date/type exports include only current grants; private notes owner-only; administrator and sibling denied; mid-job/download/range revocation invalidates protected output and cancels an active stream within its specified bounded delivery boundary; snapshot cutoff and omissions correct | DL-19–DL-20; AF-01–AF-03 | P5.2 |
| T22 | Normal and split packages open with standard tools/browser while offline; hashes and complete inventories verify; Unicode/geometry/attachments/order survive supported-version round trip | AF-01–AF-05, AF-11 | P5.2/P5.7 |
| T23 | Reject ZIP traversal/collisions/links/specials/bombs/unsupported versions and forged manifests; cap decoded images/JSON/coordinates/CPU; no executable HTML/SVG/URL fetch reaches the site renderer | DL-21; AF-06–AF-08 | P5.4 |
| T24 | Temporary archive viewer is read-only, owner-scoped, metered and expires; re-upload of old content remains viewable without live republishing or retention bypass | DL-21, DL-23; AF-07–AF-08 | P5.4 |
| T25 | Materialization validates destination/audience, maps IDs/authors without new grants, reserves quota, handles duplicates/partial failure, disables old reminders, preserves lineage and refuses active-board/history overwrite | DL-22–DL-23; AF-09–AF-11 | P5.7 |
| T26 | All jobs survive restart with leases/checkpoints and safe idempotent retries; no duplicate notifications/billing/purge; cancellation boundaries and partial states actionable | DL-24–DL-25; AC-14–AC-16 | Each job slice |
| T27 | Recovery restores policy/holds/meters/job intent, revokes sessions, pauses destructive jobs, reconciles current time/deletion intent before exposure; independent intent-ledger continuity/checkpoints verified, gaps keep the target isolated; stale backup cannot resurrect removed content publicly | DL-26; AC-17–AC-19 | P5.5/P5.6 |
| T28 | Capability matrix covers every admin route/stream/report; ordinary admin cannot retrieve private bodies/notes/files via dashboards, logs, export or metadata samples; board-only sessions refused | AC-01–AC-03; DL-19 | P5.1 onward |
| T29 | Invalid/stale/concurrently edited plans, changed holds/grants/data and expired approval cannot activate; dry runs mutate nothing; high-risk two-person review and explicit single-operator mode verified | AC-03–AC-08; DL-18 | P5.3/P5.6 |
| T30 | Complete overview/storage/user/activity/job/policy/error/backup/audit/system views link to measured data; every metric has source/window/freshness; unknown/stale/unsupported never shown as healthy/zero | AC-09–AC-10 | P5.1/P5.8 |
| T31 | Activity definitions, event vs ingestion time, dedup, cohorts, per-user drilldown audit and telemetry retention verified; no content/search-query leakage or external analytics | AC-11–AC-13 | P5.8 |
| T32 | Events filter/paginate/correlate without merging attempts; severity/recurrence/partial state/runbooks accurate; CSV injection escaped; acknowledge/silence does not hide real failure; unknown errors stay honest | AC-14–AC-16 | Each slice/P5.8 |
| T33 | Web backup controls accept approved aliases only; no shell/path/URL injection; verified quiescence/integrity/restore evidence required; cannot delete needed recovery point or restore over live state | AC-17–AC-18 | P5.5/P5.8 |
| T34 | Emergency pause modes and operator fallback work under full disk/DB failure/audit failure/worker loss/clock drift; no automatic destructive cleanup; document unrecoverable boundaries | AC-19; DL-10, DL-25–DL-26 | P5.3/P5.6/P5.8 |
| T35 | Keyboard/screen-reader flows, prefix routes, UTC/local deadlines, empty/stale/error states and preserved filters/drafts verified; representative load meets DL-27 without dashboard/job starvation | DL-27; AC-13, AC-20 | Each UI slice/P5.8 |
| T36 | Backfill/observation precede enforcement/purge; migrations/rollback preserve accounting/provenance; independent review and operator exercises diagnose quota, reserve, purge, backup and collector failures from UI | DL-28; AC-21 | Each gate/P5.8 |

No implementation is accepted based on a formatter, zero-test run, static mock dashboard, unchecked backup checkbox or unexecuted dry run. T15–T36 supplement rather than replace T01–T14, offline release/recovery evidence and site/device gates.

P5.1 current foundation checks: `test_governance.py` exercises strict draft validation, audit/conflict behavior, queued authority loss and downgrade refusal; `test_usage.py` exercises original-byte scope/privacy and bounded partial observations. `e2e/governance.mjs` runs against a fresh local disposable proxy stack and checks root/prefix forms, conflict preservation, non-activation, usage visibility and mobile navigation. These validate the implemented subset, not completion of T15–T36. See [P5 status](docs/P5-PROGRESS.md).

T16 upload request identity: `test_upload_idempotency.py` covers same-key replay at quota, changed content/metadata, per-user key separation, concurrent pending attempts, current-access loss, deleted results, failed/expired attempts, lost/unknown commit replies, CSRF/panel denial, history-preserving downgrade and failure-release/admission lock ordering. The latter waits for actual PostgreSQL blocking before releasing the paused worker. `e2e/upload-receipts.mjs` uses Chromium to lose a committed response, recover/replay it and verify single charging and revoked-access denial at root/prefix. Run on a **fresh disposable** `scripts/proxy-stack.sh start` stack: it removes Ben's section grant, so reset before other membership-dependent flows. These checks do not claim full ledger/daily-rate/retention coverage.

T16/T35 file-picker recovery: `uploads.test.ts` exercises bounded in-memory attempts, same-key retries, receipt states, age guards and leaving a view; `api.test.ts` verifies CSRF/key transport and unreadable success bodies. `e2e/upload-recovery-ui.mjs` against a fresh proxy stack covers real noticeboard/board inputs, lost and truncated committed replies, explicit check/retry, single charging, blocked incomplete posts and durable attachments at root/prefix. It captures desktop and mobile evidence. Navigation/reload recovery is not provided by this slice.

T17 preview integrity: `test_preview_integrity.py` covers both writers, exact preview hashes/bytes, unknown historical metadata, user/site scope, corrupted/missing previews, inspection budget limits, restore-reference refusal, half-null/invalid DB metadata and downgrade protection. Real recovery also round-trips a committed preview. `e2e/preview-observations.mjs` verifies root/prefix user/admin observations without filenames; `e2e/inspection-view.mjs` checks the actual operator inspection receipts. Recorded metadata is not live disk verification; creation/inspection alone does not backfill history or provide a full ledger. The narrow reconciliation tool below handles eligible historical metadata separately.

T17/T26 historical preview reconciliation: `test_preview_reconciliation.py` verifies dry-run immutability, explicit confirmation, changed-plan refusal, original hash trust, bounded batches/cursors, symlinks, budget exhaustion, growth after initial stat, pixel limits, audit rollback, lost commit replies and actual CLI dry-run/apply/refusal. Only matching preview metadata is filled; no files are repaired or deleted. `e2e/preview-reconciliation-view.mjs` displays actual host-operator dry-run receipts at root/prefix with no web apply action. Its browser fixtures already have known measurements, so those dry runs correctly report zero candidates; nonzero application is exercised in disposable PostgreSQL tests. See [operator procedure](docs/PREVIEW-RECONCILIATION.md).

T17 text/whiteboard logical charges: `test_content_charges.py` covers UTF-8 bytes rather than characters for posts, replies, chat and notes; edit and removed-but-stored states; own-user versus site visibility without content; attribution after deactivation; board add/move/erase/undo/restore, original-author attribution for restore and panel writes; unknown-to-complete transition for historical boards; exact ledger after concurrent drawing; every drift class in a non-mutating dry run; refusal without attestation, with a wrong digest or after renewed drift; reviewed apply; historical board completion; cursor batches; object/time budget stops; CLI exit codes; migration backfill, method-identifier parity and data-preserving downgrade. `e2e/content-charges.mjs` on a fresh proxy stack checks root/prefix user and admin views, the lower-bound label and an actual operator dry run and apply. Physical database size, board history bytes and enforcement remain out of scope.

T13 full workload and accessibility: `scripts/rehearsal.py` (gate logic in `test_rehearsal_report.py`) runs N clients over two sibling workspaces with every client subscribed. It fails on lost, duplicated or gapped board operations, undelivered committed events, cross-workspace delivery, request errors, and enforced p95 targets. `test_realtime.py` adds ordered and complete burst fanout to several subscribers on one event loop, the batched recheck dropping only a client whose access was removed directly in the database, and slow-client closure without stalling others. `LABADDA_PROXY_TLS=1` runs the proxy stack over https/wss. `e2e/accessibility.mjs` runs axe-core WCAG 2.1 A/AA rules plus skip-link, focus-visibility and phone-overflow checks on desktop, mobile and panel views at root and prefix. Automated rules do not replace the manual screen-reader/visual review or the physical panel test.

T17/T28/T35 workspace usage: `test_workspace_usage.py` covers upward-only org access, direct project/group membership, admin/operational-reader denial without content grants, colleague-owned files, private-note/body/identifier exclusions, parent/child isolation, removed-but-stored attachments, provisional/pending non-attribution, erased board image retention, unknown preview measurements, localized board coverage, membership/session/deactivation during measurement, database failure, archived read access and panel denial. `e2e/workspace-usage.mjs` on a fresh disposable proxy stack checks actual Storage navigation at root/prefix, colleague contributions, exclusions, unknown/budget labels, parent scope, sibling/admin denial and revoked-refresh clearing. It runs axe on desktop and mobile workspace views and checks phone overflow. It removes Ben's section grant, so reset before other membership-dependent flows. No quota activation or full-ledger claim is made.

T15/T29/T35 capacity proposals: `test_capacity.py` covers immutable V1/V2 compatibility, strict units/bounds, integer reserve ceiling/floor arithmetic, preview/pending inclusion in lower bounds, missing filesystem and reserve shortfalls, unchanged pilot admission/content/revisions, sanitized audit, admin/CSRF/panel/delegation boundaries, demotion/session revocation during measurement and populated-V2 downgrade refusal. `e2e/capacity-proposals.mjs` on fresh root/prefix proxy fixtures covers actual preview/save/history, edit and reload invalidation, delayed-response suppression, current limits unchanged, mobile axe/overflow and keyboard scrolling of proposal history. Previews are always incomplete and cannot authorize policy activation.

T17 asset-directory inventory: `test_inventory.py` checks reference/temporary/unexpected classification, physical inode deduplication, symlink/special/nested-directory refusal, missing roots, entry/reference budgets, non-finite budget rejection, sanitized persisted receipts and CLI success/failure. This observation does not authorize deletion, verify hashes, detect missing references or reconcile a live transactional generation. See [procedure](docs/STORAGE-INVENTORY.md).

T17/T35 inventory presentation: `e2e/storage-inventory.mjs` compares actual operator inventory receipts with the admin view at root/prefix; checks candidate labels, no filenames/mutation controls, desktop/mobile axe and overflow. Run `labadda inventory-storage` for both disposable proxy databases after creating a synthetic unreferenced candidate; never assume the asset directory is empty after database reseeding.

T10 queued-delivery revocation: `test_realtime.py` pauses a batch inside a send, revokes the workspace and proves no remaining content follows the revocation frame. A stalled revoked socket must not delay healthy recipients or leave closure unbounded. Paused authorization checks cannot restore writable state after revocation or revoke a newer subscription, both in batch delivery and explicit revalidation. The first two regressions were executed against the pre-fix implementation and failed as expected. These deterministic races supplement rather than replace the representative workload/site gates.

T26 durable inventory jobs: `test_inventory_jobs.py` covers strict parameter/key binding, concurrent request deduplication and single claim, expired-worker fencing, cancellation/checkpoints, explicit retries preserving attempts, receipt binding, transactional audit rollback, recovery pause, populated downgrade refusal and CLI execution. The real recovery integration test also restores a running inventory job and verifies its copied lease/attempt are paused. These are operator-only observations restarting from the beginning, not resumable enumeration or a general lifecycle job engine.

T28/T30 inventory job API: `test_inventory_job_api.py` checks administrator/delegated-reader access, anonymous/non-reader/panel denial, absence of request keys/paths/write routes, keyset pages/filter validation, expired-lease truthfulness and post-measurement loss of admin role, delegation or session for both routes. Detail history is bounded by the100-attempt invariant; listing omits histories.

T26/T35 job observation UI: `e2e/inventory-jobs.mjs` with `e2e/inventory-jobs-fixture.py` verifies root/prefix bounded paging, state filters, failed-to-completed attempt history, expired-lease warnings, absence of mutation controls, delayed detail suppression, observer access/revoked refresh, desktop/mobile axe and overflow. `test_inventory_jobs.py` also injects lost completion commit replies and completion audit failures. [Evidence](docs/evidence/inventory-jobs/README.md).

## Collaboration track acceptance (C1–C5)

| ID | Required evidence | Stage |
| --- | --- | --- |
| T37 | Personal owner-only lists; upward-only org reads; sibling/parent-only/admin/panel denial; project/group direct membership; write/read-only/archive/revocation matrix | C1 |
| T38 | List/task persistence; checklist/Unicode/calendar dates/priority/completion/reopening; bounded pages/payloads; identical create replay vs changed intent; stale/concurrent revision protection; migration/recovery | C1 |
| T39 | Root/prefix desktop/mobile lists/tasks, explicit audience, loading/failure/conflict draft recovery, denied refresh clearing, accessibility and no external requests | C1 |
| T40 | Assignment grants no access; authorised My Tasks, comments/history/live convergence, revoked subscriptions and notification boundaries | C2 |
| T41 | Post/chat conversion and board references preserve source permissions and explicit broader-audience confirmation | C3 |
| T42 | Threaded chat/attachment retry/private conversations; five-user sibling-section/division scenario, fixture screenshots and qualification | C4–C5 |

C1 backend evidence: `test_todos.py` covers personal/admin isolation, upward/sibling/parent boundaries, direct group/project membership, read-only/archive, create intent binding, calendar/checklist/completion/reopening persistence, invalid bounds, cursor pages, CSRF/panel refusal, revocation, two-writer revision conflicts and downgrade protection. A PostgreSQL blocking test reproduces workspace row-writer ordering; expiry during a scope wait cannot commit. Real recovery integration preserves personal tasks/checklists. The previous job downgrade assertion now uses the actual schema head rather than a stale0016 literal.

C1 web evidence: `e2e/todos.mjs` passed60 root/prefix checks on 2026-11-10, including native form actions, owner/shared scope, lost creation replies, list/task conflicts, deliberate latest-version reload, delayed editor/rename responses and denied refresh clearing; desktop/mobile axe/overflow passed. [Reproduction and limits](docs/evidence/todos/README.md). `GET /todos/lists/{id}` is covered by the owner/shared privacy matrix in test_todos.py.

**T43 · CT-06, C2 workflow/history.** Verify workflow/completion consistency; C1 create replay after migration and old-client state-preserving edits; atomic revision history/actor attribution, failure rollback, scope/panel/revocation denial, bounded history pages and explicit migration baseline; web state transitions/history and C1 regression flows. Tests: backend/tests/test_task_workflow.py, real recovery integration and e2e/todos.mjs.

**T44 · CT-07, assignment/My Tasks.** Check active current-reader eligibility,
private owner-only assignment, upward/direct-project/group rules, no admin/sibling
bypass, history and old-edit preservation, target revocation/deactivation,
revision/CSRF/panel denial, bounded search/pages/status filters, current-grant
aggregation and grant loss during serialization (including cursor suppression),
reciprocal identity lock ordering and downgrade protection for past assignments.
Focused backend source: backend/tests/test_task_assignment.py. Browser delivery and
its evidence are separate slices until recorded in the roadmap ledger.

T44 web evidence: `e2e/task-assignment.mjs` exercises real picker/assignment and My
Tasks across sibling sections, division, group and private lists, conflict and lost
reply reload, revoked visibility and delayed filter response, desktop/mobile axe
and overflow. Its46 checks passed; existing66 task checks passed too. Reset proxy
fixtures between scripts: both revoke Ben's section membership. [Evidence](docs/evidence/task-assignment/README.md).

**T45 · CT-08, task comments.** Verify owner/private and actual shared source policy
at section/division/project/group, admin/sibling/panel denial, read-only/archive and
revoked access, strict text bounds, UTF-8/plain-text/newline rendering, creation
replay/changed-intent/destination binding, concurrent contiguous sequences and
bounded latest-first pages. Final expiry/read-grant checks must prevent unauthorized
persistence/delivery; retry must work at capacity. Protect populated downgrade and
round-trip comments in real recovery. Backend: backend/tests/test_task_comments.py.
Browser: e2e/task-comments.mjs on disposable fixtures; keep source contracts and
feature guide synchronized when recording delivery evidence.

T45 delivery evidence:15 focused backend cases, full461/recovery/drift,31 frontend
checks/build and162 browser checks passed (48comments+48assignment+66task regression).
Discussion drafts survive same-list reload/field edits; the explicit assignment
reload also resolves a never-committed write with unchanged revision. [Evidence](docs/evidence/task-comments/README.md).

**T46 · CT-09, shared task invalidation.** `test_task_events.py` verifies six
post-commit mutation paths with an independent database reader, replay/no-op/
rejection silence, personal mutation silence, rollback silence, actual payload,
delivery-time grant removal and durable HTTP catch-up after an offline write.
`test_panel_socket_gets_board_events_only` also excludes task hints. Existing
realtime session/queue/generation/revocation tests remain mandatory.

T46 browser regression: `e2e/task-updates.mjs` covers root/prefix live notices,
visible-card and second-page draft preservation, unchanged editor revision,
assignment review, explicit comment/My Tasks catch-up, a newer signal during a
paused old HTTP snapshot, failed reads, offline-write reconnect, minimal payload,
sibling denial and revocation clearing. Reset proxy fixtures between scripts.

**T47 · CT-10, conversation conversion.** `test_task_conversion.py` covers posts/
chat to personal/same-workspace/different-workspace lists; explicit confirmation;
reviewed copy vs source metadata, replay binding and C1 identity compatibility;
source/destination/panel denial; read-only source vs destination; removal/purge,
atomic rollback and guarded downgrade; expiry before commit, final-read revocation
and actual PostgreSQL blocked source-deletion races for shared/personal targets.
Real recovery integration round-trips a protected post reference.

`e2e/task-conversion.mjs` uses fresh disposable proxy fixtures and revokes Ben's
source grant last. Cover root/prefix, editable copies, frozen lost-reply retry,
actual audience confirmation/reset, source plain-text safety, private and sibling
isolation, destination-list paging and delayed first-source-response revocation.

**T48 · CT-11, board task context.** `test_task_board_conversion.py` covers personal/
same-workspace/different-workspace scopes, explicit confirmation, minimal source
metadata, retries after ink/restore, context conflicts, CSRF/panel/current-reader
and read-only boundaries, actual PostgreSQL FOR SHARE wait races, rollback, expiry,
final-read revocation/purge, bounded context lookup and populated downgrade.
Real recovery round-trips a recorded board reference. T47 also adds a hard post
purge during final refresh to preserve uniform404 after ORM expiry.

`e2e/task-board-reference.mjs` covers root/prefix context review and draft recovery,
lost-reply retry after further ink, recorded vs current context after restore,
explicit different audience, sibling denial and delayed source-only revocation.
A MutationObserver detects even transient restoration of revoked context. Desktop/
mobile WCAG2.1 A/AA and overflow checks apply to form and protected view. Existing
post/chat conversion and chat/board/panel regressions remain required; panel flow
asserts task creation is absent. Use separately reset disposable proxy fixtures.

**T49 · CT-12, C4 threads.** `test_chat_threads.py` covers actual root/workspace,
parent spoofing, personal-group/sibling/admin/panel boundaries, bounded thread and
legacy stream pagination, changed retry intent, expiry/rollback, protected downgrade
and two-author commit ordering. Recovery integration round-trips a reply. Existing
chat/board/realtime tests remain required. Browser stage follows with live hints,
reconnect, frozen reply retry, draft preservation and revoked-response races.

T49 web evidence: e2e/chat-threads.mjs covers retained drafts, lost-reply recovery,
root/prefix desktop/mobile accessibility, held older-page vs latest-view race,
new-message notice while viewing old history, held old HTTP snapshot across
reconnect/offline write, and revocation clearing stream/thread/composer.
