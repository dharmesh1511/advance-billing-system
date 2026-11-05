import logging
from decimal import Decimal
from django import forms
from django.contrib import admin
from .models import Customer, Product, Invoice, InvoiceItem
from .views import generate_unique_invoice_number

logger = logging.getLogger(__name__)


class InvoiceAdminForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "invoice_number" in self.fields:
            self.fields["invoice_number"].required = False
            self.fields["invoice_number"].help_text = "Leave empty to automatically generate a unique invoice number."
        if "subtotal" in self.fields:
            self.fields["subtotal"].required = False
            self.fields["subtotal"].help_text = "Auto-calculated from items if left blank or 0."
        if "total_gst" in self.fields:
            self.fields["total_gst"].required = False
            self.fields["total_gst"].help_text = "Auto-calculated from items if left blank or 0."
        if "grand_total" in self.fields:
            self.fields["grand_total"].required = False
            self.fields["grand_total"].help_text = "Auto-calculated from items if left blank or 0."

    def clean(self):
        cleaned_data = super().clean()
        distributor = cleaned_data.get("distributor")
        inv_num = cleaned_data.get("invoice_number")
        if not inv_num or not inv_num.strip():
            if distributor:
                cleaned_data["invoice_number"] = generate_unique_invoice_number(distributor)
            else:
                cleaned_data["invoice_number"] = "PENDING"
        if cleaned_data.get("subtotal") is None:
            cleaned_data["subtotal"] = Decimal("0.00")
        if cleaned_data.get("total_gst") is None:
            cleaned_data["total_gst"] = Decimal("0.00")
        if cleaned_data.get("grand_total") is None:
            cleaned_data["grand_total"] = Decimal("0.00")
        return cleaned_data


class InvoiceItemInlineForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ["product_name", "unit_price", "gst_rate", "discount_percent", "taxable_amount", "gst_amount", "line_total"]:
            if field_name in self.fields:
                self.fields[field_name].required = False
                self.fields[field_name].help_text = "Auto-calculated from selected product if left blank."

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        if product:
            if not cleaned_data.get("product_name"):
                cleaned_data["product_name"] = product.name
            if cleaned_data.get("unit_price") is None:
                cleaned_data["unit_price"] = product.price
            if cleaned_data.get("gst_rate") is None:
                cleaned_data["gst_rate"] = product.gst_rate
            if cleaned_data.get("discount_percent") is None:
                cleaned_data["discount_percent"] = Decimal("0.00")

            qty = cleaned_data.get("quantity") or 1
            unit_price = cleaned_data.get("unit_price") or product.price
            disc_pct = cleaned_data.get("discount_percent") or Decimal("0.00")
            gst_rate = cleaned_data.get("gst_rate") or product.gst_rate

            gross = Decimal(qty) * unit_price
            discount = (gross * (disc_pct / Decimal("100.00"))).quantize(Decimal("0.01"))
            taxable = gross - discount
            gst = (taxable * (gst_rate / Decimal("100.00"))).quantize(Decimal("0.01"))
            total = taxable + gst

            if not cleaned_data.get("taxable_amount"):
                cleaned_data["taxable_amount"] = taxable
            if not cleaned_data.get("gst_amount"):
                cleaned_data["gst_amount"] = gst
            if not cleaned_data.get("line_total"):
                cleaned_data["line_total"] = total

        return cleaned_data


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    form = InvoiceItemInlineForm
    extra = 1
    fields = (
        "product",
        "product_name",
        "quantity",
        "unit_price",
        "discount_percent",
        "gst_rate",
        "taxable_amount",
        "gst_amount",
        "line_total",
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "phone",
        "city",
        "distributor",
        "created_at",
    )
    list_filter = ("state", "city", "created_at", "distributor")
    search_fields = (
        "name",
        "email",
        "phone",
        "city",
        "state",
        "pincode",
        "distributor__username",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if "distributor" not in initial and request.user.is_authenticated:
            initial["distributor"] = request.user.pk
        return initial

    def save_model(self, request, obj, form, change):
        if not obj.distributor_id and request.user.is_authenticated:
            obj.distributor = request.user
        super().save_model(request, obj, form, change)


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
    list_filter = ("category", "is_active", "created_at", "distributor")
    search_fields = ("name", "sku", "category", "distributor__username")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if "distributor" not in initial and request.user.is_authenticated:
            initial["distributor"] = request.user.pk
        return initial

    def save_model(self, request, obj, form, change):
        if not obj.distributor_id and request.user.is_authenticated:
            obj.distributor = request.user
        super().save_model(request, obj, form, change)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    form = InvoiceAdminForm
    list_display = (
        "invoice_number",
        "customer",
        "invoice_date",
        "grand_total",
        "subtotal",
        "total_gst",
        "distributor",
        "created_at",
    )
    list_filter = ("invoice_date", "created_at", "distributor")
    search_fields = (
        "invoice_number",
        "customer__name",
        "customer__email",
        "customer__phone",
        "distributor__username",
    )
    ordering = ("-created_at",)
    date_hierarchy = "invoice_date"
    inlines = [InvoiceItemInline]
    readonly_fields = ("created_at", "updated_at")

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if "distributor" not in initial and request.user.is_authenticated:
            initial["distributor"] = request.user.pk
        import datetime
        if "invoice_date" not in initial:
            initial["invoice_date"] = datetime.date.today()
        return initial

    def save_model(self, request, obj, form, change):
        if not obj.distributor_id and request.user.is_authenticated:
            obj.distributor = request.user
        if not obj.invoice_number or not obj.invoice_number.strip():
            obj.invoice_number = generate_unique_invoice_number(obj.distributor)
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        invoice = form.instance
        items = invoice.items.all()
        if items.exists():
            subtotal = sum((item.taxable_amount for item in items), Decimal("0.00"))
            total_gst = sum((item.gst_amount for item in items), Decimal("0.00"))
            grand_total = subtotal + total_gst
            Invoice.objects.filter(pk=invoice.pk).update(
                subtotal=subtotal,
                total_gst=total_gst,
                grand_total=grand_total
            )
            invoice.refresh_from_db()
        try:
            invoice.generate_and_save_qr_code(force=True)
        except Exception as e:
            logger.error(f"Error generating QR code in admin for invoice {invoice.pk}: {e}")


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    form = InvoiceItemInlineForm
    list_display = (
        "invoice",
        "product_name",
        "quantity",
        "unit_price",
        "line_total",
        "taxable_amount",
        "gst_amount",
        "product",
    )
    list_filter = ("created_at", "gst_rate", "product")
    search_fields = (
        "product_name",
        "product__name",
        "invoice__invoice_number",
        "invoice__customer__name",
    )
    ordering = ("-id",)
    readonly_fields = ("created_at",)
