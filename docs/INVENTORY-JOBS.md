# Durable operator inventory jobs

This P5.1 protocol runs only metadata-only asset inventories. It is not a general
worker service or an authorization to repair, delete, enforce quotas or export
content. The trusted host operator runs it with the configured database and asset
root. There is no automatic scheduler or web execution control.

1. Queue with `labadda queue-inventory --request-key <opaque-key>` and optional
   `--max-entries`, `--max-assets`, `--max-seconds`. Use an 8–64 character ASCII
   letters/digits/underscore/hyphen key without names or secrets. Parameters are
   strict integers: entries/assets 1–100,000, seconds 1–300. Repeating the key with
   the same normalized parameters returns the same job; different parameters fail.
2. Run `labadda run-inventory <job-id>`. One claimant receives a 30-second lease
   using the database clock. Checkpoints renew it approximately once per second
   of active scanning. Job and attempt history are durable before scanning starts.
3. Inspect `labadda show-inventory <job-id>`. Completion links the accepted
   receipt to its exact attempt. Exit 0 from the runner means the selected pass
   completed without issues; exit 2 means incomplete, failed or unconfirmed.
4. After investigation, `labadda run-inventory <job-id> --retry` can claim a failed,
   partial, recovery-paused or expired job. It starts a new attempt and scans from
   the beginning. It does not resume directory enumeration or combine partial
   scans into a complete generation. Completed/cancelled jobs cannot be retried.
   Each job allows at most 100 attempts; create a new reviewed request thereafter.
5. `labadda cancel-inventory <job-id>` fences a queued, paused or running job.
   Active scanning stops at a subsequent checkpoint; cancellation never removes
   files or receipts. A blocked filesystem call has no hard cancellation deadline.

The lease fences **accepted results**, not physical filesystem activity: an old
process stalled past expiry can briefly coexist with a new read-only attempt.
The stale process cannot renew or complete the job. A diagnostic inspection
receipt may still exist without being accepted by any attempt. Missing replies or
failed commits are unconfirmed: inspect the same job ID before retrying. Never
infer success from a stopped process or a stale `running` label. Scan receipts and
job transitions use transactional audit; audit failure cannot accept completion.

Isolated operator restore preserves jobs and attempts but pauses copied queued or
running jobs and running attempts, clears their leases and requires explicit
operator retry. Existing terminal history stays intact. Migration 0016 refuses a
downgrade while jobs exist rather than discarding evidence. No automatic pruning
of job/attempt/audit history is provided yet; monitor database growth.

Jobs record site scope, operator source, normalized budget/plan digest, attempt
number, lease/heartbeat timestamps and accepted receipt. There is no effective
policy revision because this workflow activates no policy. Fine-grained progress,
resumable inventory generations, arbitrary job kinds, per-user requests, review
capabilities and scheduled execution remain later work. All measurement caveats in
[STORAGE-INVENTORY.md](STORAGE-INVENTORY.md) continue to apply.

The web administration and Operations views now show read-only job histories.
Filter by state, page through older jobs, and select a job to inspect attempts and
accepted receipt IDs. An expired lease is labeled explicitly even while its stored
state remains `running`. Refresh clears old data before fetching; a denied refresh
hides it. Only administrators and current operational readers can use these views.
Execution, retry and cancellation remain trusted-host commands.
