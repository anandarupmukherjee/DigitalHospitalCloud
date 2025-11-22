from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from services.data_storage.models import Location, ProductItem, Product
from .models import LocationStock, UserLocation

User = get_user_model()


class LocationStockForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.order_by("name"),
        label="Product",
    )
    product_item = forms.ModelChoiceField(
        queryset=ProductItem.objects.none(),
        label="Lot",
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.order_by("name"),
        label="Location",
    )
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        product = self.data.get("product") or self.initial.get("product")
        if product:
            self.fields["product_item"].queryset = ProductItem.objects.filter(product_id=product).order_by("expiry_date")
        else:
            self.fields["product_item"].queryset = ProductItem.objects.select_related("product").order_by("product__name")
        if not self.is_bound:
            self.fields["product"].initial = self.initial.get("product")
            self.fields["product_item"].initial = self.initial.get("product_item")


class LocationTransferForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.order_by("name"),
        label="Product",
    )
    product_item = forms.ModelChoiceField(
        queryset=ProductItem.objects.none(),
        label="Lot",
    )
    from_location = forms.ModelChoiceField(
        queryset=Location.objects.order_by("name"),
        label="From Location",
    )
    to_location = forms.ModelChoiceField(
        queryset=Location.objects.order_by("name"),
        label="To Location",
    )
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        product = self.data.get("product") or self.initial.get("product")
        product_item_id = self.data.get("product_item") or self.initial.get("product_item")
        if product:
            self.fields["product_item"].queryset = ProductItem.objects.filter(product_id=product).order_by("expiry_date")
        else:
            self.fields["product_item"].queryset = ProductItem.objects.none()
        if not self.is_bound:
            self.fields["product"].initial = self.initial.get("product")
            self.fields["product_item"].initial = self.initial.get("product_item")

        # Limit "from" locations to those with stock for the selected item, if any
        stock_qs = LocationStock.objects.none()
        if product_item_id:
            stock_qs = LocationStock.objects.filter(product_item_id=product_item_id, quantity__gt=0)
        if stock_qs.exists():
            self.fields["from_location"].queryset = Location.objects.filter(
                location_stocks__in=stock_qs
            ).distinct().order_by("name")
        else:
            self.fields["from_location"].queryset = Location.objects.order_by("name")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("from_location") == cleaned.get("to_location"):
            raise forms.ValidationError("Choose different locations for transfer.")
        return cleaned


class UserLocationForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.order_by("username"),
        label="User",
    )
    locations = forms.ModelMultipleChoiceField(
        queryset=Location.objects.order_by("name"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 10}),
        label="Assigned Locations",
    )
