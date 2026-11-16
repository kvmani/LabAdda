# Office pilot rollout — 16 November 2026

This is the execution guide for LabAdda **0.0.2-beta** on the Ubuntu **24.04** office server
already serving project_management_software (PM). The owner confirmed the OS on 15 November.
The office hostname, IP, SMTP relay and available resources remain operator inputs.
Do not install over an existing LabAdda instance: use the verified upgrade procedure instead.

## Decisions and shared-server boundaries

| Item | LabAdda pilot | Existing PM baseline to preserve |
| --- | --- | --- |
| Browser address | `https://labadda.domain.xx.in/` — replace domain | Existing `/production`, `/staging`, `/chemistry` routes |
| Backend | `127.0.0.1:8100`, one process | Backend ports 8000/8001/8002; frontend 4173/4174/4175 |
| Service | System unit `labadda-main.service`, Unix user `labadda` | Existing user units named `ipms-*` |
| Persistent root | `/srv/labadda/main` | `/srv/apex_pm/*` |
| Config | `/etc/labadda/main.env`, `main.site.json` | PM's per-instance `project_config.yml` and `env.sh` |
| Database and role | `labadda_main` on local PostgreSQL 16 | Existing PM data/config/venvs stay in place |
| Cookie | `labadda_main`, Secure, host-only, path `/` | Existing PM sessions |
| Backups | `/srv/labadda-backups/main`, separate off-host copy | Existing PM backup jobs |
| Nightly time | Proposed 03:40 IST, verify non-overlap | Record actual PM/host backup windows first |
| Mail sender | `admin.labadda@domain.xx.in` | Existing PM mail configuration |
| Mail recipient | `labadda-operators@domain.xx.in` — replace/approve | No copied PM recipient list |

Reference checked: `kvmani/project_management_software` at
`afc50a9871c1e8a0dedd94ae6ab825925a9083ec`, its production-baseline, air-gap,
service-admin and rollout documents and **sanitized** deployment examples. The documented PM
production baseline is v1.9.0 (`f8cd28a`). These are repository facts, not observations of the
live server. Do not copy PM's virtualenv, database, password, nginx default site or configuration.
Do not upgrade its OS, Python environment or PostgreSQL cluster as part of this rollout.

## Prepare before leaving the connected build machine

Use a clean committed checkout, Ubuntu 24.04 x86-64, Python 3.12, Node 22 and the locked development
requirements. Node is build-time only. The office server needs neither GitHub nor npm access.
A kit must match the target OS/version/architecture/Python; the verifier enforces this.

```bash
git pull --ff-only origin main
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
.venv/bin/pip install --no-deps -e backend
(cd frontend && npm ci)
# Disposable test databases are required; see README. Never point tests at office data.
LABADDA_RECOVERY_TESTS=1 scripts/verify.sh --e2e
.venv/bin/python scripts/check_advisories.py --output /tmp/labadda-advisory-report.json
scripts/make-release-bundle.sh /tmp/labadda-office-kit
```

The owner selected **mirror mode**: the bundle carries the prebuilt frontend, exact dependency
lock, licences, manifest, checksums and operator tools, **without Python wheels or OS packages**.
OS packages come from the signed internal Ubuntu mirror; Python packages come from the configured
internal Python mirror. The office server needs no public internet or npm. Before rollout, ensure
that mirror contains every entry in `backend/requirements.lock`, including the approved security
updates. Preserve certificate verification and the age/advisory checks. Do not use `--offline-kit`
with this mirror-mode bundle.

Copy the whole kit, this guide, the three office templates and the candidate validation report to
approved transfer media. Record the SHA256SUMS fingerprint separately, through a trusted channel.
Hashes on the same media alone do not establish who supplied it. Keep certificates/private keys
and actual passwords separate; these templates contain no real credentials.

## 1. Preflight on the office host — no changes yet

Record command output in a private operator log. Do not paste secret configs into a ticket/chat.
Confirm CPU architecture with `uname -m` (`x86_64` required for this kit), and review available RAM,
CPU, disk and PostgreSQL connections. Start with 5–10 volunteers in one or two workspaces.
Allow at least 15 GiB free for the pilot and its first backups; recalculate for actual uploads.
The app's health reserve alone is 5 GiB and the default per-user upload quota is 500 MiB.

```bash
cat /etc/os-release
uname -m
python3.12 --version
free -h
df -h /srv /var/lib/postgresql
ss -ltn '( sport = :8100 or sport = :8101 )'
systemctl list-timers --all
sudo nginx -t
sudo -u postgres psql -Atqc 'show server_version'
sudo -u postgres psql -Atqc 'show max_connections'
```

8100 and the temporary restore port 8101 must be free. LabAdda's SQLAlchemy pool can open up to
15 connections in its one process; retain headroom for PM, backups and administration.
Record the status of PM's actual user units as their owning account, and open its production,
staging and chemistry browser pages. Establish a known-good PM backup using its own runbook.
Do not run PM's destructive demos or reset commands.

Have IT create the LabAdda DNS record and certificate, confirm relay access from this host, and
ensure that the new hostname is not already owned by another nginx server block. Retain 80/443
as shared nginx listeners; **do not expose 8100/8101 to the LAN**. Keep existing firewall rules.
If OS packages are missing, ask the host administrator to review apt's proposed changes first:

```bash
sudo apt-get update
sudo apt-get -s install --no-install-recommends postgresql-16 postgresql-client-16 nginx python3.12-venv openssl ca-certificates
# Proceed only after checking this does not upgrade/restart PM's existing database or proxy unexpectedly.
sudo apt-get install --no-install-recommends postgresql-16 postgresql-client-16 nginx python3.12-venv openssl ca-certificates
```

Do not restart a shared PostgreSQL cluster just to install LabAdda. Stop if the existing database
major version is incompatible; schedule a separate infrastructure decision.

## 2. Fill configuration and verify the transferred kit

From the transferred kit folder, prepare private editable copies first:

```bash
sudo install -d -m 0700 /root/labadda-rollout
sudo install -m 0600 office-pilot/install.conf.example /root/labadda-rollout/labadda-install.conf
sudo install -m 0644 office-pilot/backup-schedule.conf.example /root/labadda-rollout/backup-schedule.conf
sudoedit /root/labadda-rollout/labadda-install.conf
sudoedit /root/labadda-rollout/backup-schedule.conf
```

Place the approved `labadda.crt`, `labadda.key` and `office-ca.crt` in that directory; keep the
private key mode 0600. These files come from IT, not this repository. Copy [install answers](../deploy/office-pilot/install.conf.example) to a private working directory,
replace every `domain.xx.in`, and choose the first administrator's actual display name.
The [runtime reference](../deploy/office-pilot/main.env.example) shows the generated values and all
supported main settings. The installer generates a random DB password; do not deploy that reference
file literally. It writes the real env file mode 0600 and secret files outside the release.

Mail defaults are provisional: **port 25, STARTTLS false, no authentication**, matching PM's sanitized
example. Replace the relay host at rollout. Confirm these with IT; set `SMTP_STARTTLS=true` if required,
and `SMTP_USER` if authentication is required. The installer prompts privately for that password and
stores it in a service-readable 0400 file. Never put it in the answers file or command history.

LabAdda mail currently delivers **user-submitted feedback**, including its selected attachments.
It does not send automatic infrastructure-health alerts or all in-app notifications. Use the
existing office monitoring system and this runbook's status checks for health and backup failures.
Reserve the chosen sender with IT; mail configuration does not create the mailbox or relay rule.

```bash
chmod 0600 /root/labadda-rollout/labadda-install.conf
cd /media/transfer/labadda-0.0.2-beta-bundle
sha256sum SHA256SUMS
sha256sum -c SHA256SUMS
python3.12 tools/scripts/kit.py verify .
```

Compare the fingerprint to the separately recorded value. Stop on any mismatch. Have the internal
CA trusted by the server and pilot browsers. If it is not already trusted, the host administrator can
install the **approved public CA certificate**, never the server's private key:

```bash
sudo install -m 0644 /root/labadda-rollout/office-ca.crt /usr/local/share/ca-certificates/labadda-office-ca.crt
sudo update-ca-certificates
```

## 3. Rehearse the plan, then install

Use a dedicated hostname and a CA-issued certificate. Avoid the installer's self-signed fallback
for real users. `--skip-os-packages` makes missing OS prerequisites fail instead of changing the host. Python pins are installed from PIP_INDEX_URL in the answers file.
`--no-timer` lets you review backup timing before enabling it. Installer scripts preserve unrelated
nginx files and refuse an occupied new-instance port. Keep the whole terminal transcript private:
the first administrator activation code is printed once.

```bash
sudo bash install.sh --site main --answers /root/labadda-rollout/labadda-install.conf \
  --skip-os-packages --no-timer --cert /root/labadda-rollout/labadda.crt --key /root/labadda-rollout/labadda.key \
  --ca-file /root/labadda-rollout/office-ca.crt --kit-fingerprint REPLACE_WITH_RECORDED_64_HEX_DIGEST --dry-run
# Review output, then repeat without --dry-run; interactive administrator details may be requested.
sudo bash install.sh --site main --answers /root/labadda-rollout/labadda-install.conf \
  --skip-os-packages --no-timer --cert /root/labadda-rollout/labadda.crt --key /root/labadda-rollout/labadda.key \
  --ca-file /root/labadda-rollout/office-ca.crt --kit-fingerprint REPLACE_WITH_RECORDED_64_HEX_DIGEST
sudo labadda-status --site main
sudo nginx -t
sudo systemctl status labadda-main --no-pager
```

The installer must complete the first verified backup and doctor checks. A failure is a failed
commissioning gate, even if the service is running. Review `journalctl -u labadda-main` locally;
logs should contain event codes/metadata, not private user content. Do not reset a failed install.
Completed steps can be retried, but never remove existing data to force initialization.

## 4. Configure the backup window and optional resource budget

Choose a window that does not overlap PM/host backups. The default is 02:30 **host time** with
random delay; the template explicitly uses 03:40 Asia/Kolkata. Backups close LabAdda briefly.
The service-limits template is optional and requires headroom review: a hard memory cap can stop
LabAdda if exceeded. Keep PostgreSQL and nginx outside these LabAdda-only limits.

```bash
sudo install -d /etc/systemd/system/labadda-backup@main.timer.d
sudo install -m 0644 /root/labadda-rollout/backup-schedule.conf /etc/systemd/system/labadda-backup@main.timer.d/office-schedule.conf
sudo systemctl daemon-reload
sudo systemctl enable --now labadda-backup@main.timer
systemctl list-timers labadda-backup@main.timer
```

If the reviewed [service budget](../deploy/office-pilot/service-limits.conf.example) is appropriate,
install it as `/etc/systemd/system/labadda-main.service.d/office-limits.conf`, daemon-reload and
restart **only LabAdda**. Recheck its health and PM afterwards. Leave it unapplied if host sizing is
uncertain and supervise resource usage during the first pilot session.

## 5. Acceptance before inviting real users

Complete these gates with two non-admin pilot accounts and a separate administrator account.
Record pass/fail, time, operator, release version/commit and actual settings in a private site record.
Use fictional test content first; introduce the approved small real-data set only after all pass.

- The CA is trusted and HTTPS has no browser warning. `/healthz` and `/readyz` answer correctly.
- PM's production/staging/chemistry URLs and existing units remain healthy after nginx reload.
- Create units, nominate stewards and activate the two pilot users. Do not run `seed` on the pilot.
- Test noticeboard, attachment upload/download, chat/thread, task assignment and private notes.
- Test two private board tabs: drawing/sticky save, switch, reload, and another user's isolation.
- Test two shared board tabs, live updates in two browsers, note editing, and a secondary restore.
- Test a calendar event, edit conflict in two browsers and cancellation. It retains its server record.
- Administrator-without-membership cannot open private content. Site administration alone is no grant.
- Send one clearly labelled feedback test. Verify sender, recipient and delivery at the actual inbox;
  check the administrator feedback screen/outbox. A configuration/doctor pass alone is not mail delivery.
- Take a new verified backup, copy it off-host, then perform the isolated restore drill below.
- Reboot only in an agreed host window: PM shares this machine. Otherwise test LabAdda unit restart
  and schedule the host-boot acceptance with the PM operator. Confirm the backup timer is enabled.

```bash
curl --fail https://labadda.domain.xx.in/healthz
curl --fail https://labadda.domain.xx.in/readyz
sudo labadda-backup-now --site main --copy-to /mnt/approved-offhost/labadda
sudo labadda-status --site main
```

The off-host location must actually be a mounted remote filesystem or removable device, not merely
a different directory on the same disk. The copy command verifies all files against the original
trusted manifest digest. Keep dumps/assets and operator logs under access control: backups contain
all content. Nightly backup gives up to 24 hours' data-loss exposure; agree that RPO with the pilot
owner. Measure restore duration for RTO; no unmeasured recovery-time guarantee is made.

## 6. Restore drill and rollback

Use a **new disposable name**, own database, Unix identity, folders and loopback port. The restore
helper disables feedback mail and all background scheduling before it starts the test service.
It does not create a second public nginx route. This is a DB/assets/loopback restore rehearsal;
the original hostname's HTTPS checks do not qualify a separate restored browser site.

```bash
# Run from the verified kit; substitute the off-host backup folder and its separately recorded digest.
sudo bash restore.sh --site main --test-site mainrestore --port 8101 \
  --bundle /mnt/approved-offhost/labadda/BACKUP_FOLDER --manifest-sha256 RECORDED_MANIFEST_DIGEST --dry-run
sudo bash restore.sh --site main --test-site mainrestore --port 8101 \
  --bundle /mnt/approved-offhost/labadda/BACKUP_FOLDER --manifest-sha256 RECORDED_MANIFEST_DIGEST
curl --fail http://127.0.0.1:8101/readyz
# Confirm the restored DB/assets/metadata and revoked old credentials; record the measured duration.
sudo bash restore.sh --site main --test-site mainrestore --remove-test
```

Removal is allowed only with a matching provenance marker created after a successful drill install.
A failed/partial drill retains its files and refuses automatic removal: use a fresh name, or have the
operator review and clean up that exact disposable target. Never label an existing site disposable.

Before onboarding, rollback can simply close LabAdda and stop its service; retain all its files and
DB for investigation. Leave PM alone. After content exists, never rewind the DB silently. Upgrade
via the next unique-version kit and `upgrade.sh`; it backs up before migration. This release adds
migrations 0043–0046; downgrades refuse retained calendar/atomic-edit history. A pre-upgrade backup
must be restored into a new isolated target for rollback across an incompatible schema. See
[recovery](RECOVERY.md) and [release lifecycle](RELEASES.md). Do not delete `/srv/labadda` or drop the
production DB to undo an application change.

## First day and limits

Check `labadda-status`, system health, free space, feedback failures and PM health before opening,
after the first session and before leaving. Nominate an operator and a deputy. Keep invitations
limited, record defects and pause the pilot on private-data exposure, lost edits, failed verified
backup, resource pressure on PM, or repeated failed sign-ins.

Personal image upload is unavailable; personal boards support drawing, text and sticky notes.
Touch-panel pairing and task references use the first shared board; secondary-board controls say so.
Calendar cancellation retains data, and stale edits need reopening/review. This is a supervised beta,
not a complete v1.0 release or an official records/approval system. Use only the real-data classes
approved by the pilot owner; the existing app guidance excludes sensitive and official records.
