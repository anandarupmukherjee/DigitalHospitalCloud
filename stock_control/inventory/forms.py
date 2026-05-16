# forms.py
import datetime
from decimal import Decimal

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from services.data_storage.models import Location, Product, ProductItem, Supplier, Withdrawal

from inventory.roles import (
    ROLE_DEFINITIONS,
    ROLE_INVENTORY_MANAGER,
    ROLE_TEAM_MANAGER,
    ROLE_STAFF,
    assign_user_role,
    ensure_role_groups,
    get_role_key_for_user,
)
from stock_control.module_loader import module_flags as get_module_flags

try:
    from solutions.location_tracking.models import UserLocation
except Exception:
    UserLocation = None


STOCK_ADMIN_LOCATION_NAMES = ("Cold Store", "Ccentral")


def get_stock_admin_locations():
    allowed_locations = []
    for name in STOCK_ADMIN_LOCATION_NAMES:
        location = Location.objects.filter(name__iexact=name).first()
        if location is None:
            location = Location.objects.create(name=name)
        allowed_locations.append(location.id)
    return Location.objects.filter(id__in=allowed_locations).order_by("name")

class WithdrawalForm(forms.ModelForm):
    # Extra fields for manual mode (not mapped to model directly)

    barcode_manual = forms.CharField(
        required=False,
        label="Barcode (Manual)",
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'id': 'id_barcode_manual'})
    )

    lot_number = forms.CharField(
        required=False,
        label="Lot Number",
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'id': 'id_lot_number'})
    )

    expiry_date = forms.DateField(
        required=False,
        label="Expiry Date",
        input_formats=["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y%m%d"],
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'id': 'id_expiry_date'})
    )

    units_per_quantity = forms.DecimalField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_units_per_quantity'})
    )

    class Meta:
        model = Withdrawal
        fields = ['barcode', 'quantity', 'withdrawal_type', 'parts_withdrawn']
        widgets = {
            'barcode': forms.TextInput(attrs={'placeholder': 'Scan Barcode', 'autocomplete': 'off', 'id': 'id_barcode'}),
            'quantity': forms.NumberInput(attrs={'min': 0.01, 'step': '0.01', 'value': 1}),
        }

    def clean_expiry_date(self):
        value = self.cleaned_data.get("expiry_date")
        if not value:
            raw_value = self.data.get("expiry_date", "")
            for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
                try:
                    return datetime.datetime.strptime(raw_value, fmt).date()
                except (ValueError, TypeError):
                    continue
            if raw_value:
                raise forms.ValidationError("Enter a valid date (use YYYY-MM-DD or DD.MM.YYYY).")
            return None
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['quantity'].required = False
        self.fields['withdrawal_type'].required = False
        self.fields['parts_withdrawn'].required = False


class ProductForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier_ref'].queryset = Supplier.objects.order_by("name")
        self.fields['location'].queryset = get_stock_admin_locations()
        # Hide legacy supplier code dropdown; rely on supplier_ref instead.
        self.fields['supplier'].widget = forms.HiddenInput()
        if not self.initial.get("supplier") and not getattr(self.instance, "supplier", None):
            self.fields['supplier'].initial = "THIRD_PARTY"

    class Meta:
        model = Product
        fields = [
            'product_code',
            'name',
            'supplier',
            'supplier_ref',
            'location',
            'threshold',
            'lead_time',
        ]


class ProductItemForm(forms.ModelForm):
    full_volume = forms.DecimalField(
        required=False,
        min_value=Decimal("0.01"),
        decimal_places=2,
        max_digits=12,
        label="Full Volume",
        help_text="Total reagent volume registered for this lot.",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
    )

    partial_withdrawal_volume = forms.DecimalField(
        required=False,
        min_value=Decimal("0.01"),
        decimal_places=2,
        max_digits=12,
        label="Unit Partial Withdrawal Volume",
        help_text="Fixed volume withdrawn for one partial withdrawal step.",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['current_stock'].required = False
        self.fields['units_per_quantity'].required = False
        self.fields['accumulated_partial'].required = False
        self.fields['units_per_quantity'].widget.attrs.update({'step': '0.01', 'min': '0.01'})
        self.fields['current_stock'].widget.attrs.update({'step': '0.01', 'min': '0'})
        self.fields['accumulated_partial'].widget = forms.HiddenInput()
        if not self.instance.pk:
            self.fields['product_feature'].initial = 'volume'
            self.fields['units_per_quantity'].initial = Decimal('1.00')
            self.fields['accumulated_partial'].initial = 0
        if (self.instance.pk and self.instance.product_feature == 'volume') or self.fields['product_feature'].initial == 'volume':
            self.fields['full_volume'].initial = self.instance.current_stock or Decimal('0.00')
            self.fields['partial_withdrawal_volume'].initial = self.instance.units_per_quantity or Decimal('1.00')

    def clean(self):
        cleaned_data = super().clean()
        product_feature = cleaned_data.get('product_feature') or 'volume'

        if product_feature == 'volume':
            full_volume = cleaned_data.get('full_volume')
            partial_withdrawal_volume = cleaned_data.get('partial_withdrawal_volume')
            if full_volume is None:
                self.add_error('full_volume', "Enter the full volume for this lot.")
            if partial_withdrawal_volume is None:
                self.add_error('partial_withdrawal_volume', "Enter the unit partial withdrawal volume.")
            if self.errors:
                return cleaned_data

            cleaned_data['current_stock'] = full_volume
            cleaned_data['units_per_quantity'] = partial_withdrawal_volume
            cleaned_data['accumulated_partial'] = self.instance.accumulated_partial if self.instance.pk else 0
        else:
            current_stock = cleaned_data.get('current_stock')
            units_per_quantity = cleaned_data.get('units_per_quantity')
            if current_stock is None:
                self.add_error('current_stock', "Enter the current stock for this lot.")
            elif current_stock != current_stock.to_integral_value():
                self.add_error('current_stock', "Unit stock must be a whole number.")

            if units_per_quantity is None:
                self.add_error('units_per_quantity', "Enter the units per quantity.")
            elif units_per_quantity != units_per_quantity.to_integral_value():
                self.add_error('units_per_quantity', "Units per quantity must be a whole number for unit products.")

        return cleaned_data

    class Meta:
        model = ProductItem
        fields = [
            'lot_number',
            'expiry_date',
            'current_stock',
            'units_per_quantity',
            'accumulated_partial',
            'product_feature',
        ]



ROLE_CHOICES = ROLE_DEFINITIONS


class AdminUserCreationForm(UserCreationForm):
    is_staff = forms.BooleanField(required=False, label="Admin Privileges")
    is_active = forms.BooleanField(required=False, label="Active User", initial=True)
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Role")
    location = forms.ModelChoiceField(
        queryset=Location.objects.order_by("name"),
        required=False,
        label="Default Location",
        help_text="Required for Staff or Team Manager roles",
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'is_staff', 'is_active', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ensure_role_groups()
        self.fields['role'].initial = 'staff'
        self.location_tracking_enabled = get_module_flags().get("location_tracking", False) and UserLocation is not None
        if not self.location_tracking_enabled:
            self.fields['location'].widget = forms.HiddenInput()
        else:
            self.fields['location'].queryset = Location.objects.order_by("name")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_staff = self.cleaned_data['is_staff']
        user.is_active = self.cleaned_data['is_active']
        self._enforce_location_requirement()
        if commit:
            user.save()
            assign_user_role(user, self.cleaned_data['role'])
            self._sync_location(user)
        return user

    def _sync_location(self, user):
        if not (self.location_tracking_enabled and UserLocation):
            return
        location = self.cleaned_data.get("location")
        UserLocation.objects.filter(user=user).delete()
        if location:
            UserLocation.objects.create(user=user, location=location)

    def _enforce_location_requirement(self):
        if not self.location_tracking_enabled:
            return
        role = self.cleaned_data.get("role")
        location = self.cleaned_data.get("location")
        if role in {"staff", "team_manager"} and not location:
            raise forms.ValidationError("Staff and Team Manager users must be assigned to a location.")


class AdminUserEditForm(forms.ModelForm):
    is_active = forms.BooleanField(required=False, label="Active User")
    is_staff = forms.BooleanField(required=False, label="Admin Privileges")
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Role")
    location = forms.ModelChoiceField(
        queryset=Location.objects.order_by("name"),
        required=False,
        label="Default Location",
        help_text="Required for Staff or Team Manager roles",
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'is_active', 'is_staff']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ensure_role_groups()
        if self.instance and self.instance.pk:
            self.fields['role'].initial = get_role_key_for_user(self.instance)
            # TODO: populate location field from user-location map once implemented
        else:
            self.fields['role'].initial = 'staff'
        self.location_tracking_enabled = get_module_flags().get("location_tracking", False) and UserLocation is not None
        if not self.location_tracking_enabled:
            self.fields['location'].widget = forms.HiddenInput()
        else:
            self.fields['location'].queryset = Location.objects.order_by("name")
            if self.instance and self.instance.pk:
                assigned = UserLocation.objects.filter(user=self.instance).values_list("location_id", flat=True).first()
                if assigned:
                    self.fields['location'].initial = assigned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_staff = self.cleaned_data['is_staff']
        user.is_active = self.cleaned_data['is_active']
        self._enforce_location_requirement()
        if commit:
            user.save()
            assign_user_role(user, self.cleaned_data['role'])
            self._sync_location(user)
        return user

    def _enforce_location_requirement(self):
        if not self.location_tracking_enabled:
            return
        role = self.cleaned_data.get("role")
        location = self.cleaned_data.get("location")
        if role in {"staff", "team_manager"} and not location:
            raise forms.ValidationError("Staff and Team Manager users must be assigned to a location.")

    def _sync_location(self, user):
        if not (self.location_tracking_enabled and UserLocation):
            return
        location = self.cleaned_data.get("location")
        UserLocation.objects.filter(user=user).delete()
        if location:
            UserLocation.objects.create(user=user, location=location)


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_email", "contact_phone"]


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["name", "description", "is_active"]
