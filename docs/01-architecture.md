# 01 · Architecture

How the pieces fit together, what every setting does, and what happens when a
browser requests a page.

## Stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Framework | Django 6.1 | Python 3.14 in `.venv` |
| Database | PostgreSQL 16 (default) | `DB_ENGINE` switch, `psycopg2-binary` |
| DB (legacy) | MariaDB/MySQL | still works: `DB_ENGINE=django.db.backends.mysql` + `mysqlclient` |
| Auth | LDAP/Active Directory + local `ModelBackend` | `django-auth-ldap` |
| Front end | Server-rendered templates, one CSS file, 85 lines of JS | no framework, no CDN, no build step |
| Charts | Hand-built SVG donuts + CSS bars | see [06-dashboard.md](06-dashboard.md) |
| i18n | `LocaleMiddleware` + `i18n_patterns` | EN/AR |
| Data source | Microsoft Access (`2026*.accdb`) through `mdbtools` | see [05-access-data-pipeline.md](05-access-data-pipeline.md) |

## Package map

```
config/
  settings.py     env-driven configuration (DB, LDAP, i18n, static, media)
  urls.py         i18n_patterns wrapper: /i18n/ + /admin/ + app URLs
  wsgi.py, asgi.py
core/             the only app (see README for the file-by-file map)
templates/        project-level templates (settings TEMPLATES DIRS)
static/           style.css, app.js, logo.svg
locale/ar/        django.po / django.mo
tests/            end-to-end scripts
db/               database dumps
docs/             this set
```

There is deliberately **one** app: models, views and templates for every
feature (RFQ, tenders, vendor list, vendors, dashboard) live side by side in
`core/`.

## settings.py walkthrough

* `load_dotenv(BASE_DIR/'.env')` runs first — every setting below reads the
  environment with a working default.
* `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` come from `DJANGO_*` variables.
* `MIDDLEWARE` order matters:

  1. `SecurityMiddleware`
  2. `SessionMiddleware`
  3. `LocaleMiddleware` — picks `en`/`ar` from the URL prefix, cookie or `Accept-Language`
  4. `CommonMiddleware` — `APPEND_SLASH` (the app relies on it: POSTs must target the exact trailing-slash URL)
  5. `CsrfViewMiddleware`
  6. `AuthenticationMiddleware` — sets `request.user`
  7. **`core.middleware.EmployeeAccessMiddleware`** — denies authenticated
     users that have no active `EmployeeAccess` row (superusers bypass it)
  8. `MessageMiddleware`, `XFrameOptionsMiddleware`

* `DATABASES['default']` — `DB_ENGINE` selects the backend. The MySQL-only
  `OPTIONS` (`charset=utf8mb4`, `sql_mode`) are only sent when the engine is
  MySQL, because PostgreSQL rejects them.
* `TEMPLATES DIRS = [BASE_DIR/'templates']` — templates are **project-level**,
  never `core/templates/`.
* `STATIC_URL/STATIC_ROOT/STATICFILES_DIRS`, `MEDIA_*` (RFQ attachments are
  uploaded to `media/`, which is git-ignored).
* `LOGIN_URL='login'`, `LOGIN_REDIRECT_URL='dashboard'`.
* `CSRF_TRUSTED_ORIGINS` from the environment (comma separated) — required
  because forms post to `http://127.0.0.1:8001`.
* **LDAP block** (bottom of the file): server `ldap://10.51.0.20:389`,
  base `DC=PMS,DC=LOCAL`, bind DN `2669@pms.local`, group search in
  `CN=Users,...`, attribute map `givenName/sn/mail → first_name/last_name/email`.
  The bind password **must** come from `AUTH_LDAP_BIND_PASSWORD` in `.env`
  (never hard-code it — see README secrets note).

## URL layout

`config/urls.py`:

```python
urlpatterns = [ path('i18n/', include('django.conf.urls.i18n')) ]
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
)
```

So every app route is prefixed with `/en` or `/ar`. `i18n_patterns` also
applies the `LocaleMiddleware` prefix detection; `/i18n/set_language/` flips
the language cookie and redirects back to the referring page (the flag
switcher in the header).

Full route table: [03-urls-and-views.md](03-urls-and-views.md).

## Request flow (typical page)

```
GET /en/vendor-list/4117/
  → LocaleMiddleware        resolves language "en"
  → Csrf/Authentication     sets request.user
  → EmployeeAccessMiddleware must find active EmployeeAccess (or be superuser)
  → core.urls               resolves views.operation_detail
  → @login_required          redirects to /en/login/ when anonymous
  → operation_detail()       Operation + operation_vendors + vendor picker context
  → render core/operation_detail.html
        base.html (sidebar, header, messages, flag switcher)
          + partials _tender_details / _tender_notes / _vendor_list_card
  → 200
```

POSTs (add/remove vendor, create RFQ, edit vendor …) require
`csrfmiddlewaretoken` + a matching `Referer`, then `redirect()` (PRG pattern)
back to a `next` target or the canonical detail page.

## Cross-cutting rules

* **No client-side state**: the only JS is `static/js/app.js`
  (Ctrl+Shift+<key> accelerators, clickable rows, tiny form niceties).
* **No external assets**: fonts are loaded from Google Fonts *with a local
  fallback stack*; nothing else leaves the server.
* **Query-string aware pagination**: list views drop only `page` when building
  `query_string`, so filters survive paging.
* **PRG + Django messages**: every successful POST shows a flash message on the
  next GET.
* **Idempotent bulk operations**: the import and the contact cleaner can be run
  repeatedly without corrupting data ([05](05-access-data-pipeline.md)).

## Performance profile

The dashboard (the heaviest screen) renders in ~117 ms with ≈41k rows across
ten tables: aggregates use `values().annotate()` (SQL `GROUP BY`), lists use
`select_related`/`prefetch_related`, and pagination is 25 rows per page. No
caching layer is used anywhere.
