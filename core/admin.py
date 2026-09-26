from django.contrib import admin

from .models import (
    ClientCode,
    CostCenter,
    Department,
    DepartmentAccess,
    EmployeeAccess,
    Location,
    MainActivity,
    Operation,
    OperationVendor,
    Project,
    RFQ,
    RFQItem,
    SubActivity,
    Vessel,
    Vendor,
    VendorActivity,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "name_ar", "code")
    search_fields = ("name", "name_ar", "code")


@admin.register(Vessel)
class VesselAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


class RFQItemInline(admin.TabularInline):
    model = RFQItem
    extra = 1
    fields = ("line_number", "description", "unit", "quantity", "inventory", "store_code", "maker")


@admin.register(RFQ)
class RFQAdmin(admin.ModelAdmin):
    list_display = (
        "request_number", "requesting_department", "preparation_date",
        "market_type", "status", "estimated_value",
    )
    list_filter = ("status", "market_type", "purchase_method", "preparation_date")
    search_fields = ("request_number", "sap_number", "project")
    inlines = [RFQItemInline]
    readonly_fields = ("created_by", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)



@admin.register(EmployeeAccess)
class EmployeeAccessAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "full_name", "department", "role", "is_active")
    list_filter = ("is_active", "role", "department")
    search_fields = ("employee_id", "full_name")
    list_editable = ("is_active", "role")


@admin.register(DepartmentAccess)
class DepartmentAccessAdmin(admin.ModelAdmin):
    list_display = ("department", "can_view_rfq", "can_create_rfq", "can_view_vendors", "can_view_reports")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "client_name")
    search_fields = ("code", "name", "client_name")


@admin.register(ClientCode)
class ClientCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(MainActivity)
class MainActivityAdmin(admin.ModelAdmin):
    list_display = ("code", "name_ar", "name_en")
    search_fields = ("code", "name_ar", "name_en")


@admin.register(SubActivity)
class SubActivityAdmin(admin.ModelAdmin):
    list_display = ("code", "name_ar", "main_activity", "name_en")
    search_fields = ("code", "name_ar", "name_en")
    list_filter = ("main_activity",)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = (
        "supplier_id", "name_ar", "name_en", "country",
        "category", "registration_status_new", "booklet_type", "is_suspended", "is_cancelled",
    )
    list_filter = ("registration_status_new", "booklet_type", "country", "is_suspended", "is_cancelled")
    search_fields = ("name_ar", "name_en", "country", "category")
    ordering = ("supplier_id",)
    list_per_page = 50
    readonly_fields = ("supplier_id",)


class OperationVendorInline(admin.TabularInline):
    model = OperationVendor
    extra = 0
    fields = ("vendor", "serial", "bid_status", "technical_study", "po_issuance_status", "notes")


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = (
        "operation_no", "year", "requesting_entity", "region",
        "overall_status", "estimated_value",
    )
    list_filter = ("year", "overall_status", "region", "file_dept", "execution_method")
    search_fields = ("task_statement", "requesting_entity", "project_name", "sap_no")
    ordering = ("-operation_no",)
    list_per_page = 50
    inlines = [OperationVendorInline]


@admin.register(OperationVendor)
class OperationVendorAdmin(admin.ModelAdmin):
    list_display = ("operation_no", "vendor", "bid_status", "technical_study", "po_issuance_status")
    list_filter = ("bid_status", "year")
    search_fields = ("vendor__name_ar", "vendor__name_en", "operation_no")
    list_select_related = ("vendor", "operation")


@admin.register(VendorActivity)
class VendorActivityAdmin(admin.ModelAdmin):
    list_display = ("vendor", "sub_activity", "registration_type", "capacity", "brand")
    list_filter = ("registration_type", "capacity")
    search_fields = ("vendor__name_ar", "vendor__name_en", "sub_activity__name_ar", "sub_activity__code")
    list_select_related = ("vendor", "sub_activity", "sub_activity__main_activity")
