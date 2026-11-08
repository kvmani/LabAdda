# Text and whiteboard charge reconciliation

LabAdda keeps a **logical charge ledger** (`content_charges`, schema 0014) for user-written text and live whiteboard objects (DL-07). This trusted-host operator tool compares the ledger with source content and corrects **ledger rows only**. It never changes posts, chat, notes, boards, files, authorship, access, admission limits or retention. There is no web apply action; the admin and observer views only list its receipts.

## What is charged

| Method | Charged item | Rule |
| --- | --- | --- |
| `utf8-text-v1` | Post or reply, chat message, personal note | UTF-8 octets of the text exactly as committed: body, or note title plus body. No normalization, trimming or per-row overhead. A removed post whose body is still stored is charged with state `removed`. |
| `board-object-json-v1` | Each live object on the current board epoch | UTF-8 octets of `{"data":…,"kind":…}` as compact JSON with sorted keys and literal non-ASCII characters, using the committed payload. Moves, history and snapshots are not part of the charge. |

Charges are attributed to the stable contributor (the original author, including for panel sessions and restored objects) and to the workspace. Personal notes have no workspace; admins and observers see only a site total for notes. A new rule needs a new method identifier; existing identifiers never change meaning.

Text rows are maintained by database triggers in the same transaction as the content change, so every writer is covered. Board rows are maintained by the board writers. Each board records which epoch's charges are complete (`boards.charges_epoch`). Boards with history from before schema 0014 stay **unknown** (reported as a lower bound) until their next write or a reconciliation completes them.

These are logical charges, not disk usage. Board history and snapshots, database size and attachments are measured separately or not yet measured. Nothing here changes admission or authorizes deletion.

## Dry run

```bash
labadda reconcile-charges --max-items 10000 --max-boards 50 --max-board-objects 200000 --max-seconds 30
```

The JSON result includes a durable receipt ID, checked item and board counts, drift counts by class (`missing_charge`, `orphan_charge`, `stale_bytes`, `stale_state`, `stale_attribution`, `stale_method`), up to 100 identifier-only samples, the number of boards to mark complete, and `plan_digest`. Samples never include text, titles or object payloads; board object IDs appear only as short digests. The CLI exits 2 when drift is found. A live dry run can race writers and is not a consistent inventory.

## Reviewed application

Stop all application, scheduler and maintenance writers using the deployment's maintenance procedure. Run a final dry run on the stopped instance, review it, then apply its digest with the same budgets and cursors:

```bash
labadda reconcile-charges --max-items 10000 --max-boards 50 --max-board-objects 200000 --max-seconds 30 \
  --apply --writers-quiesced --expected-plan 'DIGEST_FROM_DRY_RUN'
```

`--writers-quiesced` attests an operator action; the tool does not stop or verify writers itself. Apply takes an advisory lock (one reconciliation at a time), locks the selected board rows, recomputes the plan and refuses with zero changes if anything differs: the selection, budgets, cursors, any correction or any observed drift class. Matching corrections, board completion markers, the receipt and the audit record commit together. A lost commit reply is reported as `uncertain` and never overwrites a completed receipt; inspect the receipt before retrying.

## Batches and limits

Each run checks at most `--max-items` text items (keyset order by type and ID), `--max-boards` boards (by workspace ID) and `--max-board-objects` folded objects. When `more_items` or `more_boards` is true, continue with `--after-item` / `--after-board` from `next_after_item` / `next_after_board`. The time budget is cooperative: it is checked between items and boards and cannot interrupt a single database statement. The text comparison runs under a 10-second statement timeout; on very large sites the database still scans the source tables for each batch. A run that exhausts a budget stops with no plan digest, so it cannot authorize an apply.

Recovery restores copy the ledger with the database; run a dry run after any restore or manual SQL change.
