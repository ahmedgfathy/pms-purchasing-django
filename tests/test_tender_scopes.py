"""Smoke test for the local/foreign tender pages + RFQ vendor list."""
import http.cookiejar
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

BASE = os.environ.get("PMS_BASE", "http://127.0.0.1:8001")
USER = os.environ.get("PMS_USER", "admin")
PASSWORD = os.environ.get("PMS_PASSWORD", "admin123")
jar = http.cookiejar.CookieJar()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(jar), _NoRedirect,
)
checks = []


def token():
    for c in jar:
        if c.name == "csrftoken":
            return c.value
    raise AssertionError("no csrf cookie")


def get(path, expect=200):
    with opener.open(BASE + path) as r:
        body = r.read().decode("utf-8")
        code = r.status
    checks.append((path, code, len(body)))
    assert code == expect, (path, code, body[:400])
    return body


def post(path, data, referer, expect=302, follow=False):
    data = dict(data, csrfmiddlewaretoken=token())
    req = urllib.request.Request(
        BASE + path,
        data=urllib.parse.urlencode(data).encode(),
        headers={
            "X-CSRFToken": token(),
            "Referer": referer,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with opener.open(req) as r:
            code, location, body = r.status, r.geturl(), r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        code, location, body = e.code, e.headers.get("Location"), e.read().decode("utf-8")
    assert code == expect, (path, code, body[:400])
    if follow and location:
        body = get(urllib.parse.urlparse(location).path)
        return body
    return location


get("/en/login/")
post("/en/login/", {"username": USER, "password": PASSWORD}, f"{BASE}/en/login/")

html = get("/en/dashboard/")
assert 'href="/en/tenders/local/"' in html, "local tender link missing"
assert 'href="/en/tenders/foreign/"' in html, "foreign tender link missing"
assert 'href="/en/vendor-list/"' not in html, "Vendor List link must be gone"

local = get("/en/tenders/local/")
foreign = get("/en/tenders/foreign/")
allt = get("/en/rfq/")
for name, txt, count in (
    ("local", local, 1694),
    ("foreign", foreign, 364),
    ("all", allt, 2058),
):
    assert f"{count} operations" in txt, (name, re.findall(r"[\d]+ operations", txt))
    checks.append((f"{name} counts", 0, count))

# the old list URL is only a redirect to the RFQ screen now
try:
    with opener.open(BASE + "/en/vendor-list/") as r:
        code, location = r.status, r.geturl()
except urllib.error.HTTPError as e:
    code, location = e.code, e.headers.get("Location")
assert (code, location) == (302, "/en/rfq/"), (code, location)

# divisions render the RFQ list, with New RFQ pre-set for that market
for page, market in ((local, "local"), (foreign, "foreign")):
    assert "New RFQ" in page, f"division {market} has no New RFQ"
    assert f"/en/rfq/create/?market={market}" in page, f"{market} market not pre-set"
    assert "market-tabs" not in page, f"division {market} still has the tab buttons"

assert "Market" in allt and "status-badge status-local" in allt

m = re.search(r'href="/en/vendor-list/(\d+)/"', local)
assert m, "no tender link on local page"
op_pk = m.group(1)
detail = get(f"/en/vendor-list/{op_pk}/")
assert "Local vendors" in detail and "All vendors" in detail, "scope toggle missing"
assert "status-badge status-local" in detail, "market badge missing"

scoped = get(f"/en/vendor-list/{op_pk}/?scope=market&vq=1")
unscoped = get(f"/en/vendor-list/{op_pk}/?scope=all&vq=1")
checks.append(("scoped search", 0, scoped.count('class="mono"')))
checks.append(("all search", 0, unscoped.count('class="mono"')))

# ---- the market scope itself (unit level) ----
from datetime import date  # noqa: E402

from core.models import (  # noqa: E402
    Department,
    Operation,
    OperationVendor,
    RFQ,
    Vendor,
)
from core.views import _scoped_vendors  # noqa: E402

local_ids = set(_scoped_vendors(Operation.Market.LOCAL, "market").values_list("pk", flat=True))
foreign_ids = set(_scoped_vendors(Operation.Market.FOREIGN, "market").values_list("pk", flat=True))
assert local_ids and foreign_ids and not (local_ids & foreign_ids), "scopes overlap"
assert local_ids | foreign_ids < set(Vendor.objects.values_list("pk", flat=True)), "scope == all?"
checks.append(("local scope vendors", 0, len(local_ids)))
checks.append(("foreign scope vendors", 0, len(foreign_ids)))

# ---- RFQ -> tender -> vendor list ----
dept = Department.objects.first()
rfq = RFQ.objects.create(
    request_number="TST-VL-001",
    requesting_department=dept,
    preparation_date=date(2026, 9, 26),
    market_type=RFQ.MarketType.LOCAL,
)
try:
    page = get(f"/en/rfq/{rfq.pk}/")
    assert "Open Vendor List" in page, "create button missing"

    # the RFQ list shows every tender, and the not-yet-opened RFQ on top
    listing = get("/en/rfq/")
    assert "All Tenders" in listing and "2058 operations" in listing, "tender list missing"
    assert "Mat. Req. No" in listing, "RFQ column missing"
    assert "RFQs without a tender" in listing and "TST-VL-001" in listing, (
        "orphan RFQ block missing",
    )
    assert "market-tabs" not in listing, "market tab buttons must be removed"
    assert "1694 operations" in get("/en/rfq/?market=local")
    assert "364 operations" in get("/en/rfq/?market=foreign")

    loc = post(f"/en/rfq/{rfq.pk}/tender/create/", {}, f"{BASE}/en/rfq/{rfq.pk}/")
    assert loc == f"/en/rfq/{rfq.pk}/", loc

    rfq.refresh_from_db()
    tender = rfq.tender
    assert tender is not None, "tender not linked"
    assert tender.market == Operation.Market.LOCAL, tender.market
    assert tender.file_dept == "المشتريات المحلية", tender.file_dept

    page = get(f"/en/rfq/{rfq.pk}/")
    assert "No vendors on this list yet." in page, page[page.find("Vendor List"):][:400]
    assert f"/en/vendor-list/{tender.pk}/" in page, "tender link missing"

    # the RFQ page carries the full بيان المهمات of its tender
    for label in (
        "Tender Details",
        "General Information",
        "Task Statement",
        "Value and Follow-up",
        "Milestone Dates",
    ):
        assert label in page, f"{label} missing on RFQ page"
    assert tender.task_statement in page, "task statement not shown"
    assert tender.get_market_display() in page

    # the tender now carries its Mat. Req. No in the list
    listing = get("/en/rfq/")
    assert "TST-VL-001" in listing, "RFQ number missing from tender list"
    assert "RFQs without a tender" not in listing, "tender still listed as orphan"

    cand = _scoped_vendors(Operation.Market.LOCAL, "market").first()
    loc = post(
        f"/en/vendor-list/{tender.pk}/vendors/add/",
        {"supplier_id": cand.pk, "next": f"/en/rfq/{rfq.pk}/"},
        f"{BASE}/en/rfq/{rfq.pk}/",
    )
    assert loc == f"/en/rfq/{rfq.pk}/", loc
    assert OperationVendor.objects.filter(operation=tender, vendor=cand).exists()
    page = get(f"/en/rfq/{rfq.pk}/")
    assert cand.name_ar in page, "vendor not shown on RFQ page"

    loc = post(
        f"/en/vendor-list/{tender.pk}/vendors/{cand.pk}/remove/",
        {"next": f"/en/rfq/{rfq.pk}/"},
        f"{BASE}/en/rfq/{rfq.pk}/",
    )
    assert loc == f"/en/rfq/{rfq.pk}/", loc
    assert not OperationVendor.objects.filter(operation=tender, vendor=cand).exists()
    checks.append(("rfq tender flow", 0, tender.pk))
finally:
    if rfq.tender_id:
        rfq.tender.delete()
    rfq.delete()

# ---- an imported Access tender shown as a full بيان المهمات on an RFQ ----
rich = (
    Operation.objects.exclude(task_statement="")
    .filter(list_approval_date__isnull=False)
    .first()
) or Operation.objects.exclude(task_statement="").first()
rfq2 = RFQ.objects.create(
    request_number="TST-VL-RICH",
    requesting_department=Department.objects.first(),
    preparation_date=date(2026, 9, 26),
    market_type=RFQ.MarketType.FOREIGN,
)
try:
    rfq2.tender = rich
    rfq2.save(update_fields=["tender"])
    page = get(f"/en/rfq/{rfq2.pk}/")
    from html import escape

    assert escape(rich.task_statement) in page, "Access task statement missing"
    for label in (
        "General Information",
        "Value and Follow-up",
        "Milestone Dates",
        "File Department",
        "Vendor Register Executor",
    ):
        assert label in page, f"{label} missing for imported tender"
    if rich.list_approval_date:
        assert str(rich.list_approval_date) in page, "milestone date missing"
    if rich.notes or rich.vendor_list_memo:
        assert "Notes" in page, "tender notes card missing"
    checks.append(("imported tender on rfq", 0, rich.pk))
finally:
    rfq2.delete()

print("\n".join(f"{p}: {c} ({n})" for p, c, n in checks))
print("OK")
