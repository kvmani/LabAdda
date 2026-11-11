"""Observation-only capacity forecasts; never an admission or activation decision."""


def forecast_capacity(profile, assets, filesystem):
    known = (
        assets["tracked_original_bytes"]
        + assets["tracked_preview_bytes"]
        + assets["pending_upload_original_bytes"]
    )
    budget = profile.site_asset_budget_bytes
    warnings = ["unmeasured_storage_classes"]
    if budget is None:
        warnings.append("site_budget_unconfigured")
    elif known > budget:
        warnings.append("known_lower_bound_over_budget")
    if assets["unknown_preview_files"]:
        warnings.append("unknown_preview_measurements")
    total, free = filesystem["total_bytes"], filesystem["free_bytes"]
    valid = (
        filesystem["state"] == "ready"
        and total is not None
        and free is not None
        and 0 <= free <= total
        and total > 0
    )
    reserve = growth = shortfall = None
    if valid:
        reserve = max(
            profile.filesystem_reserve_bytes, (total * profile.filesystem_reserve_percent + 99) // 100
        )
        growth = max(0, free - reserve)
        shortfall = max(0, reserve - free)
        if reserve > total:
            warnings.append("reserve_exceeds_filesystem")
        if shortfall:
            warnings.append("filesystem_reserve_not_met")
    else:
        warnings.append("filesystem_unavailable")
    return {
        "state": "incomplete",
        "profile": profile.model_dump(),
        "known_asset_lower_bound_bytes": known,
        "unknown_preview_files": assets["unknown_preview_files"],
        "asset_observed_at": assets["observed_at"],
        "site_asset_budget": {
            "proposed_bytes": budget,
            "maximum_possible_headroom_bytes": max(0, budget - known) if budget is not None else None,
            "known_lower_bound_exceeds_budget": known > budget if budget is not None else None,
        },
        "filesystem": {
            "state": "ready" if valid else "unknown",
            "observed_at": filesystem["observed_at"],
            "free_bytes": free if valid else None,
            "total_bytes": total if valid else None,
            "proposed_reserve_bytes": reserve,
            "maximum_growth_above_reserve_bytes": growth,
            "reserve_shortfall_bytes": shortfall,
        },
        "warnings": warnings,
        "complete_for_enforcement": False,
        "activation_supported": False,
        "admission_changed": False,
        "limitations": [
            "metadata_not_disk_inventory",
            "unknown_historical_previews",
            "unreferenced_files",
            "other_derivatives",
            "temporary_and_system_storage",
            "shared_filesystem",
            "independently_observed_database_and_filesystem",
        ],
    }
