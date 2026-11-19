from django import forms
from django.contrib import admin
from django.contrib.auth.models import User, Group
from .models import (
    DistributorProfile,
    Distributor,
    OTPVerification,
    AdminPasswordResetToken,
    UserSecurityStatus,
)


class DistributorAdminForm(forms.ModelForm):
    initial_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Optional: Set a login password for this distributor account (default: Distributor@123)."
    )

    class Meta:
        model = DistributorProfile
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["initial_password"].help_text = (
                "Leave blank to keep existing user password, or type a new password to reset it."
            )


@admin.register(DistributorProfile)
class DistributorProfileAdmin(admin.ModelAdmin):
    form = DistributorAdminForm
    list_display = (
        "full_name",
        "business_name",
        "email",
        "phone",
        "user",
        "created_at",
    )
    list_display_links = ("full_name", "business_name")
    search_fields = (
        "full_name",
        "email",
        "business_name",
        "phone",
        "user__username",
    )
    list_filter = (
        "created_at",
        "user__is_active",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Distributor Information", {
            "fields": (
                "full_name",
                "business_name",
                "email",
                "phone",
                "address",
            )
        }),
        ("Authentication & Access", {
            "fields": (
                "user",
                "initial_password",
            ),
            "description": "Select an existing User or leave blank to automatically create a linked distributor user account."
        }),
        ("Audit Information", {
            "fields": (
                "created_at",
            ),
            "classes": ("collapse",),
        }),
    )

    def save_model(self, request, obj, form, change):
        initial_password = form.cleaned_data.get("initial_password")
        super().save_model(request, obj, form, change)

        if initial_password and obj.user:
            obj.user.set_password(initial_password)
            obj.user.save()

    def delete_model(self, request, obj):
        user = obj.user
        super().delete_model(request, obj)
        if user and not user.is_staff and not user.is_superuser:
            user.delete()

    def delete_queryset(self, request, queryset):
        users_to_delete = [
            obj.user for obj in queryset
            if obj.user and not obj.user.is_staff and not obj.user.is_superuser
        ]
        super().delete_queryset(request, queryset)
        for u in users_to_delete:
            try:
                u.delete()
            except Exception:
                pass


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ("email", "purpose", "is_verified", "is_used", "created_at", "expires_at")
    list_filter = ("purpose", "is_verified", "is_used")
    search_fields = ("email", "otp_code")
    readonly_fields = ("created_at",)


@admin.register(AdminPasswordResetToken)
class AdminPasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "is_used", "created_at", "expires_at")
    list_filter = ("is_used",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at",)


@admin.register(UserSecurityStatus)
class UserSecurityStatusAdmin(admin.ModelAdmin):
    list_display = ("user", "password_changed_at", "jwt_revoked_before")
    search_fields = ("user__username", "user__email")
