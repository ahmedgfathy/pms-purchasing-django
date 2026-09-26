from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from .contacts import CONTACT_FIELDS, clean_contacts
from .models import Department, CostCenter, RFQ, RFQItem, Vessel, Vendor, VendorActivity


class RFQForm(forms.ModelForm):
    class Meta:
        model = RFQ
        fields = [
            "request_number", "sap_number",
            "requesting_department", "vessel", "project", "location", "cost_center",
            "preparation_date", "requisition_rec_date", "supply_period",
            "market_type", "purchase_method", "partial_order_accepted",
            "status",
            "budget_year", "gl_account", "emf_number", "estimated_value",
            "budget_type", "budget_code", "book_number",
            "warranty_notes", "delivery_notes",
            "attachment",
        ]
        widgets = {
            "request_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 1568"}),
            "sap_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 10008216"}),
            "project": forms.TextInput(attrs={"class": "form-input"}),
            "location": forms.TextInput(attrs={"class": "form-input", "value": "Main HQ"}),
            "supply_period": forms.TextInput(attrs={"class": "form-input"}),
            "preparation_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "requisition_rec_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "chairman_approved_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "budget_year": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 2025"}),
            "gl_account": forms.TextInput(attrs={"class": "form-input"}),
            "emf_number": forms.TextInput(attrs={"class": "form-input"}),
            "estimated_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "budget_code": forms.TextInput(attrs={"class": "form-input"}),
            "book_number": forms.TextInput(attrs={"class": "form-input"}),
            "warranty_notes": forms.Textarea(attrs={"class": "form-input", "rows": 2}),
            "delivery_notes": forms.Textarea(attrs={"class": "form-input", "rows": 2}),
            "attachment": forms.ClearableFileInput(attrs={"class": "form-input", "accept": ".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.bmp,.tiff"}),
            "requesting_department": forms.Select(attrs={"class": "form-input"}),
            "vessel": forms.Select(attrs={"class": "form-input"}),
            "cost_center": forms.Select(attrs={"class": "form-input"}),
            "market_type": forms.Select(attrs={"class": "form-input"}),
            "purchase_method": forms.Select(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-input"}),
            "budget_type": forms.Select(attrs={"class": "form-input"}),
        }


class RFQItemForm(forms.ModelForm):
    class Meta:
        model = RFQItem
        fields = ["line_number", "description", "unit", "quantity", "inventory", "store_code", "maker"]
        widgets = {
            "line_number": forms.NumberInput(attrs={"class": "form-input", "style": "width:60px"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 2}),
            "unit": forms.TextInput(attrs={"class": "form-input", "value": "Piece"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input", "style": "width:80px"}),
            "inventory": forms.TextInput(attrs={"class": "form-input"}),
            "store_code": forms.TextInput(attrs={"class": "form-input"}),
            "maker": forms.TextInput(attrs={"class": "form-input"}),
        }


RFQItemFormSet = inlineformset_factory(
    RFQ, RFQItem,
    form=RFQItemForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class StyledFormMixin:
    """Apply the Win95 field styling to every widget of a form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check")
            else:
                widget.attrs.setdefault("class", "form-input")
            if isinstance(widget, forms.DateInput):
                widget.attrs.setdefault("type", "date")
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("rows", 3)


class VendorForm(StyledFormMixin, forms.ModelForm):
    """[Vendors] add / edit screen (Access 'New Vendor Enter')."""

    class Meta:
        model = Vendor
        fields = [
            # identification
            "name_ar", "name_en", "booklet_no", "booklet_type", "category",
            "sab_no", "country", "address", "website",
            # contacts
            "phone1", "phone2", "phone3",
            "mobile1", "mobile2", "mobile3",
            "fax1", "fax2",
            "email1", "email2", "email3",
            # agent
            "agent", "agent_address",
            "agent_phone1", "agent_phone2", "agent_phone3",
            "agent_fax1", "agent_fax2", "agent_fax3",
            "agent_mobile1", "agent_mobile2", "agent_mobile3",
            "agent_email1", "agent_email2", "agent_email3",
            # registration
            "registration_status", "registration_status_new",
            "committee_no", "committee_date", "data_registered", "certified",
            "capital_amount", "capital_currency",
            "is_local_registered", "is_foreign_registered",
            "is_suspended", "is_cancelled", "is_flagged",
            # documents
            "commercial_register", "commercial_register_expiry",
            "tax_card", "tax_card_expiry",
            "vat_registration", "vat_expiry",
            "contact_person", "owner_name", "free_zone",
            "agency_documents", "cd_vendor", "committee_file",
            # notes
            "notes", "notes2", "special_notes",
        ]

    def clean_name_ar(self):
        value = (self.cleaned_data.get("name_ar") or "").strip()
        if not value:
            raise forms.ValidationError(_("Vendor name is required."))
        return value

    def clean(self):
        """Keep the contact boxes in the shape core.contacts.py defines:
        real addresses only (one per link) and one usable website URL."""
        cleaned = super().clean() or {}
        fields = [
            name for name in CONTACT_FIELDS
            if name in self.fields and name in cleaned
        ]
        data = {name: cleaned[name] or "" for name in fields}
        clean_contacts(data)
        cleaned.update(data)
        return cleaned


class VendorActivityForm(StyledFormMixin, forms.ModelForm):
    """Register a vendor on a sub activity (Access 'Vendor VS Tasks')."""

    class Meta:
        model = VendorActivity
        fields = [
            "sub_activity", "registration_type", "capacity",
            "original_factory", "brand", "origin_country", "origin", "notes",
        ]
