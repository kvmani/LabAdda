"""Workspace-owned metadata observations in one SQL statement/MVCC snapshot.

No subtree expansion, private notes, provisional uploads or site overhead.
"""
from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB

from .charges import BOARD_METHOD, TEXT_METHOD
from .models import Asset, Board, ContentCharge, Post, ChatMessage
from .security import utcnow
from .serialize import iso

SHARED_TYPES = ('post', 'chat', 'board_object')


def workspace_observation(db, workspace_id):
    files = select(func.jsonb_build_object(
        'retained_files', func.count(Asset.id),
        'retained_original_bytes', func.coalesce(func.sum(Asset.size), 0),
        'recorded_preview_bytes', func.coalesce(func.sum(Asset.preview_size), 0),
        'unknown_preview_files', func.count(case((Asset.has_preview & Asset.preview_size.is_(None), 1))),
        'removed_post_original_bytes', func.coalesce(func.sum(case((Post.deleted_at.is_not(None), Asset.size), else_=0)), 0),
        type_=JSONB,
    )).select_from(Asset).outerjoin(Post, Asset.post_id == Post.id).outerjoin(ChatMessage,Asset.chat_message_id==ChatMessage.id).where(
        Asset.status == 'committed',
        or_(Asset.board_workspace_id == workspace_id, Post.workspace_id == workspace_id, ChatMessage.workspace_id==workspace_id))
    columns = [files.scalar_subquery()]
    for kind in SHARED_TYPES:
        columns.append(select(func.jsonb_build_object(
            'live_bytes', func.coalesce(func.sum(case((ContentCharge.state == 'live', ContentCharge.bytes), else_=0)), 0),
            'live_items', func.count(case((ContentCharge.state == 'live', 1))),
            'removed_bytes', func.coalesce(func.sum(case((ContentCharge.state == 'removed', ContentCharge.bytes), else_=0)), 0),
            'removed_items', func.count(case((ContentCharge.state == 'removed', 1))), type_=JSONB,
        )).where(ContentCharge.workspace_id == workspace_id, ContentCharge.item_type == kind).scalar_subquery())
    incomplete = select(func.count()).select_from(Board).where(
        Board.workspace_id == workspace_id, Board.revision > 0,
        Board.charges_epoch.is_distinct_from(Board.epoch))
    columns.append(incomplete.scalar_subquery())
    file_counts, *rest = db.execute(select(*columns)).one()
    buckets, unreconciled = rest[:-1], rest[-1]
    by_type = dict(zip(SHARED_TYPES, buckets, strict=True))
    observed_at = iso(utcnow())
    return {
        'scope': 'workspace', 'workspace_id': str(workspace_id), 'observed_at': observed_at,
        'files': {**file_counts, 'pending_upload_bytes': None,
                  'pending_attribution': 'not_attributed_before_destination_commit',
                  'source': 'workspace_asset_metadata', 'state': 'partial'},
        'logical_charges': {
            'methods': {'text': TEXT_METHOD, 'board': BOARD_METHOD}, 'by_type': by_type,
            'live_logical_bytes': sum(bucket['live_bytes'] for bucket in buckets),
            'removed_logical_bytes': sum(bucket['removed_bytes'] for bucket in buckets),
            'board_charges': 'incomplete' if unreconciled else 'complete',
            'unreconciled_boards': unreconciled, 'observed_at': observed_at,
            'source': 'content_charges_ledger', 'complete_for_enforcement': False,
        },
        'workspace_budget': {'bytes': None, 'state': 'not_configured', 'policy_proposals_enforced': False},
        'unmeasured': ['unattributed_pending_uploads', 'other_or_historical_derivative_bytes',
                       'trash', 'temporary_archives', 'reference_reconciliation'],
        'complete_for_enforcement': False,
    }
