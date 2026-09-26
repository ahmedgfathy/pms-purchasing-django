# PMS Purchasing - Django Project

Django 6.1 purchasing-management app. Mirrors the sibling "trunk" project
(`/home/xinreal/trunk`) in theme, structure, and conventions.

## Environment

- WSL distro: `Ubuntu-26.04` (path `\\wsl.localhost\Ubuntu-26.04\home\xinreal\pms-purchasing-django`)
- Run commands via PowerShell: `wsl -d Ubuntu-26.04 -- bash -lc "..."`
- Python 3.14.4; venv at `.venv` (activate: `.venv/bin/python`)
- PostgreSQL 16 on 127.0.0.1:5432; DB `pms_purchasing`, role `xinreal` /
  `pms_purchasing` (MariaDB still selectable via `DB_ENGINE`,
  `setup_db.sql` creates that DB/role)
- Credentials in `.env` (loaded by `python-dotenv` in settings); every
  variable is documented in `.env.example` — the AD bind password
  (`AUTH_LDAP_BIND_PASSWORD`) must only ever live there, never in source
- Windows PowerShell quoting is fragile: write scripts to files, then
  `wsl -d Ubuntu-26.04 -- bash /path/script.sh`. Avoid inline nested quotes.

## Run

```bash
cd /home/xinreal/pms-purchasing-django
.venv/bin/python manage.py runserver 0.0.0.0:8001
```

- App URL: http://localhost:8001 (port 8000 is trunk — do not reuse)
- Login: `admin` / `admin123`
- Log: `/tmp/pms-server.log`

## Verify

```bash
.venv/bin/python manage.py check
for t in tests/test_*.py; do .venv/bin/python "$t"; done   # server must run on 8001
bash tests/test_vendor_flows.sh
msgfmt --statistics -o /dev/null locale/ar/LC_MESSAGES/django.po   # 0 fuzzy/0 untranslated
grep -c "Internal Server Error" /tmp/pms-server.log                # baseline: 7
```

End-to-end: `GET /en/login/` 200, `GET /ar/login/` 200 (Arabic translations),
POST credentials → 302, `GET /en/dashboard/` 200 shows "Welcome back, admin."

## Documentation

`docs/` is the complete reference (start at `README.md`): architecture,
field-level data model, URL/view table, UI system, Access import pipeline,
dashboard, business workflow, auth/ACL, i18n, testing, operations. Use
`AGENTS.md` (this file) as the short operational brief.

## Structure

- `config/` — project package (`settings.py`, `urls.py`)
- `core/` — single app (`views.py`, `urls.py`, `forms.py`, `models.py`, `admin.py`,
  `backends.py` (ActiveDirectoryBackend), `middleware.py` (EmployeeAccessMiddleware),
  `charts.py` (SVG donut geometry for the dashboard),
  `contacts.py` (e-mail/website cleaning rules), `templatetags/contacts.py`
  (`|emails`, `|website_url` filters),
  `management/commands/import_vendor_data.py`,
  `management/commands/normalize_vendor_contacts.py`)
- `templates/` — project-level templates (NOT `core/templates/`): `core/base.html`,
  `core/login.html`, `core/dashboard.html`, RFQ screens, and the vendor-list
  screens `operation_detail.html`, `vendor_register.html`,
  `vendor_detail.html`, `vendor_form.html`, plus the shared partials
  `core/_vendor_list_card.html` (vendor list + market-scoped add/vendor search),
  `core/_tender_details.html` (general info / value / milestone dates of a
  tender), `core/_tender_notes.html` (Access memo fields) and
  `core/_tender_list_table.html` (filters + tender table + pagination,
  shared by `rfq_list.html`, `tenders/local/` and `tenders/foreign/`) and
  `core/_chart_legend.html` (donut legend, used twice by the dashboard)
- `static/` — copied verbatim from trunk: `css/style.css`, `js/app.js`, `img/logo.svg`
  (logo rebranded with "P")
- `locale/ar/LC_MESSAGES/django.po` — Arabic translations (388 msgids, 0 fuzzy/0 untranslated)
- `docs/` — full documentation set (01 architecture … 11 operations),
  `README.md` — entry point, `tests/` — 5 end-to-end scripts,
  `db/pms_purchasing_2026-09-26.sql.gz` — compressed PostgreSQL dump,
  `2026.accdb` + `2026-data.accdb` — legacy Access front/back end (import source)
- `.env` (git-ignored), `.env.example`, `requirements.txt`
  (Django==6.1.*, mysqlclient==2.*, python-dotenv==1.*, django-auth-ldap, psycopg2-binary)

## Dashboard

`/dashboard/` (`core/dashboard.html`) is the statistics home screen:

- six **stat cards** (tenders, vendors, vendor-list entries, RFQs, vendor
  activities, estimated value) — each links to the screen it counts.
- four **SVG donuts** (market, vendor-list coverage, vendor scope,
  registration status) + six **CSS bar charts** (execution method, file
  department, region, estimated value by currency, top vendors, top
  activities). No JS and no CDN: geometry comes from `core/charts.py`
  (`donut()` builds stroke-dasharray arcs, `abbrev()` shortens card
  figures), bars are `width: %` divs, the legend is `_chart_legend.html`.
- an **RFQ workflow** panel (donut by status; empty state with a *New RFQ*
  button while `RFQ` has no rows) and a **Database Summary** table with one
  row per table of the imported data.
- aggregates are built by `_dashboard_context()` in `core/views.py`:
  market/scope counts reuse `_scoped_vendors()`, values are summed **per
  currency** (the Access file mixes EGP/USD/EUR — never across), bar rows
  are sized against the biggest row with a 0.8% hairline floor, and the
  palette is `charts.PALETTE` (blue/amber first so local/foreign matches
  the badges).
- after changing strings: `makemessages -l ar` → fill msgstr →
  `compilemessages`, and bump `style.css?v=` in `base.html` when the CSS
  changes (currently `v=9`).

## Conventions

- Theme: classic Windows-95 desktop style from trunk — 3D bevel buttons, blue
  accent series, Cairo font (Google Fonts), EN/AR flag language switch.
- URLs: `config/urls.py` wraps app URLs in `i18n_patterns`; `/i18n/` set_language
  route handles the flag switcher. Real routes are `/en/...` and `/ar/...`.
- Auth: `CustomLoginView(LoginView)` in `core/views.py`, `template_name='core/login.html'`,
  `redirect_authenticated_user=True`, redirects to `dashboard`.
- `home` redirects authenticated users to dashboard, anonymous to login.
- Use `{% load i18n %}` + `{% trans %}` / `{% blocktrans %}` in templates; keep
  `locale/ar` in sync after template changes:
  ```bash
  .venv/bin/python manage.py makemessages -l ar
  .venv/bin/python manage.py compilemessages
  ```
- `settings.py` mirrors trunk: `LocaleMiddleware`, `LOCALE_PATHS`, `STATICFILES_DIRS`,
  `TEMPLATES DIRS`, `LOGIN_URL`/`LOGIN_REDIRECT_URL`, `CSRF_TRUSTED_ORIGINS`.
- Trunk imports settings as `django_settings` because a view named `settings`
  shadows the module.

## Vendor List Module

Rebuilt 1:1 from the Access front end (`2026.accdb`) and back end
(`2026-data.accdb`). Keep it faithful to the Access forms/labels.

- Models (appended to `core/models.py`): `Vendor`, `Operation`, `OperationVendor`,
  `VendorActivity`, plus code lookups `Project`, `ClientCode`, `Location`,
  `CostCenter`, `MainActivity`, `SubActivity`.
- Routes (`core/urls.py`): `rfq/` (the tender list, see below),
  `vendor-list/<pk>/` (one tender: data + vendor sub list + add/search),
  `vendor-list/` is only a **redirect to `rfq/`** (its sidebar entry was
  removed — the tender list lives on the RFQ screen now),
  `vendors/` (register), `vendors/<pk>/`, `vendors/new/`, `vendors/<pk>/edit/`,
  plus POST-only `.../vendors/add|remove/` and `.../activities/add|remove/`.
- Tenders by market (sidebar "Local Tender" / "Foreign Tender" = the two
  divisions): `tenders/local/`, `tenders/foreign/` render the same RFQ list
  scoped by `Operation.market` (import sets it: file dept `المشتريات المحلية*`
  → local, `المشتريات الخارجية` → foreign, other depts fall back to the
  currency; currently 1694 local / 364 foreign). Each division shows its own
  "RFQs without a tender" and a **New RFQ** button that passes
  `?market=<division>` to `rfq_create` so the form opens pre-set. There are
  **no tab/segment buttons** — the sidebar is the only local/foreign switch
  (user asked to drop the duplicate classification), so `_tender_list()`
  builds no tab context any more.
- The RFQ screen (`rfq/`, `core/rfq_list.html`) **is** the list of all
  tenders — and the template every list view renders (`_tender_list()`,
  default `template="core/rfq_list.html"`; `?market=local|foreign` still
  narrows it for deep links). Rows are `Operation`s, one per
  tender, with a Mat. Req. No column linking to the linked `RFQ` ("Open" goes
  to the RFQ page when one exists, else to the tender page). RFQs that have no
  tender yet are listed above the table under "RFQs without a tender".
- One tender per RFQ: `RFQ.tender` (nullable FK → `Operation`). The RFQ **is**
  the بيان المهمات that opens the tender, so `rfq_detail` renders the tender's
  full details under a "Tender Details" heading — task statement, general
  information, value/follow-up, milestone dates, notes and the vendor list —
  through `_tender_details.html`, `_tender_notes.html` and
  `_vendor_list_card.html` (all shared with `operation_detail`);
  "Open Vendor List" POSTs to `rfq_tender_create`, which opens the Access-style
  operation (next free `operation_no`, market + file dept from the RFQ,
  execution method from the purchase method, rec. date + budget code carried
  over). Vendor add/remove POSTs take an optional `next` field to return to
  the RFQ.
- Vendor search is market-scoped (`_scoped_vendors`): local = booklet `محلى`
  (or country مصر/Egypt when the booklet is blank), foreign = booklet `خارجى`
  (or a non-Egypt country when the booklet is blank); the card offers a
  "Local/Foreign vendors | All vendors" toggle.
- Import all Access data (mdbtools at `~/.local/bin`, PostgreSQL only):
  ```bash
  .venv/bin/python manage.py import_vendor_data            # re-export + load
  .venv/bin/python manage.py import_vendor_data --keep     # reuse /tmp/accdb_csv
  ```
  Clears + reloads the vendor tables inside one transaction (~41k rows);
  reference tables are upserted, not cleared. Re-runnable.
- Access quirks honored: `Supplier ID` is a non-auto PK (assigned max+1 on save),
  `Oprations.[رقم العملية]` is NOT unique (dup 170/1929), 92 `Vendor Opration`
  rows have an empty operation no (kept as raw `operation_no`, FK nullable),
  estimated value is text with Arabic-Indic digits, Access `Memo` columns are
  `TextField` (e-mail fields reach 929 chars).
- Required vendor fields are only `name_ar` and `registration_status_new`
  (both NOT NULL in Access).
- After adding strings: `makemessages -l ar` → fill msgstr (use the original
  Access Arabic column labels as the Arabic terms) → `compilemessages`.

### Vendor contacts (e-mail / website)

The Access back end stores those two columns as *hyperlinks*, so mdbtools
hands us Jet's `display#target#` encoding — `a@b.com#mailto:a@b.com#`,
`www.site.com#http://www.site.com#` — plus pasted junk (company names,
Outlook file paths, an address typed into the wrong column).
`core/contacts.py` is the single set of rules for all of it
(`parse_emails()`, `clean_emails()`, `clean_website()`, `clean_contacts(data)`).
It is idempotent and runs in three places:

- `import_vendor_data` — cleans while it loads (a fresh import leaves the
  columns clean; re-import sets `RFQ.tender` to NULL because the Operations
  get new PKs, `on_delete=SET_NULL` keeps the RFQs).
- `VendorForm.clean()` — normalizes whatever people type into the form
  (stray spaces around `@`, `site ,com`, multi-address pastes).
- `manage.py normalize_vendor_contacts` — cleans rows already in the DB and
  prints per-field counts; a second run reports "already clean".
  Cross-column repairs happen inside `clean_contacts()`: a URL sitting in a
  mail box fills an empty Website, an address in the Website box fills an
  empty E-mail 1, and duplicates pasted into several boxes are kept only in
  the first one.

Templates turn the results into links through the `contacts` templatetags —
`{{ vendor.email1|emails }}` (list of addresses → `mailto:` anchors) and
`{{ vendor.website|website_url }}` (`href`, opens in a new tab) — while
`Vendor.email` (first deliverable address) feeds the **E-mail** column of
the tender vendor list, the vendor search and the register. Link styling is
`.contact-link` in `style.css` (RTL-safe: `direction: ltr; unicode-bidi:
plaintext`).

## Gotchas

- Do NOT touch `/home/xinreal/pms-purchasing` — that folder holds a different,
  unrelated Node/React project. This project lives in `pms-purchasing-django`.
- Admin user password is `admin123` (default, for dev only).