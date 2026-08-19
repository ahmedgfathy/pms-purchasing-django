# PMS Purchasing - Django Project

Django 6.1 purchasing-management app. Mirrors the sibling "trunk" project
(`/home/xinreal/trunk`) in theme, structure, and conventions.

## Environment

- WSL distro: `Ubuntu-26.04` (path `\\wsl.localhost\Ubuntu-26.04\home\xinreal\pms-purchasing-django`)
- Run commands via PowerShell: `wsl -d Ubuntu-26.04 -- bash -lc "..."`
- Python 3.14.4; venv at `.venv` (activate: `.venv/bin/python`)
- MariaDB 11.8.6; DB `pms_purchasing`, user `pms_purchasing` / `pms_purchasing`
- Credentials in `.env` (loaded by `python-dotenv` in settings)
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
```

End-to-end: `GET /en/login/` 200, `GET /ar/login/` 200 (Arabic translations),
POST credentials → 302, `GET /en/dashboard/` 200 shows "Welcome back, admin."

## Structure

- `config/` — project package (`settings.py`, `urls.py`)
- `core/` — single app (`views.py`, `urls.py`)
- `templates/` — project-level templates (NOT `core/templates/`): `core/base.html`,
  `core/login.html`, `core/dashboard.html`
- `static/` — copied verbatim from trunk: `css/style.css`, `js/app.js`, `img/logo.svg`
  (logo rebranded with "P")
- `locale/ar/LC_MESSAGES/django.po` — Arabic translations
- `.env`, `requirements.txt` (Django==6.1.*, mysqlclient==2.*, python-dotenv==1.*)

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

## Gotchas

- Do NOT touch `/home/xinreal/pms-purchasing` — that folder holds a different,
  unrelated Node/React project. This project lives in `pms-purchasing-django`.
- Admin user password is `admin123` (default, for dev only).