# Testing LabAdda on Windows

Use this to try LabAdda on a Windows 10/11 PC with **fictional fixture data only**. The office
server is Ubuntu 24.04; Windows is a test copy, never a place for real data, backups or the
offline kit. Installer, backup, restore and nginx scripts (`deploy/`, `scripts/*.sh`) are
Ubuntu-only and are not run on Windows.

## Install once

1. Python 3.12 (python.org installer, tick **py launcher**), Node 22 LTS, PostgreSQL 16 for
   Windows (EDB installer; remember the `postgres` password), and Git for Windows only if you clone.
2. Unzip the release's **Source code (zip)** (or clone the repository; its `.gitattributes`
   keeps Unix line endings, which the Ubuntu scripts and the format checks need).
3. In **SQL Shell (psql)** signed in as `postgres`, create the disposable databases:

```sql
create role labadda login password 'labadda-dev' createdb;
create database labadda_dev owner labadda;
create database labadda_test owner labadda;
```

4. In PowerShell, from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\setup-dev.ps1
```

The script creates `.venv`, installs the locked packages (on Windows the lock swaps `uvloop`,
which has no Windows build, for the standard event loop, and adds `tzdata`, because Windows has no
built-in time-zone database), builds the frontend, migrates and loads the fixture.

Packages come from your internal mirrors through your own settings, as for any other project on
that PC: `%APPDATA%\pip\pip.ini` (`[global]` `index-url = …`) and `%USERPROFILE%\.npmrc`
(`registry=…`). The locked versions are all at least 30 days old, so a mirror a few days behind
still has them.

## Update to a new release (zip only, no git)

1. Stop the server (Ctrl+C) and delete the old folder; then unzip the release's **Source code
   (zip)**. Do **not** unzip on top of the old folder: files removed in the new release (for
   example a replaced database migration) would stay behind and can stop the server starting.
   Keeping `.venv` or `frontend\node_modules` gains nothing: a moved `.venv` still points at the
   old folder, and `npm ci` replaces `node_modules` anyway.
2. Run `scripts\windows\setup-dev.ps1` (it recreates `.venv` and `node_modules` from your mirrors,
   builds the screens, migrates and reloads the fictional data), then `scripts\windows\serve-dev.ps1`.

## Run and sign in

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\serve-dev.ps1
```

Open <http://127.0.0.1:8000/>. Fixture accounts and their roles are listed in the
[README](../../README.md#run-locally-development-fictional-data); the password is
`fixture-pass-123`. To reload clean data, run the setup script again (it erases `labadda_dev`).

To try the prefixed layout used behind a proxy, set `$env:LABADDA_BASE_PATH="/labadda"` and a
distinct `$env:LABADDA_COOKIE_NAME` before starting, then open `http://127.0.0.1:8000/labadda/`.

## Run the checks

```powershell
.venv\Scripts\ruff.exe format --config backend\pyproject.toml --check backend scripts e2e
cd backend; ..\.venv\Scripts\python.exe -m pytest tests\test_policy.py -q; cd ..
cd frontend; npm run lint; npm run typecheck; npx vitest run; cd ..
```

The full gate `scripts/verify.sh` is a bash script; run it on Ubuntu (or WSL 2) before a release.
Tests that drive the Ubuntu installer or recovery shell scripts need bash and are expected to
fail on native Windows.

## Known differences on Windows

- Disk space is read with the Windows free-space call. Windows has no file-slot (inode) count,
  so the file-slot part of the storage health check always reads as plenty free. Do not judge
  storage health from a Windows copy.
- File-system hardening that relies on POSIX flags (no-follow, directory sync) is skipped. This
  is acceptable for a test copy and is the reason real data stays on Ubuntu.
