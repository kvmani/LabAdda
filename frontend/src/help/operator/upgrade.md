---
title: Upgrading to a new release
summary: Install a new release beside the old one, preview the upgrade, and apply it in a quiet period.
audience: operator
screen: none
updated: 2026-11-12
---

## What this is for

An upgrade replaces the running release with a newer one. The tool takes a verified backup first, changes the site, checks it, and reopens it. Plan for the site to be unavailable for a few minutes, longer on a large site.

Replace `<site-name>`, `<tools>`, `<version>`, `<old-version>`, `<old-schema>` and `<trusted-digest>` with your own values. Every tool shows a plan first and changes nothing until you add `--apply`.

## Before you start

- You have the new release archive and a checksum that reached you separately from the archive.
- You know the version and database schema number you are running now. The preview shows what the tool found; if they differ from what you expected, stop and find out why.
- Choose a quiet time and tell people when the site will be unavailable.
- Make sure no other LabAdda job is running at that time, such as a manual backup or a reminder run.

## Steps

1. Check the archive and install it beside the old release. Nothing changes for users yet:

   ```bash
   python3.12 <tools>/scripts/release.py verify labadda-<version>.tar.gz --sha256 <trusted-digest>
   python3.12 <tools>/scripts/release.py install labadda-<version>.tar.gz \
     --sha256 <trusted-digest> --instance /srv/labadda/<site-name>
   ```

2. Preview the upgrade. This takes no action and prints the plan:

   ```bash
   python3 <tools>/scripts/lifecycle.py --site /etc/labadda/<site-name>.site.json upgrade \
     --expected-current <old-version> --expected-schema <old-schema> --candidate <version>
   ```

3. Read the plan. When it matches what you expect, run the same command again with the two extra options that apply it. They are your promise that nothing else is writing to the site:

   ```bash
   python3 <tools>/scripts/lifecycle.py --site /etc/labadda/<site-name>.site.json upgrade \
     --expected-current <old-version> --expected-schema <old-schema> --candidate <version> \
     --apply --external-writers-stopped
   ```

4. When it finishes, run the doctor from the new release, then open the site and sign in:

   ```bash
   cd /srv/labadda/<site-name>/current/backend
   ../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/<site-name>.env
   ```

## What happens next

The tool puts the site into maintenance, takes a verified backup, applies the update, restarts the service, checks the site and reopens it. People see a short maintenance notice in between. Afterwards, keep the old release folder until you are sure you will not need it.

## If something goes wrong

- The tool says the current release or schema is not what you gave it. Someone changed the site since you wrote your plan. Read the live values, then start again from the preview.
- The upgrade stops part-way. The site stays in maintenance on purpose. Do not run the command again and do not delete anything. Keep the tool's output, then follow [Restoring from a backup](restore.md) and ask the supplier of the release for advice.
- The site is closed after a successful upgrade. See [When the site is down](site-is-down.md).

## Related

- [Taking and checking backups](backup.md)
- [Restoring from a backup](restore.md)
- [When the site is down](site-is-down.md)
