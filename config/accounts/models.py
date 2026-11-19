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
        related_name="distributor_profile",
        null=True,
        blank=True,
        verbose_name="User Account",
        help_text="Associated login user account (auto-created if left blank)"
    )

    full_name = models.CharField(
        max_length=150,
        verbose_name="Distributor Name",
        help_text="Full name of the distributor"
    )
    email = models.EmailField(
        verbose_name="Email",
        help_text="Distributor email address"
    )
    phone = models.CharField(
        max_length=20,
        verbose_name="Phone Number",
        help_text="Distributor contact phone number"
    )
    business_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Business Name",
        help_text="Company or trading business name"
    )
    address = models.TextField(
        blank=True,
        default="",
        verbose_name="Address",
        help_text="Business / Office address"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created Date"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Distributor"
        verbose_name_plural = "Distributors"

    def __str__(self):
        if self.business_name:
            return f"{self.full_name} ({self.business_name})"
        return f"Distributor: {self.full_name} ({self.email})"

    @property
    def distributor_name(self):
        return self.full_name

    def save(self, *args, **kwargs):
        from django.contrib.auth.models import Group
        if not self.user_id and self.email:
            normalized_email = self.email.strip().lower()
            existing_user = (
                User.objects.filter(email__iexact=normalized_email).first()
                or User.objects.filter(username__iexact=normalized_email).first()
            )
            if existing_user:
                self.user = existing_user
            else:
                name_parts = (self.full_name or "").strip().split(" ", 1)
                first_name = name_parts[0] if name_parts else "Distributor"
                last_name = name_parts[1] if len(name_parts) > 1 else ""

                base_username = normalized_email
                username = base_username
                counter = 1
                while User.objects.filter(username__iexact=username).exists():
                    username = f"{base_username}_{counter}"
                    counter += 1

                new_user = User.objects.create_user(
                    username=username,
                    email=normalized_email,
                    first_name=first_name,
                    last_name=last_name
                )
                new_user.set_password("Distributor@123")
                new_user.save()
                self.user = new_user

        super().save(*args, **kwargs)

        if self.user:
            dist_group, _ = Group.objects.get_or_create(name="Distributor")
            if not self.user.groups.filter(name="Distributor").exists():
                self.user.groups.add(dist_group)


# Model alias: both Distributor and DistributorProfile point to the exact same model
Distributor = DistributorProfile



