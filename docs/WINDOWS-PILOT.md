# Offline Windows 11 pilot (Python 3.12, PostgreSQL 16)

This is a small, attended LAN pilot. Use the managed [Ubuntu deployment](DEPLOYMENT.md) for the
permanent office server. Download a source ZIP, PostgreSQL 16 Windows offline installer and
mkcert Windows executable on a connected machine, then transfer them through your approved
process. Python and npm packages come from your internal mirrors; no wheel bundle is needed.
No Git installation is required on Windows. Examples use fictional addresses.

## Prepare in VS Code PowerShell

Open the extracted repository folder. Install Python 3.12 and a supported Node release
(Node 24.15 or later for the current frontend test dependencies). Confirm your organisation's
pip/npm mirror configuration. Skip creating or installing anything that is already present.

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.lock
& .\.venv\Scripts\python.exe -m pip install --no-deps -e .\backend
& .\.venv\Scripts\python.exe -m pip check
npm --prefix frontend ci --no-audit --no-fund
npm --prefix frontend run build
New-Item -ItemType Directory -Force .\var\windows-pilot\assets
```

The lock file excludes Linux-only uvloop on Windows. The build needs no external runtime
assets. Install PostgreSQL **Database Server** and **Command Line Tools**; Stack Builder and
its internet downloads are optional. Retain the database password privately. Leave PostgreSQL
listening on localhost; colleagues connect to the website, not the database.

In PostgreSQL's SQL Shell, connect locally as postgres. Run these one at a time; `\password`
prompts without putting a password in SQL history:

```sql
CREATE ROLE labadda_win LOGIN;
\password labadda_win
CREATE DATABASE labadda_win OWNER labadda_win;
\q
```

## Configure this terminal

Create `var/windows-pilot.env` with the following **non-secret** settings; replace the sample
LAN IP, email domain and folder paths for your machine. Do not include comment lines when
using this simple loader. This file and all files under var stay outside version control.

```dotenv
LABADDA_ENV=pilot
LABADDA_INSTANCE=windows-pilot
LABADDA_BASE_PATH=
LABADDA_COOKIE_SECURE=true
LABADDA_COOKIE_NAME=labadda_windows_pilot
LABADDA_TRUSTED_ORIGINS=https://localhost:8100,https://10.20.30.40:8100
LABADDA_ASSET_DIR=C:/LabAdda/var/windows-pilot/assets
LABADDA_FRONTEND_DIST=C:/LabAdda/frontend/dist
LABADDA_TIMEZONE=Asia/Kolkata
LABADDA_EMAIL_DOMAIN=domain.xx.in
LABADDA_SMTP_HOST=
LABADDA_SMTP_FROM=admin.labadda@domain.xx.in
```

```powershell
Get-Content .\var\windows-pilot.env | ForEach-Object {
    $name, $value = $_ -split '=', 2
    [Environment]::SetEnvironmentVariable($name, $value, 'Process')
}
$DbSecret = Read-Host 'Password for labadda_win' -AsSecureString
$DbPlain = [System.Net.NetworkCredential]::new('', $DbSecret).Password
$DbEncoded = [uri]::EscapeDataString($DbPlain)
$env:LABADDA_DATABASE_URL = "postgresql+psycopg://labadda_win:${DbEncoded}@127.0.0.1:5432/labadda_win"
Remove-Variable DbPlain, DbEncoded, DbSecret
```

Do not replace `${DbEncoded}` with a password inside the braces: this is PowerShell variable
interpolation. Do not print the database URL or share terminal output containing activation
codes. Environment variables set here last only for this terminal and its child processes.

## HTTPS and first startup

Install mkcert's local CA once and create a certificate including the machine's current LAN
IP. The official executable releases are at <https://github.com/FiloSottile/mkcert/releases>.

```powershell
& 'C:\Tools\mkcert\mkcert.exe' -install
$LanIp = Read-Host 'Active adapter IPv4 address'
& 'C:\Tools\mkcert\mkcert.exe' -cert-file .\var\dev-cert.pem -key-file .\var\dev-key.pem localhost 127.0.0.1 $LanIp
& .\.venv\Scripts\python.exe -m labadda.cli migrate
& .\.venv\Scripts\python.exe -m labadda.cli create-admin localadmin --display-name 'Local Pilot Administrator'
& .\.venv\Scripts\python.exe -m labadda.cli serve --host 0.0.0.0 --port 8100 --ssl-certfile .\var\dev-cert.pem --ssl-keyfile .\var\dev-key.pem
```

`serve` selects the Windows selector event loop explicitly, including for HTTPS/WebSockets.
Keep this terminal running. Open `https://localhost:8100/activate`, enter the displayed
one-time code and choose a password. Create the organisation hierarchy, import staff, verify
home units and appoint stewards. With mail disabled, deliver activation codes individually
through your usual trusted channel; lost codes can be reissued from People.

In a separate **administrator PowerShell**, allow only local-subnet web access:

```powershell
New-NetFirewallRule -DisplayName 'LabAdda pilot HTTPS 8100' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8100 -Profile Private,Domain -RemoteAddress LocalSubnet
```

Check that the active network is Private or Domain. Colleagues open `https://YOUR-LAN-IP:8100`.
Install the **public** `rootCA.pem` from mkcert's `-CAROOT` directory in each client computer's
Trusted Root Certification Authorities store (Local Machine, using the certificate import
wizard). Verify the certificate with your administrator before trusting it. Never distribute
`rootCA-key.pem` or `dev-key.pem`. Browser exceptions may leave secure-context features
unavailable; install the CA instead. Reissue the server certificate if the IP changes.

## Stop, upgrade, preserve data

Use Ctrl+C once and allow shutdown to finish. If a process hangs, identify its PID by the
command line and stop only that LabAdda process, not every Python process. Confirm port 8100
is free before restarting. Do not run multiple servers against this native pilot at once.
The health page reports Windows inode capacity as **Unknown** while still measuring free
bytes: Windows does not provide the Linux inode counters. Do not invent healthy counters.

Before replacing a ZIP or running an upgrade, stop writes and make a PostgreSQL custom dump
with the matching PostgreSQL 16 `pg_dump.exe`, and copy the **entire asset directory** from
the same stopped point. Retain configuration separately and securely. Do not run `seed` or
`reset` on the pilot database. Preserve the source version alongside every backup.

For Windows → Ubuntu 24.04, use logical PostgreSQL dump/restore plus that complete asset tree;
keep the same IDs and database contents. Do not copy PostgreSQL's data directory, Windows
venv, node_modules or local TLS private keys. Build a Linux environment from the locked mirror
packages, restore into an isolated database, migrate once, and verify accounts, private/team
boards, notes, files, delegation and tasks before switching users. Record a successful test
restore using [the recovery procedure](RECOVERY.md). Linux managed site scripts intentionally
refuse operations when locking/deadline guarantees are unavailable on Windows.

This guide is source-reviewed and has simulated Windows regression coverage on Linux. Native
Windows restart, client certificate trust and office-network acceptance remain operator checks.
