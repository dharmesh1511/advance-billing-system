import hashlib
import logging
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.sessions.models import Session
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from .models import OTPVerification, AdminPasswordResetToken, UserSecurityStatus

logger = logging.getLogger(__name__)
User = get_user_model()

ADMIN_RECOVERY_PURPOSE = "admin_password_reset"
OTP_EXPIRY_MINUTES = 5
RESET_TOKEN_EXPIRY_MINUTES = 10
RESEND_COOLDOWN_SECONDS = 60
MAX_FAILED_OTP_ATTEMPTS = 5


def generate_secure_numeric_otp() -> str:
    """Generate a cryptographically secure 6-digit numeric string."""
    return f"{secrets.randbelow(1000000):06d}"


def hash_otp(otp: str) -> str:
    """Securely hash OTP using Django's password hasher."""
    return make_password(otp)


def verify_otp_hash(otp: str, hashed_otp: str) -> bool:
    """Check an OTP against its stored hash."""
    if not hashed_otp:
        return False
    return check_password(otp, hashed_otp)


def generate_reset_token() -> str:
    """Generate a cryptographically secure 256-bit URL-safe token."""
    return secrets.token_urlsafe(32)


def hash_reset_token(raw_token: str) -> str:
    """Compute deterministic SHA-256 hash of a reset token for indexed lookup."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def lookup_eligible_admin_by_email(email: str):
    """
    Look up an eligible Admin account by email.
    Eligible: active user with is_staff=True.
    Returns: (user, status_code)
      - (user, "ok") if exactly 1 eligible account exists.
      - (None, "ambiguous") if multiple eligible accounts share the email.
      - (None, "not_found") if no eligible account exists.
    """
    if not email:
        return None, "not_found"
    email = email.strip().lower()

    eligible = User.objects.filter(
        email__iexact=email,
        is_staff=True,
        is_active=True
    )
    count = eligible.count()
    if count == 1:
        return eligible.first(), "ok"
    elif count > 1:
        logger.warning("Duplicate eligible Admin accounts detected for email lookup.")
        return None, "ambiguous"
    return None, "not_found"


def send_admin_recovery_email(email: str, otp: str) -> bool:
    """
    Send professional Admin Password Recovery email with OTP
    using HTML and plain-text templates rendered via EmailMultiAlternatives.
    Logs delivery errors safely without revealing credentials or OTPs.
    """
    subject = "Advance Billing System - Password Reset OTP"
    context = {
        "otp": otp,
        "validity_minutes": OTP_EXPIRY_MINUTES,
    }

    try:
        text_content = render_to_string("emails/admin_password_reset_otp.txt", context)
        html_content = render_to_string("emails/admin_password_reset_otp.html", context)

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        return True
    except Exception:
        logger.error("Admin recovery email delivery failed for recipient.")
        return False


def invalidate_user_sessions(user) -> None:
    """Invalidate all active Django sessions for the given user."""
    user_id_str = str(user.pk)
    try:
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
        session_keys_to_delete = []
        for session in active_sessions:
            try:
                data = session.get_decoded()
                if str(data.get("_auth_user_id")) == user_id_str:
                    session_keys_to_delete.append(session.session_key)
            except Exception:
                continue
        if session_keys_to_delete:
            Session.objects.filter(session_key__in=session_keys_to_delete).delete()
    except Exception as e:
        logger.error("Error invalidating user sessions: %s", type(e).__name__)


def revoke_user_jwt_tokens(user) -> None:
    """
    Set timestamp marking that all JWT tokens issued before now
    cannot authenticate the account.
    """
    try:
        security_status, _ = UserSecurityStatus.objects.get_or_create(user=user)
        now = timezone.now()
        security_status.jwt_revoked_before = now
        security_status.password_changed_at = now
        security_status.save()
    except Exception as e:
        logger.error("Error setting JWT revocation status: %s", type(e).__name__)
