"""DL-04/07, T15/T29: capacity previews never imply complete accounting or activation."""

from types import SimpleNamespace

import pytest
from alembic import command
from sqlalchemy import text

from labadda.api.governance import CapacityProfile
from labadda.capacity import forecast_capacity
from labadda.cli import alembic_config
from labadda.fixtures import fixture_password
from tests.migration_helpers import downgrade_legacy
from tests.test_panel import pair

GiB = 1024**3


def profile(**overrides):
    return {"schema_version": 2, **overrides}


def forecast(api, **overrides):
    return api.post("/admin/capacity-forecasts", json={"profile": profile(**overrides)})


def test_v1_history_and_v2_capacity_proposals_keep_original_contract(as_user):
    admin = as_user("admin")
    first = admin.post(
        "/admin/policy-drafts", json={"base_revision": 0, "reason": "Legacy profile retained", "profile": {}}
    )
    assert first.status_code == 201 and first.json()["schema_version"] == 1
    second = admin.post(
        "/admin/policy-drafts",
        json={
            "base_revision": 1,
            "reason": "Capacity proposal only",
            "profile": profile(site_asset_budget_bytes=10 * GiB),
        },
    )
    assert second.status_code == 201 and second.json()["schema_version"] == 2
    assert second.json()["profile"]["site_asset_budget_bytes"] == 10 * GiB and not second.json()["enforced"]
    history = admin.get("/admin/policy-drafts").json()
    assert history["drafts"][1]["profile"] == first.json()["profile"]
    assert history["supported_schemas"] == [1, 2] and not history["activation_supported"]
    assert history["runtime_limits"]["user_quota_bytes"] == 500 * 1024**2
    stale = admin.post(
        "/admin/policy-drafts",
        json={"base_revision": 1, "reason": "Stale capacity edit", "profile": profile()},
    )
    assert stale.status_code == 409


@pytest.mark.parametrize(
    "invalid",
    [
        {"site_asset_budget_bytes": 0},
        {"site_asset_budget_bytes": True},
        {"site_asset_budget_bytes": 1.5},
        {"site_asset_budget_bytes": 11 * 1024 * GiB},
        {"filesystem_reserve_bytes": 0},
        {"filesystem_reserve_bytes": False},
        {"filesystem_reserve_percent": 0},
        {"filesystem_reserve_percent": 51},
        {"filesystem_reserve_percent": 10.5},
        {"schema_version": 2.0},
        {"schema_version": 3},
        {"mode": "enforced"},
        {"unknown_field": 1},
        {"site_asset_budget_bytes": 10},
    ],
)
def test_invalid_capacity_is_not_previewed_or_saved(as_user, invalid):
    admin = as_user("admin")
    assert forecast(admin, **invalid).status_code == 422
    saved = admin.post(
        "/admin/policy-drafts",
        json={"base_revision": 0, "reason": "Invalid bounds check", "profile": profile(**invalid)},
    )
    assert saved.status_code == 422
    assert admin.get("/admin/policy-drafts").json()["latest_revision"] == 0


def test_integer_forecast_counts_previews_and_pending_as_lower_bound():
    proposal = CapacityProfile(
        max_attachment_bytes=1, site_asset_budget_bytes=100, filesystem_reserve_bytes=1
    )
    assets = {
        "tracked_original_bytes": 100,
        "tracked_preview_bytes": 5,
        "pending_upload_original_bytes": 7,
        "unknown_preview_files": 2,
        "observed_at": "synthetic",
    }
    fs = {"state": "ready", "total_bytes": 14, "free_bytes": 9, "observed_at": "synthetic"}
    result = forecast_capacity(proposal, assets, fs)
    assert result["known_asset_lower_bound_bytes"] == 112
    assert result["site_asset_budget"]["known_lower_bound_exceeds_budget"] is True
    assert result["site_asset_budget"]["maximum_possible_headroom_bytes"] == 0
    assert result["filesystem"]["proposed_reserve_bytes"] == 2  # 10% rounded up, not float arithmetic.
    assert result["filesystem"]["maximum_growth_above_reserve_bytes"] == 7
    assert "unknown_preview_measurements" in result["warnings"]
    assert (
        result["state"] == "incomplete"
        and not result["complete_for_enforcement"]
        and not result["admission_changed"]
    )


def test_preview_has_no_policy_or_content_side_effect_and_audits_no_bodies(as_user, monkeypatch):
    from labadda.api import usage

    admin = as_user("admin")
    bharat = as_user("bharat")
    uploaded = bharat.post(
        "/uploads", files={"file": ("private-name.pdf", b"%PDF-1.4\nfixture\n%%EOF", "application/pdf")}
    )
    assert uploaded.status_code == 201
    before = bharat.get("/usage").json()
    monkeypatch.setattr(
        usage.os,
        "statvfs",
        lambda _: SimpleNamespace(f_bavail=8 * GiB, f_frsize=1, f_blocks=12 * GiB, f_favail=123),
    )
    result = forecast(admin, site_asset_budget_bytes=10 * GiB)
    assert result.status_code == 200 and "no-store" in result.headers["cache-control"]
    data = result.json()
    assert data["filesystem"]["proposed_reserve_bytes"] == 2 * GiB
    assert data["filesystem"]["maximum_growth_above_reserve_bytes"] == 6 * GiB
    assert data["site_asset_budget"]["maximum_possible_headroom_bytes"] == 10 * GiB - uploaded.json()["size"]
    after = bharat.get("/usage").json()
    assert after["runtime_limit"] == before["runtime_limit"]
    assert after["measurement"]["tracked_files"] == before["measurement"]["tracked_files"]
    assert admin.get("/admin/policy-drafts").json()["latest_revision"] == 0
    audit = admin.get("/admin/audit").json()["events"]
    assert any(e["action"] == "policy.capacity_forecast" for e in audit)
    assert "private-name" not in result.text and "private-name" not in str(audit)


def test_missing_filesystem_and_unconfigured_site_remain_unknown(as_user, monkeypatch):
    from labadda.api import usage

    def absent(_):
        raise OSError("synthetic unavailable")

    monkeypatch.setattr(usage.os, "statvfs", absent)
    data = forecast(as_user("admin")).json()
    assert (
        data["filesystem"]["state"] == "unknown"
        and data["filesystem"]["maximum_growth_above_reserve_bytes"] is None
    )
    assert data["site_asset_budget"]["maximum_possible_headroom_bytes"] is None
    assert {"filesystem_unavailable", "site_budget_unconfigured"} <= set(data["warnings"])


def test_reserve_shortfall_cannot_be_reported_as_available_growth(as_user, monkeypatch):
    from labadda.api import usage

    monkeypatch.setattr(
        usage.os, "statvfs", lambda _: SimpleNamespace(f_bavail=1, f_frsize=1, f_blocks=1024, f_favail=10)
    )
    data = forecast(as_user("admin")).json()
    assert data["filesystem"]["maximum_growth_above_reserve_bytes"] == 0
    assert data["filesystem"]["reserve_shortfall_bytes"] == 2 * GiB - 1
    assert {"reserve_exceeds_filesystem", "filesystem_reserve_not_met"} <= set(data["warnings"])


def test_capacity_preview_requires_admin_csrf_and_normal_session(as_user, ids, make_client):
    admin = as_user("admin")
    bharat = as_user("bharat")
    assert forecast(bharat).status_code == 403
    assert (
        admin.post(
            "/admin/usage-readers",
            json={
                "user_id": ids["users"]["bharat"],
                "hours": 1,
                "reason": "Synthetic observer scope",
                "password": fixture_password(),
            },
        ).status_code
        == 201
    )
    assert bharat.get("/admin/usage").status_code == 200 and forecast(bharat).status_code == 403
    assert (
        admin.client.post(admin.url("/admin/capacity-forecasts"), json={"profile": profile()}).status_code
        == 403
    )
    assert (
        admin.post(
            "/admin/capacity-forecasts", headers={"X-LabAdda-Panel": "1"}, json={"profile": profile()}
        ).status_code
        == 401
    )
    panel = pair(as_user, make_client, ids)
    assert panel.post("/admin/capacity-forecasts", json={"profile": profile()}).status_code == 401


@pytest.mark.parametrize("change,status", [("demote", 403), ("revoke", 401)])
def test_authority_is_rechecked_after_measurement(as_user, db_factory, monkeypatch, change, status):
    from labadda.api import governance

    admin = as_user("admin")
    original = governance.forecast_capacity

    def changed(*args):
        result = original(*args)
        with db_factory() as db:
            sql = (
                "update users set is_admin=false where username='admin'"
                if change == "demote"
                else "update auth_sessions set revoked_at=now() where user_id=(select id from users where "
                "username='admin')"
            )
            db.execute(text(sql))
            db.commit()
        return result

    monkeypatch.setattr(governance, "forecast_capacity", changed)
    assert forecast(admin).status_code == status
    with db_factory() as db:
        assert (
            db.scalar(text("select count(*) from audit_events where action='policy.capacity_forecast'")) == 0
        )


def test_capacity_history_blocks_incompatible_downgrade(as_user, settings):
    result = as_user("admin").post(
        "/admin/policy-drafts",
        json={"base_revision": 0, "reason": "Preserve capacity proposal", "profile": profile()},
    )
    assert result.status_code == 201
    with pytest.raises(RuntimeError, match="Capacity proposals exist"):
        downgrade_legacy(alembic_config(settings.database_url), "0014")


def test_migration_round_trip_preserves_v1_proposal_exactly(as_user, settings):
    admin = as_user("admin")
    before = admin.post(
        "/admin/policy-drafts", json={"base_revision": 0, "reason": "Preserved legacy history", "profile": {}}
    )
    assert before.status_code == 201
    cfg = alembic_config(settings.database_url)
    try:
        downgrade_legacy(cfg, "0014")
    finally:
        command.upgrade(cfg, "head")
    after = admin.get("/admin/policy-drafts").json()["drafts"][0]
    assert after == before.json()
