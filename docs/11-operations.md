# 11 · Operations — run, back up, restore, troubleshoot

## Run the app

```bash
cd /home/xinreal/pms-purchasing-django
.venv/bin/python manage.py runserver 0.0.0.0:8001     # port 8001 only! 8000 is another project
# log: /tmp/pms-server.log
```

* URL: http://localhost:8001 — login `admin` / `admin123` (dev only).
* WSL path from Windows: `\\wsl.localhost\Ubuntu-26.04\home\xinreal\pms-purchasing-django`.
* Windows/PowerShell quoting is fragile: put commands in a `.sh` file and run
  `wsl -d Ubuntu-26.04 -- bash /path/script.sh`.

## Environment

`.env` (git-ignored) is loaded by `python-dotenv` in `settings.py`; every
variable is documented in `.env.example`. Key ones:

```
DJANGO_SECRET_KEY, DJANGO_DEBUG, DJANGO_ALLOWED_HOSTS
DB_ENGINE, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
CSRF_TRUSTED_ORIGINS        # must include http://localhost:8001, http://127.0.0.1:8001
AUTH_LDAP_BIND_PASSWORD     # AD bind password — required for LDAP logins only
```

## Database

* **PostgreSQL 16** inside WSL, listening on `127.0.0.1:5432`.
* Role `xinreal` (no superuser/CREATEDB), password `pms_purchasing`;
  database `pms_purchasing` (owner `xinreal`, UTF8 / `en_US.UTF-8`).
* Configured through `DB_ENGINE` (default
  `django.db.backends.postgresql`). To use MariaDB/MySQL instead:
  `DB_ENGINE=django.db.backends.mysql`, `DB_PORT=3306`, and install
  `mysqlclient` — `setup_db.sql` still creates that database/role.

### Schema

```bash
.venv/bin/python manage.py migrate          # migrations 0001..0007
.venv/bin/python manage.py check            # must print "no issues"
```

### Loading data — choose one

**(a) Restore the committed dump** (no Access tooling needed):

```bash
export PGPASSWORD=pms_purchasing
gunzip -c db/pms_purchasing_2026-09-26.sql.gz \
  | psql -h 127.0.0.1 -U xinreal -d pms_purchasing
```

On a brand-new database the restoring role must own the schema (PostgreSQL 16
revokes `CREATE` on `public` from non-owners):

```bash
sudo -u postgres createdb -O xinreal pms_purchasing
sudo -u postgres psql -d pms_purchasing -c 'GRANT ALL ON SCHEMA public TO xinreal;'
```

**(b) Re-import from Access** (needs `mdbtools`):

```bash
.venv/bin/python manage.py import_vendor_data            # export + load (~41k rows)
.venv/bin/python manage.py import_vendor_data --keep     # reuse /tmp/accdb_csv (~10 s)
```

Both paths must yield: Vendors 8,878 · Operations 2,058 · Operation Vendors
6,436 · Vendor Activities 22,945 · Sub Activities 846 · Main Activities 107 ·
Projects 19 · Clients 63 · Cost Centers 72 · Locations 10.

### Backups

```bash
export PGPASSWORD=pms_purchasing
pg_dump -h 127.0.0.1 -U xinreal -d pms_purchasing \
        --no-owner --no-privileges --encoding=UTF8 \
  | gzip -9 > db/pms_purchasing_$(date +%F).sql.gz          # ~1.3 MB, 2 s
```

The committed dump was verified by restoring it into a scratch database and
counting every table — do the same after each backup you care about:

```bash
sudo -u postgres createdb pms_restore_test
gunzip -c db/pms_purchasing_YYYY-MM-DD.sql.gz | sudo -u postgres psql -d pms_restore_test -q
sudo -u postgres psql -d pms_restore_test -tAc \
  "select count(*) from core_vendor; select count(*) from core_operation;"
sudo -u postgres dropdb pms_restore_test
```

`db/pms_purchasing.sql` is the older, schema-only MariaDB file kept for
history.

## mdbtools (for the Access import)

```bash
sudo apt install mdbtools        # or build into ~/.local/bin (default search path)
which mdb-export
```

The command falls back to `~/.local/bin/mdb-export`; CSVs are cached in
`/tmp/accdb_csv`.

## Translations

```bash
.venv/bin/python manage.py makemessages -l ar
# ... fill msgstr in locale/ar/LC_MESSAGES/django.po ...
.venv/bin/python manage.py compilemessages
msgfmt --statistics -o /dev/null locale/ar/LC_MESSAGES/django.po   # "388 translated messages."
```

## Static files

* Development: the dev server serves `static/` directly.
* Production: `.venv/bin/python manage.py collectstatic` → `staticfiles/`
  (git-ignored) + a real WSGI server (`gunicorn`/`uwsgi` behind nginx).
* After every CSS change bump `style.css?v=` in `templates/core/base.html`
  (`?v=9` today) **and** in `templates/core/login.html` (`?v=2` today).

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `relation ... does not exist` | migrations not applied → `manage.py migrate` |
| `permission denied for schema public` on restore | the role does not own the database (PG 16) → create the DB as `postgres` and `GRANT ALL ON SCHEMA public` |
| `fe_sendauth: no password supplied` | `PGPASSWORD`/`.env` password missing |
| Startup errors about `charset` / `sql_mode` options | those `OPTIONS` are MySQL-only and are gated by `DB_ENGINE` in `settings.py` — don't remove that gate |
| 303/404 on `/dashboard/` | missing language prefix — use `/en/dashboard/` or `/ar/dashboard/` |
| Form POST rejected (403) | `CSRF_TRUSTED_ORIGINS` missing your origin, or the `Referer`/`X-CSRFToken` headers absent (curl must send both) |
| "Access denied. Contact administrator…" | the logged-in user has no active `EmployeeAccess` row → add it in admin |
| LDAP login fails, `admin` works | `AUTH_LDAP_BIND_PASSWORD` empty, AD unreachable (`10.51.0.20:389`), or the employee is not in AD → check the server log and `.env` |
| Stale CSS after a change | bump the `?v=` query string |
| `mdb-export: command not found` | install mdbtools or put it in `~/.local/bin` |
| WSL IP changed after reboot | `172.20.175.167` is dynamic — always use `localhost`/`127.0.0.1` |
| Import took the RFQ links away | expected: a re-import recreates `Operation` rows and `RFQ.tender` is SET_NULL |
| Server 500s | `grep -c "Internal Server Error" /tmp/pms-server.log` — the baseline is 7 historical entries; investigate any new one |

## Gotchas

* **Never** touch `/home/xinreal/pms-purchasing` — an unrelated Node project.
* Port **8001** only; port 8000 belongs to another app.
* Never sum money across currencies (Access mixes EGP/USD/EUR).
* `Operation.operation_no` is not unique — always key on `Operation.id`.
* `Vendor.supplier_id` is the primary key and is assigned `max+1` on create.
* Templates live in top-level `templates/`, not `core/templates/`.
* Keep `locale/ar` at 0 fuzzy / 0 untranslated.
* Secrets stay in `.env` (git-ignored) — `.env.example` carries placeholders.
* The repository is **public** on GitHub: the two `.accdb` files and the SQL
  dump contain real business data — that is intentional per project owner
  instruction; do not add credentials to any of them.
