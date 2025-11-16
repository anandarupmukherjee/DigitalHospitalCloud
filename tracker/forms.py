from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from tracker.utils import ROLE_CHOICES, assign_role, ensure_role_groups


class UserCreationWithRoleForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=ROLE_CHOICES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ensure_role_groups()

    def clean_username(self):
        username = self.cleaned_data["username"]
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

    def save(self):
        data = self.cleaned_data
        User = get_user_model()
        user = User.objects.create_user(
            username=data["username"],
            email=data.get("email") or "",
            password=data["password"],
        )
        assign_role(user, data["role"])
        return user


class TrayConfigForm(forms.Form):
    pico_id = forms.CharField(label="Pico ID", max_length=64)
    tray_id = forms.CharField(label="Tray ID", max_length=64)
    location_label = forms.CharField(label="Location label", max_length=255)
    latitude = forms.FloatField()
    longitude = forms.FloatField()

    def payload(self):
        cleaned = self.cleaned_data
        return {
            "pico_id": cleaned["pico_id"],
            "tray_id": cleaned["tray_id"],
            "location_label": cleaned["location_label"],
            "latitude": cleaned["latitude"],
            "longitude": cleaned["longitude"],
        }
