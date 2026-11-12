---
title: When the site is down
summary: Find out whether the service, the database, the certificate or a closed maintenance gate is the problem.
audience: operator
screen: none
updated: 2026-11-12
---

## What this is for

Use this page when people say they cannot reach LabAdda. Work from the top. Each step changes nothing, so you can do them all safely before you fix anything.

Replace `<site-name>` and `<tools>` with your own values.

## Before you start

- Ask one person exactly what they see: a browser warning, a blank page, a maintenance notice or a sign-in message. The answer narrows the search.
- Check whether an upgrade or backup is running or has just failed. A failed one leaves the site closed on purpose.

## Steps

1. Run the doctor and read the first line that fails. It says in plain words what is wrong and how to fix it:

   ```bash
   cd /srv/labadda/<site-name>/current/backend
   ../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/<site-name>.env
   ```

2. Ask the service whether it is running, and read its recent log:

   ```bash
   sudo systemctl status labadda-<site-name>
   sudo journalctl -u labadda-<site-name> --since "1 hour ago"
   ```

3. Probe the service directly, then through the public address:

   ```bash
   python3 <tools>/scripts/operations.py --site /etc/labadda/<site-name>.site.json probe --direct
   python3 <tools>/scripts/operations.py --site /etc/labadda/<site-name>.site.json probe --ca-file /etc/labadda/site-ca.crt
   ```

   If the first passes and the second fails, the problem is the web server or the certificate.
4. Check whether the maintenance gate is closed. A file named `maintenance` in the `traffic` folder of the site's root folder closes the site. Look, but do not remove it yet:

   ```bash
   ls -l /srv/labadda/<site-name>/traffic/
   ```

5. Check the disk. A full disk stops the database and the service:

   ```bash
   df -h
   ```

6. Fix the one thing you found, using the page for it, then run step 1 again.

## What happens next

When the doctor and both probes pass, open the site from another computer and sign in. Tell people it is back. Write down what happened for your records.

## If something goes wrong

- The gate is closed and you did not close it. A backup or upgrade did not finish. Read the log from step 2. Do not remove the file until the log shows why it was left and the site has been checked. Follow [Restoring from a backup](restore.md) if data may be at risk.
- The service will not start after a fix: keep its log and ask the supplier of the release before trying anything else.
- The disk is full: see [When the disk is filling up](disk-is-filling.md).
- Only the certificate is wrong: see [Renewing the site certificate](certificate-renewal.md).

## Related

- [Getting a status report](status-report.md)
- [Renewing the site certificate](certificate-renewal.md)
- [When the disk is filling up](disk-is-filling.md)
