from datetime import timedelta
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny

from .authentication import SecureJWTAuthentication
from .models import OTPVerification, AdminPasswordResetToken
from .serializers import (
    AdminRegistrationSerializer,
    AdminForgotPasswordSerializer,
    AdminVerifyResetOTPSerializer,
    AdminResetPasswordSerializer,
    AdminResendResetOTPSerializer,
    CustomerRegistrationSerializer,
)
from .permissions import IsDistributor
from .services import (
    ADMIN_RECOVERY_PURPOSE,
    OTP_EXPIRY_MINUTES,
    RESET_TOKEN_EXPIRY_MINUTES,
    RESEND_COOLDOWN_SECONDS,
    MAX_FAILED_OTP_ATTEMPTS,
    generate_secure_numeric_otp,
    hash_otp,
    verify_otp_hash,
    generate_reset_token,
    hash_reset_token,
    lookup_eligible_admin_by_email,
    send_admin_recovery_email,
    invalidate_user_sessions,
    revoke_user_jwt_tokens,
)
from .throttling import (
    AdminRecoveryIPRateThrottle,
    AdminRecoveryEmailRateThrottle,
)


class AdminRegistrationAPIView(APIView):
    """
    POST /api/admin/register/

    Only superusers can register new Admin users.
    Supports JWT Bearer Token and Session Authentication.
    """

    authentication_classes = [
        SecureJWTAuthentication,
        SessionAuthentication,
    ]

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Only superusers can create Admin users
        if not request.user.is_superuser:
            return Response(
                {
                    "detail": "You do not have permission to perform this action."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = AdminRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            admin_user = serializer.save()

            return Response(
                {
                    "message": "Admin user registered successfully.",
                    "admin": {
                        "id": admin_user.id,
                        "username": admin_user.username,
                        "email": admin_user.email,
                        "first_name": admin_user.first_name,
                        "last_name": admin_user.last_name,
                    }
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class AdminForgotPasswordAPIView(APIView):
    """
    POST /api/admin/forgot-password/

    Initiates Admin password recovery via 6-digit numeric OTP.
    Accessible without authentication. Returns generic response to prevent
    account enumeration.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AdminRecoveryIPRateThrottle, AdminRecoveryEmailRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = AdminForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        user, lookup_status = lookup_eligible_admin_by_email(email)

        if lookup_status == "ok" and user:
            # Invalidate any previous unverified Admin recovery OTPs for this user
            OTPVerification.objects.filter(
                models.Q(user=user) | models.Q(email__iexact=user.email),
                purpose=ADMIN_RECOVERY_PURPOSE,
                is_verified=False
            ).update(is_verified=True)

            # Invalidate any outstanding reset tokens
            AdminPasswordResetToken.objects.filter(
                user=user,
                is_used=False
            ).update(is_used=True)

            # Generate and hash 6-digit OTP
            otp = generate_secure_numeric_otp()
            otp_h = hash_otp(otp)
            expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)

            # Save in database without storing plaintext OTP
            OTPVerification.objects.create(
                user=user,
                email=user.email,
                otp_code="",
                otp_hash=otp_h,
                purpose=ADMIN_RECOVERY_PURPOSE,
                expires_at=expires_at,
                is_verified=False,
                attempts=0
            )

            # Send branded email safely
            send_admin_recovery_email(user.email, otp)

        # Consistent generic response to prevent account enumeration
        return Response(
            {
                "message": "If an eligible account exists, a password reset OTP has been sent."
            },
            status=status.HTTP_200_OK
        )


class AdminVerifyResetOTPAPIView(APIView):
    """
    POST /api/admin/verify-reset-otp/

    Verifies the submitted 6-digit OTP against its stored hash.
    On successful verification, invalidates the OTP and returns a cryptographically
    secure, short-lived, single-use password reset token.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AdminRecoveryIPRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = AdminVerifyResetOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        submitted_otp = serializer.validated_data["otp"]

        otp_record = OTPVerification.objects.filter(
            email__iexact=email,
            purpose=ADMIN_RECOVERY_PURPOSE,
            is_verified=False
        ).order_by("-created_at").first()

        if not otp_record or not otp_record.user:
            return Response(
                {"detail": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Account must still be an eligible active staff member
        if not otp_record.user.is_active or not otp_record.user.is_staff:
            return Response(
                {"detail": "Account is not eligible for admin recovery."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Expiry check
        if timezone.now() > otp_record.expires_at:
            return Response(
                {"detail": "OTP has expired. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Attempt lockout check
        if otp_record.attempts >= MAX_FAILED_OTP_ATTEMPTS:
            return Response(
                {"detail": "Too many failed attempts. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Hash verification
        if not verify_otp_hash(submitted_otp, otp_record.otp_hash):
            otp_record.attempts += 1
            otp_record.save(update_fields=["attempts"])
            remaining = MAX_FAILED_OTP_ATTEMPTS - otp_record.attempts
            if remaining <= 0:
                return Response(
                    {"detail": "Too many failed attempts. Please request a new OTP."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {"detail": f"Invalid OTP. {remaining} attempt(s) remaining."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verification successful: Invalidate OTP
        otp_record.is_verified = True

        # Generate single-use reset token and store only its SHA-256 hash
        reset_token = generate_reset_token()
        token_hash = hash_reset_token(reset_token)
        token_expires_at = timezone.now() + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)

        AdminPasswordResetToken.objects.create(
            user=otp_record.user,
            token_hash=token_hash,
            expires_at=token_expires_at,
            is_used=False
        )

        otp_record.reset_token_hash = token_hash
        otp_record.reset_token_expires_at = token_expires_at
        otp_record.is_used = False
        otp_record.save(update_fields=["is_verified", "reset_token_hash", "reset_token_expires_at", "is_used"])

        return Response(
            {
                "message": "OTP verified successfully.",
                "reset_token": reset_token
            },
            status=status.HTTP_200_OK
        )


class AdminResetPasswordAPIView(APIView):
    """
    POST /api/admin/reset-password/

    Resets the Admin's password using the single-use reset token.
    Validates token, enforces Django password validators, updates the password,
    invalidates sessions and active JWTs, and marks the token used.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AdminRecoveryIPRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = AdminResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        reset_token = serializer.validated_data["reset_token"]
        new_password = serializer.validated_data["new_password"]
        token_hash = hash_reset_token(reset_token)

        with transaction.atomic():
            # Atomically lock and fetch reset token
            token_obj = (
                AdminPasswordResetToken.objects.select_for_update()
                .filter(token_hash=token_hash)
                .first()
            )

            if not token_obj or token_obj.is_used:
                return Response(
                    {"detail": "Invalid or expired reset token."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if timezone.now() > token_obj.expires_at:
                return Response(
                    {"detail": "Reset token has expired."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = token_obj.user
            if not user.is_active or not user.is_staff:
                return Response(
                    {"detail": "Account is not eligible for admin recovery."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate password against Django configured validators
            try:
                validate_password(new_password, user=user)
            except DjangoValidationError as e:
                return Response(
                    {"new_password": list(e.messages)},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update password securely without altering permissions or groups
            user.set_password(new_password)
            user.save()

            # Mark token used immediately to prevent reuse
            token_obj.is_used = True
            token_obj.save(update_fields=["is_used"])

            # Invalidate all remaining recovery credentials for this user
            AdminPasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)
            OTPVerification.objects.filter(
                user=user,
                purpose=ADMIN_RECOVERY_PURPOSE
            ).update(is_verified=True, is_used=True)

            # Invalidate all active Django sessions
            invalidate_user_sessions(user)

            # Invalidate all previously issued JWT tokens
            revoke_user_jwt_tokens(user)

        return Response(
            {
                "message": "Password reset successfully. Please login with your new password."
            },
            status=status.HTTP_200_OK
        )


class AdminResendResetOTPAPIView(APIView):
    """
    POST /api/admin/resend-reset-otp/

    Resends a new 6-digit OTP for Admin password recovery.
    Enforces a strict 60-second cooldown and generic responses.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AdminRecoveryIPRateThrottle, AdminRecoveryEmailRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = AdminResendResetOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        user, lookup_status = lookup_eligible_admin_by_email(email)

        # Consistent generic response when account is unknown or ineligible
        if lookup_status != "ok" or not user:
            return Response(
                {
                    "message": "If an eligible account exists, a new password reset OTP has been sent."
                },
                status=status.HTTP_200_OK
            )

        # Enforce 60-second cooldown against the latest OTP record
        latest_otp = OTPVerification.objects.filter(
            email__iexact=user.email,
            purpose=ADMIN_RECOVERY_PURPOSE
        ).order_by("-created_at").first()

        if latest_otp:
            elapsed = (timezone.now() - latest_otp.created_at).total_seconds()
            if elapsed < RESEND_COOLDOWN_SECONDS:
                remaining = int(RESEND_COOLDOWN_SECONDS - elapsed)
                return Response(
                    {
                        "detail": f"Please wait {remaining} seconds before requesting a new OTP."
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

        # Invalidate previous unverified OTPs
        OTPVerification.objects.filter(
            models.Q(user=user) | models.Q(email__iexact=user.email),
            purpose=ADMIN_RECOVERY_PURPOSE,
            is_verified=False
        ).update(is_verified=True)

        # Invalidate any unused reset tokens
        AdminPasswordResetToken.objects.filter(
            user=user,
            is_used=False
        ).update(is_used=True)

        # Generate new OTP, hash, and set 5-minute expiry
        otp = generate_secure_numeric_otp()
        otp_h = hash_otp(otp)
        expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)

        OTPVerification.objects.create(
            user=user,
            email=user.email,
            otp_code="",
            otp_hash=otp_h,
            purpose=ADMIN_RECOVERY_PURPOSE,
            expires_at=expires_at,
            is_verified=False,
            attempts=0
        )

        send_admin_recovery_email(user.email, otp)

        return Response(
            {
                "message": "If an eligible account exists, a new password reset OTP has been sent."
            },
            status=status.HTTP_200_OK
        )


class CustomerRegistrationAPIView(APIView):
    """
    POST /api/distributor/customers/register/

    Allows an authenticated Distributor to register a customer.
    The customer is linked to the authenticated Distributor.
    """
    authentication_classes = [
        SecureJWTAuthentication,
        SessionAuthentication,
    ]
    permission_classes = [IsAuthenticated, IsDistributor]

    def post(self, request, *args, **kwargs):
        serializer = CustomerRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            customer = serializer.save(distributor=request.user)
            return Response(
                {
                    "message": "Customer registered successfully.",
                    "customer": {
                        "id": customer.id,
                        "name": customer.name,
                        "email": customer.email,
                        "phone": customer.phone,
                        "address": customer.address,
                        "city": customer.city,
                        "state": customer.state,
                        "pincode": customer.pincode,
                    }
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )