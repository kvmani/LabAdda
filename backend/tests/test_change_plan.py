"""P2 plan integrity and immutable snapshots, without executable API or database writes."""

from dataclasses import FrozenInstanceError, replace
from datetime import date
from hashlib import sha256

import pytest

from labadda.changes.plan import Blocker, Plan, Snapshot, Step, Warning, canonical_json


def sample_plan() -> Plan:
    """Build a fictional edit whose consequences contain only staff metadata."""
    return Plan(
        kind="edit_person",
        actor_id="administrator-id",
        request=Snapshot({"person_id": "bharat-id", "display_name": "Bharat Kulkarni"}),
        revisions=Snapshot({"bharat-id": 3}),
        steps=(
            Step(
                "identity",
                "bharat-id",
                "Change Bharat's display name",
                Snapshot({"display_name": "Bharat"}),
                Snapshot({"display_name": "Bharat Kulkarni"}),
            ),
        ),
        affected_people=0,
    )


def test_canonical_snapshot_has_exact_unicode_and_stable_object_order():
    values = {"b": "研究", "a": [True, None, 2, {"z": False}]}
    expected = '{"a":[true,null,2,{"z":false}],"b":"研究"}'
    assert canonical_json(values) == expected
    assert canonical_json({"a": values["a"], "b": values["b"]}) == expected


def test_snapshot_detaches_inputs_and_every_serialized_result():
    values = {"memberships": [{"role": "member"}]}
    snapshot = Snapshot(values)
    values["memberships"][0]["role"] = "steward"
    exported = snapshot.to_dict()
    exported["memberships"][0]["role"] = "steward"
    assert snapshot.to_dict() == {"memberships": [{"role": "member"}]}
    assert "member" not in repr(snapshot)
    with pytest.raises(FrozenInstanceError):
        snapshot._canonical = "{}"


@pytest.mark.parametrize("value", [0.5, float("nan"), float("inf"), date(2026, 11, 11), ("tuple",)])
def test_snapshot_refuses_values_that_need_implicit_or_unstable_json_coercion(value):
    with pytest.raises(TypeError):
        Snapshot({"value": value})


def test_snapshot_requires_an_object_and_string_keys():
    with pytest.raises(TypeError):
        Snapshot(["array"])
    with pytest.raises(TypeError):
        Snapshot({1: "numeric key"})


def test_plan_digest_covers_the_versioned_payload_without_hashing_itself():
    plan = sample_plan()
    payload = plan.to_dict()
    digest = payload.pop("digest")
    assert len(digest) == 64
    assert digest == plan.digest
    assert digest == sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    assert payload["format_version"] == 1
    assert payload["steps"][0]["summary"] == "Change Bharat's display name"


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "transfer"},
        {"actor_id": "other-administrator"},
        {"request": Snapshot({"person_id": "chitra-id"})},
        {"revisions": Snapshot({"bharat-id": 4})},
        {"steps": ()},
        {"warnings": (Warning("last_steward", "The unit needs a steward", "unit-id"),)},
        {"blockers": (Blocker("duplicate_employee", "Employee number is already used"),)},
        {"affected_people": 1},
    ],
)
def test_each_reviewed_consequence_changes_the_digest(changes):
    plan = sample_plan()
    assert replace(plan, **changes).digest != plan.digest


def test_ordered_steps_are_significant_and_input_collections_cannot_mutate_plan():
    first = sample_plan().steps[0]
    second = replace(first, summary="Change the designation")
    steps = [first, second]
    plan = replace(sample_plan(), steps=steps)
    steps.clear()
    assert plan.steps == (first, second)
    assert replace(plan, steps=(second, first)).digest != plan.digest
    payload = plan.to_dict()
    payload["request"]["display_name"] = "Changed outside the plan"
    assert plan.to_dict()["request"]["display_name"] == "Bharat Kulkarni"
    with pytest.raises(FrozenInstanceError):
        plan.actor_id = "other-administrator"


@pytest.mark.parametrize("count", [-1, 0.5, True])
def test_invalid_affected_counts_are_refused(count):
    with pytest.raises(ValueError):
        replace(sample_plan(), affected_people=count)


@pytest.mark.parametrize("revision", [0, -1, True, "3"])
def test_record_revisions_are_positive_integers(revision):
    with pytest.raises(ValueError):
        replace(sample_plan(), revisions=Snapshot({"bharat-id": revision}))
