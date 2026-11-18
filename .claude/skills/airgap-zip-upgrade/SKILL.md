---
name: airgap-zip-upgrade
description: Cut a LabAdda release and install or upgrade it on an air-gapped Ubuntu 24.04 server from GitHub's "Source code (zip)", with no git on the server and packages from the office mirrors. Use when the owner asks to cut or prepare a release, deploy, install, upgrade or roll out LabAdda, or asks for step-by-step server commands.
---

# LabAdda air-gapped zip release and upgrade

Same model as project_management_software (PM): the owner publishes a GitHub release, downloads
**Source code (zip)**, records its SHA-256 on the connected PC and copies the zip to the server.
Read [docs/deployment/README.md](../../../docs/deployment/README.md) (setups A/B/C) and, for a server
shared with PM, [pm-coexistence.md](../../../docs/deployment/pm-coexistence.md) first. The owner runs
every server command; send one step per message, each ending with "what to look for".

## Part A — cut the release (in the repository)

1. `git pull --ff-only origin main`. Review every commit since the version the server runs: migrations
   (each has a tested upgrade and a data-safe downgrade), new settings (optional, safe default),
   dependency changes, deleted or renamed files (copying over an old folder would leave them).
2. Bump the version in `backend/labadda/__init__.py`, `backend/pyproject.toml`,
   `frontend/package.json` and the two `"version"` lines of `frontend/package-lock.json`, plus the
   current-version assertions in `backend/tests/test_version.py` and `frontend/src/buildInfo.test.ts`.
   Beta stays `-beta`; bump the minor number for a feature release. Never reuse a published number.
3. Gates, all must pass and be recorded: `scripts/verify.sh --e2e`;
   `python scripts/check_dependency_age.py` (every pin >= 30 days, no exceptions);
   then on the exact candidate commit, as GitHub will package it:
   ```bash
   git archive --format=zip --prefix=LabAdda-X.Y.Z/ HEAD > /tmp/LabAdda-X.Y.Z.zip
   sudo scripts/rehearse-rollout.sh --zip /tmp/LabAdda-X.Y.Z.zip
   sudo scripts/rehearse-rollout.sh --zip /tmp/LabAdda-X.Y.Z.zip --dedicated-http
   sudo scripts/rehearse-rollout.sh --zip /tmp/LabAdda-X.Y.Z.zip --shared-http
   sudo scripts/rehearse-rollout.sh <bundle of the running version> --upgrade-zip /tmp/LabAdda-X.Y.Z.zip
   ```
4. Ledger row in `ROADMAP.md`, status in `docs/plan/README.md`; commit and push `main` (fast-forward).
5. The owner publishes the release in the browser (Releases → Draft new release → tag `vX.Y.Z`,
   target the pushed commit). Pushing tags is blocked from cloud sessions.
6. Give the owner the commit SHA to expect: `upgrade.sh` prints it from the zip's comment.

## Part B — on the server (owner runs; wrap blocks as `bash <<'STEPn' … STEPn`)

1. **Connected PC:** download Source code (zip); `sha256sum LabAdda-X.Y.Z.zip` (or
   `Get-FileHash -Algorithm SHA256`); note the hash apart from the zip; copy the zip to the server.
2. **Read-only checks:** `sha256sum` again, `unzip -q`, `cat LabAdda-X.Y.Z/backend/labadda/__init__.py`,
   `sudo labadda-status`, `df -h /srv /var/tmp`, `node -v`, `npm -v`.
3. **Dry run** — zip, build prerequisites, mirrors and running-site sanity; changes nothing:
   `sudo bash LabAdda-X.Y.Z/deploy/upgrade.sh --zip LabAdda-X.Y.Z.zip --sha256 <HASH> --dry-run`
   (first install: `deploy/install.sh … --answers FILE --skip-os-packages --dry-run`).
4. **Upgrade:** the same command without `--dry-run`; type `UPGRADE` when asked. It builds beside the
   live site, then closes it, takes and verifies a backup, migrates, switches, starts and checks health.
5. **Verify:** `sudo labadda-status` (new version, web address answers, last backup minutes old), the
   doctor output printed at the end, a sign-in in the browser; setup B: one PM page still opens.
6. **If it failed:** the script says whether it rolled back automatically. If the site was left closed,
   collect `sudo labadda-status` and the printed backup name; restore only with the owner
   (`docs/RECOVERY.md`). Never delete data or rerun destructive steps to "get past" an error.

Setup B only: if PM's `deploy_all` ran later and LabAdda stopped answering, `sudo labadda-reattach-nginx`.
Windows test PCs (setup C) take the same zip: delete the old folder, unzip the new one (never on
top), then `scripts\windows\setup-dev.ps1` and `serve-dev.ps1`.
