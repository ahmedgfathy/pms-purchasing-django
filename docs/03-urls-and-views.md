# 03 · URLs and views

All routes are declared in `core/urls.py` and mounted under `i18n_patterns`
(⇒ every path below exists as `/en/...` and `/ar/...`).

## Route table

| URL | name | View | Methods | Purpose |
| --- | --- | --- | --- | --- |
| `""` | `home` | `home` | GET | authenticated → `dashboard`, anonymous → `login` |
| `login/` | `login` | `CustomLoginView` | GET/POST | AD or local login, redirects to `dashboard` |
| `logout/` | `logout` | `logout_view` | GET | logs out, redirects to `login` |
| `dashboard/` | `dashboard` | `dashboard` | GET | statistics screen ([06](06-dashboard.md)) |
| `rfq/` | `rfq_list` | `rfq_list` | GET | **the tender list** + "RFQs without a tender" |
| `rfq/create/` | `rfq_create` | `rfq_create` | GET/POST | new RFQ (+ line items formset), `?market=` pre-sets the division |
| `rfq/<pk>/` | `rfq_detail` | `rfq_detail` | GET | RFQ file; when `rfq.tender` exists also the tender details + vendor list |
| `rfq/<pk>/edit/` | `rfq_edit` | `rfq_edit` | GET/POST | edit RFQ + items |
| `rfq/<pk>/delete/` | `rfq_delete` | `rfq_delete` | GET/POST | confirm + delete |
| `rfq/<pk>/tender/create/` | `rfq_tender_create` | `rfq_tender_create` | **POST** | open the Access-style tender for the RFQ (one per RFQ) |
| `tenders/local/` | `local_tender` | `local_tender` | GET | tender list scoped to `market=local` |
| `tenders/foreign/` | `foreign_tender` | `foreign_tender` | GET | tender list scoped to `market=foreign` |
| `vendor-list/` | `vendor_list` | `vendor_list` | GET | **302 → `rfq_list`** (the sidebar entry was removed) |
| `vendor-list/<pk>/` | `operation_detail` | `operation_detail` | GET | one tender: general info, value, dates, notes, vendor list |
| `vendor-list/<pk>/vendors/add/` | `operation_vendor_add` | `operation_vendor_add` | **POST** | put a vendor on the list (`supplier_id`) |
| `vendor-list/<pk>/vendors/<vendor_pk>/remove/` | `operation_vendor_remove` | `operation_vendor_remove` | **POST** | drop a vendor from the list |
| `vendors/` | `vendor_register` | `vendor_register` | GET | vendor register with search/filters/paging |
| `vendors/<pk>/` | `vendor_detail` | `vendor_detail` | GET | vendor file: contacts, activity registrations, operations |
| `vendors/new/` | `vendor_create` | `vendor_create` | GET/POST | create a vendor (Access "New Vendor Enter") |
| `vendors/<pk>/edit/` | `vendor_edit` | `vendor_edit` | GET/POST | edit a vendor |
| `vendors/<pk>/activities/add/` | `vendor_activity_add` | `vendor_activity_add` | **POST** | register the vendor on a sub activity |
| `vendors/<pk>/activities/<activity_pk>/remove/` | `vendor_activity_remove` | `vendor_activity_remove` | **POST** | remove one registration |

Everything except `home`, `login`, `logout` and the language switcher is
`@login_required(login_url="login")`, and additionally gated by
`EmployeeAccessMiddleware` ([08](08-auth-and-access-control.md)).
Django admin sits at `/en/admin/`.

## List screens — `_tender_list()`

`rfq_list`, `local_tender`, `foreign_tender` and `vendor_list` all funnel into
one helper (`core/views.py`) that renders `core/rfq_list.html`:

```python
_tender_list(request, market=None, default_title=None,
             template="core/rfq_list.html", extra=None)
```

* `market` — `local`/`foreign`/`None` (all). The GET parameter `?market=` can
  override it (kept for deep links; the sidebar is the real switch).
* Query parameters: `q` (task statement / requesting entity / project / SAP no,
  or the operation number when numeric), `year`, `status` (overall status),
  `region`, `dept` (file department), `page`.
* Context: `page_obj` (25 per page), `query_string` (all params except `page`),
  `year_choices`/`status_choices`/`region_choices`/`dept_choices` (distinct
  values), `market_label`, and the totals `total_operations`, `total_links`,
  `total_vendors`.
* `extra` adds `orphan_rfqs` + `show_new_rfq` for the RFQ screen.

`rfq_list` also lists **RFQs without a tender** above the table; each row of the
table is an `Operation` (one row per tender) with its Mat. Req. No cell linking
to the related `RFQ`.

## Vendor picker (shared by tender page and RFQ page)

`_vendor_picker_context(request, operation, vendors)` builds:

* `candidates` — vendors **not yet** on this list, filtered by `?vq=` (name /
  supplier id / country / activity code), optionally by `?activity=`,
* `scope` — `market` (default) or `all`; the toggle POSTs/links `?scope=all`,
* `market` — the tender's market, used by `_scoped_vendors()` to limit the
  candidates to the right booklet ([07](07-business-workflow.md)),
* `search`, `activity_choices`.

`_redirect_target(request, default)` reads the optional `next` POST field so
add/remove can return to whichever page submitted the form (RFQ detail or
tender detail).

## Create/update semantics

* **RFQ** — `RFQForm` + `RFQItemFormSet` (inline, `extra=1`, `can_delete=True`).
  `rfq_create` sets `created_by = request.user` and honours `?market=`.
* **Tender** — `rfq_tender_create` (POST only): allocates
  `max(operation_no)+1`, fills market + file department from the RFQ's market,
  execution method from the purchase method, currency `جنيه مصرى`,
  task statement from the project, executor from the logged-in user, and links
  `rfq.tender = operation`. A second call is a no-op redirect.
* **Vendor** — `VendorForm.clean()` normalizes contacts through
  `core.contacts.clean_contacts()`; `supplier_id` is assigned max+1 when new.
* **Activity registration** — duplicates are refused with a warning message
  rather than a validation error.

All POST handlers follow *validate → act → `messages.*` → redirect (PRG)*.

## Dashboard helpers

| Helper | Role |
| --- | --- |
| `_dashboard_context()` | all aggregates for the dashboard (see [06](06-dashboard.md)) |
| `_donut(title, rows, colors)` | one SVG donut dict (geometry from `core/charts.py`) |
| `_bars(title, rows, limit, other, formatter)` | one CSS bar chart dict |
| `_count_by(field, blank)` | `GROUP BY` counter used by the bar charts |
| `_scoped_vendors(market, scope)` | local/foreign/all vendor queryset |
| `_distinct(model, field)` | sorted distinct values for filter dropdowns |
| `_vendor_search(qs, search)` | name/supplier-id/e-mail/country/activity search |
