# 02 · Data model

Seventeen models in `core/models.py`. Two worlds meet here:

* **The RFQ world** — what the purchasing department creates day to day
  (`Department`, `Vessel`, `CostCenter`, `RFQ`, `RFQItem`).
* **The Access world** — everything imported from `2026-data.accdb`
  (`Vendor`, `Operation`, `OperationVendor`, `VendorActivity` and the code
  lookups `Project`, `ClientCode`, `Location`, `CostCenter`, `MainActivity`,
  `SubActivity`).

`CostCenter` belongs to both worlds: it is the lookup table the Access import
fills and the FK an RFQ points at.

## Entity relationships

```
Department ─< RFQ >─ Vessel
     │            └── CostCenter
     │                 └── Operation (RFQ.tender, one tender per RFQ, SET_NULL)
     └── EmployeeAccess          │
DepartmentAccess (1:1 Department)│
                                 ├── OperationVendor >── Vendor
                                 │                          │
                                 └── (lookup FKs)           └── VendorActivity >── SubActivity >── MainActivity
                                          │
                              Project  ClientCode  Location  CostCenter
                                          └── all keyed by `code` (to_field), not by id
```

Notes on the link semantics:

* `RFQ.tender` → `Operation`, `null=True`, `on_delete=SET_NULL`: re-importing
  Access data creates new `Operation` rows, so links are dropped (set to NULL)
  instead of deleting RFQs.
* `Operation.project / client / cost_center / location` are FKs whose
  `to_field="code"` — children store the *code* string, which is why the import
  validates codes against the lookup tables before assigning them.
* `Vendor.supplier_id` is the **primary key** (Access `Supplier ID` is a
  non-auto number assigned by Access; the import keeps it and the form
  assigns max+1 on save).
* `VendorActivity.vendor` → `Vendor.supplier_id`, `sub_activity` →
  `SubActivity.code`; `OperationVendor.vendor` → `Vendor.supplier_id`.

## Access quirks that shaped the schema

| Quirk in `2026-data.accdb` | How the model handles it |
| --- | --- |
| `Supplier ID` is a non-auto PK | `Vendor.supplier_id = IntegerField(primary_key=True)` |
| `Oprations.[رقم العملية]` is **not** unique (170 / 1929 duplicated) | `Operation.operation_no` is a plain field; `id` is the real key, `RFQ.tender` points at `id` |
| 92 `Vendor Opration` rows have an empty operation no | `OperationVendor.operation` is nullable, the raw number is kept in `operation_no` |
| Estimated value is text with Arabic-Indic digits | `Operation.estimated_value` is `DecimalField`, parsed by the importer |
| Access `Memo` columns | `TextField` (`tech_specs`, notes, memos, `email1..3`, `website`, …) — e-mail fields reach 929 chars |
| Hyperlink columns (`display#target#`) | cleaned by `core/contacts.py` during import (see [05](05-access-data-pipeline.md)) |
| Blank/absent reference codes | every lookup FK is `null=True, blank=True`; the importer stores `NULL` for unknown codes |
| Access boolean-ish columns | `BooleanField` with `False` default, parsed from yes/no junk |

## Counts in the shipped database

| Table | Rows |
| --- | --- |
| `Project` | 19 |
| `ClientCode` | 63 |
| `Location` | 10 |
| `CostCenter` | 72 |
| `MainActivity` | 107 |
| `SubActivity` | 846 |
| `Vendor` | 8,878 |
| `Operation` | 2,058 (1,694 local / 364 foreign) |
| `VendorActivity` | 22,945 |
| `OperationVendor` | 6,436 (758 tenders legitimately have no vendors) |
| `RFQ` | 0 — created by users through the UI |
| `auth_user` | 1 (`admin`) |

`Department`, `Vessel` and the two access models are *not* imported: they are
seeded by `create_initial_access.py` / the admin.

## Choices (enumerations)

```python
RFQ.MarketType      local | foreign
RFQ.PurchaseMethod  general_tender | direct_order | budgetary | negotiation |
                    valid_contract | limited_tender
RFQ.Status          draft | submitted | under_review | chairman_approved |
                    rejected | vendor_selection | completed
RFQ.BudgetType      assets | projects | current
Operation.Market    local | foreign        (derived from the Access file department)
Vendor.BookletType  محلى | خارجى …        (Arabic literals from Access)
```

Only three purchase methods map to an Access execution method when a tender is
opened from an RFQ: `general_tender → مناقصة عامة`, `direct_order → أمر مباشر`,
`limited_tender → مناقصة محدودة`; everything else leaves the field blank.

## Model reference

Field order follows `model._meta.get_fields()` (concrete fields after the
reverse relations). `notes` columns: `null` = nullable, `blank` = form-optional,
`max=` = `max_length`, `-> X.y` = foreign key target, `default=` = field default.

### `ClientCode`

table `core_clientcode`

> ClientCode(id, code, name, note)

- `operations` — reverse -> Operation
- `id` — BigAutoField — ID — blank; pk
- `code` — CharField — Client Code — max=255
- `name` — CharField — Client Name — max=255
- `note` — CharField — Note — blank; default=''; max=255

### `CostCenter`

table `core_costcenter`

> CostCenter(id, name, code, note)

- `rfqs` — reverse -> RFQ
- `operations` — reverse -> Operation
- `id` — BigAutoField — ID — blank; pk
- `name` — CharField — Name — max=255
- `code` — CharField — Code — max=255
- `note` — CharField — Note — blank; default=''; max=255

### `Department`

table `core_department`

> Department(id, name, name_ar, code)

- `rfqs` — reverse -> RFQ
- `employees` — reverse -> EmployeeAccess
- `access_config` — reverse -> DepartmentAccess
- `id` — BigAutoField — ID — blank; pk
- `name` — CharField — Name — max=200
- `name_ar` — CharField — Name (Arabic) — blank; default=''; max=200
- `code` — CharField — Code — max=255

### `DepartmentAccess`

table `core_departmentaccess`

> Which departments can see which modules.

- `id` — BigAutoField — ID — blank; pk
- `department` — reverse -> Department
- `can_view_rfq` — BooleanField — can view rfq — default=True
- `can_create_rfq` — BooleanField — can create rfq — default=True
- `can_view_vendors` — BooleanField — can view vendors — default=True
- `can_view_reports` — BooleanField — can view reports — default=True

### `EmployeeAccess`

table `core_employeeaccess`

> Controls which AD employees can login and what they see.

- `id` — BigAutoField — ID — blank; pk
- `employee_id` — CharField — Employee ID — max=50
- `full_name` — CharField — Full Name — blank; default=''; max=200
- `department` — ForeignKey — Department — null; blank; -> Department.id
- `role` — CharField — Role — default='viewer'; max=20
- `is_active` — BooleanField — Active — default=True
- `can_view_rfq` — BooleanField — Can view RFQ — default=True
- `can_create_rfq` — BooleanField — Can create RFQ — default=False
- `can_edit_rfq` — BooleanField — Can edit RFQ — default=False
- `can_delete_rfq` — BooleanField — Can delete RFQ — default=False
- `can_approve_rfq` — BooleanField — Can approve RFQ — default=False
- `can_view_vendors` — BooleanField — Can view vendors — default=True
- `can_create_vendors` — BooleanField — Can create vendors — default=False
- `can_view_reports` — BooleanField — Can view reports — default=True
- `can_view_admin` — BooleanField — Can view administration — default=False
- `created_at` — DateTimeField — Created at — blank

### `Location`

table `core_location`

> Location(id, code, name, note)

- `operations` — reverse -> Operation
- `id` — BigAutoField — ID — blank; pk
- `code` — CharField — Location Code — max=255
- `name` — CharField — Location Name — max=255
- `note` — CharField — Note — blank; default=''; max=255

### `MainActivity`

table `core_mainactivity`

> [Tasks] — main activity categories (Arabic + English names).

- `sub_activities` — reverse -> SubActivity
- `id` — BigAutoField — ID — blank; pk
- `code` — CharField — Activity Code — max=10
- `name_ar` — CharField — Name (Arabic) — max=100
- `name_en` — CharField — Name (English) — blank; default=''; max=100

### `Operation`

table `core_operation`

> [Oprations] — record source of the legacy 'Vendor List' screen.

- `rfqs` — reverse -> RFQ
- `operation_vendors` — reverse -> OperationVendor
- `id` — BigAutoField — ID — blank; pk
- `operation_no` — IntegerField — Operation No
- `file_dept` — CharField — File Department — default=''; max=50
- `market` — CharField — Market — default=Operation.Market.LOCAL; max=10
- `execution_method` — CharField — Execution Method — blank; default=''; max=50
- `region` — CharField — Region — default=''; max=50
- `year` — CharField — Year — default=''; max=4
- `overall_status` — CharField — Overall Status — default=''; max=50
- `project_name` — CharField — Project Name — blank; default=''; max=50
- `requesting_entity` — CharField — Requesting Entity — blank; default=''; max=50
- `executor_name` — CharField — Executor Name — blank; default=''; max=50
- `task_statement` — CharField — Task Statement — default=''; max=255
- `tech_specs` — TextField — Technical Specs — blank; default=''
- `vendor_list_handover_date` — DateField — Vendor List Handover Date — null; blank
- `list_approval_date` — DateField — Vendor List Approval Date — null; blank
- `execution_handover_date` — DateField — Execution Handover Date — null; blank
- `tender_date` — DateField — Tender Date — null; blank
- `technical_opening_date` — DateField — Technical Opening Date — null; blank
- `offers_sent_date` — DateField — Offers Sent Date — null; blank
- `final_tech_report_date` — DateField — Final Technical Report Date — null; blank
- `financial_opening_date` — DateField — Financial Opening Date — null; blank
- `committee_presentation_date` — DateField — Committee Presentation Date — null; blank
- `committee_approval_date` — DateField — Committee Approval Date — null; blank
- `list_sent_entity_date` — DateField — List Sent to Entity Date — null; blank
- `list_sent_bd_date` — DateField — List Sent to BD Date — null; blank
- `list_approved_entity_date` — DateField — List Approved by Entity Date — null; blank
- `list_approved_bd_date` — DateField — List Approved by BD Date — null; blank
- `followup_handover_date` — DateField — Follow-up Handover Date — null; blank
- `list_preparation_date` — DateField — List Preparation Date — null; blank
- `requisition_rec_date` — DateField — Requisition Received Date — null; blank
- `till_now` — DateTimeField — Till Now — null; blank
- `notes` — TextField — Notes — blank; default=''
- `execution_notes` — TextField — Execution Notes — blank; default=''
- `followup_notes` — TextField — Follow-up Notes — blank; default=''
- `request_notes` — TextField — Request Notes — blank; default=''
- `vendor_list_memo` — TextField — Vendor List — blank; default=''
- `purchasing_department_memo` — TextField — Purchasing Department — blank; default=''
- `estimated_value` — DecimalField — Estimated Value — null; blank
- `currency` — CharField — Currency — blank; default=''; max=50
- `budget` — CharField — Budget — blank; default=''; max=50
- `general_supplies` — CharField — General Supplies — blank; default=''; max=255
- `tender_days` — CharField — Tender Days — blank; default=''; max=50
- `total_days` — IntegerField — Total Days — null; blank
- `all_seq` — IntegerField — Sequence (ALL) — null; blank
- `maker_name` — CharField — Maker Name — blank; default=''; max=255
- `project` — ForeignKey — Project Code — null; blank; -> Project.code
- `client` — ForeignKey — Client Code — null; blank; -> ClientCode.code
- `cost_center` — ForeignKey — Cost Center — null; blank; -> CostCenter.code
- `location` — ForeignKey — Location Code — null; blank; -> Location.code
- `year_code` — IntegerField — Year Code — null; blank
- `vendor_register_executor` — CharField — Vendor Register Executor — blank; default=''; max=50
- `request_receiver` — CharField — Request Receiver — default=''; max=50
- `followup_name` — CharField — Follow-up Person — blank; default=''; max=50
- `po_status` — CharField — Purchase Order Status — default=''; max=255
- `sap_no` — CharField — SAP No — blank; default=''; max=255

### `OperationVendor`

table `core_operationvendor`

> [Vendor Opration] — the vendor list of one operation (the sub form).

- `id` — BigAutoField — ID — blank; pk
- `operation` — ForeignKey — Operation — null; blank; -> Operation.id
- `operation_no` — IntegerField — Operation No — null; blank
- `vendor` — ForeignKey — Vendor — -> Vendor.supplier_id
- `serial` — IntegerField — Serial — null; blank
- `year` — CharField — Year — blank; default=''; max=4
- `bid_status` — CharField — Bid Status — blank; default=''; max=255
- `advance_security_status` — CharField — Advance Security Status — blank; default=''; max=255
- `final_security_status` — CharField — Final Security Status — blank; default=''; max=255
- `supply_status` — CharField — Supply Status — blank; default=''; max=255
- `technical_study` — CharField — Technical Study — blank; default=''; max=255
- `technical_match` — CharField — Technical Match — blank; default=''; max=255
- `technical_rejection_reason` — CharField — Technical Rejection Reason — blank; default=''; max=255
- `delay_penalty` — CharField — Delay Penalty — blank; default=''; max=255
- `po_issuance_status` — CharField — PO Issuance Status — blank; default=''; max=255
- `certificates_status` — CharField — Certificates Status — blank; default=''; max=255
- `advance_security_type` — CharField — Advance Security Type — blank; default=''; max=255
- `notes` — CharField — Notes — blank; default=''; max=255
- `access_id` — IntegerField — Access ID — null; blank

### `Project`

table `core_project`

> Project(id, code, name, client_name, note)

- `operations` — reverse -> Operation
- `id` — BigAutoField — ID — blank; pk
- `code` — CharField — Project Code — max=255
- `name` — CharField — Project Name — max=255
- `client_name` — CharField — Client Name — blank; default=''; max=200
- `note` — CharField — Note — blank; default=''; max=255

### `RFQ`

table `core_rfq`

> RFQ(id, request_number, sap_number, requesting_department, vessel, project, location, cost_center, tender, preparation_date, requisition_rec_date, supply_period, market_type, purchase_method, partial_order_accepted, status, chairman_approved, chairman_approved_date, budget_year, gl_account, emf_number, estimated_value, budget_type, budget_code, book_number, warranty_notes, delivery_notes, attachment, created_by, created_at, updated_at)

- `items` — reverse -> RFQItem
- `id` — BigAutoField — ID — blank; pk
- `request_number` — CharField — Mat. Req. No — max=50
- `sap_number` — CharField — SAP No — blank; default=''; max=50
- `requesting_department` — ForeignKey — Department — -> Department.id
- `vessel` — ForeignKey — Vessel — null; blank; -> Vessel.id
- `project` — CharField — Project — blank; default=''; max=200
- `location` — CharField — Location — blank; default='Main HQ'; max=200
- `cost_center` — ForeignKey — Cost Center — null; blank; -> CostCenter.id
- `tender` — ForeignKey — Tender — null; blank; -> Operation.id
- `preparation_date` — DateField — Preparation Date
- `requisition_rec_date` — DateField — Rec. Date — null; blank
- `supply_period` — CharField — Supply Period — blank; default=''; max=200
- `market_type` — CharField — Market — default=RFQ.MarketType.LOCAL; max=20
- `purchase_method` — CharField — Purchase Method — default=RFQ.PurchaseMethod.GENERAL_TENDER; max=20
- `partial_order_accepted` — BooleanField — Partial order accepted — default=False
- `status` — CharField — Status — default=RFQ.Status.DRAFT; max=20
- `chairman_approved` — BooleanField — Chairman Approved — default=False
- `chairman_approved_date` — DateField — Approved Date — null; blank
- `budget_year` — CharField — Budget Year — blank; default=''; max=10
- `gl_account` — CharField — G.L. Account — blank; default=''; max=30
- `emf_number` — CharField — E.M.F. — blank; default=''; max=30
- `estimated_value` — DecimalField — Estimated Value (EGP) — default=0
- `budget_type` — CharField — Budget Type — default=RFQ.BudgetType.CURRENT; max=20
- `budget_code` — CharField — Budget Code — blank; default=''; max=30
- `book_number` — CharField — Book Number — blank; default=''; max=30
- `warranty_notes` — TextField — Warranty Notes — blank; default=''
- `delivery_notes` — TextField — Delivery Notes — blank; default=''
- `attachment` — FileField — Hard Copy — blank; default=''; max=100
- `created_by` — ForeignKey — created by — null; -> User.id
- `created_at` — DateTimeField — Created at — blank
- `updated_at` — DateTimeField — Updated at — blank

### `RFQItem`

table `core_rfqitem`

> RFQItem(id, rfq, line_number, description, unit, quantity, inventory, store_code, maker)

- `id` — BigAutoField — ID — blank; pk
- `rfq` — ForeignKey — rfq — -> RFQ.id
- `line_number` — PositiveIntegerField — Line No.
- `description` — TextField — Description
- `unit` — CharField — Unit — default='Piece'; max=20
- `quantity` — PositiveIntegerField — Qty
- `inventory` — CharField — Inventory — blank; default=''; max=50
- `store_code` — CharField — Store Code — blank; default=''; max=30
- `maker` — CharField — Maker — blank; default=''; max=100

### `SubActivity`

table `core_subactivity`

> [Tasks sub] — sub activities under a main activity.

- `vendors` — reverse -> VendorActivity
- `id` — BigAutoField — ID — blank; pk
- `code` — CharField — Sub Activity Code — max=10
- `main_activity` — ForeignKey — Main Activity — -> MainActivity.code
- `name_ar` — CharField — Name (Arabic) — max=150
- `name_en` — CharField — Name (English) — blank; default=''; max=150

### `Vendor`

table `core_vendor`

> [Vendors] — the vendor register (سجل الموردين), 8.8k rows in 2026-data.

- `activities` — reverse -> VendorActivity
- `operation_links` — reverse -> OperationVendor
- `supplier_id` — IntegerField — Supplier ID — pk
- `name_ar` — CharField — Vendor Name (Arabic) — max=75
- `name_en` — CharField — Vendor Name (English) — blank; default=''; max=75
- `booklet_no` — IntegerField — Booklet No — null; blank
- `booklet_type` — CharField — Booklet Type — blank; default=''; max=10
- `category` — CharField — Category — blank; default=''; max=255
- `sab_no` — CharField — SAP No. — blank; default=''; max=255
- `agent` — CharField — Agent — blank; default=''; max=50
- `country` — CharField — Country — blank; default=''; max=50
- `address` — CharField — Address — blank; default=''; max=255
- `website` — TextField — Website — blank; default=''
- `phone1` — CharField — Phone 1 — blank; default=''; max=50
- `phone2` — CharField — Phone 2 — blank; default=''; max=50
- `phone3` — CharField — Phone 3 — blank; default=''; max=50
- `fax1` — CharField — Fax 1 — blank; default=''; max=50
- `fax2` — CharField — Fax 2 — blank; default=''; max=50
- `mobile1` — CharField — Mobile 1 — blank; default=''; max=50
- `mobile2` — CharField — Mobile 2 — blank; default=''; max=50
- `mobile3` — CharField — Mobile 3 — blank; default=''; max=50
- `email1` — TextField — E-mail 1 — blank; default=''
- `email2` — TextField — E-mail 2 — blank; default=''
- `email3` — TextField — E-mail 3 — blank; default=''
- `agent_address` — CharField — Agent Address — blank; default=''; max=255
- `agent_phone1` — CharField — Agent Phone 1 — blank; default=''; max=50
- `agent_phone2` — CharField — Agent Phone 2 — blank; default=''; max=50
- `agent_phone3` — CharField — Agent Phone 3 — blank; default=''; max=50
- `agent_fax1` — CharField — Agent Fax 1 — blank; default=''; max=50
- `agent_fax2` — CharField — Agent Fax 2 — blank; default=''; max=50
- `agent_fax3` — CharField — Agent Fax 3 — blank; default=''; max=50
- `agent_mobile1` — CharField — Agent Mobile 1 — blank; default=''; max=50
- `agent_mobile2` — CharField — Agent Mobile 2 — blank; default=''; max=50
- `agent_mobile3` — CharField — Agent Mobile 3 — blank; default=''; max=50
- `agent_email1` — TextField — Agent E-mail 1 — blank; default=''
- `agent_email2` — TextField — Agent E-mail 2 — blank; default=''
- `agent_email3` — TextField — Agent E-mail 3 — blank; default=''
- `committee_no` — CharField — Committee No — blank; default=''; max=50
- `committee_date` — DateField — Committee Date — null; blank
- `registration_status` — CharField — Registration Status — blank; default=''; max=50
- `registration_status_new` — CharField — Registration Status (new) — default=''; max=50
- `data_registered` — CharField — Data Registered By — blank; default=''; max=255
- `commercial_register` — CharField — Commercial Register — blank; default=''; max=50
- `commercial_register_expiry` — DateField — Commercial Register Expiry — null; blank
- `tax_card` — CharField — Tax Card — blank; default=''; max=50
- `tax_card_expiry` — DateField — Tax Card Expiry — null; blank
- `vat_registration` — CharField — VAT Registration — blank; default=''; max=50
- `vat_expiry` — DateField — VAT Expiry — null; blank
- `contact_person` — CharField — Contact Person — blank; default=''; max=50
- `owner_name` — CharField — Owner Name — blank; default=''; max=50
- `capital_amount` — IntegerField — Capital Amount — null; blank
- `capital_currency` — CharField — Capital Currency — blank; default=''; max=50
- `is_local_registered` — BooleanField — Registered locally — default=False
- `is_foreign_registered` — BooleanField — Registered abroad — default=False
- `is_suspended` — BooleanField — Suspended — default=False
- `is_cancelled` — BooleanField — Cancelled — default=False
- `is_flagged` — BooleanField — Flagged — default=False
- `certified` — CharField — A Certified — blank; default=''; max=20
- `notes` — CharField — Notes — blank; default=''; max=255
- `notes2` — TextField — Notes 2 — blank; default=''
- `special_notes` — CharField — Special Notes — blank; default=''; max=255
- `free_zone` — CharField — Free Zone — blank; default=''; max=255
- `agency_documents` — TextField — Agency Documents — blank; default=''
- `cd_vendor` — TextField — CD Vendor — blank; default=''
- `committee_file` — TextField — Committee File — blank; default=''
- `access_id` — IntegerField — Access ID — null; blank

### `VendorActivity`

table `core_vendoractivity`

> [Vendor VS Tasks] — which vendor is registered for which sub activity.

- `id` — BigAutoField — ID — blank; pk
- `vendor` — ForeignKey — Vendor — -> Vendor.supplier_id
- `sub_activity` — ForeignKey — Sub Activity — -> SubActivity.code
- `registration_type` — CharField — Registration Type — blank; default=''; max=100
- `capacity` — CharField — Registration Capacity — blank; default=''; max=100
- `notes` — TextField — Notes — blank; default=''
- `selected` — BooleanField — Selected — default=False
- `flagged` — CharField — Flag — blank; default=''; max=255
- `original_factory` — CharField — Original Factory — blank; default=''; max=255
- `brand` — CharField — Brand — blank; default=''; max=255
- `origin_country` — CharField — Origin Country — blank; default=''; max=255
- `origin` — CharField — Origin — blank; default=''; max=255

### `Vessel`

table `core_vessel`

> Vessel(id, name, code)

- `rfqs` — reverse -> RFQ
- `id` — BigAutoField — ID — blank; pk
- `name` — CharField — Name — max=255
- `code` — CharField — Code — max=255

