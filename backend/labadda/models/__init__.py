"""Persistent data model, one module per area.

Schema changes are applied only through Alembic migrations in ``backend/migrations``. Keep these
modules and the migrations in step. Every model is re-exported here, so ``from .models import X``
works and the declarative registry knows every class before relationships are resolved.
"""

from .base import POSTING_POLICIES, ROLES, WORKSPACE_KINDS, Base
from .boards import (
    Board,
    BoardOp,
    BoardSnapshot,
    PersonalBoardRevision,
    WorkspaceBoard,
)
from .content import (
    Asset,
    CalendarEvent,
    ChatMessage,
    ChatRead,
    Feedback,
    FeedbackMail,
    Note,
    Notification,
    NotificationPreference,
    Post,
    SiteBroadcast,
    SystemSetting,
)
from .identity import (
    AuthSession,
    CredentialToken,
    PanelPairing,
    User,
)
from .operations import (
    ActivityDay,
    ContentCharge,
    InventoryAttempt,
    InventoryJob,
    MetricSample,
    OpsEvent,
    PolicyDraft,
    StorageInspection,
    UploadReceipt,
    UploadReservation,
    UsageObservation,
)
from .organisation import (
    AuditEvent,
    ContributionDelegation,
    JoinRequest,
    Membership,
    ScheduledChange,
    UnitAdminGrant,
    UnitPosition,
    UsageReaderGrant,
    Workspace,
)
from .tasks import (
    TodoChange,
    TodoComment,
    TodoList,
    TodoSource,
    TodoTask,
)

__all__ = [
    "POSTING_POLICIES",
    "ROLES",
    "WORKSPACE_KINDS",
    "ActivityDay",
    "Asset",
    "AuditEvent",
    "AuthSession",
    "Base",
    "Board",
    "BoardOp",
    "BoardSnapshot",
    "CalendarEvent",
    "ChatMessage",
    "ChatRead",
    "ContentCharge",
    "ContributionDelegation",
    "CredentialToken",
    "Feedback",
    "FeedbackMail",
    "InventoryAttempt",
    "InventoryJob",
    "JoinRequest",
    "Membership",
    "MetricSample",
    "Note",
    "Notification",
    "NotificationPreference",
    "OpsEvent",
    "PanelPairing",
    "PersonalBoardRevision",
    "PolicyDraft",
    "Post",
    "ScheduledChange",
    "SiteBroadcast",
    "StorageInspection",
    "SystemSetting",
    "TodoChange",
    "TodoComment",
    "TodoList",
    "TodoSource",
    "TodoTask",
    "UnitAdminGrant",
    "UnitPosition",
    "UploadReceipt",
    "UploadReservation",
    "UsageObservation",
    "UsageReaderGrant",
    "User",
    "Workspace",
    "WorkspaceBoard",
]
