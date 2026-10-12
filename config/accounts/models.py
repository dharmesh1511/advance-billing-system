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

    otp_code = models.CharField(max_length=255, blank=True, default="")
    otp_hash = models.CharField(max_length=255, blank=True, default="")

    purpose = models.CharField(
        max_length=50,
        default="forgot_password"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    expires_at = models.DateTimeField()

    is_verified = models.BooleanField(default=False)

    attempts = models.PositiveIntegerField(default=0)

    reset_token_hash = models.CharField(max_length=255, blank=True, default="", db_index=True)
    reset_token_expires_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP for {self.email} ({self.purpose})"


class AdminPasswordResetToken(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="admin_password_reset_tokens"
    )
    token_hash = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"AdminResetToken for {self.user.username} (used={self.is_used})"


class UserSecurityStatus(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="security_status"
    )
    password_changed_at = models.DateTimeField(null=True, blank=True)
    jwt_revoked_before = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"SecurityStatus for {self.user.username}"


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


