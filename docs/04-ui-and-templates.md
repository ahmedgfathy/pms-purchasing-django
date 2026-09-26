# 04 · UI, templates and styling

Server-rendered HTML, one stylesheet, ~85 lines of vanilla JS. No framework,
no bundler, no CDN-hosted scripts.

## Template inventory (`templates/core/`)

| Template | Used by | Content |
| --- | --- | --- |
| `base.html` | every app page | shell: topbar, language switcher, sidebar, messages, footer |
| `login.html` | `CustomLoginView` | standalone Win95 login window (no sidebar) |
| `dashboard.html` | `dashboard` | stat cards, donuts, bars, RFQ workflow, DB summary |
| `rfq_list.html` | `_tender_list()` (all list views) | header + orphan RFQ block + `_tender_list_table.html` |
| `_tender_list_table.html` | partial | filters, sortable-ish table, pagination |
| `rfq_form.html` | `rfq_create`, `rfq_edit` | RFQ fields + line-items formset |
| `rfq_detail.html` | `rfq_detail` | RFQ file + tender details/vendor list when linked |
| `rfq_confirm_delete.html` | `rfq_delete` | delete confirmation |
| `operation_detail.html` | `operation_detail` | one tender + `_vendor_list_card.html` |
| `_tender_details.html` | partial (shared) | general info / value / milestone dates of a tender |
| `_tender_notes.html` | partial (shared) | Access "notes" memo fields |
| `_vendor_list_card.html` | partial (shared) | vendor sub-list + add/search (incl. E-mail column) |
| `vendor_register.html` | `vendor_register` | register table with filters |
| `vendor_detail.html` | `vendor_detail` | vendor file: contacts, activities, operations |
| `vendor_form.html` | `vendor_create`, `vendor_edit` | create/edit vendor |
| `_chart_legend.html` | partial | donut legend, used twice by the dashboard |

Blocks every page template fills: `title`, `content`, optional `extra_js`.
`base.html` also exposes the container (`{% block content %}` inside
`section.content`) where Django messages are rendered as `.message.*` divs.

## The shell (`base.html`)

```
body
 └ div.app
    ├ div.topbar           brand + language switcher (EN/AR flag buttons)
    │                       + user chip + Sign Out (data-accel="g")
    ├ div.app-shell
    │  ├ aside.sidebar     brand block + ul.side-nav (see below)
    │  └ section.content   flash messages + {% block content %}
    └ div.app-footer       © 2026 PMS Purchasing · v1.0
 script js/app.js?v=1
```

Sidebar entries (label · `data-accel` key · URL):

| Item | Key | URL |
| --- | --- | --- |
| Dashboard | `d` | `/dashboard/` |
| RFQ | `r` | `/rfq/` |
| Vendor Register | `n` | `/vendors/` |
| Foreign Tender | `f` | `/tenders/foreign/` |
| Local Tender | `l` | `/tenders/local/` |
| Market | `k` | `/dashboard/` (placeholder — links to the dashboard) |
| Reports | `p` | `/dashboard/` (placeholder — links to the dashboard) |
| Administration | `a` | `/admin/` (opens in a new tab) |

There is deliberately **no "Vendor List" sidebar entry** (`/vendor-list/` only
redirects to `/rfq/`) and **no local/foreign tab buttons**: the sidebar is the
single switch between divisions.

The language switcher is a POST form to `set_language` carrying `next` =
current full path, so switching language keeps you on the same record.

## Win95 theme system (`static/css/style.css`, 2,211 lines)

Tokens in `:root`:

```css
--chrome-dark/--chrome-mid/--chrome/--chrome-light   window chrome greys
--panel --bg --text --text-dim --border --highlight --shadow
--accent:#1d4ed8  --accent-bright:#3b82f6  --accent-light:#93c5fd
--accent-dark:#1e3a8a  --accent-deep:#172554  --accent-soft:#dbeafe  --focus:#2563eb
```

Signature pieces:

* **3D bevels** — `.window`, `.titlebar`, `.btn`, `.panel`, `.field` use
  paired `border-top/left: --highlight` + `border-bottom/right: --shadow`
  (and the inverted variant for pressed/inset states).
* **Buttons** — `.btn`, `.btn-primary` (blue accent), `.btn-secondary`,
  `.btn-sm`/`.btn-small`, `.btn-danger`, `.btn-ghost`.
* **Layout** — `.app-shell` grid with fixed `.sidebar` and fluid `.content`;
  `.page-header`, `.toolbar-row`, `.filter-row`/`.filter-bar`, `.panel`,
  `.form-grid`, `.form-section`, `.form-actions`, `.table-wrap`.
* **Tables** — `.data-table` with striped rows, `.col-actions`, `.btn-small`;
  `table.data-clickable tbody tr[data-href]` makes rows navigate on click.
* **Dashboard** — `.stat-cards`/`.stat-card`, `.chart`, `.bar`, `.bar-label`,
  `.bar-value`, `.donut`, plus `.contact-link` for e-mail/website anchors.
* **Feedback** — `.message.success/warning/error`, `.flash`, `.target-flash`
  (keyboard-accelerator feedback), `.field-errors`, `.errorbar`.
* **Accessibility** — visible `:focus-visible` outlines in `--focus`; the page
  gets `dir="rtl"` and `lang="ar"` when Arabic is active, and `.contact-link`
  is explicitly RTL-safe (`direction: ltr; unicode-bidi: plaintext`).

Cache busting: `style.css?v=9` in `base.html` (and `?v=2` in `login.html` —
**bump both** when the CSS changes), `app.js?v=1`.

Fonts: Cairo from Google Fonts with a local fallback stack
(`"MS Sans Serif", "Segoe UI", Tahoma, Verdana, Arial, sans-serif`).

## JavaScript (`static/js/app.js`, 85 lines)

1. **Accelerators** — `Ctrl+Shift+<letter>` activates the element carrying
   `data-accel="<letter>"` (and its `data-target` selector), flashing it for
   900 ms.
2. **Clickable rows** — `tr[data-href]` navigates unless the click landed on a
   link/button.
3. Small niceties (focus/flash helpers).

The dashboard needs **no JavaScript at all**: donuts are SVG built in Python
(`core/charts.py`), bars are `width: %` divs.

## Styling conventions

* Class names are semantic and kebab-case; never inline `style=` in templates
  except tiny layout fixes already present in the code base.
* Every new user-visible string must be translatable (`{% trans %}`), and the
  Arabic form must use the original Access terminology ([09](09-internationalization.md)).
* Forms: widgets get `class="form-input"` through the form classes
  (`StyledFormMixin`), so templates never style inputs individually.
