"""Dashboard checks: sums, SVG donuts, CSS bars, EN + AR."""

import os
import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("PMS_BASE", "http://127.0.0.1:8001")
USER = os.environ.get("PMS_USER", "admin")
PASSWORD = os.environ.get("PMS_PASSWORD", "admin123")

jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def csrf():
    return next(c.value for c in jar if c.name == "csrftoken")


def post(path, data, referer):
    req = urllib.request.Request(
        BASE + path, data=urllib.parse.urlencode(data).encode(),
        headers={"X-CSRFToken": csrf(), "Referer": referer,
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        op.open(req)
    except urllib.error.HTTPError as exc:
        assert exc.code in (302,), (path, exc.code)


def get(path):
    with op.open(BASE + path) as res:
        assert res.status == 200, (path, res.status)
        return res.read().decode()


def balance(html, path):
    tags = {}
    for close, name in re.findall(r"<(/?)(\w+)", html):
        if name in ("br", "hr", "img", "input", "meta", "link",
                    "path", "circle", "rect", "use", "source"):
            continue
        tags[name] = tags.get(name, 0) + (-1 if close else 1)
    bad = {k: v for k, v in tags.items() if v}
    assert not bad, (path, bad)


def text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


op.open(BASE + "/en/login/")
post("/en/login/", {"username": USER, "password": PASSWORD,
                    "csrfmiddlewaretoken": csrf()}, BASE + "/en/login/")

en = get("/en/dashboard/")
balance(en, "/en/dashboard/")
t = text(en)

# the sums of everything
for probe in ("2,058", "8,878", "6,436", "22,945", "1,300", "758",
              "1,694", "364", "4,584", "2,414"):
    assert probe in t, f"sum {probe} missing"
assert "63.2%" in t and "82.3%" in t, "pie percentages missing"
assert en.count('class="donut"') == 4, "expected 4 donuts (RFQ one is empty)"
assert en.count("bar-row") >= 30, en.count("bar-row")
for title in ("Tenders by Market", "Vendor List Coverage", "Vendors by Scope",
              "Vendor Registration Status", "Tenders by Execution Method",
              "Tenders by File Department", "Estimated Value by Currency",
              "Top Vendors by Tenders", "Vendor Registrations by Activity",
              "RFQ Workflow", "Database Summary"):
    assert title in t, f"title {title!r} missing"
assert "No RFQs yet" in t and "New RFQ" in t, "RFQ empty state missing"
assert 'style.css?v=9' in en, "css cache not bumped"
# database summary: the whole data set, one row per table
for label, count in (("Projects", "19"), ("Clients", "63"),
                     ("Cost Centers", "72"), ("Locations", "10"),
                     ("Main Activities", "107"), ("Sub Activities", "846")):
    assert re.search(label + r".{0,40}?" + count + r"\b", t), (label, count)
# bars are sized against the biggest row
widths = [float(w) for w in re.findall(r'bar-fill" style="width: ([\d.]+)%', en)]
assert widths and max(widths) == 100.0, widths[:5]
assert all(0 < w <= 100 for w in widths), widths

ar = get("/ar/dashboard/")
balance(ar, "/ar/dashboard/")
ta = text(ar)
for probe in ("الرسوم البيانية", "المناقصات حسب السوق", "تغطية قوائم الموردين",
              "حالة تسجيل الموردين", "ملخص قاعدة البيانات", "مسار طلبات المهمات",
              "الإجمالى", "بها موردون", "غير مسجل", "2,058", "8,878"):
    assert probe in ta, f"AR {probe!r} missing"
assert "Tenders by Market" not in ta, "untranslated donut title"
assert "Database Summary" not in ta, "untranslated section title"
assert ar.count('class="donut"') == 4, "AR donuts missing"

print("dashboard EN/AR OK  (donuts=%d, bars=%d)"
      % (en.count('class="donut"'), en.count("bar-row")))
sys.exit(0)
