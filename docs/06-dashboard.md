# 06 · Dashboard

`/en/dashboard/` — "graph charts pie statistics for the sum of everything".
One screen aggregating the whole data set, rendered in ~117 ms with **zero
JavaScript and zero CDN assets**: donuts are SVG built in Python, bars are
`width: %` divs.

## Layout (top → bottom)

1. **Header** — "Dashboard" + `Welcome back, <username>.`
2. **Six stat cards** (`.stat-cards`), each an SVG icon, an abbreviated figure,
   a sub-tag and a link to the screen it counts:

   | Card | Value | Tag | Links to |
   | --- | --- | --- | --- |
   | Tenders | 2,058 | 1,694 Local · 364 Foreign | `/rfq/` |
   | Vendors | 8,878 | local/foreign scope counts | `/vendors/` |
   | Vendor List Entries | 6,436 | 1,300 / 2,058 Tenders (coverage) | `/rfq/` |
   | RFQs | count | N without a tender | `/rfq/` |
   | Vendor Activities | 22,945 | 846 Sub · 107 Main Activities | `/vendors/` |
   | Estimated Value | `822.2M` | currency + tender count | `/rfq/` |

   Figure abbreviation comes from `charts.abbrev()` (`848300227.68 → 848.3M`).

3. **Four SVG donuts** (`.chart` + `_chart_legend.html` legend):
   * Tenders by Market (82.3 % local / 17.7 % foreign)
   * Vendor List Coverage (with / without vendors — 63.2 / 36.8)
   * Vendors by Scope (local / foreign / other)
   * Vendor Registration Status (`مسجل`, `غير مسجل`, `تحت التسجيل`, `شطب`, Other)
4. **Six CSS bar charts**:
   * Tenders by Execution Method (top 6 + Other)
   * Tenders by File Department (top 6 + Other)
   * Tenders by Region (top 4 + Other)
   * Estimated Value by Currency (per-currency totals)
   * Top Vendors by Tenders (top 10)
   * Vendor Registrations by Activity (top 8 main activities)
5. **RFQ workflow panel** — a donut of `RFQ.Status` (Draft → Submitted → Under
   Review → Chairman Approved → Rejected → Vendor Selection → Completed),
   counts for total/opened/without-tender, and an **empty state with a
   *New RFQ* button** while `RFQ` has no rows.
6. **Database Summary table** — one row per table of the imported data
   (tenders, vendors, entries, activities, RFQs, main/sub activities,
   projects, clients, cost centres, locations, departments) with counts
   formatted `{:,}`.

## How it is built

### `core/charts.py` — pure geometry

```python
PALETTE = ("#1d4ed8", "#f59e0b", "#16a34a", "#94a3b8",
           "#ef4444", "#a855f7", "#14b8a6", "#60a5fa")
donut(values, colors=None, size=152, thickness=28) -> "<svg …>"
abbrev(value) -> "848.3M"
```

`donut()` emits one `<circle>` per slice using `stroke-dasharray` arcs, the
whole group rotated −90° so slices start at 12 o'clock. Empty data returns
`""` and the template shows a placeholder. Slice order = legend order; blue and
amber come first so the local/foreign pies match the market badges used
everywhere else.

### `core/views.py` — aggregation helpers

| Helper | Output |
| --- | --- |
| `_dashboard_context()` | everything the template needs (`cards`, `donuts`, `bars`, `rfq`, `summary`) |
| `_donut(title, rows, colors)` | drops zero rows, computes `total` and per-slice `pct` (`{:.1f}`), picks colours from `PALETTE` |
| `_bars(title, rows, limit, other, formatter)` | truncates to `limit` (folding the tail into *Other* when given), sizes rows against the **biggest** row, and floors tiny rows at **0.8 %** so a hairline stays visible |
| `_count_by(field, blank)` | `Operation.values(field).annotate(n=Count).order_by('-n')`, blanks become "Not set" |

### Rules that must not be broken

* **Never sum across currencies.** `estimated_value` is grouped by
  `Operation.currency` first (`value_by_currency`), and the big "Estimated
  Value" card uses the EGP row (`جنيه مصرى`) when present — currently
  **822.2M EGP across 1,486 tenders**. USD/EUR rows are their own lines.
* **Coverage counts distinct operations**: an `Operation` with at least one
  `OperationVendor` row counts once (`values('pk').distinct()`).
* **Scope counts reuse `_scoped_vendors(market)`** so the dashboard and the
  vendor-list screens always agree on what "local" and "foreign" mean.
* Percentages are computed in Python (`{:.1f}`), never in JS.
* Every label is a `gettext` string (translated in `locale/ar`).

## Template

`templates/core/dashboard.html` + `templates/core/_chart_legend.html`.

* Cards: `for card in cards` → `{{ card.icon|safe }}` (inline SVG strings built
  in `_ICONS`), `{{ card.value }}`, `{{ card.tag }}`, `href={{ card.href }}`.
* Donuts: `{{ donut.svg|safe }}` + legend rows `label / value / pct %`.
* Bars: `<div class="bar" style="width: {{ row.pct }}%">` with label and value
  spans.
* RFQ panel: `_donut` output + `rfq.total / rfq.opened / rfq.orphan` and the
  `{% empty %}` → *New RFQ* branch.
* Summary: a two-column `.data-table`.

## Performance

Aggregates are SQL `GROUP BY`s (no Python loops over 41k rows), the page issues
one query per card/donut/bar, and everything renders in ~117 ms on the dev
server. There is no cache; if the data grows by an order of magnitude, add
`django.core.cache` around `_dashboard_context()` first.
