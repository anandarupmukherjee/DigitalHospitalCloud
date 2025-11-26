from django import forms
from django.utils.timezone import now

from services.data_storage.models import PurchaseOrder


class PurchaseOrderForm(forms.ModelForm):
    product_name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"readonly": "readonly", "id": "order-product-name"}
        ),
    )
    product_code = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"readonly": "readonly", "id": "order-product-code"}
        ),
    )

    class Meta:
        model = PurchaseOrder
        fields = [
            "product_name",
            "product_code",
            "quantity_ordered",
            "expected_delivery",
            "status",
        ]
        widgets = {
            "expected_delivery": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "status": forms.Select(
                choices=[("Ordered", "Ordered"), ("Delivered", "Delivered")]
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product_name"].label = "Product Name"
        self.fields["product_code"].label = "Product Code"
        if not self.initial.get("expected_delivery"):
            self.initial["expected_delivery"] = now().strftime("%Y-%m-%dT%H:%M")


class PurchaseOrderCompletionForm(forms.Form):
    barcode = forms.CharField(
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Scan or enter barcode"}
        )
    )
    product_code = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    product_name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    lot_number = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    expiry_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    quantity_ordered = forms.IntegerField(
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    status = forms.ChoiceField(
        choices=[("Delivered", "Delivered")],
        widget=forms.Select(attrs={"class": "form-control"}),
    )
