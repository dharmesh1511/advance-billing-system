from django.db import models
from django.contrib.auth.models import User


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
