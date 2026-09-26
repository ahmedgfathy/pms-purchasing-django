"""Arabic side of the tender pages."""
import http.cookiejar
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

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


def token():
    return next(c.value for c in jar if c.name == "csrftoken")


def get(path):
    with opener.open(BASE + path) as r:
        body = r.read().decode("utf-8")
        assert r.status == 200, (path, r.status)
        return body


def post(path, data, referer):
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
        opener.open(req)
    except urllib.error.HTTPError as e:
        assert e.code == 302, (path, e.code)
        return e.headers.get("Location")


get("/ar/login/")
post("/ar/login/", {"username": USER, "password": PASSWORD}, f"{BASE}/ar/login/")

listing = get("/ar/rfq/")
assert "جميع المناقصات" in listing, "tabs not translated"
assert "2058 عملية" in listing, "tender list missing in Arabic"
assert "رقم طلب المواد" in listing, "RFQ column not translated"
assert "1694 عملية" in get("/ar/rfq/?market=local")
assert "364 عملية" in get("/ar/rfq/?market=foreign")
assert 'href="/ar/vendor-list/"' not in get("/ar/dashboard/"), "Vendor List link must be gone"
assert "طلب مهمات جديد" in get("/ar/tenders/local/"), "New RFQ not translated"

local = get("/ar/tenders/local/")
foreign = get("/ar/tenders/foreign/")
allt = get("/ar/rfq/")  # /ar/vendor-list/ redirects here now
assert "جميع المناقصات" in allt, "All Tenders not translated"
assert "1694 عملية" in local, re.findall(r"\d+ عملية", local)
assert "364 عملية" in foreign, re.findall(r"\d+ عملية", foreign)

pk = re.search(r'href="/ar/vendor-list/(\d+)/"', local).group(1)
detail = get(f"/ar/vendor-list/{pk}/")
for s in ("موردون محليون", "جميع الموردين", "البحث في:"):
    assert s in detail, f"{s} missing on tender page"
assert "السوق" in detail, "Market label missing"

# RFQ flow in Arabic
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from datetime import date  # noqa: E402

from core.models import Department, RFQ  # noqa: E402

rfq = RFQ.objects.create(
    request_number="TST-VL-AR",
    requesting_department=Department.objects.first(),
    preparation_date=date(2026, 9, 26),
    market_type=RFQ.MarketType.FOREIGN,
)
try:
    page = get(f"/ar/rfq/{rfq.pk}/")
    assert "فتح قائمة الموردين" in page, "Open Vendor List not translated"
    assert "لا توجد مناقصة" in page, "empty hint not translated"
    post(f"/ar/rfq/{rfq.pk}/tender/create/", {}, f"{BASE}/ar/rfq/{rfq.pk}/")
    rfq.refresh_from_db()
    assert rfq.tender_id
    page = get(f"/ar/rfq/{rfq.pk}/")
    assert "قائمة الموردين" in page
    assert f"/ar/vendor-list/{rfq.tender_id}/" in page
    assert "المناقصة" in page, "Tender label missing on RFQ page"
    for label in ("تفاصيل المناقصة", "بيان المهمات", "القيمة التقديرية"):
        assert label in page, f"{label} missing on AR RFQ page"
finally:
    if rfq.tender_id:
        rfq.tender.delete()
    rfq.delete()

print("AR OK")
