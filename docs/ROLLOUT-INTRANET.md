# Intranet rollout checklist (pilot)

For the person who puts LabAdda on the office server and looks after it. Plain steps, in order.
Every command is typed on the server unless a step says "build machine". Names such as
`labadda.lab.example.in` and `Asia/Kolkata` are examples: use your own. Never paste real
passwords, activation codes or addresses into tickets or chat.

The kit is one folder, `labadda-<version>-offline-kit`, that you carry on a USB drive. It holds the
application, every Python package, the operating-system packages (PostgreSQL 16, nginx, python3.12-venv)
and the install scripts. The server never needs internet. Background rules: [deployment](DEPLOYMENT.md),
[recovery](RECOVERY.md), [pilot runbook](PILOT-RUNBOOK.md).

## 1. Before the day

| Decide or get | Detail |
| --- | --- |
| Server | One Ubuntu **24.04 LTS** x86-64 virtual machine. Start with 4 processors, 8 GB memory, 100 GB disk (not measured on your site). Fresh install is best. |
| Name | A hostname on the intranet that points to the server (ask the network team to add it to the internal DNS), for example `labadda.lab.example.in`. |
| Certificate | A certificate file and key from your internal authority for that hostname. For the pilot you may skip this: the installer makes a self-signed one and browsers show a warning until you trust it. |
| Firewall | Allow only **443/tcp** from the office network (plus 22/tcp for your own administration). Nothing else is needed; the app listens on the server itself only. |
| Mail | The relay host and port, and an administrator feedback address. This release does not send e-mail; the installer records the answers for a later release. |
| People | Two administrators (a person and a deputy), and one person who runs the daily check. |
| Off-server copy | A second USB drive or network folder for backups, kept in a locked place. |

## 2. Build the kit (connected build machine)

Needs Ubuntu 24.04 x86-64, Node 22, `dpkg-dev`, and the Python environment from the [README](../README.md)
(`.venv`). Use a clean, committed checkout of the commit you mean to ship.

```bash
sudo apt-get install -y dpkg-dev
scripts/make-offline-kit.sh ~/kits
```

Expected: the last lines say `kit verify: OK`, `Kit ready: .../labadda-<version>-offline-kit` and a
**kit fingerprint**. Write the fingerprint on paper. The version comes from the code
(`backend/labadda/__init__.py`), so the folder name and the version on the login page agree.
If a step fails the script stops and says which; nothing half-built is left behind.

Check it again at any time: `python3.12 scripts/kit.py verify ~/kits/labadda-<version>-offline-kit`.

## 3. Carry it in

1. Copy the whole folder to a USB drive formatted ext4 or exFAT.
2. On the server, copy it to local disk (for example `/root/kit`) and run `cd /root/kit/labadda-<version>-offline-kit`.
3. Check it: `sha256sum SHA256SUMS`. The first characters must equal the fingerprint on your paper.
   If they differ, do not install: copy again from the original.

## 4. Install

```bash
sudo bash install.sh --dry-run        # shows the plan, changes nothing
sudo bash install.sh                  # the real install
```

Add `--cert /path/server.crt --key /path/server.key` to use your certificate, and
`--kit-fingerprint <paper value>` to let the script compare it for you. It asks only:
site name, server hostname, time zone (default `Asia/Kolkata`), e-mail domain, feedback address,
mail relay, then the **first administrator's** username and full name.
For several servers, put the answers in a file and use `--answers file --yes`.

What it does, and says as it goes (each step prints `OK:`): checks Ubuntu 24.04 and free disk, checks
every kit file, installs the operating-system packages from the kit, creates the `labadda` service
account and folders under `/srv/labadda/main`, creates the PostgreSQL login and database with a generated
password (kept in `/etc/labadda/secrets/`, root only), writes `/etc/labadda/main.env` (never overwritten),
installs the release with `pip --no-index`, makes or installs the certificate, installs the service, nightly
backup timer and nginx site, creates the database tables, makes the first administrator, starts everything,
checks health locally and over `https://<hostname>`, takes the **first backup** and runs `labadda doctor`.

The activation code for the first administrator is printed **once**. Give it privately to that person.

If a step fails the message starts with `STOPPED:` and says what to fix. Fix it and run the same command
again: finished steps are recognised and skipped. Do not delete folders by hand.

## 5. First sign-in

1. On an office computer open `https://<hostname>/activate`, enter the activation code and choose a password.
2. Self-signed pilot certificate: the browser warns once. Ask the network team to trust `/etc/ssl/labadda/server.crt`
   on office computers; do not train staff to click through warnings.
3. Run `sudo labadda-status`. Expected: version, `labadda active`, `nginx active`, app `ready`, web address `answers`,
   last backup `success` a few minutes ago.

## 6. First-day administrator steps

Sign in, open **Administration**, then **Help for administrators** (`/admin/help/setup`). The setup checklist
reads the real state, so it cannot be ticked by hand. In order:

1. People, **Add a person**: create the second administrator.
2. Organisation chart: create the units; note each unit's code.
3. People, **Import staff list**: save the Excel sheet as CSV UTF-8, check the report, give a reason, apply, print the activation slips.
4. Make sure every unit has a steward or head.
5. Confirm **Backups** shows the first backup, and the time zone line is done.
6. Send a **broadcast message** to everyone: a short welcome and who to ask for help.

## 7. Daily checks (two minutes)

```bash
sudo labadda-status
```

Everything `active` and `ready`, last backup under 26 hours old and `success`, disk not above about 80 %.
Once a week also run the doctor and read any line that is not fine:

```bash
cd /srv/labadda/main/current/backend && sudo ../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/main.env
```

## 8. Backups and the off-server copy

The server backs itself up every night at about 02:30 (the site is closed for a few minutes) and keeps seven.
A backup that only lives on the server is not safe. At least weekly, with the second drive plugged in:

```bash
sudo labadda-backup-now --copy-to /media/offsite/labadda-backups
```

It takes a new verified backup, copies it and checks the copy, then prints the **manifest digest**. Write the digest
in your log next to the date; a restore needs it. Backups contain all content: keep the drive locked away.

## 9. Restore

Always restore into a separate test copy first. From the kit folder:

```bash
sudo bash restore.sh --bundle /srv/labadda-backups/main/<backup-folder> --manifest-sha256 <digest> --test-site mainrestore
```

It creates a second site (own database and folders, port 8101, not on the web) from the backup. Look at it
with an administrator, then remove it: `sudo bash restore.sh --remove-test --test-site mainrestore`.
**Whole server lost:** install the kit on the new server with
`sudo bash install.sh --restore-bundle <folder> --manifest-sha256 <digest>`; accounts and content come from the backup.
Practise the test restore once before the pilot starts and record the time it took.

## 10. Upgrade with a new kit

1. Build the new kit (section 2); carry it in and check the fingerprint (section 3).
2. Tell people; choose a quiet time. Run `sudo bash upgrade.sh --dry-run`, then `sudo bash upgrade.sh`.
3. It installs the new files next to the old, takes a verified backup, closes the site, migrates, switches, restarts, checks
   health, reopens and runs the doctor. Expected last lines: `now running <version>; the site is open again`.

## 11. If an upgrade fails, and rollback

The script decides for you. If nothing had changed, or the database layout is the same in both versions, it puts
the old version back by itself and says `ROLLED BACK AUTOMATICALLY`. Otherwise it leaves the site **closed** (so
nothing is lost), names the backup it took just before, and stops. Then:

1. Run `sudo labadda-status` and the doctor; send both (section 12).
2. Do not retry the upgrade. To go back to the old version, restore that backup on a new test copy (section 9),
   check it, and plan the switch with the developer.

## 12. What to send back if something breaks

```bash
sudo labadda-status > status.txt
cd /srv/labadda/main/current/backend && sudo ../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/main.env > doctor.txt
```

Neither file contains passwords or content. Add the exact message that began with `STOPPED:` and what you were doing.

## 13. Taking it out of service

`sudo bash uninstall-keep-data.sh` stops and removes the service, timer and web site but keeps the database,
uploaded files, backups and settings. Running `install.sh` again brings the site back.

## What has been rehearsed

The kit builder, `install.sh` (dry run and real), status, a second install run, backup with copy, test restore,
upgrade and uninstall were rehearsed end to end on a scratch Ubuntu 24.04 machine with a real nginx and PostgreSQL
(`scripts/rehearse-rollout.sh`). Not rehearsed there, so watch them on the real server: real systemd (enable at boot,
timer firing), your real certificate in browsers, installing the operating-system packages on a blank server, and
the firewall. See the [pilot runbook](PILOT-RUNBOOK.md) for acceptance limits.
