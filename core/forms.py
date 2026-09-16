from django import forms
from django.forms import inlineformset_factory

from .models import Department, CostCenter, RFQ, RFQItem, Vessel


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
