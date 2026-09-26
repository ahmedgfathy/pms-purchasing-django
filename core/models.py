from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .contacts import parse_emails


class Department(models.Model):
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    name_ar = models.CharField(
        max_length=200, blank=True, default="", verbose_name=_("Name (Arabic)"),
    )
    code = models.CharField(max_length=255, unique=True, verbose_name=_("Code"))

    class Meta:
        ordering = ["name"]
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")

    def __str__(self):
        return f"{self.name} ({self.code})"


class Vessel(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    code = models.CharField(max_length=255, unique=True, verbose_name=_("Code"))

    class Meta:
        ordering = ["name"]
        verbose_name = _("Vessel")
        verbose_name_plural = _("Vessels")

    def __str__(self):
        return f"{self.name} ({self.code})"


class CostCenter(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    code = models.CharField(max_length=255, unique=True, verbose_name=_("Code"))
    note = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Note"))

    class Meta:
        ordering = ["name"]
        verbose_name = _("Cost Center")
        verbose_name_plural = _("Cost Centers")

    def __str__(self):
        return f"{self.name} ({self.code})"


class RFQ(models.Model):
    class MarketType(models.TextChoices):
        LOCAL = "local", _("Local Market")
        FOREIGN = "foreign", _("Foreign Market")

    class PurchaseMethod(models.TextChoices):
        GENERAL_TENDER = "general_tender", _("General Tender")
        DIRECT_ORDER = "direct_order", _("Direct Order")
        BUDGETARY = "budgetary", _("Budgetary")
        NEGOTIATION = "negotiation", _("Negotiation")
        VALID_CONTRACT = "valid_contract", _("Valid Contract")
        LIMITED_TENDER = "limited_tender", _("Limited Tender")

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        SUBMITTED = "submitted", _("Submitted")
        UNDER_REVIEW = "under_review", _("Under Review")
        CHAIRMAN_APPROVED = "chairman_approved", _("Chairman Approved")
        REJECTED = "rejected", _("Rejected")
        VENDOR_SELECTION = "vendor_selection", _("Vendor Selection")
        COMPLETED = "completed", _("Completed")

    class BudgetType(models.TextChoices):
        ASSETS = "assets", _("Assets")
        PROJECTS = "projects", _("Projects")
        CURRENT = "current", _("Current")

    request_number = models.CharField(
        max_length=50, unique=True, verbose_name=_("Mat. Req. No"),
    )
    sap_number = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("SAP No"),
    )

    requesting_department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="rfqs",
        verbose_name=_("Department"),
    )
    vessel = models.ForeignKey(
        Vessel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rfqs", verbose_name=_("Vessel"),
    )
    project = models.CharField(max_length=200, blank=True, default="", verbose_name=_("Project"))
    location = models.CharField(
        max_length=200, blank=True, default="Main HQ", verbose_name=_("Location"),
    )
    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rfqs", verbose_name=_("Cost Center"),
    )

    # One tender (procurement operation) belongs to this RFQ; the vendor list
    # lives on the tender — see Operation / OperationVendor.
    tender = models.ForeignKey(
        "Operation", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rfqs", verbose_name=_("Tender"),
    )

    preparation_date = models.DateField(verbose_name=_("Preparation Date"))
    requisition_rec_date = models.DateField(
        null=True, blank=True, verbose_name=_("Rec. Date"),
    )
    supply_period = models.CharField(
        max_length=200, blank=True, default="", verbose_name=_("Supply Period"),
    )

    market_type = models.CharField(
        max_length=20, choices=MarketType.choices, default=MarketType.LOCAL,
        verbose_name=_("Market"),
    )
    purchase_method = models.CharField(
        max_length=20, choices=PurchaseMethod.choices,
        default=PurchaseMethod.GENERAL_TENDER,
        verbose_name=_("Purchase Method"),
    )
    partial_order_accepted = models.BooleanField(
        default=False, verbose_name=_("Partial order accepted"),
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT,
        verbose_name=_("Status"),
    )

    chairman_approved = models.BooleanField(default=False, verbose_name=_("Chairman Approved"))
    chairman_approved_date = models.DateField(
        null=True, blank=True, verbose_name=_("Approved Date"),
    )

    budget_year = models.CharField(max_length=10, blank=True, default="", verbose_name=_("Budget Year"))
    gl_account = models.CharField(max_length=30, blank=True, default="", verbose_name=_("G.L. Account"))
    emf_number = models.CharField(max_length=30, blank=True, default="", verbose_name=_("E.M.F."))
    estimated_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name=_("Estimated Value (EGP)"),
    )

    budget_type = models.CharField(
        max_length=20, choices=BudgetType.choices, default=BudgetType.CURRENT,
        verbose_name=_("Budget Type"),
    )
    budget_code = models.CharField(max_length=30, blank=True, default="", verbose_name=_("Budget Code"))
    book_number = models.CharField(
        max_length=30, blank=True, default="", verbose_name=_("Book Number"),
    )

    warranty_notes = models.TextField(blank=True, default="", verbose_name=_("Warranty Notes"))
    delivery_notes = models.TextField(blank=True, default="", verbose_name=_("Delivery Notes"))
    attachment = models.FileField(
        upload_to="rfq/attachments/%Y/%m/",
        blank=True,
        default="",
        verbose_name=_("Hard Copy"),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="rfqs_created",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated at"))

    class Meta:
        ordering = ["-preparation_date", "-request_number"]
        verbose_name = _("RFQ")
        verbose_name_plural = _("RFQs")

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
    line_number = models.PositiveIntegerField(verbose_name=_("Line No."))
    description = models.TextField(verbose_name=_("Description"))
    unit = models.CharField(max_length=20, default="Piece", verbose_name=_("Unit"))
    quantity = models.PositiveIntegerField(verbose_name=_("Qty"))
    inventory = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Inventory"))
    store_code = models.CharField(max_length=30, blank=True, default="", verbose_name=_("Store Code"))
    maker = models.CharField(max_length=100, blank=True, default="", verbose_name=_("Maker"))

    class Meta:
        ordering = ["line_number"]
        unique_together = ["rfq", "line_number"]

    def __str__(self):
        return f"Line {self.line_number}: {self.description[:50]}"



# ---------------------------------------------------------------------------
# Vendor list domain — modelled 1:1 from the legacy Access files
# 2026.accdb (front end) + 2026-data.accdb (back end / linked tables).
#
# Access object -> Django model
#   [Tasks]                  -> MainActivity
#   [Tasks sub]              -> SubActivity
#   [Vendors]                -> Vendor            (the vendor register)
#   [Vendor VS Tasks]        -> VendorActivity     (vendor <-> activity)
#   [Oprations]              -> Operation         (Vendor List screen source)
#   [Vendor Opration]        -> OperationVendor   (vendor list of an operation)
#   [Project Code]           -> Project
#   [Client Code]            -> ClientCode
#   [Location Code]          -> Location
# ---------------------------------------------------------------------------


class Project(models.Model):
    code = models.CharField(max_length=255, unique=True, verbose_name=_("Project Code"))
    name = models.CharField(max_length=255, verbose_name=_("Project Name"))
    client_name = models.CharField(
        max_length=200, blank=True, default="", verbose_name=_("Client Name"),
    )
    note = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Note"))

    class Meta:
        ordering = ["code"]
        verbose_name = _("Project")
        verbose_name_plural = _("Projects")

    def __str__(self):
        return f"{self.code} - {self.name}"


class ClientCode(models.Model):
    code = models.CharField(max_length=255, unique=True, verbose_name=_("Client Code"))
    name = models.CharField(max_length=255, verbose_name=_("Client Name"))
    note = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Note"))

    class Meta:
        ordering = ["code"]
        verbose_name = _("Client")
        verbose_name_plural = _("Clients")

    def __str__(self):
        return f"{self.code} - {self.name}"


class Location(models.Model):
    code = models.CharField(max_length=255, unique=True, verbose_name=_("Location Code"))
    name = models.CharField(max_length=255, verbose_name=_("Location Name"))
    note = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Note"))

    class Meta:
        ordering = ["code"]
        verbose_name = _("Location")
        verbose_name_plural = _("Locations")

    def __str__(self):
        return f"{self.code} - {self.name}"


class MainActivity(models.Model):
    """[Tasks] — main activity categories (Arabic + English names)."""

    code = models.CharField(max_length=10, unique=True, verbose_name=_("Activity Code"))
    name_ar = models.CharField(max_length=100, verbose_name=_("Name (Arabic)"))
    name_en = models.CharField(
        max_length=100, blank=True, default="", verbose_name=_("Name (English)"),
    )

    class Meta:
        ordering = ["code"]
        verbose_name = _("Main Activity")
        verbose_name_plural = _("Main Activities")

    def __str__(self):
        return f"{self.code} - {self.name_ar}"

    @property
    def label(self):
        return self.name_ar or self.name_en


class SubActivity(models.Model):
    """[Tasks sub] — sub activities under a main activity."""

    code = models.CharField(max_length=10, unique=True, verbose_name=_("Sub Activity Code"))
    main_activity = models.ForeignKey(
        MainActivity, on_delete=models.PROTECT, related_name="sub_activities",
        to_field="code", verbose_name=_("Main Activity"),
    )
    name_ar = models.CharField(max_length=150, verbose_name=_("Name (Arabic)"))
    name_en = models.CharField(
        max_length=150, blank=True, default="", verbose_name=_("Name (English)"),
    )

    class Meta:
        ordering = ["code"]
        verbose_name = _("Sub Activity")
        verbose_name_plural = _("Sub Activities")

    def __str__(self):
        return f"{self.code} - {self.name_ar}"

    @property
    def label(self):
        return self.name_ar or self.name_en


class Vendor(models.Model):
    """[Vendors] — the vendor register (سجل الموردين), 8.8k rows in 2026-data."""

    class BookletType(models.TextChoices):
        LOCAL = "محلى", _("Local")
        FOREIGN = "خارجى", _("Foreign")
        NONE = "", _("—")

    supplier_id = models.IntegerField(primary_key=True, verbose_name=_("Supplier ID"))
    name_ar = models.CharField(max_length=75, verbose_name=_("Vendor Name (Arabic)"))
    name_en = models.CharField(
        max_length=75, blank=True, default="", verbose_name=_("Vendor Name (English)"),
    )

    booklet_no = models.IntegerField(null=True, blank=True, verbose_name=_("Booklet No"))
    booklet_type = models.CharField(
        max_length=10, choices=BookletType.choices, blank=True, default="",
        verbose_name=_("Booklet Type"),
    )
    category = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Category"),
    )
    sab_no = models.CharField(max_length=255, blank=True, default="", verbose_name=_("SAP No."))

    agent = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Agent"))
    country = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Country"))
    address = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Address"),
    )
    # Access stores these as Memo/Hyperlink columns (values go far beyond 255)
    website = models.TextField(blank=True, default="", verbose_name=_("Website"))

    phone1 = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Phone 1"))
    phone2 = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Phone 2"))
    phone3 = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Phone 3"))
    fax1 = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Fax 1"))
    fax2 = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Fax 2"))
    mobile1 = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Mobile 1"))
    mobile2 = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Mobile 2"))
    mobile3 = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Mobile 3"))
    email1 = models.TextField(blank=True, default="", verbose_name=_("E-mail 1"))
    email2 = models.TextField(blank=True, default="", verbose_name=_("E-mail 2"))
    email3 = models.TextField(blank=True, default="", verbose_name=_("E-mail 3"))

    agent_address = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Agent Address"),
    )
    agent_phone1 = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Agent Phone 1"),
    )
    agent_phone2 = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Agent Phone 2"),
    )
    agent_phone3 = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Agent Phone 3"),
    )
    agent_fax1 = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Agent Fax 1"),
    )
    agent_fax2 = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Agent Fax 2"),
    )
    agent_fax3 = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Agent Fax 3"),
    )
    agent_mobile1 = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Agent Mobile 1"),
    )
    agent_mobile2 = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Agent Mobile 2"),
    )
    agent_mobile3 = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Agent Mobile 3"),
    )
    agent_email1 = models.TextField(blank=True, default="", verbose_name=_("Agent E-mail 1"))
    agent_email2 = models.TextField(blank=True, default="", verbose_name=_("Agent E-mail 2"))
    agent_email3 = models.TextField(blank=True, default="", verbose_name=_("Agent E-mail 3"))

    committee_no = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Committee No"),
    )
    committee_date = models.DateField(
        null=True, blank=True, verbose_name=_("Committee Date"),
    )
    registration_status = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Registration Status"),
    )
    registration_status_new = models.CharField(
        max_length=50, default="", verbose_name=_("Registration Status (new)"),
    )
    data_registered = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Data Registered By"),
    )

    commercial_register = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Commercial Register"),
    )
    commercial_register_expiry = models.DateField(
        null=True, blank=True, verbose_name=_("Commercial Register Expiry"),
    )
    tax_card = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Tax Card"),
    )
    tax_card_expiry = models.DateField(
        null=True, blank=True, verbose_name=_("Tax Card Expiry"),
    )
    vat_registration = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("VAT Registration"),
    )
    vat_expiry = models.DateField(
        null=True, blank=True, verbose_name=_("VAT Expiry"),
    )
    contact_person = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Contact Person"),
    )
    owner_name = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Owner Name"),
    )

    capital_amount = models.IntegerField(
        null=True, blank=True, verbose_name=_("Capital Amount"),
    )
    capital_currency = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Capital Currency"),
    )
    is_local_registered = models.BooleanField(default=False, verbose_name=_("Registered locally"))
    is_foreign_registered = models.BooleanField(default=False, verbose_name=_("Registered abroad"))
    is_suspended = models.BooleanField(default=False, verbose_name=_("Suspended"))
    is_cancelled = models.BooleanField(default=False, verbose_name=_("Cancelled"))
    is_flagged = models.BooleanField(default=False, verbose_name=_("Flagged"))
    certified = models.CharField(
        max_length=20, blank=True, default="", verbose_name=_("A Certified"),
    )

    notes = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Notes"))
    notes2 = models.TextField(blank=True, default="", verbose_name=_("Notes 2"))
    special_notes = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Special Notes"),
    )
    free_zone = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Free Zone"),
    )
    agency_documents = models.TextField(
        blank=True, default="", verbose_name=_("Agency Documents"),
    )
    cd_vendor = models.TextField(blank=True, default="", verbose_name=_("CD Vendor"))
    committee_file = models.TextField(blank=True, default="", verbose_name=_("Committee File"))
    access_id = models.IntegerField(null=True, blank=True, verbose_name=_("Access ID"))

    class Meta:
        ordering = ["name_ar"]
        verbose_name = _("Vendor")
        verbose_name_plural = _("Vendors")
        indexes = [
            models.Index(fields=["name_ar"], name="vendor_name_ar_idx"),
            models.Index(fields=["registration_status_new"], name="vendor_regstatus_idx"),
            models.Index(fields=["country"], name="vendor_country_idx"),
        ]

    def __str__(self):
        return f"{self.supplier_id} - {self.name_ar}"

    @property
    def label(self):
        return self.name_ar or self.name_en

    @property
    def phone(self):
        return self.phone1 or self.mobile1 or ""

    @property
    def email(self):
        """First deliverable address (E-mail 1, else the agent's) — the
        list tables link this one with ``mailto:`` (see core/contacts.py)."""
        for raw in (self.email1, self.agent_email1):
            found = parse_emails(raw)
            if found:
                return found[0]
        return ""

    def save(self, *args, **kwargs):
        if not self.supplier_id:
            top = Vendor.objects.aggregate(m=models.Max("supplier_id"))["m"] or 0
            self.supplier_id = top + 1
        super().save(*args, **kwargs)


class VendorActivity(models.Model):
    """[Vendor VS Tasks] — which vendor is registered for which sub activity."""

    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name="activities",
        verbose_name=_("Vendor"),
    )
    sub_activity = models.ForeignKey(
        SubActivity, on_delete=models.PROTECT, related_name="vendors",
        to_field="code", verbose_name=_("Sub Activity"),
    )
    registration_type = models.CharField(
        max_length=100, blank=True, default="", verbose_name=_("Registration Type"),
    )
    capacity = models.CharField(
        max_length=100, blank=True, default="", verbose_name=_("Registration Capacity"),
    )
    notes = models.TextField(blank=True, default="", verbose_name=_("Notes"))
    selected = models.BooleanField(default=False, verbose_name=_("Selected"))
    flagged = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Flag"),
    )
    original_factory = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Original Factory"),
    )
    brand = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Brand"))
    origin_country = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Origin Country"),
    )
    origin = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Origin"))

    class Meta:
        ordering = ["sub_activity__code"]
        verbose_name = _("Vendor Activity")
        verbose_name_plural = _("Vendor Activities")

    def __str__(self):
        return f"{self.vendor_id} - {self.sub_activity_id}"


class Operation(models.Model):
    """[Oprations] — record source of the legacy 'Vendor List' screen."""

    class Market(models.TextChoices):
        LOCAL = "local", _("Local")
        FOREIGN = "foreign", _("Foreign")

    operation_no = models.IntegerField(verbose_name=_("Operation No"), db_index=True)
    file_dept = models.CharField(
        max_length=50, default="", verbose_name=_("File Department"),
    )
    market = models.CharField(
        max_length=10, choices=Market.choices, default=Market.LOCAL,
        db_index=True, verbose_name=_("Market"),
    )
    execution_method = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Execution Method"),
    )
    region = models.CharField(max_length=50, default="", verbose_name=_("Region"))
    year = models.CharField(max_length=4, default="", verbose_name=_("Year"))
    overall_status = models.CharField(
        max_length=50, default="", verbose_name=_("Overall Status"),
    )
    project_name = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Project Name"),
    )
    requesting_entity = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Requesting Entity"),
    )
    executor_name = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Executor Name"),
    )
    task_statement = models.CharField(
        max_length=255, default="", verbose_name=_("Task Statement"),
    )
    tech_specs = models.TextField(blank=True, default="", verbose_name=_("Technical Specs"))

    vendor_list_handover_date = models.DateField(
        null=True, blank=True, verbose_name=_("Vendor List Handover Date"),
    )
    list_approval_date = models.DateField(
        null=True, blank=True, verbose_name=_("Vendor List Approval Date"),
    )
    execution_handover_date = models.DateField(
        null=True, blank=True, verbose_name=_("Execution Handover Date"),
    )
    tender_date = models.DateField(null=True, blank=True, verbose_name=_("Tender Date"))
    technical_opening_date = models.DateField(
        null=True, blank=True, verbose_name=_("Technical Opening Date"),
    )
    offers_sent_date = models.DateField(
        null=True, blank=True, verbose_name=_("Offers Sent Date"),
    )
    final_tech_report_date = models.DateField(
        null=True, blank=True, verbose_name=_("Final Technical Report Date"),
    )
    financial_opening_date = models.DateField(
        null=True, blank=True, verbose_name=_("Financial Opening Date"),
    )
    committee_presentation_date = models.DateField(
        null=True, blank=True, verbose_name=_("Committee Presentation Date"),
    )
    committee_approval_date = models.DateField(
        null=True, blank=True, verbose_name=_("Committee Approval Date"),
    )
    list_sent_entity_date = models.DateField(
        null=True, blank=True, verbose_name=_("List Sent to Entity Date"),
    )
    list_sent_bd_date = models.DateField(
        null=True, blank=True, verbose_name=_("List Sent to BD Date"),
    )
    list_approved_entity_date = models.DateField(
        null=True, blank=True, verbose_name=_("List Approved by Entity Date"),
    )
    list_approved_bd_date = models.DateField(
        null=True, blank=True, verbose_name=_("List Approved by BD Date"),
    )
    followup_handover_date = models.DateField(
        null=True, blank=True, verbose_name=_("Follow-up Handover Date"),
    )
    list_preparation_date = models.DateField(
        null=True, blank=True, verbose_name=_("List Preparation Date"),
    )
    requisition_rec_date = models.DateField(
        null=True, blank=True, verbose_name=_("Requisition Received Date"),
    )
    till_now = models.DateTimeField(null=True, blank=True, verbose_name=_("Till Now"))

    notes = models.TextField(blank=True, default="", verbose_name=_("Notes"))
    execution_notes = models.TextField(blank=True, default="", verbose_name=_("Execution Notes"))
    followup_notes = models.TextField(blank=True, default="", verbose_name=_("Follow-up Notes"))
    request_notes = models.TextField(blank=True, default="", verbose_name=_("Request Notes"))
    vendor_list_memo = models.TextField(
        blank=True, default="", verbose_name=_("Vendor List"),
    )
    purchasing_department_memo = models.TextField(
        blank=True, default="", verbose_name=_("Purchasing Department"),
    )

    estimated_value = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        verbose_name=_("Estimated Value"),
    )
    currency = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Currency"))
    budget = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Budget"))
    general_supplies = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("General Supplies"),
    )
    tender_days = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Tender Days"),
    )
    total_days = models.IntegerField(null=True, blank=True, verbose_name=_("Total Days"))
    all_seq = models.IntegerField(null=True, blank=True, verbose_name=_("Sequence (ALL)"))
    maker_name = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Maker Name"),
    )

    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="operations", to_field="code", verbose_name=_("Project Code"),
    )
    client = models.ForeignKey(
        ClientCode, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="operations", to_field="code", verbose_name=_("Client Code"),
    )
    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="operations", to_field="code", verbose_name=_("Cost Center"),
    )
    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="operations", to_field="code", verbose_name=_("Location Code"),
    )
    year_code = models.IntegerField(null=True, blank=True, verbose_name=_("Year Code"))

    vendor_register_executor = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Vendor Register Executor"),
    )
    request_receiver = models.CharField(
        max_length=50, default="", verbose_name=_("Request Receiver"),
    )
    followup_name = models.CharField(
        max_length=50, blank=True, default="", verbose_name=_("Follow-up Person"),
    )
    po_status = models.CharField(
        max_length=255, default="", verbose_name=_("Purchase Order Status"),
    )
    sap_no = models.CharField(max_length=255, blank=True, default="", verbose_name=_("SAP No"))

    class Meta:
        ordering = ["-operation_no"]
        verbose_name = _("Operation")
        verbose_name_plural = _("Operations")

    def __str__(self):
        return f"{self.operation_no} - {self.task_statement[:40]}"

    @property
    def vendors_count(self):
        return self.operation_vendors.count()

    @property
    def display_value(self):
        if self.estimated_value is None:
            return ""
        return f"{self.estimated_value:,.2f} {self.currency}".strip()


class OperationVendor(models.Model):
    """[Vendor Opration] — the vendor list of one operation (the sub form)."""

    operation = models.ForeignKey(
        Operation, on_delete=models.CASCADE, related_name="operation_vendors",
        null=True, blank=True, verbose_name=_("Operation"),
    )
    operation_no = models.IntegerField(
        null=True, blank=True, verbose_name=_("Operation No"), db_index=True,
    )
    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name="operation_links",
        verbose_name=_("Vendor"),
    )
    serial = models.IntegerField(null=True, blank=True, verbose_name=_("Serial"))
    year = models.CharField(max_length=4, blank=True, default="", verbose_name=_("Year"))

    bid_status = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Bid Status"),
    )
    advance_security_status = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Advance Security Status"),
    )
    final_security_status = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Final Security Status"),
    )
    supply_status = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Supply Status"),
    )
    technical_study = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Technical Study"),
    )
    technical_match = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Technical Match"),
    )
    technical_rejection_reason = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Technical Rejection Reason"),
    )
    delay_penalty = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Delay Penalty"),
    )
    po_issuance_status = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("PO Issuance Status"),
    )
    certificates_status = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Certificates Status"),
    )
    advance_security_type = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Advance Security Type"),
    )
    notes = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Notes"),
    )
    access_id = models.IntegerField(null=True, blank=True, verbose_name=_("Access ID"))

    class Meta:
        ordering = ["serial", "vendor_id"]
        verbose_name = _("Operation Vendor")
        verbose_name_plural = _("Operation Vendors")

    def __str__(self):
        return f"op {self.operation_no} / vendor {self.vendor_id}"


class EmployeeAccess(models.Model):
    """Controls which AD employees can login and what they see."""

    ROLE_CHOICES = [
        ("viewer", _("Viewer")),
        ("requester", _("Requester")),
        ("purchaser", _("Purchaser")),
        ("manager", _("Manager")),
        ("admin", _("Admin")),
    ]

    employee_id = models.CharField(
        max_length=50, unique=True,
        help_text=_("AD sAMAccountName (e.g. 2669)"),
        verbose_name=_("Employee ID"),
    )
    full_name = models.CharField(
        max_length=200, blank=True, default="", verbose_name=_("Full Name"),
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="employees",
        verbose_name=_("Department"),
    )
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default="viewer", verbose_name=_("Role"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    # Module visibility
    can_view_rfq = models.BooleanField(default=True, verbose_name=_("Can view RFQ"))
    can_create_rfq = models.BooleanField(default=False, verbose_name=_("Can create RFQ"))
    can_edit_rfq = models.BooleanField(default=False, verbose_name=_("Can edit RFQ"))
    can_delete_rfq = models.BooleanField(default=False, verbose_name=_("Can delete RFQ"))
    can_approve_rfq = models.BooleanField(default=False, verbose_name=_("Can approve RFQ"))

    can_view_vendors = models.BooleanField(default=True, verbose_name=_("Can view vendors"))
    can_create_vendors = models.BooleanField(default=False, verbose_name=_("Can create vendors"))

    can_view_reports = models.BooleanField(default=True, verbose_name=_("Can view reports"))
    can_view_admin = models.BooleanField(default=False, verbose_name=_("Can view administration"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))

    class Meta:
        ordering = ["employee_id"]
        verbose_name = _("Employee Access")
        verbose_name_plural = _("Employee Access")

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
        verbose_name = _("Department Access")
        verbose_name_plural = _("Department Access")

    def __str__(self):
        return _("Access: %(department)s") % {"department": self.department}
