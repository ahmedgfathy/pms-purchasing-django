# 10 · Testing

Five end-to-end scripts live in `tests/`. They talk to the **running dev
server** over HTTP (logging in as a real browser would) *and* to the database
through the ORM, so they exercise the whole stack.

## Prerequisites

```bash
.venv/bin/python manage.py runserver 0.0.0.0:8001     # terminal 1
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `PMS_BASE` | `http://127.0.0.1:8001` | server under test |
| `PMS_USER` / `PMS_PASSWORD` | `admin` / `admin123` | login used by the scripts |
| `PMS_COOKIES` | `/tmp/pms-cookies.txt` | cookie jar for the shell script |

## The scripts

| Script | What it proves |
| --- | --- |
| `tests/test_dashboard.py` | Dashboard EN+AR: stat-card sums present (`63.2%`, `82.3%`), exactly 4 SVG donuts, ≥30 bar rows, bar widths ≤ 100 with the biggest = 100, RFQ empty state + *New RFQ*, `style.css?v=9` bumped, all section titles translated in AR (no English leaks) |
| `tests/test_tender_scopes.py` | Sidebar has Local/Foreign links and **no** "Vendor List" link; `/vendor-list/` → 302 `/rfq/`; division pages show their own counts (1,694 / 364) and a *New RFQ* with `?market=`; no `market-tabs`; market scope sets don't overlap; full RFQ → tender flow: create RFQ, open vendor list, tender gets `market=local` + `file_dept=المشتريات المحلية`, tender details render on the RFQ page, the RFQ leaves the orphan block |
| `tests/test_ar_tenders.py` | Arabic side: `/ar/` pages, counts (`364 عملية`), tender page labels, the Arabic RFQ flow including *فتح قائمة الموردين*, and cleanup of the created rows |
| `tests/test_vendor_contacts.py` | Contact data: no `#`/`mailto:`/newlines anywhere, every token is a valid address, websites are normalized **and idempotent**; `VendorForm` normalizes pasted junk; `normalize_vendor_contacts` reports "already clean" on a second run; pages render `mailto:`/`target="_blank"` links (EN + AR) and the E-mail column exists |
| `tests/test_vendor_flows.sh` | Writes: add vendor to a tender (and the duplicate warning), remove it, create a vendor, register/unregister an activity, edit the vendor, then delete everything it created |

Run them:

```bash
for t in tests/test_*.py; do echo "== $t"; .venv/bin/python "$t"; done
bash tests/test_vendor_flows.sh
```

Expected tails:

```
dashboard EN/AR OK  (donuts=4, bars=36)
OK                       (test_tender_scopes)
AR OK
form OK — junk pasted into the boxes is normalized on save
command OK — vendors scanned: 8878 / all contact columns already clean
pages OK — detail / register / vendor list link e-mail + website (EN+AR)
  deleted test vendor 250006824   (test_vendor_flows.sh)
```

The scripts are **self-cleaning**: `test_tender_scopes` and `test_ar_tenders`
delete the RFQ/tender they create, `test_vendor_flows.sh` deletes the vendor it
creates — re-running them leaves the database exactly as it was.

## Other checks

```bash
.venv/bin/python manage.py check          # system check, must be clean
msgfmt --statistics -o /dev/null locale/ar/LC_MESSAGES/django.po
                                           # "N translated messages." only
grep -c "Internal Server Error" /tmp/pms-server.log
                                           # must stay at its baseline (7)
```

The baseline of 7 errors comes from historical `/ar/vendor-list/` 404s logged
while the redirect was being introduced; a change in that number means a new
error was introduced.

## Writing more tests

* A script should be runnable from any machine: no absolute paths (compute the
  repo root from `__file__`), no hard-coded credentials (`PMS_*` env), and it
  must clean up after itself.
* Keep the "login through the real form" pattern — it also proves CSRF and the
  `EmployeeAccessMiddleware` still accept the admin.
* For pure data checks, use the ORM directly (`django.setup()` after putting
  the repo root on `sys.path`); for markup checks, fetch the page with `urllib`
  and assert on substrings (there is no BeautifulSoup dependency).
* `core/tests.py` is intentionally empty — the project runs these external
  scripts instead so they can also run against a *deployed* instance via
  `PMS_BASE`.
