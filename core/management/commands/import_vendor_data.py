"""Import the legacy Access back-end (2026-data.accdb) into PostgreSQL.

The Access tables map to the Django models as follows:

    [Project Code]    -> Project          [Tasks]        -> MainActivity
    [Client Code]     -> ClientCode       [Tasks sub]    -> SubActivity
    [Location Code]   -> Location         [Vendors]      -> Vendor
    [Cost Center]     -> CostCenter       [Vendor VS Tasks] -> VendorActivity
    [Oprations]       -> Operation        [Vendor Opration] -> OperationVendor

mdbtools' ``mdb-export`` is used to dump each table to CSV; the dump is then
parsed and loaded with ``bulk_create``.  Everything is wrapped in a
transaction so a half-finished import never leaves the database inconsistent.

Usage:
    manage.py import_vendor_data                    # export + import
    manage.py import_vendor_data --keep             # reuse previous CSV dump
    manage.py import_vendor_data --no-clear         # do not truncate first
    manage.py import_vendor_data --file /path/to/2026-data.accdb
"""

import csv
import os
import shutil
import subprocess
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.contacts import clean_contacts
from core.models import (
    ClientCode,
    CostCenter,
    Location,
    MainActivity,
    Operation,
    OperationVendor,
    Project,
    SubActivity,
    Vendor,
    VendorActivity,
)

CSV_DIR = "/tmp/accdb_csv"

# Access table name -> safe csv file name inside CSV_DIR
TABLES = {
    "Project Code": "Project_Code.csv",
    "Client Code": "Client_Code.csv",
    "Location Code": "Location_Code.csv",
    "Cost Center": "Cost_Center.csv",
    "Tasks": "Tasks.csv",
    "Tasks sub": "Tasks_sub.csv",
    "Vendors": "Vendors.csv",
    "Vendor VS Tasks": "Vendor_VS_Tasks.csv",
    "Oprations": "Oprations.csv",
    "Vendor Opration": "Vendor_Opration.csv",
}

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


class Command(BaseCommand):
    help = "Import 2026-data.accdb (Access vendor list domain) into PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=os.path.join(settings.BASE_DIR, "2026-data.accdb"),
            help="Path to the Access back-end file.",
        )
        parser.add_argument(
            "--keep",
            action="store_true",
            help="Reuse the CSV files already present in %s." % CSV_DIR,
        )
        parser.add_argument(
            "--no-clear",
            action="store_true",
            help="Do not delete existing vendor-list rows before importing.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Rows per bulk_create batch (default 500).",
        )

    # ------------------------------------------------------------------ util
    def handle(self, *args, **opts):
        accdb = opts["file"]
        if not opts["keep"]:
            self._export(accdb)

        missing = [t for t, f in TABLES.items() if not os.path.exists(os.path.join(CSV_DIR, f))]
        if missing:
            raise CommandError("Missing CSV dumps: %s" % ", ".join(missing))

        self.stats = {}
        with transaction.atomic():
            if not opts["no_clear"]:
                self._clear()
            self._import(opts["batch_size"])

        self.stdout.write(self.style.SUCCESS("Import finished:"))
        for table, count in self.stats.items():
            self.stdout.write("  %-18s %6d rows" % (table, count))

    # ---------------------------------------------------------------- export
    def _export(self, accdb):
        if not os.path.exists(accdb):
            raise CommandError("Access file not found: %s" % accdb)
        mdb_export = shutil.which("mdb-export") or os.path.expanduser("~/.local/bin/mdb-export")
        if not os.path.exists(mdb_export):
            raise CommandError("mdb-export not found (install mdbtools).")
        os.makedirs(CSV_DIR, exist_ok=True)
        for table, filename in TABLES.items():
            out = os.path.join(CSV_DIR, filename)
            cmd = [
                mdb_export,
                "-b", "strip",
                "-D", "%Y-%m-%d",
                "-T", "%Y-%m-%d %H:%M:%S",
                accdb, table,
            ]
            with open(out, "w", encoding="utf-8") as fh:
                proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                raise CommandError(
                    "mdb-export failed for %s: %s" % (table, proc.stderr.decode(errors="replace"))
                )
            self.stdout.write("  exported %-18s -> %s" % (table, out))

    def _clear(self):
        # children first
        OperationVendor.objects.all().delete()
        VendorActivity.objects.all().delete()
        Operation.objects.all().delete()
        Vendor.objects.all().delete()
        SubActivity.objects.all().delete()
        MainActivity.objects.all().delete()
        # reference tables are kept (RFQs point at cost centers): update only
        self.stdout.write("  cleared vendor-list tables")

    # ----------------------------------------------------------------- read
    @staticmethod
    def _rows(filename):
        path = os.path.join(CSV_DIR, filename)
        with open(path, encoding="utf-8", errors="replace", newline="") as fh:
            for row in csv.DictReader(fh):
                yield row

    @staticmethod
    def _s(row, col):
        value = row.get(col)
        if value is None:
            return ""
        return str(value).strip()

    @classmethod
    def _i(cls, row, col, default=None):
        raw = cls._s(row, col)
        if not raw:
            return default
        try:
            return int(float(raw.replace(",", "")))
        except ValueError:
            return default

    @classmethod
    def _d(cls, row, col):
        raw = cls._s(row, col)
        if not raw:
            return None
        try:
            value = datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
        if not 1900 <= value.year <= 2100:  # typo years such as 206 / 2062
            return None
        return value

    @classmethod
    def _dt(cls, row, col):
        raw = cls._s(row, col)
        if not raw:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw[:19], fmt)
            except ValueError:
                continue
        return None

    @classmethod
    def _b(cls, row, col):
        raw = cls._s(row, col).lower()
        return raw in ("1", "true", "-1", "yes", "y")

    @classmethod
    def _dec(cls, row, col):
        raw = cls._s(row, col).translate(ARABIC_DIGITS)
        raw = raw.replace(",", "").replace("٫", ".").strip()
        if not raw or raw in (".", "-", "/"):
            return None
        try:
            return Decimal(raw)
        except InvalidOperation:
            return None

    # --------------------------------------------------------------- import
    def _import(self, batch_size):
        self._import_lookups(batch_size)
        self._import_activities(batch_size)
        self._import_vendors(batch_size)
        self._import_operations(batch_size)
        self._import_vendor_activities(batch_size)
        self._import_operation_vendors(batch_size)

    def _import_lookups(self, batch_size):
        projects, clients, locations, centers = [], [], [], []
        for row in self._rows(TABLES["Project Code"]):
            code = self._s(row, "project code")
            if code:
                projects.append(Project(
                    code=code,
                    name=self._s(row, "project name"),
                    client_name=self._s(row, "Client name"),
                    note=self._s(row, "note"),
                ))
        for row in self._rows(TABLES["Client Code"]):
            code = self._s(row, "Client code")
            if code:
                clients.append(ClientCode(
                    code=code,
                    name=self._s(row, "Client name"),
                    note=self._s(row, "note"),
                ))
        for row in self._rows(TABLES["Location Code"]):
            code = self._s(row, "Location code")
            if code:
                locations.append(Location(
                    code=code,
                    name=self._s(row, "Location name"),
                    note=self._s(row, "note"),
                ))
        for row in self._rows(TABLES["Cost Center"]):
            # one Access row carries an empty cost code - keep it (unique = '')
            code = self._s(row, "Cost code")
            centers.append(CostCenter(
                code=code,
                name=self._s(row, "Cost name") or (code or "-"),
                note=self._s(row, "note"),
            ))

        # reference tables may already hold rows used by other modules
        self._upsert(projects, Project, "Project")
        self._upsert(clients, ClientCode, "ClientCode")
        self._upsert(locations, Location, "Location")
        self._upsert(centers, CostCenter, "CostCenter")
        self.stats["Projects"] = len(projects)
        self.stats["Clients"] = len(clients)
        self.stats["Locations"] = len(locations)
        self.stats["Cost Centers"] = len(centers)

    @staticmethod
    def _upsert(objs, model, label):
        for obj in objs:
            model.objects.update_or_create(code=obj.code, defaults={
                f.name: getattr(obj, f.name)
                for f in model._meta.fields
                if f.name != "id" and f.name != "code"
            })

    def _import_activities(self, batch_size):
        mains, subs = [], []
        for row in self._rows(TABLES["Tasks"]):
            code = self._s(row, "كود النشاط الرئيسى")
            if not code:
                continue
            mains.append(MainActivity(
                code=code,
                name_ar=self._s(row, "أسم النشاط الرئيسى A") or code,
                name_en=self._s(row, "أسم النشاط الرئيسى E"),
            ))
        for row in self._rows(TABLES["Tasks sub"]):
            code = self._s(row, "كود النشاط الفرعى")
            main_code = self._s(row, "كود النشاط الرئيسى")
            if not code or not main_code:
                continue
            subs.append(SubActivity(
                code=code,
                main_activity_id=main_code,
                name_ar=self._s(row, "أسم النشاط الفرعى A") or code,
                name_en=self._s(row, "أسم النشاط الفرعى E"),
            ))
        MainActivity.objects.bulk_create(mains, batch_size=batch_size, ignore_conflicts=True)
        # main activities referenced by sub activities must exist
        known = set(MainActivity.objects.values_list("code", flat=True))
        missing = {s.main_activity_id for s in subs} - known
        if missing:
            MainActivity.objects.bulk_create(
                [MainActivity(code=c, name_ar=c) for c in missing], batch_size=batch_size,
            )
        self.stats["Main Activities"] = len(mains)
        self.stats["Sub Activities"] = len(
            SubActivity.objects.bulk_create(subs, batch_size=batch_size, ignore_conflicts=True)
        )

    def _import_vendors(self, batch_size):
        seen, dup = set(), 0
        objs = []
        for row in self._rows(TABLES["Vendors"]):
            pk = self._i(row, "Supplier ID")
            if pk is None or pk in seen:
                dup += 1
                continue
            seen.add(pk)
            data = dict(
                supplier_id=pk,
                name_ar=self._s(row, "أسم المورد A") or "-",
                name_en=self._s(row, "أسم المورد E"),
                booklet_no=self._i(row, "رقم الكراسة"),
                booklet_type=self._s(row, "نوع الكراسة"),
                category=self._s(row, "Categry"),
                sab_no=self._s(row, "رقم الساب"),
                agent=self._s(row, "الوكيل"),
                country=self._s(row, "البلد"),
                address=self._s(row, "العنوان"),
                website=self._s(row, "الموقع الالكترونى"),
                phone1=self._s(row, "التليفون 1"),
                phone2=self._s(row, "التليفون 2"),
                phone3=self._s(row, "التليفون 3"),
                fax1=self._s(row, "الفاكس 1"),
                fax2=self._s(row, "الفاكس 2"),
                mobile1=self._s(row, "المحمول 1"),
                mobile2=self._s(row, "المحمول 2"),
                mobile3=self._s(row, "المحمول 3"),
                email1=self._s(row, "E_mail 1"),
                email2=self._s(row, "E_mail 2"),
                email3=self._s(row, "E_mail 3"),
                agent_address=self._s(row, "عنوان الوكيل"),
                agent_phone1=self._s(row, "تليفون الوكيل 1"),
                agent_phone2=self._s(row, "تليفون الوكيل 2"),
                agent_phone3=self._s(row, "تليفون الوكيل 3"),
                agent_fax1=self._s(row, "فاكس الوكيل 1"),
                agent_fax2=self._s(row, "فاكس الوكيل 2"),
                agent_fax3=self._s(row, "فاكس الوكيل 3"),
                agent_mobile1=self._s(row, "محمول الوكيل 1"),
                agent_mobile2=self._s(row, "محمول الوكيل 2"),
                agent_mobile3=self._s(row, "محمول الوكيل 3"),
                agent_email1=self._s(row, "E_mail الوكيل 1"),
                agent_email2=self._s(row, "E_mail الوكيل 2"),
                agent_email3=self._s(row, "E_mail الوكيل 3"),
                committee_no=self._s(row, "رقم اللجنة"),
                committee_date=self._d(row, "تاريخ اللجنة"),
                registration_status=self._s(row, "موقف  التسجيل"),
                registration_status_new=self._s(row, "موقف التسجيل جديد"),
                data_registered=self._s(row, "مسجل البيانات"),
                commercial_register=self._s(row, "السجل التجارى"),
                commercial_register_expiry=self._d(row, "تاريخ انتهاء السجل التجاري"),
                tax_card=self._s(row, "البطاقه الضريبيه"),
                tax_card_expiry=self._d(row, "تاريخ انتهاء البطاقة الضريبية"),
                vat_registration=self._s(row, "القيمة المضافه"),
                vat_expiry=self._d(row, "تاريخ انتهاء ضريبة القيمة المضافة"),
                contact_person=self._s(row, "الشخص المتصل"),
                owner_name=self._s(row, "أسم صاحب المنشأة"),
                capital_amount=self._i(row, "مبلغ رأس المال"),
                capital_currency=self._s(row, "عملة رأس المال"),
                is_local_registered=self._b(row, "مسجل محلي"),
                is_foreign_registered=self._b(row, "مسجل خارجى"),
                is_suspended=self._b(row, "موقوف"),
                is_cancelled=self._b(row, "مشطوب"),
                is_flagged=self._b(row, "Ahmed"),
                certified=self._s(row, "A certified"),
                notes=self._s(row, "ملاحظات"),
                notes2=self._s(row, "ملاحظات2"),
                special_notes=self._s(row, "ملاحظات خاصة"),
                free_zone=self._s(row, "منطقة حرة"),
                agency_documents=self._s(row, "مستندات الوكالة"),
                cd_vendor=self._s(row, "CD Vendor"),
                committee_file=self._s(row, "committee"),
                access_id=self._i(row, "ID"),
            )
            # the e-mail / website boxes arrive as Access hyperlinks
            # (`a@b.com#mailto:a@b.com#`); store them as real addresses
            clean_contacts(data)
            objs.append(Vendor(**data))
        created = Vendor.objects.bulk_create(objs, batch_size=batch_size)
        self.stats["Vendors"] = len(created)
        if dup:
            self.stdout.write(self.style.WARNING("  skipped %d duplicate vendor IDs" % dup))

    # Access splits the tenders over file departments; the two markets the app
    # cares about are driven by them, the remaining departments (contracts,
    # naval units) fall back to the tender currency.
    FOREIGN_CURRENCIES = {"دولار أمريكى", "يورو", "جنيه إسترلينى", "ريال سعودي"}

    def _market(self, row):
        dept = self._s(row, "إدارة الملف")
        if dept.startswith("المشتريات المحلية"):
            return Operation.Market.LOCAL
        if dept == "المشتريات الخارجية":
            return Operation.Market.FOREIGN
        if self._s(row, "العملة") in self.FOREIGN_CURRENCIES:
            return Operation.Market.FOREIGN
        return Operation.Market.LOCAL

    def _import_operations(self, batch_size):
        # the lookup FKs point at to_field="code", so children store the code
        project_codes = set(Project.objects.values_list("code", flat=True))
        client_codes = set(ClientCode.objects.values_list("code", flat=True))
        center_codes = set(CostCenter.objects.values_list("code", flat=True))
        location_codes = set(Location.objects.values_list("code", flat=True))

        def ref(code, known):
            return code if code and code in known else None

        objs = []
        self.operation_no_map = {}
        for row in self._rows(TABLES["Oprations"]):
            no = self._i(row, "رقم العملية")
            if no is None:
                continue
            obj = Operation(
                operation_no=no,
                file_dept=self._s(row, "إدارة الملف"),
                market=self._market(row),
                execution_method=self._s(row, "طريقة التنفيذ"),
                region=self._s(row, "المنطقة"),
                year=self._s(row, "العام"),
                overall_status=self._s(row, "الموقف العام"),
                project_name=self._s(row, "أسم المشروع"),
                requesting_entity=self._s(row, "الجهة الطالبة"),
                executor_name=self._s(row, "أسم المنفذ"),
                task_statement=self._s(row, "بيان المهمات"),
                tech_specs=self._s(row, "المواصفات الفنية"),
                vendor_list_handover_date=self._d(row, "تاريخ تسليم قائمة الموردين"),
                list_approval_date=self._d(row, "تاريخ إعتماد القائمة"),
                execution_handover_date=self._d(row, "تاريخ تسليم التنفيذ"),
                tender_date=self._d(row, "تاريخ الطرح"),
                technical_opening_date=self._d(row, "تاريخ الفض الفنى"),
                offers_sent_date=self._d(row, "تاريخ إرسال العروض للجهة الطالبة"),
                final_tech_report_date=self._d(row, "تاريخ التقرير الفنى النهائى"),
                financial_opening_date=self._d(row, "تاريخ الفض المالى"),
                committee_presentation_date=self._d(row, "تاريخ العرض على لجنة البت"),
                committee_approval_date=self._d(row, "تاريخ إعتماد لجنة البت"),
                list_sent_entity_date=self._d(row, "تاريخ إرسال القائمة للجهة الطالبة"),
                list_sent_bd_date=self._d(row, "تاريخ إرسال القائمة للتنمية الاعمال"),
                list_approved_entity_date=self._d(row, "تاريخ إعتماد القائمة من الجهة الطالبة"),
                list_approved_bd_date=self._d(row, "تاريخ إعتماد القائمة من تنمية الاعمال"),
                followup_handover_date=self._d(row, "تاريخ تسليم المتابعة"),
                list_preparation_date=self._d(row, "تاريخ اعداد القائمة"),
                requisition_rec_date=self._d(row, "تاريخ إستلام طلب المهمات"),
                till_now=self._dt(row, "till now"),
                notes=self._s(row, "ملاحظات"),
                execution_notes=self._s(row, "ملاحظات تنفيذ"),
                followup_notes=self._s(row, "ملاحظات متابعة"),
                request_notes=self._s(row, "ملاحظات طلبات"),
                vendor_list_memo=self._s(row, "Vendor List"),
                purchasing_department_memo=self._s(row, "Purchasing department"),
                estimated_value=self._dec(row, "إجمالى القيمة التقديرية"),
                currency=self._s(row, "العملة"),
                budget=self._s(row, "الموازنة"),
                general_supplies=self._s(row, "توريدات عمومية"),
                tender_days=self._s(row, "مدة الطرح بالايام"),
                total_days=self._i(row, "total days"),
                all_seq=self._i(row, "ALL"),
                maker_name=self._s(row, "Maker Name"),
                project_id=ref(self._s(row, "project code"), project_codes),
                client_id=ref(self._s(row, "Client Code"), client_codes),
                cost_center_id=ref(self._s(row, "Cost code"), center_codes),
                location_id=ref(self._s(row, "Location Code"), location_codes),
                year_code=self._i(row, "Year Code"),
                vendor_register_executor=self._s(row, "منفذ سجل الموردين"),
                request_receiver=self._s(row, "مستلم طلب المهمات"),
                followup_name=self._s(row, "أسم المتابع"),
                po_status=self._s(row, "موقف أمر التوريد"),
                sap_no=self._s(row, "SAP NO"),
            )
            objs.append(obj)

        created = Operation.objects.bulk_create(objs, batch_size=batch_size)
        self.stats["Operations"] = len(created)
        # re-read ids so child rows can be linked by operation number
        for pk, no in Operation.objects.values_list("id", "operation_no"):
            self.operation_no_map.setdefault(no, pk)

    def _import_vendor_activities(self, batch_size):
        vendor_ids = set(Vendor.objects.values_list("supplier_id", flat=True))
        sub_codes = set(SubActivity.objects.values_list("code", flat=True))
        objs, orphan = [], 0
        for row in self._rows(TABLES["Vendor VS Tasks"]):
            vendor_id = self._i(row, "Supplier ID")
            sub_code = self._s(row, "كود النشاط الفرعى")
            if vendor_id not in vendor_ids or sub_code not in sub_codes:
                orphan += 1
                continue
            objs.append(VendorActivity(
                vendor_id=vendor_id,
                sub_activity_id=sub_code,
                registration_type=self._s(row, "نوع التسجيل"),
                capacity=self._s(row, "صفة التسجيل"),
                notes=self._s(row, "ملاحظات"),
                selected=self._b(row, "Select"),
                flagged=self._s(row, "Ahmed Hany"),
                original_factory=self._s(row, "مصنع أصلى"),
                brand=self._s(row, "الماركة"),
                origin_country=self._s(row, "بلد المنشأ"),
                origin=self._s(row, "المنشأ"),
            ))
        self.stats["Vendor Activities"] = len(
            VendorActivity.objects.bulk_create(objs, batch_size=batch_size)
        )
        if orphan:
            self.stdout.write(self.style.WARNING("  skipped %d orphan vendor/activity rows" % orphan))

    def _import_operation_vendors(self, batch_size):
        vendor_ids = set(Vendor.objects.values_list("supplier_id", flat=True))
        objs, orphan, no_match = [], 0, 0
        for row in self._rows(TABLES["Vendor Opration"]):
            vendor_id = self._i(row, "Supplier ID")
            no = self._i(row, "رقم العملية")
            if vendor_id not in vendor_ids:
                orphan += 1
                continue
            operation_id = self.operation_no_map.get(no) if no is not None else None
            if no is not None and operation_id is None:
                no_match += 1
            objs.append(OperationVendor(
                operation_id=operation_id,
                operation_no=no,
                vendor_id=vendor_id,
                serial=self._i(row, "مسلسل"),
                year=self._s(row, "العام"),
                bid_status=self._s(row, "موقف التقدم"),
                advance_security_status=self._s(row, "موقف التأمين الإبتدائى"),
                final_security_status=self._s(row, "موقف التأمين النهائى"),
                supply_status=self._s(row, "موقف التوريد"),
                technical_study=self._s(row, "موقف الدراسة الفنية"),
                delay_penalty=self._s(row, "موقف غرامة التأخير"),
                notes=self._s(row, "ملاحظات"),
                technical_rejection_reason=self._s(row, "سبب الرفض الفنى"),
                po_issuance_status=self._s(row, "موقف إصدار أمر التوريد"),
                certificates_status=self._s(row, "موقف الشهادات"),
                technical_match=self._s(row, "المطابقة الفنية"),
                advance_security_type=self._s(row, "نوع التأمين الإبتدائى"),
                access_id=self._i(row, "id"),
            ))
        self.stats["Operation Vendors"] = len(
            OperationVendor.objects.bulk_create(objs, batch_size=batch_size)
        )
        if orphan:
            self.stdout.write(self.style.WARNING("  skipped %d orphan operation/vendor rows" % orphan))
        if no_match:
            self.stdout.write(self.style.WARNING("  %d rows reference an unknown operation no" % no_match))
