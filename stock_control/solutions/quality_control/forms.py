from django import forms
from services.data_storage.models import ProductItem

from .models import QualityCheck


class QualityCheckForm(forms.ModelForm):
    product_name_lookup = forms.CharField(
        required=False,
        label="Product Name",
        help_text="Optional alternative to the product lot dropdown.",
    )
    lot_number_lookup = forms.CharField(
        required=False,
        label="Lot Number",
        help_text="Optional alternative to the product lot dropdown.",
    )
    signed_off_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        label="Sign-off Time",
    )

    class Meta:
        model = QualityCheck
        fields = [
            "product_item",
            "status",
            "test_reference",
            "result",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, allowed_product_ids=None, **kwargs):
        super().__init__(*args, **kwargs)
        base_queryset = ProductItem.objects.select_related("product").all()
        if allowed_product_ids is not None:
            base_queryset = base_queryset.filter(product_id__in=allowed_product_ids)

        if not self.instance.pk or not getattr(self.instance, "product_item_id", None):
            base_queryset = base_queryset.exclude(
                quality_checks__status=QualityCheck.STATUS_COMPLETED,
                quality_checks__result="pass",
            ).distinct()

        base_queryset = base_queryset.order_by("product__name", "lot_number", "expiry_date")
        self.fields["product_item"].queryset = base_queryset
        self.fields["product_item"].label = "Product Lot"
        self.fields["product_item"].required = False
        self.fields["product_item"].help_text = "Select a lot, or use Product Name and/or Lot Number below."
        self.fields["product_name_lookup"].widget.attrs["list"] = "qc-product-name-options"
        self.fields["lot_number_lookup"].widget.attrs["list"] = "qc-lot-number-options"

        product_names = (
            base_queryset.order_by("product__name")
            .values_list("product__name", flat=True)
            .distinct()
        )
        lot_numbers = base_queryset.order_by("lot_number").values_list("lot_number", flat=True).distinct()
        self.product_name_options = [name for name in product_names if name]
        self.lot_number_options = [lot for lot in lot_numbers if lot]
        self.product_item_options = [
            {
                "id": item.id,
                "label": str(item),
                "product_name": item.product.name,
                "lot_number": item.lot_number,
            }
            for item in base_queryset
        ]

    def clean(self):
        cleaned_data = super().clean()
        selected_item = cleaned_data.get("product_item")
        product_name = (cleaned_data.get("product_name_lookup") or "").strip()
        lot_number = (cleaned_data.get("lot_number_lookup") or "").strip()

        if selected_item:
            return cleaned_data

        if not product_name and not lot_number:
            raise forms.ValidationError(
                "Select a product lot, or provide a product name and/or lot number."
            )

        matches = self.fields["product_item"].queryset
        if product_name:
            matches = matches.filter(product__name__iexact=product_name)
        if lot_number:
            matches = matches.filter(lot_number__iexact=lot_number)

        match_count = matches.count()
        if match_count == 1:
            cleaned_data["product_item"] = matches.first()
            return cleaned_data

        if match_count == 0:
            raise forms.ValidationError(
                "No matching product lot was found for the product name / lot number entered."
            )

        raise forms.ValidationError(
            "Multiple lots match that selection. Add the lot number or use the product lot dropdown."
        )
