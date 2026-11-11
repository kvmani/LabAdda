"""Bounded host-operator reconciliation of the logical text/board charge ledger (DL-07, DL-09, T17).

The ledger is derived data: expected charges are recomputed from source content under the
versioned methods in :mod:`labadda.charges`. A dry run (default) reports drift and a plan
digest. ``apply`` requires stopped writers and the reviewed digest, recomputes the plan under
locks, and corrects ledger rows only. Content, files, access and admission are never changed.

Scope per run is bounded by item, board, board-object and cooperative time budgets with
keyset cursors, so a large site is reconciled in resumable batches.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from . import audit
from .boardstate import state_at
from .charges import BOARD_METHOD, TEXT_METHOD, expected_board_rows
from .models import Board, ContentCharge, StorageInspection
from .security import utcnow

PLAN_VERSION = 1
MAX_ISSUE_SAMPLES = 100

# Expected text charges from source rows, joined to the ledger. Keyset-ordered by (type, key).
TEXT_DIFF = text("""
WITH expected AS (
  SELECT 'post'::text AS t, id::text AS k, author_id AS u, workspace_id AS w,
         CASE WHEN deleted_at IS NULL THEN 'live' ELSE 'removed' END AS s,
         labadda_utf8_octets(body) AS b
  FROM posts
  UNION ALL
  SELECT 'chat', id::text, author_id, workspace_id, 'live', labadda_utf8_octets(body) FROM chat_messages
  UNION ALL
  SELECT 'note', id::text, owner_id, NULL, 'live', labadda_utf8_octets(title) + labadda_utf8_octets(body)
  FROM notes
), ledger AS (
  SELECT item_type AS t, item_key AS k, user_id AS u, workspace_id AS w, state AS s, bytes AS b, method AS m
  FROM content_charges WHERE item_type IN ('post', 'chat', 'note')
)
SELECT coalesce(e.t, l.t) AS item_type, coalesce(e.k, l.k) AS item_key,
       e.u AS eu, e.w AS ew, e.s AS es, e.b AS eb,
       l.u AS lu, l.w AS lw, l.s AS ls, l.b AS lb, l.m AS lm
FROM expected e FULL OUTER JOIN ledger l ON l.t = e.t AND l.k = e.k
WHERE (coalesce(e.t, l.t), coalesce(e.k, l.k)) > (:after_t, :after_k)
ORDER BY 1, 2
LIMIT :limit
""")


class ReconciliationStopped(Exception):
    pass


def _issue_code(expected: tuple | None, ledger: tuple | None) -> str | None:
    """Compare (user, workspace, state, bytes, method) tuples; return a drift code or None."""
    if expected is None:
        return "orphan_charge"
    if ledger is None:
        return "missing_charge"
    if expected[4] != ledger[4]:
        return "stale_method"
    if expected[3] != ledger[3]:
        return "stale_bytes"
    if expected[2] != ledger[2]:
        return "stale_state"
    if expected[:2] != ledger[:2]:
        return "stale_attribution"
    return None


def _correction(item_type: str, key: str, expected: tuple | None) -> list:
    if expected is None:
        return ["delete", item_type, key]
    user, workspace, state, size, method = expected
    return [
        "upsert",
        item_type,
        key,
        str(user),
        str(workspace) if workspace else None,
        state,
        int(size),
        method,
    ]


def _apply(db: Session, correction: list) -> None:
    if correction[0] == "delete":
        db.execute(
            delete(ContentCharge).where(
                ContentCharge.item_type == correction[1], ContentCharge.item_key == correction[2]
            )
        )
        return
    _, item_type, key, user, workspace, state, size, method = correction
    values = {
        "item_type": item_type,
        "item_key": key,
        "user_id": uuid.UUID(user),
        "workspace_id": uuid.UUID(workspace) if workspace else None,
        "method": method,
        "state": state,
        "bytes": size,
        "updated_at": utcnow(),
    }
    stmt = insert(ContentCharge).values(**values)
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["item_type", "item_key"],
            set_={k: stmt.excluded[k] for k in values if k not in ("item_type", "item_key")},
        )
    )


def reconcile_content_charges(
    factory,
    *,
    max_items: int = 10_000,
    max_boards: int = 50,
    max_board_objects: int = 200_000,
    max_seconds: float = 30,
    after_item: str | None = None,
    after_board: uuid.UUID | str | None = None,
    apply: bool = False,
    expected_plan: str | None = None,
    writers_quiesced: bool = False,
) -> dict:
    if not (
        1 <= max_items <= 1_000_000
        and 0 <= max_boards <= 10_000
        and 1 <= max_board_objects <= 5_000_000
        and 0 < max_seconds <= 600
    ):
        raise ValueError("Reconciliation budget is outside supported bounds")
    if apply and (not writers_quiesced or not re.fullmatch(r"[0-9a-f]{64}", expected_plan or "")):
        raise ValueError("Apply requires stopped writers and the reviewed dry-run plan digest")
    if not apply and (expected_plan is not None or writers_quiesced):
        raise ValueError("Application confirmation is only valid with apply")
    after_t, after_k = "", ""
    if after_item:
        after_t, sep, after_k = after_item.partition(":")
        if not sep or after_t not in ("post", "chat", "note"):
            raise ValueError("after_item must look like <post|chat|note>:<id>")
    after_board = uuid.UUID(str(after_board)) if after_board else None

    began = time.monotonic()
    summary = {
        "source": "operator_cli",
        "scope": "content_charge_reconciliation",
        "mode": "apply" if apply else "dry_run",
        "complete_for_enforcement": False,
        "methods": {"text": TEXT_METHOD, "board": BOARD_METHOD},
        "budget": {
            "items": max_items,
            "boards": max_boards,
            "board_objects": max_board_objects,
            "seconds": float(max_seconds),
        },
        "time_budget_kind": "cooperative_scan_only",
        "concurrent_changes_possible": not apply,
        "after_item": after_item,
        "after_board": str(after_board) if after_board else None,
        "checked_items": 0,
        "checked_boards": 0,
        "checked_board_objects": 0,
        "issue_count": 0,
        "issue_counts": {},
        "issues": [],
        "issues_truncated": False,
        "correction_count": 0,
        "boards_to_complete": 0,
        "applied_count": 0,
    }
    with factory() as db:
        receipt = StorageInspection(status="running", summary=summary.copy(), created_at=utcnow())
        db.add(receipt)
        db.commit()
        receipt_id = receipt.id
    commit_started = False

    def budget():
        if time.monotonic() - began >= max_seconds:
            raise ReconciliationStopped("time_budget_exhausted")

    def issue(item_type: str, key: str, code: str):
        summary["issue_count"] += 1
        summary["issue_counts"][code] = summary["issue_counts"].get(code, 0) + 1
        # Identifiers only: never bodies, titles, names or object payloads. Board object IDs are
        # client-chosen strings, so samples carry the workspace and a short digest instead.
        if len(summary["issues"]) < MAX_ISSUE_SAMPLES:
            if item_type == "board_object":
                workspace, _, object_id = key.partition(":")
                key = f"{workspace}:sha256:{hashlib.sha256(object_id.encode()).hexdigest()[:16]}"
            summary["issues"].append({"item_type": item_type, "item_key": key, "code": code})
        else:
            summary["issues_truncated"] = True

    try:
        with factory() as db:
            db.execute(text("set local statement_timeout = '10s'"))
            if apply and not db.scalar(
                text("select pg_try_advisory_xact_lock(hashtext('labadda_charge_reconciliation'))")
            ):
                raise ReconciliationStopped("reconciliation_busy")
            corrections: list[list] = []
            completions: list[list] = []

            # Text items (trigger-maintained; drift means a bypassed or disabled trigger).
            rows = db.execute(
                TEXT_DIFF, {"after_t": after_t, "after_k": after_k, "limit": max_items + 1}
            ).all()
            summary["more_items"] = len(rows) > max_items
            rows = rows[:max_items]
            summary["next_after_item"] = (
                f"{rows[-1].item_type}:{rows[-1].item_key}" if summary["more_items"] else None
            )
            for row in rows:
                budget()
                summary["checked_items"] += 1
                expected = None if row.eu is None else (row.eu, row.ew, row.es, int(row.eb), TEXT_METHOD)
                ledger = None if row.lu is None else (row.lu, row.lw, row.ls, int(row.lb), row.lm)
                code = _issue_code(expected, ledger)
                if code:
                    issue(row.item_type, row.item_key, code)
                    corrections.append([code, *_correction(row.item_type, row.item_key, expected)])

            # Boards: fold current state and compare per object.
            query = select(Board).order_by(Board.workspace_id).limit(max_boards + 1)
            if after_board is not None:
                query = query.where(Board.workspace_id > after_board)
            if apply:
                query = query.with_for_update()
            boards = db.scalars(query).all() if max_boards else []
            summary["more_boards"] = len(boards) > max_boards
            boards = boards[:max_boards]
            summary["next_after_board"] = str(boards[-1].workspace_id) if summary["more_boards"] else None
            for board in boards:
                budget()
                objects = state_at(db, board)
                summary["checked_board_objects"] += len(objects)
                if summary["checked_board_objects"] > max_board_objects:
                    raise ReconciliationStopped("board_object_budget_exhausted")
                summary["checked_boards"] += 1
                expected_rows = {
                    key: (user, board.workspace_id, "live", size, BOARD_METHOD)
                    for key, (user, size) in expected_board_rows(board.workspace_id, objects).items()
                }
                ledger_rows = {
                    r.item_key: (r.user_id, r.workspace_id, r.state, int(r.bytes), r.method)
                    for r in db.scalars(
                        select(ContentCharge).where(
                            ContentCharge.item_type == "board_object",
                            ContentCharge.workspace_id == board.workspace_id,
                        )
                    )
                }
                for key in sorted(set(expected_rows) | set(ledger_rows)):
                    code = _issue_code(expected_rows.get(key), ledger_rows.get(key))
                    if code:
                        issue("board_object", key, code)
                        corrections.append([code, *_correction("board_object", key, expected_rows.get(key))])
                if board.charges_epoch != board.epoch:
                    completions.append([str(board.workspace_id), board.epoch, board.revision])

            # Board-object charges whose workspace has no board row at all (bounded sample).
            if not after_board:
                orphans = db.scalars(
                    select(ContentCharge.item_key)
                    .where(
                        ContentCharge.item_type == "board_object",
                        ContentCharge.workspace_id.not_in(select(Board.workspace_id)),
                    )
                    .order_by(ContentCharge.item_key)
                    .limit(max_items)
                ).all()
                for key in orphans:
                    issue("board_object", key, "orphan_charge")
                    corrections.append(["orphan_charge", "delete", "board_object", key])

            summary["correction_count"] = len(corrections)
            summary["boards_to_complete"] = len(completions)
            # The digest covers the bounded selection, methods, budgets, each observed drift class and
            # its correction, so renewed drift invalidates an earlier review even if the fix is identical.
            payload = [
                PLAN_VERSION,
                summary["methods"],
                summary["budget"],
                summary["after_item"],
                summary["after_board"],
                summary["more_items"],
                summary["more_boards"],
                corrections,
                completions,
            ]
            summary["plan_digest"] = hashlib.sha256(
                json.dumps(payload, separators=(",", ":"), default=str).encode()
            ).hexdigest()
            if apply:
                if summary["plan_digest"] != expected_plan:
                    raise ReconciliationStopped("plan_changed")
                for _code, *correction in corrections:
                    _apply(db, correction)
                by_id = {str(b.workspace_id): b for b in boards}
                for workspace, epoch, _revision in completions:
                    by_id[workspace].charges_epoch = epoch
                summary["applied_count"] = len(corrections) + len(completions)
            summary["state"] = "applied" if apply else "dry_run"
            receipt = db.get(StorageInspection, receipt_id, with_for_update=True)
            receipt.status, receipt.summary, receipt.finished_at = "completed", summary, utcnow()
            audit.record(
                db,
                actor=None,
                action="storage.charge_reconcile",
                scope_type="site",
                target_id=receipt_id,
                mode=summary["mode"],
                plan_digest=summary["plan_digest"],
                corrections=summary["correction_count"],
            )
            commit_started = True
            db.commit()
        return {"id": str(receipt_id), "status": "completed", "summary": summary}
    except Exception as exc:
        if commit_started:
            # A lost commit reply must not overwrite a possibly completed run.
            with factory() as fresh:
                receipt = fresh.get(StorageInspection, receipt_id)
                if receipt.status == "completed":
                    return {"id": str(receipt_id), "status": receipt.status, "summary": receipt.summary}
            return {
                "id": str(receipt_id),
                "status": "uncertain",
                "summary": {"state": "commit_unknown", "applied_count": None},
            }
        reason = str(exc) if isinstance(exc, ReconciliationStopped) else "reconciliation_unavailable"
        summary.update(state="stopped", applied_count=0, stop_reason=reason)
        if not isinstance(exc, ReconciliationStopped):
            summary["error_class"] = type(exc).__name__  # diagnosable without exposing data
        summary.pop("plan_digest", None)  # A stopped attempt cannot supply application confirmation.
        with factory() as db:
            receipt = db.get(StorageInspection, receipt_id)
            receipt.status, receipt.summary, receipt.finished_at = "failed", summary, utcnow()
            audit.record(
                db,
                actor=None,
                action="storage.charge_reconcile",
                scope_type="site",
                target_id=receipt_id,
                outcome="failed",
                mode=summary["mode"],
                stop_reason=reason,
            )
            db.commit()
        return {"id": str(receipt_id), "status": "failed", "summary": summary}
