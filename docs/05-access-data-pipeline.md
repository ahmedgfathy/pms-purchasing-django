# 05 · Access → PostgreSQL data pipeline

Everything about getting the legacy data into Django: the source files, the
export, the table/field mapping, the quirks, and the e-mail/website cleaning.

## Source files (committed to this repo)

| File | Role | Size |
| --- | --- | --- |
| `2026.accdb` | Access **front end** — the forms whose screens are rebuilt here (Vendor List, Vendor View, New Vendor Enter, Vendor VS Tasks, …) | 35 MB |
| `2026-data.accdb` | Access **back end** — the 10 tables that hold the data | 19 MB |

mdbtools must be on the PATH (installed per user under `~/.local/bin`):

```bash
# Ubuntu/WSL
sudo apt install mdbtools          # or a user build in ~/.local/bin
which mdb-export
```

## Export step

`manage.py import_vendor_data` calls `mdb-export` for each table:

```
mdb-export -b strip -D '%Y-%m-%d' -T '%Y-%m-%d %H:%M:%S' 2026-data.accdb "<Table>"
```

* `-b strip` removes the "export header" row, `-D/-T` normalize date/datetime
  formats.
* CSVs land in **`/tmp/accdb_csv`** (`--keep` reuses them instead of re-reading
  the .accdb — much faster, ~10 s for the whole load).
* Failure of any table aborts the command with the mdbtools stderr.

## Table map

| Access table (back end) | Model | Rows |
| --- | --- | --- |
| `Project Code` | `Project` | 19 |
| `Client Code` | `ClientCode` | 63 |
| `Location Code` | `Location` | 10 |
| `Cost Center` | `CostCenter` | 72 |
| `Tasks` | `MainActivity` | 107 |
| `Tasks sub` | `SubActivity` | 846 |
| `Vendors` | `Vendor` | 8,878 |
| `Vendor VS Tasks` | `VendorActivity` | 22,945 |
| `Oprations` | `Operation` | 2,058 |
| `Vendor Opration` | `OperationVendor` | 6,436 |

Field-level mapping lives in `core/management/commands/import_vendor_data.py`
(`_import_lookups`, `_import_activities`, `_import_vendors`,
`_import_operations`, `_import_vendor_activities`, `_import_operation_vendors`)
— each `self._s/_i/_d/_dt/_b/_dec(row, "<Arabic column>")` call documents the
exact Access column name (e.g. `إدارة الملف` → `file_dept`,
`طريقة التنفيذ` → `execution_method`, `إجمالى القيمة التقديرية` →
`estimated_value`).

## Pipeline behaviour

1. **Export** (unless `--keep`).
2. **`transaction.atomic()`** — clear + import are all-or-nothing; a failed run
   leaves the previous data intact.
3. **Clear** (unless `--no-clear`), children first:
   `OperationVendor → VendorActivity → Operation → Vendor → SubActivity → MainActivity`.
   Reference tables (`Project`, `ClientCode`, `Location`, `CostCenter`) are
   **upserted, never cleared**, because RFQs point at cost centres.
4. **Import** with `bulk_create(batch_size=500)`; reference FKs are resolved by
   `code` and validated (`ref()` stores `NULL` for unknown codes).
5. Report per-table counts.

Re-running is safe. Consequences of a re-import: every `Operation` gets a new
`id`, so `RFQ.tender` (SET_NULL) is reset to `NULL` — RFQs are never deleted.

```bash
.venv/bin/python manage.py import_vendor_data            # export + load
.venv/bin/python manage.py import_vendor_data --keep     # reuse /tmp/accdb_csv
.venv/bin/python manage.py import_vendor_data --no-clear --batch-size 1000
.venv/bin/python manage.py import_vendor_data --file /path/to/other.accdb
```

## Access quirks handled by the importer

| Quirk | Handling |
| --- | --- |
| `Supplier ID` non-auto PK | kept as `Vendor.supplier_id`; duplicates skipped with a warning |
| `Oprations.[رقم العملية]` not unique (dup 170/1929) | `id` is the key; `operation_no_map` keeps the **first** pk per number |
| 92 `Vendor Opration` rows with an empty operation no | imported with `operation=None`, raw number preserved |
| Unknown operation number on a child row | counted and reported (`rows reference an unknown operation no`) |
| Estimated value is Arabic-Indic text | `ARABIC_DIGITS` translation + `_dec()` → `Decimal` |
| Access `Memo` columns (long, `&`, line breaks) | loaded into `TextField` unchanged |
| Hyperlink contact columns (`display#target#`) | cleaned by `clean_contacts()` while loading |
| Market not stored in Access | derived (see below) |

### Market derivation (`_market()`)

```
file dept starts with "المشتريات المحلية"      → local
file dept ==     "المشتريات الخارجية"          → foreign
currency in {دولار أمريكى, يورو, جنيه إسترلينى, ريال سعودي} → foreign
otherwise                                       → local
```

Result: **1,694 local / 364 foreign** of 2,058 tenders. The file department
also groups the remaining departments (contracts, naval units) which the app
shows in the "Tenders by File Department" chart.

## E-mail / website cleaning (`core/contacts.py`)

Access stored those boxes as *hyperlinks*, so mdbtools hands Jet's
`display#target#` encoding (`a@b.com#mailto:a@b.com#`,
`www.site.com#http://www.site.com#`) plus pasted junk (company names, Outlook
file paths, an address typed into the wrong column).

Single source of truth — `parse_emails()`, `clean_emails()`, `clean_website()`,
`clean_contacts(data)` — **idempotent**, applied in three places:

1. **Import** — `clean_contacts(data)` inside `_import_vendors()`.
2. **`VendorForm.clean()`** — normalizes whatever a user types into the form.
3. **`manage.py normalize_vendor_contacts`** — cleans rows already in the DB
   and prints per-field counts (second run reports "already clean").

Rules:

* `_repair()` undoes spacing typos (`info @x.com`, `x@site .com`, `x@site,com`).
* `parse_emails()` keeps only addresses matching
  `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}`, de-duplicated case-insensitively.
* `clean_website()` takes the first fragment that really is a host
  (`HOST_RE` rejects `A. Albert GmbH`, `DOF Egypt`, paths with `\`), adds
  `https://` when the scheme is missing.
* **Cross-column repair** inside `clean_contacts()`:
  * a URL sitting in a mail box fills an *empty* Website,
  * an address in the Website box fills *empty* `E_mail 1`,
  * duplicates pasted into several boxes are kept only in the first one.
* Result format: e-mails are a `"; "`-separated list, website always has a scheme.

Measured outcome of the migration: **7,604 vendors updated**, second run clean;
7,452 addresses in `email1`, 1,316 websites, 7,482 vendors reachable; audit
shows 0 occurrences of `#`, `mailto:`, newlines, invalid tokens or bad hosts.

### Rendering the contacts

* `Vendor.email` (model property) — the first deliverable address, used by the
  **E-mail column** of the vendor list / candidates / register.
* Templates use the `contacts` templatetag filters:
  `{{ vendor.email1|emails }}` → one `mailto:` anchor per address,
  `{{ vendor.website|website_url }}` → `href` (opens in a new tab).
* Styling: `.contact-link` in `style.css`, RTL-safe
  (`direction: ltr; unicode-bidi: plaintext`).

## Dump instead of import

For a machine without mdbtools, `db/pms_purchasing_2026-09-26.sql.gz` is a
gzip-compressed `pg_dump` of the exact dataset (see
[11-operations.md](11-operations.md) for restore/backup commands). Restoring it
and re-importing from `2026-data.accdb` produce identical counts.
