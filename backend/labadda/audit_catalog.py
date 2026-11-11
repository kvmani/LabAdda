"""One plain-English description for every audit action, grouped as AD-09 requires."""

from __future__ import annotations

from dataclasses import dataclass

GROUPS: dict[str, str] = {
    "people": "People",
    "access": "Access",
    "organisation": "Organisation",
    "authority": "Authority",
    "sign_in": "Sign-in security",
    "settings": "Settings and storage",
    "exports": "Exports",
}


@dataclass(frozen=True)
class Entry:
    group: str
    sentence: str


# Placeholders: {actor}, {target} and {unit} are filled with names the console may show;
# {role}, {rows} and similar come from the recorded detail. Missing values read "unknown".
CATALOG: dict[str, Entry] = {
    "identity.create": Entry("people", "{actor} created the account for {target}."),
    "identity.update": Entry("people", "{actor} changed the account details of {target}."),
    "identity.reset": Entry("people", "{actor} issued a password reset link for {target}."),
    "people.change": Entry("people", "{actor} applied a reviewed staff change for {target}."),
    "people.change_step": Entry("people", "{actor} updated the staff record of {target}."),
    "membership.set": Entry("access", "{actor} set the role of {target} in {unit} to {after}."),
    "membership.remove": Entry("access", "{actor} removed {target} from {unit}."),
    "tree.create": Entry("organisation", "{actor} created {unit}."),
    "tree.move": Entry("organisation", "{actor} moved {unit} to a different place in the organisation."),
    "workspace.archive": Entry("organisation", "{actor} archived {unit}."),
    "workspace.unarchive": Entry("organisation", "{actor} restored {unit} from the archive."),
    "workspace.posting_policy": Entry("organisation", "{actor} changed who may post in {unit}."),
    "group.create": Entry("organisation", "{actor} created {unit}."),
    "group.archive": Entry("organisation", "{actor} archived {unit}."),
    "group.unarchive": Entry("organisation", "{actor} restored {unit} from the archive."),
    "usage.reader.grant": Entry("authority", "{actor} gave {target} read-only operational access."),
    "usage.reader.revoke": Entry("authority", "{actor} withdrew the operational access of {target}."),
    "usage.reader.reauthenticate": Entry(
        "authority", "{actor} was asked to confirm their password to manage operational access."
    ),
    "post.moderate_remove": Entry("authority", "{actor} removed a notice-board post in {unit}."),
    "post.pin": Entry("authority", "{actor} pinned a notice-board post in {unit}."),
    "post.unpin": Entry("authority", "{actor} unpinned a notice-board post in {unit}."),
    "board.restore": Entry("authority", "{actor} restored an earlier version of the whiteboard in {unit}."),
    "board.snapshot_publish": Entry("authority", "{actor} published a whiteboard snapshot to {unit}."),
    "auth.login": Entry("sign_in", "{actor} signed in."),
    "auth.password_changed": Entry("sign_in", "{actor} changed their own password."),
    "auth.session_ended": Entry("sign_in", "{actor} signed out one of their other sessions."),
    "auth.activation_redeemed": Entry("sign_in", "{actor} activated their account."),
    "auth.reset_redeemed": Entry("sign_in", "{actor} finished a password reset."),
    "panel.pairing_created": Entry(
        "sign_in", "{actor} created a pairing code for a shared board screen in {unit}."
    ),
    "panel.start": Entry("sign_in", "A shared board screen for {unit} started a session."),
    "panel.lock": Entry("sign_in", "A shared board screen for {unit} locked after being idle."),
    "panel.end": Entry("sign_in", "A shared board screen for {unit} ended its session."),
    "policy.draft": Entry("settings", "{actor} saved a draft storage policy."),
    "policy.capacity_forecast": Entry("settings", "{actor} recorded a storage capacity forecast."),
    "usage.observe": Entry("settings", "{actor} recorded a storage usage observation."),
    "storage.inspect": Entry("settings", "Operator tooling recorded a storage inspection."),
    "storage.inventory": Entry("settings", "Operator tooling recorded a storage inventory."),
    "storage.preview_reconcile": Entry("settings", "Preview storage was reconciled in {mode} mode."),
    "storage.charge_reconcile": Entry("settings", "Storage charges were reconciled in {mode} mode."),
    "inventory_job.request": Entry("settings", "A storage inventory job was requested."),
    "inventory_job.claim": Entry("settings", "Operator tooling started a storage inventory job."),
    "inventory_job.finish": Entry("settings", "Operator tooling finished a storage inventory job."),
    "inventory_job.cancel": Entry("settings", "A storage inventory job was cancelled."),
    "site.banner_set": Entry("settings", "{actor} published a site notice."),
    "site.banner_clear": Entry("settings", "{actor} removed the site notice."),
    "ops_event.acknowledge": Entry("settings", "{actor} acknowledged a system event."),
    "ops_event.resolve": Entry("settings", "{actor} marked a system event as resolved."),
    "people.export": Entry("exports", "{actor} exported {rows} rows of the staff directory."),
    "audit.export": Entry("exports", "{actor} exported {rows} entries of the audit trail."),
}

UNKNOWN = Entry("settings", "{actor} performed an action this version does not describe.")


def entry(action: str) -> Entry:
    return CATALOG.get(action, UNKNOWN)


def actions_in_group(group: str) -> list[str]:
    return [name for name, item in CATALOG.items() if item.group == group]
