# P5 implementation status

P5 remains **in progress**. The normative lifecycle/archive/admin documents govern later work; this page records only implemented slices. No P4 site/device gate is waived.

| Slice | Implemented | Evidence / limitation |
| --- | --- | --- |
| Policy proposal foundation (`b18a53f`) | Immutable site draft revisions, strict bounded schema-1 observation proposals, conflict refusal, atomic audit, locked authority refresh, history-preserving migration | Twelve focused tests include queued demotion/revocation and downgrade refusal. No activation, inherited rules, exceptions or reviewed deletion |
| Partial observations (`bff92dd`) | Own-user upload counters; admin site original-byte aggregates; filesystem capacity state; explicit recorded samples with bounded history | Five focused tests cover scope, privacy, missing measurements and retention bound. These are samples, not a complete durable admission ledger |
| Web inspection/proposals | User storage page, admin observations/history/proposal form, mobile navigation, explicit partial/unknown labels and draft-only success state | 18 actual browser checks at root and prefix; input preserved on validation/conflict. Screenshots under `docs/evidence/governance/` |

Validation: `LABADDA_RECOVERY_TESTS=1 scripts/verify.sh` passed 198 backend tests including the real PostgreSQL recovery round trip, with no migration drift; frontend tests/typecheck/build passed. The final format suite adds eight byte-display cases (11 frontend tests total), ensuring small positive uploads do not round to a misleading zero MiB. `node e2e/governance.mjs` against a fresh local `scripts/proxy-stack.sh start` stack passed 18 browser checks; stop the disposable stack afterward. Hosted CI completion is not claimed.

Migration heads 0006/0007 preserve governance history and refuse destructive downgrades when their tables contain rows. Existing instances must migrate before using the new routes. Existing release archives predate these changes and retain their historical source/schema; do not call them current candidates.

Current pilot upload limits remain environment-controlled. Proposed values do not activate or affect storage admission. Measurement includes original asset metadata only; derivatives, board/text bytes, reservations, trash, temporary archives, full reference reconciliation and configured site budget remain explicitly unmeasured/unavailable. The current API uses existing administrator gating; a configurable capability/approval system is not complete.

Next: complete durable accounting and bounded reconciliation/capability design within P5.1. P5.2 portable export and all retention, archive viewing/materialization, policy activation, destructive dry-run/approval and operational analytics phases remain unimplemented. Do not enable enforcement or purge based on these partial observations.
