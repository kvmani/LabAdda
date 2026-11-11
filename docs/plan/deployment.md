# Track D — deployment, operation and release

Contracts: [DEPLOYMENT.md](../DEPLOYMENT.md), [RELEASES.md](../RELEASES.md),
[RECOVERY.md](../RECOVERY.md), [COMMISSIONING.md](../COMMISSIONING.md). Developer guide:
[operations.md](../development/operations.md). Existing tooling: `scripts/release.py`,
`operations.py`, `lifecycle.py`, `commission.py`.

Rules for the whole track: tools are **plan-first** (show what would happen; change nothing
without an explicit flag), refuse to run on a non-empty or unexpected target, never print
secrets, and never touch a real site from an agent session. An agent prepares and tests on
disposable local stacks; the owner or operator runs anything on a real host.

### D1 · Rehearsal on a disposable Ubuntu 24.04 host

Status `owner`. Size M for the operator; an agent prepares the checklist and fixes findings.

**Goal.** Prove the whole lifecycle on the real target platform: build the offline release on
Ubuntu 24.04, commission an empty site, activate, take a baseline backup, upgrade, rehearse a
failed upgrade, restore to an isolated instance from an off-host copy, and measure how long
recovery takes and how much data could be lost.

**Agent part.** Turn [the operations evidence handoff](../evidence/operations/README.md) into a
numbered rehearsal sheet `docs/REHEARSAL-SHEET.md`: each step with the exact command, the
expected output, and a box for the observed result. Fix any defect the operator reports, with a
regression test.

**Acceptance.** The completed sheet is committed (fictional host names) with every step
observed, and the measured recovery time and recovery point recorded.

### D2 · Operator quickstart and `labadda doctor`

Size M. Depends on nothing.

**Goal.** A careful person with basic Linux skills can install, check and upgrade LabAdda from
one short guide, and one command tells them whether the installation is sound.

**Build.** `labadda doctor` (in `backend/labadda/cli.py`, logic in a new `doctor.py`):
read-only checks with plain-language results and a fix hint each — configuration valid,
database reachable and schema matches the release, asset directory writable with free space
above reserve, service and proxy reachable at the configured address and prefix, TLS readiness
when configured, backup status file present and fresh, time zone valid. Exit code 0 only when
every check passes; `--json` for the console. `docs/OPERATOR-QUICKSTART.md`: a two-page path
through install → first administrator → doctor → backup → upgrade, linking to the detailed
documents; it becomes the source for the operator help pages (H4).

**Acceptance.** Each check has a passing and a failing unit test with an injected environment.
`doctor` never prints a secret (test seeds a secret-like value). The quickstart is followed
end to end on the local proxy stack by someone other than its author (a fresh agent session
counts) with no step missing.

### D3 · Scheduled backups with status file

Size M. Depends on nothing.

**Goal.** Backups run on a schedule and report their result where the console can read it
(AD-10).

**Build.** A systemd timer and service template in `deploy/systemd/` that calls the existing
backup lifecycle; after each run `scripts/lifecycle.py` writes `backup-status.json`
atomically (write to a temporary file, fsync, rename) into `LABADDA_STATUS_DIR`, with the
schema in ADMIN-CONSOLE-V1 AD-10 and no paths or secrets. A verification step records the
manifest check result. Retention of local backups by count, plan-first. Document in
`RECOVERY.md` and the quickstart.

**Acceptance.** Tests: status file written on success and on failure; a crash mid-write leaves
the previous file intact; the file validates against the same schema module the backend reader
uses (one shared definition, imported by both).

### D4 · Site acceptance

Status `owner`.

**Goal.** The site owner accepts LabAdda for a supervised pilot.

**Checklist** (the owner records each as accepted, with the date): identity and account policy
confirmed · site TLS and address in place · `labadda doctor` clean on the site host · backup to
off-host storage and a restore rehearsal completed · touch-panel test with pen and finger on
the real panel · screen-reader and visual review of the main flows · two real sibling sections
and their division rehearsed with the staff who will use it · independent review per
[REVIEW.md](../../REVIEW.md) concluded "ready for supervised pilot" · setup checklist in the
console fully green.

### D5 · Release 1.0

Size S. Depends on D4.

**Goal.** A tagged, documented 1.0 release.

**Build.** Set version `1.0.0` in `backend/pyproject.toml` and `frontend/package.json` (one
helper keeps them equal; the version shows in the console and in `doctor`). `CHANGELOG.md`
(Keep a Changelog format) and `docs/releases/1.0.0.md` in plain language. `docs/UPGRADING.md`:
the compatibility promise from 1.0 onward — every later release upgrades in place from the
previous one without data loss, and any breaking change needs the owner's written approval.
Update "What's new" in help.

**Acceptance.** Offline release built and verified by `scripts/release.py`; the upgrade from
the last pre-1.0 commit is rehearsed on the local stack with data preserved.
