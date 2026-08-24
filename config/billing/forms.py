import re
from django import forms
from .models import Customer


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "pincode",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Enter customer full name",
                "id": "id_name",
                "class": "form-input"
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "Enter email address (optional)",
                "id": "id_email",
                "class": "form-input"
            }),
            "phone": forms.TextInput(attrs={
                "placeholder": "Enter 10-digit phone number",
                "id": "id_phone",
                "class": "form-input"
            }),
            "address": forms.Textarea(attrs={
                "placeholder": "Enter complete customer address (optional)",
                "id": "id_address",
                "class": "form-textarea",
                "rows": 3
            }),
            "city": forms.TextInput(attrs={
                "placeholder": "Enter city (optional)",
                "id": "id_city",
                "class": "form-input"
            }),
            "state": forms.TextInput(attrs={
                "placeholder": "Enter state (optional)",
                "id": "id_state",
                "class": "form-input"
            }),
            "pincode": forms.TextInput(attrs={
                "placeholder": "Enter 6-digit pincode (optional)",
                "id": "id_pincode",
                "class": "form-input"
            }),
        }
        error_messages = {
            "name": {
                "required": "Please enter a valid customer name.",
                "invalid": "Please enter a valid customer name."
            },
            "email": {
                "invalid": "Please enter a valid email address."
            },
            "phone": {
                "required": "Please enter a valid 10-digit phone number.",
                "invalid": "Please enter a valid 10-digit phone number."
            }
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name or len(name) < 2 or len(name) > 150:
            raise forms.ValidationError("Please enter a valid customer name.")
        if name.isdigit():
            raise forms.ValidationError("Please enter a valid customer name.")
        return name

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            email = email.strip()
            if not email:
                return None
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if not re.match(r"^[6-9]\d{9}$", phone):
            raise forms.ValidationError("Please enter a valid 10-digit phone number.")
        return phone

    def clean_address(self):
        address = self.cleaned_data.get("address")
        if address:
            address = address.strip()
            if not address:
                return None
        return address

    def clean_city(self):
        city = self.cleaned_data.get("city")
        if city:
            city = city.strip()
            if not city:
                return None
            if len(city) > 100 or re.search(r"\d", city):
                raise forms.ValidationError("Please enter a valid city.")
        return city

    def clean_state(self):
        state = self.cleaned_data.get("state")
        if state:
            state = state.strip()
            if not state:
                return None
            if len(state) > 100 or re.search(r"\d", state):
                raise forms.ValidationError("Please enter a valid state.")
        return state

    def clean_pincode(self):
        pincode = self.cleaned_data.get("pincode")
        if pincode:
            pincode = pincode.strip()
            if not pincode:
                return None
            if not re.match(r"^\d{6}$", pincode):
                raise forms.ValidationError("Please enter a valid 6-digit pincode.")
        return pincode
