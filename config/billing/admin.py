from django.contrib import admin
from .models import Customer, Product, Invoice, InvoiceItem


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "city", "distributor", "created_at", "updated_at")
    list_filter = ("city", "state", "created_at")
    search_fields = ("name", "email", "phone", "city")
    ordering = ("-created_at",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "price",
        "stock",
        "gst_rate",
        "sku",
        "distributor",
        "created_at",
        "updated_at",
    )
    list_filter = ("category", "created_at")
    search_fields = ("name", "sku", "category")
    ordering = ("-created_at",)


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "customer",
        "distributor",
        "invoice_date",
        "subtotal",
        "total_gst",
        "grand_total",
        "created_at",
    )
    list_filter = ("invoice_date", "created_at")
    search_fields = ("invoice_number", "customer__name", "distributor__username")
    ordering = ("-created_at",)
    inlines = [InvoiceItemInline]


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "product",
        "product_name",
        "quantity",
        "unit_price",
        "gst_rate",
        "taxable_amount",
        "gst_amount",
        "line_total",
    )
    search_fields = ("product_name", "invoice__invoice_number")


