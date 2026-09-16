from django.contrib import admin

from .models import CostCenter, Department, RFQ, RFQItem, Vessel


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
