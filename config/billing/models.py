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

