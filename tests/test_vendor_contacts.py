"""Vendor contact columns: data cleaned (no Access hyperlink junk) and
rendered as live mailto:/http links — data checks + EN/AR pages."""

import http.cookiejar
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import django  # noqa: E402

django.setup()

from io import StringIO  # noqa: E402

from django.core.management import call_command  # noqa: E402

from core.contacts import EMAIL_FIELDS, clean_website, parse_emails  # noqa: E402
from core.forms import VendorForm  # noqa: E402
from core.models import Operation, Vendor  # noqa: E402

BASE = os.environ.get("PMS_BASE", "http://127.0.0.1:8001")
USER = os.environ.get("PMS_USER", "admin")
PASSWORD = os.environ.get("PMS_PASSWORD", "admin123")
TOKEN_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# ---------------------------------------------------------------- data ----
counts, worst = {}, (0, "")
with_site = with_mail = 0
for vendor in Vendor.objects.all().only(*EMAIL_FIELDS, "website"):
    for name in EMAIL_FIELDS:
        raw = getattr(vendor, name) or ""
        if not raw:
            continue
        counts[name] = counts.get(name, 0) + 1
        assert "#" not in raw, (vendor.pk, name, raw[:80])
        assert "mailto" not in raw, (vendor.pk, name, raw[:80])
        assert "\n" not in raw and "\r" not in raw, (vendor.pk, name, raw[:60])
        parts = [t.strip() for t in raw.split(";") if t.strip()]
        for token in parts:
            assert TOKEN_RE.fullmatch(token), (vendor.pk, name, token)
        found = parse_emails(raw)
        assert found and len(found) == len(parts), (vendor.pk, name, raw[:80])
        if len(found) > worst[0]:
            worst = (len(found), raw[:70])
    site = vendor.website or ""
    if site:
        with_site += 1
        assert site.startswith(("http://", "https://")), (vendor.pk, site)
        assert "#" not in site and "\n" not in site and " " not in site, site
        assert clean_website(site) == site, site  # already normalized
    if vendor.email:
        with_mail += 1

assert counts.get("email1", 0) > 7000, counts
assert with_site > 1200, with_site
print("data OK — email1=%d website=%d reachable=%d | fattest box: %d addrs"
      % (counts.get("email1", 0), with_site, with_mail, worst[0]))

# ------------------------------------------------------------ the form ----
form = VendorForm(data={
    "name_ar": "اختبار التسجيل",
    "registration_status_new": "مسجل",
    "email1": "info @test-house.com#mailto:info @test-house.com#",
    "email2": "info@test-house.com; sales@test-house.com",
    "website": "www.test-house.com#http://www.test-house.com#",
})
assert form.is_valid(), form.errors
assert form.cleaned_data["email1"] == "info@test-house.com", form.cleaned_data["email1"]
assert form.cleaned_data["email2"] == "sales@test-house.com", form.cleaned_data["email2"]
assert form.cleaned_data["website"] == "http://www.test-house.com", form.cleaned_data["website"]
print("form OK — junk pasted into the boxes is normalized on save")

# ------------------------------------------------------------- command ----
first, second = StringIO(), StringIO()
call_command("normalize_vendor_contacts", stdout=first)
call_command("normalize_vendor_contacts", stdout=second)
assert "already clean" in second.getvalue(), second.getvalue()
print("command OK — %s" % second.getvalue().strip())

# --------------------------------------------------------------- pages ----
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def csrf():
    return next(c.value for c in jar if c.name == "csrftoken")


def get(path):
    with op.open(BASE + path) as res:
        assert res.status == 200, (path, res.status)
        return res.read().decode()


def balance(html, path):
    tags = {}
    for close, name in re.findall(r"<(/?)(\w+)", html):
        if name in ("br", "hr", "img", "input", "meta", "link", "path",
                    "circle", "rect", "use", "source"):
            continue
        tags[name] = tags.get(name, 0) + (-1 if close else 1)
    bad = {k: v for k, v in tags.items() if v}
    assert not bad, (path, bad)


vendor = (Vendor.objects.exclude(email1="").exclude(website="").first()
          or Vendor.objects.exclude(email1="").first())
operation = Operation.objects.filter(
    operation_vendors__isnull=False,
).distinct().first()
assert vendor and operation

op.open(BASE + "/en/login/")
req = urllib.request.Request(
    BASE + "/en/login/",
    data=urllib.parse.urlencode(
        {"username": USER, "password": PASSWORD, "csrfmiddlewaretoken": csrf()}).encode(),
    headers={"X-CSRFToken": csrf(), "Referer": BASE + "/en/login/",
             "Content-Type": "application/x-www-form-urlencoded"},
)
try:
    op.open(req)
except urllib.error.HTTPError as exc:
    assert exc.code == 302, exc.code

# vendor detail: website opens the web, every address opens the mail client
detail = get("/en/vendors/%d/" % vendor.pk)
balance(detail, "detail")
assert "#mailto:" not in detail and "#http" not in detail, "hyperlink junk on screen"
assert 'href="mailto:' in detail, "no mailto link"
assert 'target="_blank"' in detail, "website does not open in a new tab"
for address in parse_emails(vendor.email1)[:3]:
    assert 'href="mailto:%s"' % address in detail, address
if vendor.website:
    assert 'href="%s"' % vendor.website in detail, vendor.website
# no raw column text anymore
assert "{{" not in detail and 'field-value">{{ vendor' not in detail

# vendor register: e-mail column with links
register = get("/en/vendors/")
balance(register, "register")
assert ">E-mail<" in register, "no e-mail column"
assert 'href="mailto:' in register, "register has no mailto links"

# the tender's vendor list: same column
listing = get("/en/vendor-list/%d/" % operation.pk)
balance(listing, "vendor list")
assert ">E-mail<" in listing, "vendor list has no e-mail column"
assert 'href="mailto:' in listing, "vendor list has no mailto links"

# Arabic screens
ar_detail = get("/ar/vendors/%d/" % vendor.pk)
balance(ar_detail, "ar detail")
assert "البريد الإلكترونى" in ar_detail, "AR e-mail labels missing"
assert "الموقع الإلكترونى" in ar_detail, "AR website label missing"
assert 'href="mailto:' in ar_detail, "AR detail lost its links"
ar_register = get("/ar/vendors/")
balance(ar_register, "ar register")
assert "البريد الإلكترونى" in ar_register and 'href="mailto:' in ar_register

print("pages OK — detail / register / vendor list link e-mail + website (EN+AR)")
sys.exit(0)
