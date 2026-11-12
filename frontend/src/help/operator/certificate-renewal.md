---
title: Renewing the site certificate
summary: Replace the certificate before it expires and check that people can still reach the site.
audience: operator
screen: none
updated: 2026-11-12
---

## What this is for

The site certificate lets browsers trust the address people type. When it expires, browsers warn people away from the site. The server's doctor and the Certificate card on the System health page warn you before that happens.

Replace `<site-name>` and `<tools>` with your own values. The certificate and key files are the ones named in the site description file as `tls_certificate` and `tls_key`.

## Before you start

- You have the new certificate from your organisation's certificate authority, and its private key if the key is new.
- Keep the key private. Never send it by email or chat.
- Keep a copy of the old certificate until the new one works.

## Steps

1. Put the new certificate at the path named by `tls_certificate`, and the key at the path named by `tls_key`, in `/etc/labadda/<site-name>.site.json`. Keep the key readable only by the web server's administrator account.
2. Ask the web server to test its settings. Continue only if it says the test is successful:

   ```bash
   sudo nginx -t
   ```

3. Tell the web server to use the new certificate without closing the site:

   ```bash
   sudo systemctl reload nginx
   ```

4. Check the site through its public address with your organisation's certificate authority file:

   ```bash
   python3 <tools>/scripts/operations.py --site /etc/labadda/<site-name>.site.json probe --ca-file /etc/labadda/site-ca.crt
   ```

5. Run the doctor. Its certificate line shows how long the new certificate is valid:

   ```bash
   cd /srv/labadda/<site-name>/current/backend
   ../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/<site-name>.env
   ```

## What happens next

People keep their sign-ins. Open the site in a browser from another computer to confirm there is no warning.

## If something goes wrong

- The web server's test fails: put the old certificate and key back, run the test again, and read the message. A certificate that does not match its key is the usual cause.
- The check says the certificate is not trusted: the certificate authority file may be missing or out of date on this computer.
- Browsers still warn about the old date: the web server was not reloaded. Run step 3 again.

## Related

- [Certificate problems](../troubleshooting/health-certificate.md)
- [When the site is down](site-is-down.md)
- [Getting a status report](status-report.md)
