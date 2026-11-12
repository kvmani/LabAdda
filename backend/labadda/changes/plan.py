"""Immutable staff-change metadata with deterministic, versioned plan digests."""

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Literal

type JsonValue = bool | int | str | list[JsonValue] | dict[str, JsonValue] | None
type JsonObject = dict[str, JsonValue]
type ChangeKind = Literal[
    "add_person",
    "edit_person",
    "transfer",
    "promote",
    "change_authority",
    "additional_charge",
    "leave",
    "return",
    "retire",
    "suspend",
    "reinstate",
    "unit_create",
    "unit_rename",
    "unit_move",
    "unit_merge",
    "unit_split",
    "unit_close",
    "unit_reopen",
    "unit_admin_grant",
    "unit_admin_revoke",
]


def canonical_json(value: JsonObject) -> str:
    """Use sorted object keys and exact Unicode; array order remains significant."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _validate_json(value: JsonValue) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Plan metadata keys must be strings")
            _validate_json(item)
    elif isinstance(value, list):
        for item in value:
            _validate_json(item)
    elif value is not None and type(value) not in (str, bool, int):
        raise TypeError("Plan metadata supports only strings, integers, booleans, null, arrays and objects")


@dataclass(frozen=True, init=False)
class Snapshot:
    """Detach structured metadata from mutable inputs and every serialized result."""

    _canonical: str = field(repr=False)

    def __init__(self, values: JsonObject) -> None:
        if not isinstance(values, dict):
            raise TypeError("A metadata snapshot must be an object")
        _validate_json(values)
        object.__setattr__(self, "_canonical", canonical_json(values))

    def to_dict(self) -> JsonObject:
        """Return a new editable copy without exposing the stored snapshot."""
        return json.loads(self._canonical)


@dataclass(frozen=True)
class Step:
    """One ordered, human-readable metadata transition for one person or unit."""

    target_type: Literal["identity", "workspace"]
    target_id: str
    summary: str
    before: Snapshot
    after: Snapshot

    def to_dict(self) -> JsonObject:
        """Serialize staff metadata without accepting client-supplied executable steps."""
        return {
            "target_type": self.target_type,
            "target_id": self.target_id,
            "summary": self.summary,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
        }


@dataclass(frozen=True)
class Warning:
    """An explicit concern; ``count`` carries a reviewed number (never content) when relevant."""

    code: str
    message: str
    target_id: str | None = None
    count: int | None = None

    def __post_init__(self) -> None:
        if self.count is not None and (type(self.count) is not int or self.count < 0):
            raise ValueError("A warning count must be a nonnegative integer")


@dataclass(frozen=True)
class Blocker:
    """A problem that prevents application until the request or server state changes."""

    code: str
    message: str
    target_id: str | None = None


@dataclass(frozen=True)
class Plan:
    """Bind a request, actor, revisions and consequences; a digest is not authorization."""

    kind: ChangeKind
    actor_id: str
    request: Snapshot = field(repr=False)
    revisions: Snapshot
    steps: tuple[Step, ...] = ()
    warnings: tuple[Warning, ...] = ()
    blockers: tuple[Blocker, ...] = ()
    affected_people: int = 0

    def __post_init__(self) -> None:
        for name in ("steps", "warnings", "blockers"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if type(self.affected_people) is not int or self.affected_people < 0:
            raise ValueError("Affected people must be a nonnegative integer")
        revisions = self.revisions.to_dict()
        if any(type(value) is not int or value < 1 for value in revisions.values()):
            raise ValueError("Record revisions must be positive integers")

    def _payload(self) -> JsonObject:
        return {
            "format_version": 1,
            "kind": self.kind,
            "actor_id": self.actor_id,
            "request": self.request.to_dict(),
            "revisions": self.revisions.to_dict(),
            "steps": [step.to_dict() for step in self.steps],
            "warnings": [asdict(warning) for warning in self.warnings],
            "blockers": [asdict(blocker) for blocker in self.blockers],
            "affected_people": self.affected_people,
        }

    @property
    def digest(self) -> str:
        """Hash the complete versioned payload; ordered consequences remain significant."""
        return sha256(canonical_json(self._payload()).encode("utf-8")).hexdigest()

    def to_dict(self) -> JsonObject:
        """Return detached metadata and its digest, ready for a future preview response."""
        payload = self._payload()
        return {**payload, "digest": sha256(canonical_json(payload).encode("utf-8")).hexdigest()}
