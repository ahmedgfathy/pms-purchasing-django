#!/bin/bash
# End-to-end test of the vendor-list write flows.
# Needs the dev server running; override with PMS_BASE / PMS_COOKIES.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
BASE="${PMS_BASE:-http://127.0.0.1:8001}"
CK="${PMS_COOKIES:-/tmp/pms-cookies.txt}"

get_csrf() {
    grep csrftoken "$CK" | awk '{print $NF}' | tail -1
}

post() { # path, extra data...
    local path="$1"; shift
    curl -s -b "$CK" -c "$CK" -o /tmp/resp.html -w "%{http_code}" \
        -H "Referer: $BASE$path" -H "X-CSRFToken: $(get_csrf)" \
        "$@" "$BASE$path"
}

# sign in first so the script is self-contained (fresh clone / fresh jar)
curl -s -b "$CK" -c "$CK" -o /tmp/pms-login.html "$BASE/en/login/"
TOKEN=$(get_csrf)
CODE=$(curl -s -b "$CK" -c "$CK" -o /dev/null -w "%{http_code}" \
    -H "Referer: $BASE/en/login/" -H "X-CSRFToken: $TOKEN" \
    --data-urlencode "csrfmiddlewaretoken=$TOKEN" \
    --data-urlencode "username=${PMS_USER:-admin}" \
    --data-urlencode "password=${PMS_PASSWORD:-admin123}" \
    "$BASE/en/login/")
echo "login http=$CODE"

# pick an operation and a vendor not yet on it
PICK=$(cd "$ROOT" && "$PY" - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from core.models import Operation, OperationVendor, Vendor, VendorActivity, SubActivity
op = Operation.objects.filter(pk=4117).first() or Operation.objects.first()
on_list = set(OperationVendor.objects.filter(operation=op).values_list('vendor_id', flat=True))
vendor = Vendor.objects.exclude(pk__in=on_list).order_by('supplier_id').first()
reg = set(VendorActivity.objects.filter(vendor=vendor).values_list('sub_activity_id', flat=True))
sub = SubActivity.objects.exclude(code__in=reg).order_by('code').first()
print(op.pk, vendor.pk, sub.code)
PY
)
read -r OP VENDOR SUBCODE <<< "$PICK"
echo "operation=$OP vendor=$VENDOR subactivity=$SUBCODE"

echo "--- add vendor to operation list:"
CODE=$(post "/en/vendor-list/$OP/vendors/add/" --data "csrfmiddlewaretoken=$(get_csrf)&supplier_id=$VENDOR")
echo "  http=$CODE"
echo "  flash: $(curl -s -b "$CK" "$BASE/en/vendor-list/$OP/" | grep -o 'class="message[^>]*">[^<]*' | head -1)"
cd "$ROOT" && "$PY" -c "
import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from core.models import OperationVendor
print('  present:', OperationVendor.objects.filter(operation_id=$OP, vendor_id=$VENDOR).exists())"

echo "--- add same vendor again (should warn, not duplicate):"
CODE=$(post "/en/vendor-list/$OP/vendors/add/" --data "csrfmiddlewaretoken=$(get_csrf)&supplier_id=$VENDOR")
echo "  http=$CODE"
cd "$ROOT" && "$PY" -c "
import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from core.models import OperationVendor
print('  count:', OperationVendor.objects.filter(operation_id=$OP, vendor_id=$VENDOR).count())"

echo "--- remove vendor from operation list:"
CODE=$(post "/en/vendor-list/$OP/vendors/$VENDOR/remove/" --data "csrfmiddlewaretoken=$(get_csrf)")
echo "  http=$CODE"
cd "$ROOT" && "$PY" -c "
import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from core.models import OperationVendor
print('  present:', OperationVendor.objects.filter(operation_id=$OP, vendor_id=$VENDOR).exists())"

echo "--- create vendor:"
CODE=$(curl -s -b "$CK" -c "$CK" -o /tmp/resp.html -w "%{http_code}" \
    -H "Referer: $BASE/en/vendors/new/" -H "X-CSRFToken: $(get_csrf)" \
    --data-urlencode "csrfmiddlewaretoken=$(get_csrf)" \
    --data-urlencode "name_ar=شركة اختبار النموذج" \
    --data-urlencode "name_en=Test Form Company" \
    --data-urlencode "country=Egypt" \
    --data-urlencode "phone1=01000000000" \
    --data-urlencode "booklet_type=محلى" \
    --data-urlencode "registration_status_new=مثبت" \
    --data-urlencode "notes=created by flow test" \
    -L "$BASE/en/vendors/new/")
echo "  http=$CODE (200 means the form was rejected)"
if [ "$CODE" = "200" ]; then grep -o 'class="error-msg">[^<]*' /tmp/resp.html | head -5; fi
NEWV=$("$PY" -c "
import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from core.models import Vendor
v=Vendor.objects.filter(name_en='Test Form Company').order_by('-supplier_id').first()
print(v.supplier_id if v else 'NONE')")
echo "  new supplier_id=$NEWV"

echo "--- register vendor on an activity:"
CODE=$(post "/en/vendors/$NEWV/activities/add/" \
    --data "csrfmiddlewaretoken=$(get_csrf)&sub_activity=$SUBCODE&registration_type=مورد أجنبي&capacity=مورد اساسى&notes=flow test")
echo "  http=$CODE"
"$PY" -c "
import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from core.models import VendorActivity
a=VendorActivity.objects.filter(vendor_id=$NEWV)
print('  registrations:', a.count(), [x.sub_activity_id for x in a])"

ACT=$("$PY" -c "
import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from core.models import VendorActivity
a=VendorActivity.objects.filter(vendor_id=$NEWV).first()
print(a.pk if a else 'NONE')")

echo "--- remove that activity registration:"
CODE=$(post "/en/vendors/$NEWV/activities/$ACT/remove/" --data "csrfmiddlewaretoken=$(get_csrf)")
echo "  http=$CODE"
"$PY" -c "
import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from core.models import VendorActivity
print('  registrations left:', VendorActivity.objects.filter(vendor_id=$NEWV).count())"

echo "--- edit the vendor:"
CODE=$(curl -s -b "$CK" -c "$CK" -o /tmp/resp.html -w "%{http_code}" \
    -H "Referer: $BASE/en/vendors/$NEWV/edit/" -H "X-CSRFToken: $(get_csrf)" \
    --data-urlencode "csrfmiddlewaretoken=$(get_csrf)" \
    --data-urlencode "name_ar=شركة اختبار النموذج" \
    --data-urlencode "name_en=Test Form Company Edited" \
    --data-urlencode "registration_status_new=جديد" \
    --data-urlencode "country=Egypt" \
    --data-urlencode "notes=edited by flow test" \
    "$BASE/en/vendors/$NEWV/edit/")
echo "  http=$CODE"
"$PY" -c "
import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from core.models import Vendor
v=Vendor.objects.filter(pk=$NEWV).first()
print('  name_en now:', v.name_en)"

echo "--- cleanup test vendor:"
"$PY" -c "
import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from core.models import Vendor, VendorActivity, OperationVendor
VendorActivity.objects.filter(vendor_id=$NEWV).delete()
OperationVendor.objects.filter(vendor_id=$NEWV).delete()
Vendor.objects.filter(pk=$NEWV).delete()
print('  deleted test vendor', $NEWV)"
