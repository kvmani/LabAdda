---
title: Getting a status report
summary: Collect a short, safe summary of how the site is doing to read yourself or send to the supplier.
audience: operator
screen: none
updated: 2026-11-12
---

## What this is for

A status report tells you in one place whether the settings, database, files, service, address, certificate, backups and time zone are all in order. It contains no passwords, no message text and no file names, so you can share it with the people helping you.

Replace `<site-name>` and `<tools>` with your own values.

## Before you start

You need to be signed in to the server as the operator account. Running a report changes nothing and does not interrupt anyone.

## Steps

1. Run the doctor for a report you can read. Each line says what was checked, whether it is fine, and how to fix a problem:

   ```bash
   cd /srv/labadda/<site-name>/current/backend
   ../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/<site-name>.env
   ```

2. For a version a program or a support person can read, add the option for a machine-readable report:

   ```bash
   ../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/<site-name>.env --json
   ```

3. Check the public address and the service:

   ```bash
   python3 <tools>/scripts/operations.py --site /etc/labadda/<site-name>.site.json probe --direct
   ```

4. Ask an administrator to open **System health** and **Backups** in Administration and tell you the words shown on each. They show times, sizes and results only.
5. When you send the report to someone, add the date, the release you are running and what people are noticing. Leave out addresses, passwords and activation codes.

## What happens next

The doctor ends with a pass when nothing failed and with a failure otherwise. Fix problems from the top and run it again. A line marked as skipped was not applicable or was blocked by an earlier problem.

## If something goes wrong

- The doctor cannot read the settings: check the path after the env-file option and that you may read that file. It names only the setting that is wrong, never its value.
- The backup line fails on a new site: no backup exists yet. See [Taking and checking backups](backup.md).
- A line fails and you do not understand the advice: send the report to the supplier of the release.

## Related

- [When the site is down](site-is-down.md)
- [Reading system health](../admin/system-health.md)
- [Taking and checking backups](backup.md)
