from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError


class Customer(models.Model):
    distributor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="customers",
        null=True,
        blank=True,
        help_text="The distributor account this customer belongs to"
    )

    name = models.CharField(
        max_length=150,
        help_text="Full name of the customer"
    )

    email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email address of the customer"
    )

    phone = models.CharField(
        max_length=20,
        help_text="Phone number of the customer"
    )

    address = models.TextField(
        blank=True,
        null=True,
        help_text="Postal address of the customer"
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    state = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    pincode = models.CharField(
        max_length=10,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

    def __str__(self):
        return self.name if self.name else f"Customer #{self.pk}"


class Product(models.Model):
    distributor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="products",
        help_text="The distributor account this product belongs to"
    )

    name = models.CharField(
        max_length=200,
        help_text="Product name"
    )

    category = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Product category"
    )

    description = models.TextField(
        blank=True,
        null=True,
        help_text="Product description"
    )

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Product selling price"
    )

    stock = models.PositiveIntegerField(
        default=0,
        help_text="Available stock quantity"
    )

    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00'))
        ],
        help_text="GST tax rate percentage (0 to 100)"
    )

    sku = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Stock keeping unit / product code"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def clean(self):
        super().clean()
        if not self.name or not self.name.strip():
            raise ValidationError({'name': 'Product name cannot be empty or contain only whitespace.'})
        if self.price is not None and self.price < Decimal('0.00'):
            raise ValidationError({'price': 'Price cannot be negative.'})
        if self.stock is not None and self.stock < 0:
            raise ValidationError({'stock': 'Stock cannot be negative.'})
        if self.gst_rate is not None and (self.gst_rate < Decimal('0.00') or self.gst_rate > Decimal('100.00')):
            raise ValidationError({'gst_rate': 'GST rate must be between 0 and 100.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Invoice(models.Model):
    distributor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="invoices",
        help_text="The distributor account this invoice belongs to"
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="invoices",
        help_text="The customer for this invoice"
    )

    invoice_number = models.CharField(
        max_length=50,
        help_text="Invoice reference number"
    )

    invoice_date = models.DateField(
        help_text="Date of invoice issuance"
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Subtotal before taxes"
    )

    total_gst = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total GST amount"
    )

    grand_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Grand total amount including GST"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
        constraints = [
            models.UniqueConstraint(
                fields=["distributor", "invoice_number"],
                name="unique_invoice_number_per_distributor"
            )
        ]

    def clean(self):
        super().clean()
        if not self.invoice_number or not self.invoice_number.strip():
            raise ValidationError({'invoice_number': 'Invoice number cannot be empty.'})
        if self.subtotal is not None and self.subtotal < Decimal('0.00'):
            raise ValidationError({'subtotal': 'Subtotal cannot be negative.'})
        if self.total_gst is not None and self.total_gst < Decimal('0.00'):
            raise ValidationError({'total_gst': 'Total GST cannot be negative.'})
        if self.grand_total is not None and self.grand_total < Decimal('0.00'):
            raise ValidationError({'grand_total': 'Grand total cannot be negative.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} ({self.customer.name if self.customer else 'No Customer'})"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="The parent invoice"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="invoice_items",
        help_text="The product item"
    )

    product_name = models.CharField(
        max_length=200,
        help_text="Snapshot of product name at invoice creation time"
    )

    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Quantity purchased"
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Snapshot of unit price at invoice creation time"
    )

    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00'))
        ],
        help_text="Snapshot of GST rate percentage at invoice creation time"
    )

    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00'))
        ],
        help_text="Snapshot of discount percentage at invoice creation time"
    )

    taxable_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Taxable amount (gross_amount - discount_amount)"
    )

    gst_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="GST amount for this line item"
    )

    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Line total amount (taxable_amount + gst_amount)"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Invoice Item"
        verbose_name_plural = "Invoice Items"

    def clean(self):
        super().clean()
        if not self.product_name or not self.product_name.strip():
            raise ValidationError({'product_name': 'Product name cannot be empty.'})
        if self.quantity is not None and self.quantity < 1:
            raise ValidationError({'quantity': 'Quantity must be at least 1.'})
        if self.unit_price is not None and self.unit_price < Decimal('0.00'):
            raise ValidationError({'unit_price': 'Unit price cannot be negative.'})
        if self.gst_rate is not None and (self.gst_rate < Decimal('0.00') or self.gst_rate > Decimal('100.00')):
            raise ValidationError({'gst_rate': 'GST rate must be between 0 and 100.'})
        if self.discount_percent is not None and (self.discount_percent < Decimal('0.00') or self.discount_percent > Decimal('100.00')):
            raise ValidationError({'discount_percent': 'Discount percentage must be between 0 and 100.'})
        if self.taxable_amount is not None and self.taxable_amount < Decimal('0.00'):
            raise ValidationError({'taxable_amount': 'Taxable amount cannot be negative.'})
        if self.gst_amount is not None and self.gst_amount < Decimal('0.00'):
            raise ValidationError({'gst_amount': 'GST amount cannot be negative.'})
        if self.line_total is not None and self.line_total < Decimal('0.00'):
            raise ValidationError({'line_total': 'Line total cannot be negative.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice.invoice_number if self.invoice else 'Invoice'} - {self.product_name}"


