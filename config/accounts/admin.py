from django.contrib import admin
from .models import DistributorProfile, OTPVerification, AdminPasswordResetToken, UserSecurityStatus


@admin.register(DistributorProfile)
class DistributorProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "email", "phone", "created_at")
    search_fields = ("full_name", "user__username", "email", "phone")
    ordering = ("-created_at",)
