from django.db import models
from django.contrib.auth.models import User


class OTPVerification(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    email = models.EmailField()

    otp_code = models.CharField(max_length=6)

    purpose = models.CharField(
        max_length=50,
        default="forgot_password"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    expires_at = models.DateTimeField()

    is_verified = models.BooleanField(default=False)

    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP {self.otp_code} for {self.email} ({self.purpose})"


class DistributorProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="distributor_profile"
    )

    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Distributor: {self.full_name} ({self.email})"

