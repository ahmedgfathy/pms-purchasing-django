# 12 · Deployment — `cb.alma.local` behind nginx + gunicorn

This is the production-ish setup that serves the app when you open
**http://cb.alma.local**. It was built on 2026-09-26 by replacing the old
React/Node app that used to live on that name. Everything below is a record of
what exists, why, and how to change it — written so an agent (or a human) who
has never seen this machine can take over.

---

## 1. What serves the name today

```
browser (Windows)
   │   cb.alma.local  →  127.0.0.1   (hosts file, both OSes)
   ▼
nginx 1.26.3 :80           /etc/nginx/conf.d/cb.alma.local.conf
   ├── /static/*  → alias  ~/pms-purchasing-django/staticfiles/   (direct)
   ├── /media/*   → alias  ~/pms-purchasing-django/media/         (direct)
   └── /*         → proxy_pass http://127.0.0.1:8001
                          ▼
gunicorn (systemd: pms-purchasing.service)  3 workers, 127.0.0.1:8001
   └── config.wsgi:application → Django 6.1 → PostgreSQL 16 (127.0.0.1:5432)
                                  └── LDAP (optional) → 10.51.0.20:389
```

| Component | Value |
| --- | --- |
| Distro | AlmaLinux 10.2 running **inside WSL2** (kernel `6.18.33.2-microsoft-standard-WSL2`), WSL distro name `AlmaLinux-10` |
| Hostname | `almalinux`, user `xinreal` (uid 1000) |
| Web server | nginx 1.26.3 (`systemctl {start,stop,restart} nginx`) |
| App server | gunicorn 26.2.0, 3 sync workers, `--timeout 60`, bound to `127.0.0.1:8001` |
| Framework | Django 6.1.1, venv `.venv` (Python 3.12.14) |
| Database | PostgreSQL 16.15 on `127.0.0.1:5432`, db `pms_purchasing`, role `xinreal` |
| Static | `staticfiles/` (git-ignored), collected by `ExecStartPost` on every service start |
| App logs | `/var/log/pms-purchasing/access.log`, `/var/log/pms-purchasing/error.log` |
| nginx logs | `/var/log/nginx/{access,error}.log` (root-readable only) |
| Auth | local `admin` always works; employees authenticate against AD `10.51.0.20:389` |

**Ports:** `80` nginx · `8001` gunicorn · `5432` PostgreSQL · `3000` the *old*
Node app (now stopped). Port `8000` belongs to a different project — never use it.

**Name resolution:** `cb.alma.local` → `127.0.0.1` in
`C:\Windows\System32\drivers\etc\hosts` (Windows) and it resolves in WSL too.
Because it points at loopback, only this machine can reach the app. There is
**no DNS server and no TLS** — plain HTTP on port 80.

---

## 2. Files that define the deployment

| File | Role |
| --- | --- |
| `/etc/nginx/conf.d/cb.alma.local.conf` | the vhost (source copy: `~/deploy/nginx-cb.alma.local.conf`) |
| `/etc/systemd/system/pms-purchasing.service` | the app service (source copy: `~/deploy/pms-purchasing.service`) |
| `~/deploy/README.md` | one-page ops + rollback cheat sheet |
| `~/deploy/check-ad.sh` | is Active Directory reachable? (ping + TCP 389 + DNS) |
| `~/deploy/test-login.ps1` | end-to-end login test run **from Windows** |
| `~/deploy-backup/` | pre-change copies of `.env` and the old vhost |
| `~/pms-purchasing-django/.env` | secrets (git-ignored) |

The systemd unit in full:

```ini
[Unit]
Description=PMS Purchasing Django application (gunicorn on 127.0.0.1:8001)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=xinreal
Group=xinreal
WorkingDirectory=/home/xinreal/pms-purchasing-django
ExecStart=/home/xinreal/pms-purchasing-django/.venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8001 \
    --timeout 60 \
    --access-logfile /var/log/pms-purchasing/access.log \
    --error-logfile /var/log/pms-purchasing/error.log \
    config.wsgi:application
# Refresh the collected static assets nginx serves from staticfiles/
ExecStartPost=/home/xinreal/pms-purchasing-django/.venv/bin/python \
    /home/xinreal/pms-purchasing-django/manage.py collectstatic --noinput
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Why `ExecStartPost`: nginx serves `staticfiles/` from disk, so a CSS/template
edit is invisible until `collectstatic` runs. Putting it in the unit means
**"restart the service" is always the fix** — nobody has to remember the step.

The vhost in full:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name cb.alma.local;

    client_max_body_size 64m;

    location /static/ {
        alias /home/xinreal/pms-purchasing-django/staticfiles/;
        access_log off;
        expires 7d;
        add_header Cache-Control "public";
    }

    location /media/ {
        alias /home/xinreal/pms-purchasing-django/media/;
        access_log off;
        expires 7d;
        add_header Cache-Control "public";
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

`proxy_set_header Host $host` is mandatory — Django validates `ALLOWED_HOSTS`
against it, and CSRF checks the `Origin`/`Referer` against
`CSRF_TRUSTED_ORIGINS`.

### Supporting changes outside the two config files

* `.env` → `DJANGO_ALLOWED_HOSTS=cb.alma.local,localhost,127.0.0.1` and
  `CSRF_TRUSTED_ORIGINS=...,http://cb.alma.local`.
* `chmod o+x /home/xinreal` — the home directory was `0700`, so the `nginx`
  user could not traverse into `staticfiles/`. Only the execute bit was added;
  directory contents stay unreadable.
* `mkdir /var/log/pms-purchasing && chown xinreal:xinreal` — gunicorn runs as
  `xinreal` and cannot write to `/var/log`.
* `systemctl enable pms-purchasing` (survives reboot).

---

## 3. Day-2 operations

```bash
sudo systemctl restart pms-purchasing      # restart the app (also re-collects static)
sudo systemctl status  pms-purchasing
sudo systemctl stop|start|restart nginx
sudo systemctl status  cb                  # the OLD app — must stay inactive/disabled
sudo systemctl daemon-reload               # after editing the unit file

journalctl -u pms-purchasing -n 100 --no-pager
tail -f /var/log/pms-purchasing/error.log
tail -f /var/log/nginx/access.log

# quick smoke test
curl -sI http://cb.alma.local/en/login/ | head -1     # HTTP/1.1 200
curl -sI http://cb.alma.local/static/css/style.css | head -1
```

Re-apply the config from the source copies (idempotent):

```bash
sudo cp ~/deploy/pms-purchasing.service /etc/systemd/system/
sudo cp ~/deploy/nginx-cb.alma.local.conf /etc/nginx/conf.d/cb.alma.local.conf
sudo nginx -t && sudo systemctl daemon-reload && sudo systemctl restart pms-purchasing nginx
```

After changing any user-visible string in templates/Python:

```bash
.venv/bin/python manage.py makemessages -l ar
# fill msgstr
.venv/bin/python manage.py compilemessages
sudo systemctl restart pms-purchasing       # or: collectstatic + restart
```

---

## 4. Incident log

### 4.1 2026-09-26 — the switch from React to Django

The name `cb.alma.local` used to proxy to `127.0.0.1:3000`, running
`~/cb/server.js` under a unit called `cb.service` (Node 22, "CB Task Board").
That was replaced by the Django app. The old unit was **stopped and disabled**
but nothing was deleted — `~/cb` is intact, so a rollback is a two-command
operation (see §6). `systemctl is-enabled cb` must read `disabled`.

### 4.2 2026-09-26 — `504 Gateway Time-out` on login

**Symptom:** submitting a username/password spun forever, then
`504 Gateway Time-out nginx/1.26.3`. PostgreSQL was suspected; it was innocent
(66 ms query, 6/100 connections).

**Chain of events:**

1. `ActiveDirectoryBackend` calls `django_auth_ldap`, which does a
   `simple_bind_s` against `ldap://10.51.0.20:389`.
2. That host was unreachable, so the TCP connect hung. There was no timeout.
3. Gunicorn killed the worker after 60 s (`handle_abort` → `sys.exit(1)`).
4. nginx had nobody to answer → 504.

**Two independent defects:**

* **Infrastructure** — the whole `10.51.0.0` subnet was dead
  (`.1`, `.10`, `.20`, `.254` all silent; `pms.local` did not resolve). The
  machine was on WiFi `192.168.1.10` with Ethernet disconnected, **no route to
  `10.0.0.0/8` and no VPN**. AD logins cannot work until the office network or
  VPN is back. Verify with `~/deploy/check-ad.sh`.
* **Configuration** — `settings.py` had `AUTH_LDAP_CONNECTION_TIMEOUT = 5`.
  **django-auth-ldap has no such setting.** `LDAPConfig` only reads names from
  its `defaults` dict; anything else is silently ignored, so the value did
  nothing at all and was never an error.

**Fix (committed in `config/settings.py`):**

```python
AUTH_LDAP_GLOBAL_OPTIONS     = {ldap.OPT_NETWORK_TIMEOUT: 5, ldap.OPT_TIMEOUT: 10}
AUTH_LDAP_CONNECTION_OPTIONS = {ldap.OPT_NETWORK_TIMEOUT: 5, ldap.OPT_TIMEOUT: 10}
```

`AUTH_LDAP_GLOBAL_OPTIONS` is applied once to the `ldap` module
(`_LDAPConfig.get_ldap`), `AUTH_LDAP_CONNECTION_OPTIONS` to every connection
right after `ldap.initialize()` and *before* the bind.

**Measured before/after:**

| Login attempt | Before | After |
| --- | --- | --- |
| `admin` (local, never touches LDAP) | 302 in 1.0 s | 302 in 1.1 s |
| any AD username | **504 after 60.0 s** | **200 login page in 6.0 s** |

`core/backends.py` already wraps the LDAP call in `try/except Exception`, so
the resulting `ldap.SERVER_DOWN: Can't contact LDAP server` is logged and the
backend returns `None` → Django shows the normal "invalid credentials" page.
A dead AD is now a *fast, quiet* failure instead of a gateway error.

**Rule:** an unknown `AUTH_*` setting in django-auth-ldap fails silently. If
you add a timeout/option, verify the name exists in
`.venv/lib/python3.12/site-packages/django_auth_ldap/config.py` (`defaults`)
or in `AUTH_LDAP_GLOBAL_OPTIONS` / `AUTH_LDAP_CONNECTION_OPTIONS`.

### 4.3 Noise in the logs (harmless)

`POST /logstores/logstore_ens_ip/shards/lb` every minute from
`log-c-lite_0.1.0` with `Host: easeusinfo.us-east-1.log.aliyuncs.com` — local
telemetry (EASEUS) hitting port 80. Django rejects it as `DisallowedHost`
(HTTP 400). Not an error, not an attack; ignore it or add a catch-all
`server { listen 80 default_server; return 444; }` above the vhost.

---

## 5. Verification

Full check, in order:

```bash
# 1. services
for u in nginx pms-purchasing postgresql cb; do
  printf '%-16s %s\n' "$u" "$(systemctl is-active $u)"; done
# expect: nginx/pms-purchasing/postgresql = active, cb = inactive

# 2. Django
cd ~/pms-purchasing-django
.venv/bin/python manage.py check                 # "System check identified no issues"
for t in tests/test_*.py; do .venv/bin/python "$t"; done
bash tests/test_vendor_flows.sh

# 3. HTTP
for u in / /en/login/ /ar/login/ /static/css/style.css; do
  printf '%-26s %s\n' "$u" "$(curl -sS -o /dev/null -w '%{http_code}' http://cb.alma.local$u)"; done
# / and /ar/login/ and static = 200 ; / redirects (302) to /en/

# 4. real login from Windows
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\AlmaLinux-10\home\xinreal\deploy\test-login.ps1
```

The `test-login.ps1` script proves the whole chain: login page 200 → POST
302 → dashboard 200 showing `Welcome back, admin.` → static 200 → `/ar/` 200.

---

## 6. Rollback to the old React app

```bash
sudo cp ~/.deploy-backup/cb.alma.local.conf.bak /etc/nginx/conf.d/cb.alma.local.conf
sudo systemctl disable --now pms-purchasing
sudo systemctl enable --now cb
sudo systemctl restart nginx
```

Originals kept in `~/.deploy-backup/`: the pre-change vhost and a copy of
`.env`.

---

## 7. Security notes

* **Loopback only.** `cb.alma.local` resolves to `127.0.0.1` on both OSes and
  gunicorn binds `127.0.0.1:8001`, so nothing off this machine can reach the
  app even though firewalld allows `http`.
* **No TLS.** Fine for loopback; if the name ever becomes a real hostname,
  add certificates and `proxy_set_header X-Forwarded-Proto`.
* **`DJANGO_DEBUG=True`** is still on. Acceptable while the app is loopback
  only — it exposes settings/tracebacks on error pages. Turn it off (and run
  `collectstatic`, which the unit already does) before any wider exposure.
* **Secrets** live only in `.env` (git-ignored). `.env.example` documents
  every variable with placeholders. Never put `AUTH_LDAP_BIND_PASSWORD`,
  `DJANGO_SECRET_KEY` or the DB password in source, in the dump, or in the
  `.accdb` files.
* **The repository is public.** The SQL dump and both `.accdb` files contain
  real business data — that is intentional per the project owner. The dump is
  taken with `--exclude-table-data=django_session` so live login sessions are
  never published (a session key would let anyone impersonate a signed-in
  user). `auth_user` holds one row: `admin`, with a Django password hash.
* **Known exposure:** `admin`/`admin123` is a development credential. Change
  it before the app is reachable by anyone else, and rotate
  `DJANGO_SECRET_KEY` + `AUTH_LDAP_BIND_PASSWORD` — both were committed in an
  earlier revision, so git history still holds them (see README).

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `504 Gateway Time-out` on login | LDAP bind hanging (AD unreachable, no timeout) | `~/deploy/check-ad.sh`; confirm the `AUTH_LDAP_*_OPTIONS` timeouts are still in `settings.py` |
| Login page loads, POST never returns | same as above — watch `journalctl -u pms-purchasing -f` for `simple_bind_s` | fix AD/VPN reachability |
| Login POST → **403** "CSRF token … incorrect length" | test client sent a truncated token (bad shell extraction), or `CSRF_TRUSTED_ORIGINS` missing `http://cb.alma.local` | re-extract the token; check `.env` |
| Login POST → **403** DisallowedHost | `Host` header not forwarded, or host missing from `DJANGO_ALLOWED_HOSTS` | keep `proxy_set_header Host $host`; check `.env` |
| `/static/...` → 404 | `collectstatic` not run, or `/home/xinreal` not `o+x` | `sudo systemctl restart pms-purchasing`; `chmod o+x /home/xinreal` |
| `/static/...` → 403 | nginx cannot traverse the home directory | `chmod o+x /home/xinreal` |
| CSS change not visible | nginx serves a stale copy of `staticfiles/` | `sudo systemctl restart pms-purchasing` (runs `collectstatic`) **or** bump `?v=` in `base.html` |
| `502 Bad Gateway` | gunicorn is down | `systemctl status pms-purchasing`; `journalctl -u pms-purchasing -n 50` |
| `Connection refused` to `:8001` | unit not running / port in use | `systemctl restart pms-purchasing`; `ss -ltnp \| grep 8001` |
| Old React app comes back | `cb.service` re-enabled | `systemctl disable cb` |
| AD logins fail but `admin` works | AD/VPN down, bind password empty, or no `EmployeeAccess` row | `~/deploy/check-ad.sh`, `.env`, admin → Employee Access |
| nginx config error after an edit | typo in the vhost | `nginx -t` before `systemctl restart nginx`; restore from `~/deploy/` |
