# 07 · Business workflow

How a request for quotation travels through the app, from the department that
needs something to the vendor list the division assembles.

## The chain

```
1. Department employee      creates an RFQ (Mat. Req. No + line items)
        │                   RFQ.status = draft
        ▼
2. Purchase department      reviews it (submitted / under review)
        │                   chairman_approved + chairman_approved_date when signed
        ▼
3. Approver picks a type    RFQ.market_type = local | foreign
                            RFQ.purchase_method = general tender / direct order / …
        ▼
4. The division picks it up  sidebar "Local Tender" or "Foreign Tender"
        │                    (tenders/local/ · tenders/foreign/)
        ▼
5. Division opens a tender   POST /rfq/<pk>/tender/create/  →  Operation
        │                    (the بيان المهمات that opens the tender)
        ▼
6. Division builds the list  add/remove vendors on the tender page,
                             scoped to the tender's market
```

An `Operation` may also exist **without** an RFQ — all 2,058 tenders imported
from Access are in that state. Those are shown on the RFQ screen above the
table under "RFQs without a tender"; linking is one-directional
(`RFQ.tender → Operation`), so an imported tender can be claimed by an RFQ
later (or opened from one).

## RFQ statuses

`RFQ.Status` (single field, editable in the RFQ form; charted on the
dashboard):

| value | label (EN) | label (AR) |
| --- | --- | --- |
| `draft` | Draft | مسودة |
| `submitted` | Submitted | مُقدَّم |
| `under_review` | Under Review | قيد المراجعة |
| `chairman_approved` | Chairman Approved | موافقة رئيس مجلس الإدارة |
| `rejected` | Rejected | مرفوض |
| `vendor_selection` | Vendor Selection | اختيار الموردين |
| `completed` | Completed | مكتمل |

Supporting flags: `chairman_approved` (bool) + `chairman_approved_date`,
`partial_order_accepted` (bool).

> **Status is advisory today** — nothing in the views enforces transitions.
> The approval step (an approver view that flips `status` and assigns the
> market) is the natural next feature; the model, the dashboard chart and the
> per-division filtering are already in place for it.

## Opening a tender from an RFQ

`rfq_tender_create` (POST only, one tender per RFQ) fills the new `Operation`
from the RFQ:

| `Operation` field | source |
| --- | --- |
| `operation_no` | `max(operation_no) + 1` |
| `market`, `file_dept` | RFQ market → `local` ⇒ `المشتريات المحلية`, `foreign` ⇒ `المشتريات الخارجية` |
| `execution_method` | purchase method (`general_tender → مناقصة عامة`, `direct_order → أمر مباشر`, `limited_tender → مناقصة محدودة`) |
| `task_statement` | RFQ project (fallback `RFQ <request_number>`) |
| `requesting_entity` | department name |
| `estimated_value`, `budget`, `requisition_rec_date`, `sap_no`, `cost_center` | copied from the RFQ |
| `currency` | `جنيه مصرى` |
| `vendor_register_executor` | full name of the logged-in user |
| `year` | first 4 chars of `budget_year` |

Then `rfq.tender = operation` and the user lands back on the RFQ page, whose
"Tender Details" section now shows general info, value, milestone dates, notes
and the vendor list.

If the RFQ has no tender yet, its detail page shows the empty state with an
**Open Vendor List** button (the Access wording) — same POST endpoint.

## Local vs foreign

* **Sidebar is the only switch.** There are no tab/segment buttons anywhere;
  `/vendor-list/` (old link) simply redirects to `/rfq/`.
* `Operation.market` (`local`/`foreign`) is derived on import from the Access
  file department + currency ([05](05-access-data-pipeline.md)); currently
  **1,694 local / 364 foreign**.
* Each division page (`tenders/<division>/`) is `_tender_list(market=…)` with
  its own "RFQs without a tender" block filtered by `RFQ.market_type`, and its
  **New RFQ** button passes `?market=<division>` so the form opens pre-set.
* `?market=local|foreign` still narrows any list URL for deep links.

## Building the vendor list

The tender page (`/vendor-list/<pk>/`) and the RFQ page share
`_vendor_list_card.html`:

* **Current list** — table of `OperationVendor` rows (vendor, e-mail, activity,
  statuses) with a *Remove* button per row.
* **Search / add** — a `?vq=` search box over name (AR/EN), supplier id,
  country and activity code; results show up to 25 *candidates* that are not on
  the list yet, each with an *Add* button (POST
  `…/vendors/add/` with `supplier_id` and a `next` field pointing back).
* **Market scope** — `_scoped_vendors(market, scope)`:

  | market | vendors included |
  | --- | --- |
  | `local` | `booklet_type = محلى`, or blank booklet with country مصر/Egypt |
  | `foreign` | `booklet_type = خارجى`, or blank booklet with a non-Egypt country |
  | `scope=all` | everything (toggle on the card: "Local/Foreign vendors \| All vendors") |

  Totals today: 4,584 local · 2,414 foreign of 8,878.
* Adding a vendor already on the list is a **warning**, not an error, and never
  creates a duplicate row; removing is idempotent.

## Vendor file & activity registration

`/vendors/<pk>/` (Access "Vendor View") shows the vendor file — contacts as
live links — plus:

* **Activity registrations** (`VendorActivity`, 22,945 rows): add via
  `POST …/activities/add/` (sub activity + registration type + capacity +
  notes); duplicates warn; each row can be removed individually.
* **Operations** the vendor appears on, newest `operation_no` first.

New vendors (`/vendors/new/`) get `supplier_id = max + 1`; the form cleans
contacts on save ([05](05-access-data-pipeline.md)).

## Roles and division of work

`EmployeeAccess` (per AD employee) and `DepartmentAccess` (per department)
carry the flags:

```
can_view_rfq, can_create_rfq, can_edit_rfq, can_delete_rfq, can_approve_rfq,
can_view_vendors, can_create_vendors, can_view_reports, can_view_admin
role ∈ {viewer, requester, purchaser, manager, admin}   is_active
```

**Today these flags gate *login* only** (through
`EmployeeAccessMiddleware` — an authenticated user without an active row is
sent back to the login screen with "Access denied"); individual views are
protected by `@login_required` alone. Enforcing the per-action flags is the
second half of the approval workflow above — see
[08-auth-and-access-control.md](08-auth-and-access-control.md).
