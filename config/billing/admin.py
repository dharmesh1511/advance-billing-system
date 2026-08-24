from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "city", "distributor", "created_at", "updated_at")
    list_filter = ("city", "state", "created_at")
    search_fields = ("name", "email", "phone", "city")
    ordering = ("-created_at",)
