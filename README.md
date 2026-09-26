# PMS Purchasing

Purchasing-management web app for **Petroleum Marine Services (PMS)** — a Django 6.1
rewrite of the legacy Microsoft Access front end (`2026.accdb`) + back end
(`2026-data.accdb`), with a statistics dashboard and full Arabic/English UI.

* **Live**: http://localhost:8001 — login `admin` / `admin123` (dev only)
* **Languages**: `/en/...` and `/ar/...` (flag switcher in the header)
* **Theme**: classic Windows-95 desktop (3D bevels, blue accent `#1d4ed8`, Cairo font)
* **Database**: PostgreSQL (default; MariaDB/MySQL still selectable via `DB_ENGINE`)
* **Data**: 8,878 vendors · 2,058 tenders (1,694 local / 364 foreign) · 6,436
  vendor-list entries · 22,945 vendor/activity registrations — all imported from Access

---

## Quick start

```bash
cd /home/xinreal/pms-purchasing-django
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                      # then edit DB/secret values
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 0.0.0.0:8001
```

Two ways to get the data in:

| Goal | Command |
| --- | --- |
| Load the exact data of this repo (fast, no Access tooling) | `gunzip -c db/pms_purchasing_2026-09-26.sql.gz \| psql -h 127.0.0.1 -U <user> -d pms_purchasing` (see [docs/11-operations.md](docs/11-operations.md)) |
| Re-import from the Access back end | `.venv/bin/python manage.py import_vendor_data` (needs mdbtools, see [docs/05-access-data-pipeline.md](docs/05-access-data-pipeline.md)) |

Verify an install:

```bash
.venv/bin/python manage.py check          # "System check identified no issues"
for t in tests/test_*.py; do .venv/bin/python "$t"; done
bash tests/test_vendor_flows.sh
```

---

## What the app does

| Screen | URL | Purpose |
| --- | --- | --- |
| Login | `/en/login/` | AD/LDAP or local account (see [docs/08](docs/08-auth-and-access-control.md)) |
| **Dashboard** | `/en/dashboard/` | Stat cards, SVG donuts, CSS bars, RFQ workflow, DB summary ([docs/06](docs/06-dashboard.md)) |
| **RFQs / Tenders** | `/en/rfq/` | Every tender, one per page, plus "RFQs without a tender" and *New RFQ* |
| Local Tender | `/en/tenders/local/` | The local division's tenders (`Operation.market=local`) |
| Foreign Tender | `/en/tenders/foreign/` | The foreign division's tenders (`Operation.market=foreign`) |
| Tender detail | `/en/vendor-list/<pk>/` | General info, value, milestone dates, notes + the **vendor list** |
| Vendor Register | `/en/vendors/` | Search/filter/page all 8,878 vendors |
| Vendor file | `/en/vendors/<pk>/` | Access "Vendor View": contacts, activity registrations, operations |
| New / Edit vendor | `/en/vendors/new/`, `/en/vendors/<pk>/edit/` | Access "New Vendor Enter" |
| Django admin | `/en/admin/` | Everything, including `EmployeeAccess` / `DepartmentAccess` |

The business workflow (department → purchase approval → division → vendor list)
is described in [docs/07-business-workflow.md](docs/07-business-workflow.md).

---

## Repository layout

```
config/            project package: settings.py, urls.py, wsgi/asgi
core/              the single Django app
  models.py        17 models (RFQ + the whole Access domain)
  views.py         all views + _dashboard_context() / _tender_list() helpers
  forms.py         RFQForm, RFQItemFormSet, VendorForm, VendorActivityForm
  charts.py        SVG donut geometry + value abbreviation (no JS, no CDN)
  contacts.py      single source of truth for e-mail/website cleaning
  backends.py      ActiveDirectoryBackend (LDAP)
  middleware.py    EmployeeAccessMiddleware (who may log in)
  templatetags/contacts.py   |emails and |website_url filters
  management/commands/
    import_vendor_data.py          Access -> PostgreSQL (transactional, re-runnable)
    normalize_vendor_contacts.py   clean contact columns already in the DB
  migrations/      0001..0007
templates/core/    project-level templates (NOT core/templates/)
static/            css/style.css, js/app.js, img/logo.svg
locale/ar/         Arabic translations (388 msgids, 0 fuzzy, 0 untranslated)
db/                PostgreSQL dump (gzip) + old MariaDB schema file
docs/              this documentation set
tests/             5 end-to-end scripts (HTTP + ORM checks)
2026.accdb         legacy Access front end  (source screens, 35 MB)
2026-data.accdb    legacy Access back end   (source data, 19 MB)
```

---

## Documentation set

Read in order; each file is self-contained and cross-links the others.

1. [docs/01-architecture.md](docs/01-architecture.md) — stack, settings, middleware, request flow
2. [docs/02-data-model.md](docs/02-data-model.md) — every model and field, relationships, Access quirks
3. [docs/03-urls-and-views.md](docs/03-urls-and-views.md) — every URL, view, parameter and POST endpoint
4. [docs/04-ui-and-templates.md](docs/04-ui-and-templates.md) — templates, partials, Win95 CSS system, JS
5. [docs/05-access-data-pipeline.md](docs/05-access-data-pipeline.md) — Access import, field map, contact cleaning
6. [docs/06-dashboard.md](docs/06-dashboard.md) — how the statistics screen is computed and rendered
7. [docs/07-business-workflow.md](docs/07-business-workflow.md) — RFQ → tender → vendor list, statuses, roles
8. [docs/08-auth-and-access-control.md](docs/08-auth-and-access-control.md) — LDAP, EmployeeAccess, admin
9. [docs/09-internationalization.md](docs/09-internationalization.md) — EN/AR, translation workflow
10. [docs/10-testing.md](docs/10-testing.md) — the test scripts and manual verification
11. [docs/11-operations.md](docs/11-operations.md) — run, backup/restore, troubleshooting, gotchas

`AGENTS.md` is the short operational brief for AI coding agents (rules,
conventions, gotchas); the `docs/` set is the complete reference.

---

## Data & secrets policy in this repository

* **Committed**: all source, templates, translations, migrations, the two Access
  files (source of truth for the import) and a compressed PostgreSQL dump
  (`db/pms_purchasing_2026-09-26.sql.gz`, ~1.3 MB, restore-verified).
* **Not committed** (`.gitignore`): `.env` (DB password, `SECRET_KEY`,
  `AUTH_LDAP_BIND_PASSWORD`), `media/` (RFQ attachments), `staticfiles/`,
  `__pycache__`, logs. `.env.example` documents every variable.
* The database dump contains *data*, not credentials — Django password hashes
  for `admin` only.
* ⚠️ **Rotate the AD bind password and the Django `SECRET_KEY`**: both were
  committed in an earlier revision (LDAP feature commit). They live only in
  `.env` now, but git history still holds them — history rewriting or a
  credential rotation is required to fully revoke them.

---

## Conventions worth knowing before changing code

* URLs live inside `i18n_patterns` → real routes are `/en/...` and `/ar/...`;
  `/i18n/` is the language switcher endpoint.
* Any new user-visible string: `{% trans %}` / `{% blocktrans %}` in templates,
  `gettext` in Python, then
  `.venv/bin/python manage.py makemessages -l ar` → fill `msgstr` →
  `manage.py compilemessages`. Keep **0 fuzzy / 0 untranslated**.
* Arabic terminology comes from the original Access column labels
  (`إدارة الملف` → File Department, `طريقة التنفيذ` → Execution Method, …).
* CSS changes: bump `style.css?v=` in `templates/core/base.html` (currently `v=9`).
* Never sum money across currencies — the Access file mixes EGP/USD/EUR.
* Ports: **8001** for this app; 8000 belongs to a different project.
* Do **not** touch `/home/xinreal/pms-purchasing` (unrelated Node project).
