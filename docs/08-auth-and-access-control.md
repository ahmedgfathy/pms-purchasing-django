# 08 · Authentication and access control

Three layers: the **authentication backend** (who you are), the
**middleware** (whether you may use the app at all), and the **per-action
permission flags** (what you may do — stored, not yet enforced).

## Login

* `CustomLoginView` (`core/views.py`) — `LoginView` with
  `template_name='core/login.html'`, `redirect_authenticated_user=True`,
  `get_redirect_url()` → `dashboard`.
* `LOGIN_URL='login'`, `LOGIN_REDIRECT_URL='dashboard'`.
* `home` (`/`) sends authenticated users to the dashboard, everyone else to
  login.
* `logout_view` logs out and redirects to `login`.

`AUTHENTICATION_BACKENDS`:

```python
['core.backends.ActiveDirectoryBackend',     # 1st
 'django.contrib.auth.backends.ModelBackend'] # fallback (local users)
```

## `core.backends.ActiveDirectoryBackend`

```python
1. username == "admin"  → local password check, return that user (superuser escape hatch)
2. else LDAP:
   LDAPBackend().authenticate(request, username, password)      # django-auth-ldap
   ├─ success → get-or-create a Django User (unusable password,
   │            first/last/e-mail mapped from AD via AUTH_LDAP_USER_ATTR_MAP)
   │            then require an *active* EmployeeAccess row:
   │            ├─ exists & is_active        → return the user
   │            ├─ exists & !is_active       → deny (inactive employee)
   │            └─ no row                    → deny ("ask admin to add them")
   └─ failure → deny (wrong password or AD unreachable)
```

LDAP settings live at the bottom of `config/settings.py`
(`AUTH_LDAP_SERVER_URI = ldap://10.51.0.20:389`, base `DC=PMS,DC=LOCAL`, bind DN
`2669@pms.local`, group search `CN=Users,DC=PMS,DC=LOCAL`, attribute map
`givenName/sn/mail`, `AUTH_LDAP_CACHE_TIMEOUT=300`).

> The bind password **must** come from `AUTH_LDAP_BIND_PASSWORD` in `.env`
> (see `.env.example`). It is not allowed to live in source code.

## `core.middleware.EmployeeAccessMiddleware`

Runs after `AuthenticationMiddleware` for every request:

```python
if request.user.is_authenticated:
    if request.user.is_superuser:            # admin bypasses everything
        pass
    elif url_name in (login, logout, set_language, admin:index, admin:login)
         or namespace == "admin":            # exempt
        pass
    else:
        EmployeeAccess.objects.get(employee_id=request.user.username, is_active=True)
        └─ DoesNotExist → messages.error("Access denied. …") → redirect('login')
        └─ found        → request.employee_access = access
```

So an AD account that authenticated successfully but has **no active
`EmployeeAccess` row** still cannot open any page of the app.

## Access models

### `EmployeeAccess` — one row per AD employee

| Field | Meaning | Default |
| --- | --- | --- |
| `employee_id` | matches the AD `sAMAccountName` / Django username | — |
| `full_name`, `department`, `role`, `is_active` | profile | `role='viewer'`, `is_active=True` |
| `can_view_rfq` / `can_create_rfq` / `can_edit_rfq` / `can_delete_rfq` / `can_approve_rfq` | RFQ rights | view True, rest False |
| `can_view_vendors` / `can_create_vendors` | vendor rights | view True, create False |
| `can_view_reports`, `can_view_admin` | dashboards / admin | True / False |

`role` choices: `viewer`, `requester`, `purchaser`, `manager`, `admin`.

### `DepartmentAccess` — one row per department

`can_view_rfq`, `can_create_rfq`, `can_view_vendors`, `can_view_reports`
(all default `True`), linked 1:1 to `Department`.

Both models are editable in Django admin (`EmployeeAccessAdmin`,
`DepartmentAccessAdmin`).

## What is enforced today

| Control | Enforced? |
| --- | --- |
| Must be logged in for every app screen | ✅ `@login_required` |
| Must have an active `EmployeeAccess` row | ✅ middleware (+ backend denies at login) |
| Superuser (`admin`) bypass | ✅ middleware + backend |
| `can_create/edit/delete/approve_rfq` | ❌ stored only — no per-view check yet |
| `can_view/create_vendors` | ❌ stored only |
| `DepartmentAccess` flags | ❌ stored only (not read by any view) |

The two ❌ groups are the intended implementation surface for the approval
workflow described in [07-business-workflow.md](07-business-workflow.md).

## Seeding and day-to-day administration

```bash
# create the IT department + EmployeeAccess for AD employee 2669 (role admin)
.venv/bin/python create_initial_access.py
```

* Grant a new employee access: **Admin → Employee Access → Add**
  (`employee_id` = AD account name, `is_active=True`).
* Grant a local (non-AD) account: create the `auth_user` in admin — it
  authenticates through `ModelBackend`, but the **middleware still requires an
  `EmployeeAccess` row** unless the user is a superuser.
* Reset the dev login: `admin` / `admin123` (superuser, always allowed).

## Security notes for this repository

1. `.env` is git-ignored and holds `DJANGO_SECRET_KEY`, DB credentials and
   `AUTH_LDAP_BIND_PASSWORD`. `.env.example` documents them with placeholders.
2. ⚠️ An earlier commit pushed the AD bind password **and** a fallback
   `SECRET_KEY` in `config/settings.py`. The source is clean now, but git
   history still contains them — rotate both credentials (and consider
   `git filter-repo` + force push) to revoke them.
3. The repo is public: never commit `.env`, dumps of credential tables, or
   real employee passwords.
