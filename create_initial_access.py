import os, sys, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, "/home/xinreal/pms-purchasing-django")
django.setup()

from core.models import EmployeeAccess, Department

# Create IT department if not exists
it_dept, _ = Department.objects.get_or_create(
    code="1110000007",
    defaults={"name": "Information Technology", "name_ar": "تكنولوجيا المعلومات"},
)

# Add user 2669 as admin
access, created = EmployeeAccess.objects.get_or_create(
    employee_id="2669",
    defaults={
        "full_name": "Admin User",
        "department": it_dept,
        "role": "admin",
        "is_active": True,
        "can_view_rfq": True,
        "can_create_rfq": True,
        "can_edit_rfq": True,
        "can_delete_rfq": True,
        "can_approve_rfq": True,
        "can_view_vendors": True,
        "can_create_vendors": True,
        "can_view_reports": True,
        "can_view_admin": True,
    },
)

if created:
    print(f"Created EmployeeAccess for 2669 (admin role)")
else:
    print(f"EmployeeAccess for 2669 already exists")
