from django.conf import settings
from django.db import models
from django.urls import reverse


class Department(models.Model):
    name = models.CharField(max_length=200)
    name_ar = models.CharField(max_length=200, blank=True, default="")
    code = models.CharField(max_length=20, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Vessel(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class CostCenter(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Cost Center"
        verbose_name_plural = "Cost Centers"

    def __str__(self):
        return f"{self.name} ({self.code})"


class RFQ(models.Model):
    class MarketType(models.TextChoices):
        LOCAL = "local", "Local Market"
        FOREIGN = "foreign", "Foreign Market"

    class PurchaseMethod(models.TextChoices):
        GENERAL_TENDER = "general_tender", "General Tender"
        DIRECT_ORDER = "direct_order", "Direct Order"
        BUDGETARY = "budgetary", "Budgetary"
        NEGOTIATION = "negotiation", "Negotiation"
        VALID_CONTRACT = "valid_contract", "Valid Contract"
        LIMITED_TENDER = "limited_tender", "Limited Tender"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        CHAIRMAN_APPROVED = "chairman_approved", "Chairman Approved"
        REJECTED = "rejected", "Rejected"
        VENDOR_SELECTION = "vendor_selection", "Vendor Selection"
        COMPLETED = "completed", "Completed"

    class BudgetType(models.TextChoices):
        ASSETS = "assets", "Assets"
        PROJECTS = "projects", "Projects"
        CURRENT = "current", "Current"

    request_number = models.CharField(max_length=50, unique=True, verbose_name="Mat. Req. No")
    sap_number = models.CharField(max_length=50, blank=True, default="", verbose_name="SAP No")

    requesting_department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="rfqs",
        verbose_name="Requesting Department",
    )
    vessel = models.ForeignKey(
        Vessel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rfqs", verbose_name="Vessel",
    )
    project = models.CharField(max_length=200, blank=True, default="")
    location = models.CharField(max_length=200, blank=True, default="Main HQ")
    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rfqs", verbose_name="Cost Center",
    )

    preparation_date = models.DateField(verbose_name="Preparation Date")
    requisition_rec_date = models.DateField(
        null=True, blank=True, verbose_name="Requisition Rec. Date",
    )
    supply_period = models.CharField(max_length=200, blank=True, default="")

    market_type = models.CharField(
        max_length=20, choices=MarketType.choices, default=MarketType.LOCAL,
    )
    purchase_method = models.CharField(
        max_length=20, choices=PurchaseMethod.choices,
        default=PurchaseMethod.GENERAL_TENDER,
    )
    partial_order_accepted = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT,
    )

    chairman_approved = models.BooleanField(default=False)
    chairman_approved_date = models.DateField(null=True, blank=True)

    budget_year = models.CharField(max_length=10, blank=True, default="")
    gl_account = models.CharField(max_length=30, blank=True, default="")
    emf_number = models.CharField(max_length=30, blank=True, default="")
    estimated_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Estimated Value (EGP)",
    )

    budget_type = models.CharField(
        max_length=20, choices=BudgetType.choices, default=BudgetType.CURRENT,
    )
    budget_code = models.CharField(max_length=30, blank=True, default="")
    book_number = models.CharField(max_length=30, blank=True, default="")

    warranty_notes = models.TextField(blank=True, default="")
    delivery_notes = models.TextField(blank=True, default="")
    attachment = models.FileField(
        upload_to="rfq/attachments/%Y/%m/",
        blank=True,
        default="",
        verbose_name="Hard Copy",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="rfqs_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-preparation_date", "-request_number"]
        verbose_name = "RFQ"
        verbose_name_plural = "RFQs"

    def __str__(self):
        return f"{self.request_number} - {self.requesting_department}"

    def get_absolute_url(self):
        return reverse("rfq_detail", kwargs={"pk": self.pk})

    @property
    def total_items(self):
        return self.items.count()

    @property
    def total_quantity(self):
        return self.items.aggregate(total=models.Sum("quantity"))["total"] or 0


class RFQItem(models.Model):
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name="items")
    line_number = models.PositiveIntegerField(verbose_name="ID")
    description = models.TextField(verbose_name="Description")
    unit = models.CharField(max_length=20, default="Piece", verbose_name="Unit")
    quantity = models.PositiveIntegerField(verbose_name="Quantity Needed")
    inventory = models.CharField(max_length=50, blank=True, default="", verbose_name="Inventory")
    store_code = models.CharField(max_length=30, blank=True, default="", verbose_name="Store Code")
    maker = models.CharField(max_length=100, blank=True, default="", verbose_name="Maker")

    class Meta:
        ordering = ["line_number"]
        unique_together = ["rfq", "line_number"]

    def __str__(self):
        return f"Line {self.line_number}: {self.description[:50]}"



class EmployeeAccess(models.Model):
    """Controls which AD employees can login and what they see."""

    ROLE_CHOICES = [
        ("viewer", "Viewer"),
        ("requester", "Requester"),
        ("purchaser", "Purchaser"),
        ("manager", "Manager"),
        ("admin", "Admin"),
    ]

    employee_id = models.CharField(
        max_length=50, unique=True,
        help_text="AD sAMAccountName (e.g. 2669)",
    )
    full_name = models.CharField(max_length=200, blank=True, default="")
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="employees",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="viewer")
    is_active = models.BooleanField(default=True)

    # Module visibility
    can_view_rfq = models.BooleanField(default=True)
    can_create_rfq = models.BooleanField(default=False)
    can_edit_rfq = models.BooleanField(default=False)
    can_delete_rfq = models.BooleanField(default=False)
    can_approve_rfq = models.BooleanField(default=False)

    can_view_vendors = models.BooleanField(default=True)
    can_create_vendors = models.BooleanField(default=False)

    can_view_reports = models.BooleanField(default=True)
    can_view_admin = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["employee_id"]
        verbose_name = "Employee Access"
        verbose_name_plural = "Employee Access"

    def __str__(self):
        return f"{self.employee_id} - {self.full_name or 'No name'} ({self.get_role_display()})"


class DepartmentAccess(models.Model):
    """Which departments can see which modules."""
    department = models.OneToOneField(
        Department, on_delete=models.CASCADE, related_name="access_config",
    )
    can_view_rfq = models.BooleanField(default=True)
    can_create_rfq = models.BooleanField(default=True)
    can_view_vendors = models.BooleanField(default=True)
    can_view_reports = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Department Access"
        verbose_name_plural = "Department Access"

    def __str__(self):
        return f"Access: {self.department}"
