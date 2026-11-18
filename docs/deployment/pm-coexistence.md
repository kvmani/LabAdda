# Living beside project_management_software (setup B)

LabAdda shares one Ubuntu 24.04 VM with **project_management_software** ("PM", also called IPMS or
Apex PM). Many contributors cannot open PM's repository, so this page records what LabAdda code must
know about it. These are facts from PM's repository (`deployment_bundle/` and its operations
guides, PM commit `afc50a9`, PM v1.9.0), not observations of the live server; re-check on the
server with the commands at the end before relying on a new assumption.

## PM on that server

| Item | PM | LabAdda must therefore |
| --- | --- | --- |
| nginx site | `/etc/nginx/sites-available/apex_pm`, enabled by symlink `sites-enabled/apex_pm`. One `server { listen 80 default_server; server_name _; }`, **plain HTTP, no port 443** | Add only its include line inside that server block, or use its own `server_name`/port; never a second `default_server` on 80 |
| Exact file | [pm-reference/apex_pm.active.conf](pm-reference/apex_pm.active.conf) (copied verbatim from PM) | Tests and `rehearse-rollout.sh --shared-http` use this file |
| nginx.conf | Ubuntu stock: `include /etc/nginx/conf.d/*.conf;` then `include /etc/nginx/sites-enabled/*;`, user `www-data` | Put http-context lines (`map`) in `conf.d/labadda-<site>.conf` |
| Routes | `/production/`, `/staging/`, `/chemistry/`: each with `api/`, `health/`, `docs`, `openapi.json`, `redoc` rewritten to a backend, and static files from `/var/www/apex_pm/<instance>/` | Use a prefix that is none of these: `/labadda` |
| Backend ports | 8000 production, 8001 staging, 8002 chemistry (127.0.0.1) | LabAdda 8100, restore test copy 8101; never 8000–8002 |
| Frontend preview ports | 4173–4175 (`npm preview`, staging) | Never use them |
| Services | systemd **user** units `ipms-<instance>-*.service`/`.timer` of the operator account (`<pm-account>`), env files `~/.config/ipms/` | LabAdda's user units are `labadda-<site>.service` and `labadda-backup@<site>.timer`: no name overlap |
| Data | `/srv/apex_pm/<instance>/` with SQLite, configs, attachments; websites `/var/www/apex_pm/` | `/srv/labadda/<site>/`, `/srv/labadda-backups/<site>/`, PostgreSQL `labadda_<site>` |
| Cookies | Per instance, `Path=/<instance>` (`PM_SESSION_COOKIE_PATH_MODE=base_path`) | `labadda_<site>` with `Path=/labadda`: neither app can read the other's session |
| Toolchain | Python 3.12 `.venv`, Node 18 / npm 9 from the Ubuntu mirror, internal pip/npm mirrors in `<pm-account>`'s config | Build with the same Node 18 and the same mirror settings |
| Upgrades | GitHub source zip + hash, `pm_upgrade.sh` / step-by-step skill, no git | Same model: `deploy/upgrade.sh --zip` |
| PM's own nginx tool | `pm_instance.py deploy_all` **rewrites `sites-available/apex_pm`** from PM's instance list and **deletes `sites-enabled/default`** | Expect the include line to vanish after a PM deploy: `labadda-reattach-nginx` restores it; never rely on Ubuntu's default site existing |

## What LabAdda may touch, and nothing else

1. `/etc/nginx/conf.d/labadda-<site>.conf` and `/etc/nginx/snippets/labadda-<site>.conf` (its own).
2. **One line** inside PM's server block: `include /etc/nginx/snippets/labadda-<site>.conf;`, added
   by `scripts/install_helpers.py attach-site` before the closing brace, after keeping the original
   as `/etc/labadda/<site>.shared-site.original`; `nginx -t` runs and any failure puts PM's file back
   byte for byte. Uninstall removes the line before the snippet. A file with more than one server
   block is refused (a person must place the line).
3. `systemctl reload nginx` — a reload, never a restart, so PM's connections are not dropped.
4. Its own PostgreSQL role and database. PM uses no PostgreSQL; never restart the cluster.

Never: edit PM's routes or `/var/www/apex_pm`, add `default_server`, rewrite cookie paths, touch
`~/.config/ipms`, PM's units or ports, or run PM's scripts. If a change needs any of these, stop and
ask the owner (AGENTS.md section 7).

## Re-checking on the server (read-only)

```bash
sudo nginx -T 2>/dev/null | grep -nE 'server_name|listen|include|location \^~ /'
ls -l /etc/nginx/sites-enabled/
ss -ltn '( sport = :8000 or sport = :8001 or sport = :8002 or sport = :8100 or sport = :8101 )'
systemctl --user list-units 'ipms-*' 'labadda*' --all --no-pager
```

If PM's file has changed shape (for example a second server block for HTTPS), update
`pm-reference/apex_pm.active.conf` from the server's file and this page in the same change, then run
`sudo scripts/rehearse-rollout.sh --zip <zip> --shared-http`.
