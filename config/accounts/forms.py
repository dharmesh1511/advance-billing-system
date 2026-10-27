from django import forms
from django.contrib.auth.models import User


class DistributorRegistrationForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your full name',
            'id': 'full_name'
        })
    )

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email address',
            'id': 'email'
        })
    )

    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your phone number',
            'id': 'phone'
        })
    )

    password = forms.CharField(
        min_length=6,
        required=True,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter your password',
            'id': 'password',
            'class': 'has-toggle'
        })
    )

    confirm_password = forms.CharField(
        min_length=6,
        required=True,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm your password',
            'id': 'confirm_password',
            'class': 'has-toggle'
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match. Please verify.")

        return cleaned_data


class DistributorProfileUpdateForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        required=True,
        error_messages={
            'required': 'Please enter a valid name.',
            'invalid': 'Please enter a valid name.'
        },
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your full name',
            'id': 'full_name',
            'class': 'form-input'
        })
    )

    email = forms.EmailField(
        required=True,
        error_messages={
            'required': 'Please enter a valid email address.',
            'invalid': 'Please enter a valid email address.'
        },
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email address',
            'id': 'email',
            'class': 'form-input'
        })
    )

    phone = forms.CharField(
        max_length=20,
        required=True,
        error_messages={
            'required': 'Please enter a valid phone number.',
            'invalid': 'Please enter a valid phone number.'
        },
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your phone number',
            'id': 'phone',
            'class': 'form-input'
        })
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if not full_name or len(full_name) < 2 or len(full_name) > 100:
            raise forms.ValidationError("Please enter a valid name.")
        return full_name

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise forms.ValidationError("Please enter a valid email address.")

        from .models import DistributorProfile
        if self.user:
            duplicate_user = User.objects.filter(
                email__iexact=email
            ).exclude(pk=self.user.pk).exists() or User.objects.filter(
                username__iexact=email
            ).exclude(pk=self.user.pk).exists()
            duplicate_profile = DistributorProfile.objects.filter(
                email__iexact=email
            ).exclude(user=self.user).exists()

            if duplicate_user or duplicate_profile:
                raise forms.ValidationError("This email address is already registered.")

        return email

    def clean_phone(self):
        import re
        phone = self.cleaned_data.get('phone', '').strip()
        if not re.match(r'^[6-9]\d{9}$', phone):
            raise forms.ValidationError("Please enter a valid phone number.")
        return phone

