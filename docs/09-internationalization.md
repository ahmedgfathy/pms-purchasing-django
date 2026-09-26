# 09 · Internationalization (EN / AR)

The app ships two complete languages: English and Arabic (RTL). The language
is part of the URL, not just a cookie.

## Routing

`config/urls.py`:

```python
urlpatterns = [path('i18n/', include('django.conf.urls.i18n'))]
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
)
```

* Real routes are **`/en/...` and `/ar/...`** (there is no language-less app
  URL — `/` redirects to `/en/dashboard/` or `/en/login/`).
* `/i18n/set_language/` (POST, CSRF-protected) flips the language cookie
  (`LANGUAGE_COOKIE_NAME = 'django_language'`) and redirects to the `next`
  value the form carries — the header's EN/AR flag buttons.

## Switcher UI

`base.html` and `login.html` both render a `.lang-switch` form with two flag
buttons (inline SVG Union Jack / Egyptian flag, no external images). The
active language gets `.active`, and the button label is `EN` / `عربي`.
Because `next={{ request.get_full_path }}`, switching keeps you on the same
record and preserves query parameters.

`<html lang="{{ CURRENT_LANG }}" {% if LANGUAGE_BIDI %}dir="rtl"{% endif %}>`
— Arabic pages get `lang="ar" dir="rtl"` and the CSS handles mirroring
(the sidebar/table/text flow flip automatically; only explicitly
direction-sensitive bits, e.g. `.contact-link`, force LTR).

## Writing translatable strings

Templates:

```django
{% load i18n %}
{% trans "Vendor Register" %}
{% blocktrans with uname=request.user.username %}Welcome back, {{ uname }}.{% endblocktrans %}
{% blocktrans count counter=page_obj.paginator.count %}{{ counter }} record{% plural %}{{ counter }} records{% endblocktrans %}
```

Python (`views.py`, `forms.py`, `models.py`, `middleware.py`,
management commands):

```python
from django.utils.translation import gettext as _        # runtime
from django.utils.translation import gettext_lazy as _   # model/form declarations
messages.success(request, _("Vendor added to the vendor list."))
```

Rules used throughout this code base:

* **Never concatenate translated fragments** — use one `blocktrans`.
* `verbose_name` of every model field is translatable, which is what makes the
  Django admin Arabic too.
* Numbers use `{:,}` formatting; dates come from the model fields.
* The **Arabic terms must match the original Access labels** — e.g.
  `File Department = إدارة الملف`, `Execution Method = طريقة التنفيذ`,
  `Estimated Value = القيمة التقديرية`, `Vendor List = قائمة الموردين`,
  `Market = السوق`, `Tenders = المناقصات/المناقصة`. When you invent an English
  label, translate the Arabic back to the wording the accountants already use.

## Translation workflow

```bash
# 1. after adding/changing any {% trans %} or gettext string:
.venv/bin/python manage.py makemessages -l ar

# 2. fill the empty msgstr in locale/ar/LC_MESSAGES/django.po
#    (poEdit, or polib in the venv for bulk edits)

# 3. compile + verify
.venv/bin/python manage.py compilemessages
msgfmt --statistics -o /dev/null locale/ar/LC_MESSAGES/django.po
```

**Definition of done:** `0 fuzzy`, `0 untranslated`, and `manage.py check`
clean. Current state: **388 translated messages, 0 fuzzy, 0 untranslated**
(plus 10 obsolete entries from screens that no longer exist).

Notes:

* `makemessages` picks up `templates/` and `core/*.py`; obsolete entries are
  prefixed `#~` and are harmless.
* After editing `.mo` or `.css`, remember `style.css?v=` in
  `templates/core/base.html` (and `?v=2` in `login.html`) for CSS changes.
* Arabic-Indic digits appear only in *source data* (Access `estimated_value`
  strings); UI numbers stay Western digits via `{:,}`.

## Verifying both languages

```bash
.venv/bin/python tests/test_ar_tenders.py   # Arabic pages + Arabic RFQ flow
.venv/bin/python tests/test_dashboard.py    # EN + AR dashboard assertions
```

Manual spot check: `/en/login/` and `/ar/login/` → 200, log in, then compare
`/en/dashboard/` and `/ar/dashboard/`, `/en/vendor-list/<pk>/` and
`/ar/vendor-list/<pk>/`.
