from django import forms
from services.data_storage.models import ProductItem

from .models import QualityCheck


class QualityCheckForm(forms.ModelForm):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_queryset = ProductItem.objects.select_related("product").all()

        if not self.instance.pk or not getattr(self.instance, "product_item_id", None):
            base_queryset = base_queryset.exclude(
                quality_checks__status=QualityCheck.STATUS_COMPLETED,
                quality_checks__result="pass",
            ).distinct()

        self.fields["product_item"].queryset = base_queryset
        self.fields["product_item"].label = "Product Lot"
