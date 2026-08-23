import secrets
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import OTPVerification, DistributorProfile
from .forms import DistributorRegistrationForm


def is_distributor(user):
    return user.groups.filter(name="Distributor").exists()


# =========================
# ADMIN LOGIN
# =========================

def admin_login(request):

    # Already logged-in admin
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("admin_dashboard")

        if is_distributor(request.user):
            return redirect("distributor_dashboard")

    error = None

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            error = "Username and password are required."

        else:
            user = authenticate(
                request,
                username=username,
                password=password
            )

            if user is not None:

                # Only staff users can access Admin
                if user.is_staff:
                    login(request, user)

                    return redirect("admin_dashboard")

                error = "You are not authorized to login as Admin."

            else:
                error = "Invalid username or password."

    return render(
        request,
        "accounts/admin_login.html",
        {
            "error": error
        }
    )


# =========================
# DISTRIBUTOR LOGIN
# =========================

def distributor_login(request):

    # Already logged-in distributor
    if request.user.is_authenticated:
        if is_distributor(request.user):
            return redirect("distributor_dashboard")

        if request.user.is_staff:
            return redirect("admin_dashboard")

    error = None

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            error = "Username and password are required."

        else:
            user = authenticate(
                request,
                username=username,
                password=password
            )

            if user is not None:

                # Only Distributor group users can access Distributor
                if is_distributor(user):
                    login(request, user)

                    return redirect("distributor_dashboard")

                error = "You are not authorized to login as Distributor."

            else:
                error = "Invalid username or password."

    return render(
        request,
        "accounts/distributor_login.html",
        {
            "error": error
        }
    )


# =========================
# DISTRIBUTOR REGISTRATION
# =========================

def distributor_register(request):
    if request.user.is_authenticated:
        if is_distributor(request.user):
            return redirect("distributor_dashboard")

    error = None
    form = DistributorRegistrationForm()

    if request.method == "POST":
        form = DistributorRegistrationForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data.get("full_name", "").strip()
            email = form.cleaned_data.get("email", "").strip()
            phone = form.cleaned_data.get("phone", "").strip()
            password = form.cleaned_data.get("password", "")

            try:
                with transaction.atomic():
                    name_parts = full_name.split(" ", 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ""

                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name
                    )

                    distributor_group, _ = Group.objects.get_or_create(name="Distributor")
                    user.groups.add(distributor_group)

                    # Save profile details in DistributorProfile model
                    DistributorProfile.objects.create(
                        user=user,
                        full_name=full_name,
                        email=email,
                        phone=phone
                    )

                messages.success(
                    request,
                    "Distributor account created successfully. Please login."
                )
                return redirect("distributor_login")
            except Exception as e:
                error = "Unable to create your account right now. Please try again."
        else:
            for field, errors in form.errors.items():
                error = errors[0]
                break

    return render(
        request,
        "accounts/distributor_register.html",
        {
            "error": error,
            "form": form
        }
    )



# =========================
# ADMIN DASHBOARD
# =========================

@login_required(login_url="/admin/login/")
def admin_dashboard(request):

    if not request.user.is_staff:
        return redirect("distributor_login")

    return render(
        request,
        "dashboard/admin_dashboard.html"
    )


# =========================
# DISTRIBUTOR DASHBOARD
# =========================

@login_required(login_url="/distributor/login/")
def distributor_dashboard(request):

    if not is_distributor(request.user):
        return redirect("admin_login")

    return render(
        request,
        "dashboard/distributor_dashboard.html"
    )


# =========================
# LOGOUT
# =========================

def logout_view(request):

    logout(request)

    return redirect("admin_login")


# =========================
# FORGOT PASSWORD
# =========================

def forgot_password(request):
    error = None
    if request.method == "POST":
        email_or_username = request.POST.get("email", "").strip()

        if not email_or_username:
            error = "Email address or username is required."
        else:
            user = User.objects.filter(email__iexact=email_or_username).first() or \
                   User.objects.filter(username__iexact=email_or_username).first()

            if user:
                target_email = user.email if user.email else email_or_username

                # Invalidate prior active OTPs for same email & purpose
                OTPVerification.objects.filter(
                    email=target_email,
                    purpose="forgot_password",
                    is_verified=False
                ).update(is_verified=True)

                # Secure 6-digit OTP generation using secrets
                otp_code = f"{secrets.randbelow(1000000):06d}"
                expires_at = timezone.now() + timedelta(minutes=5)

                # Save OTP in database
                OTPVerification.objects.create(
                    user=user,
                    email=target_email,
                    otp_code=otp_code,
                    purpose="forgot_password",
                    expires_at=expires_at,
                    is_verified=False,
                    attempts=0
                )

                # Store minimal session metadata for tracking reset flow
                request.session["reset_user_id"] = user.id
                request.session["reset_email"] = target_email
                request.session["password_reset_verified"] = False

                # Send Email
                try:
                    send_mail(
                        subject="Password Reset OTP - Advance Billing System",
                        message=(
                            f"Your OTP is: {otp_code}\n\n"
                            f"This OTP is valid for 5 minutes.\n\n"
                            f"Do not share this OTP with anyone."
                        ),
                        from_email=None,
                        recipient_list=[target_email],
                        fail_silently=False,
                    )
                except Exception as e:
                    print(f"Error sending OTP email: {e}")

                return redirect("verify_otp")
            else:
                error = "No account found with that email address or username."

    return render(
        request,
        "accounts/forgot_password.html",
        {"error": error}
    )


# =========================
# VERIFY OTP
# =========================

def verify_otp(request):
    target_email = request.session.get("reset_email")
    if not target_email or not request.session.get("reset_user_id"):
        return redirect("forgot_password")

    error = None

    if request.method == "POST":
        user_otp = request.POST.get("otp", "").strip()

        # Find latest active OTP record from DB
        otp_record = OTPVerification.objects.filter(
            email=target_email,
            purpose="forgot_password",
            is_verified=False
        ).order_by("-created_at").first()

        if not otp_record:
            error = "No active OTP found. Please request a new OTP."
        elif timezone.now() > otp_record.expires_at:
            error = "OTP has expired. Please request a new OTP."
        elif otp_record.attempts >= 5:
            error = "Too many incorrect attempts. Please request a new OTP."
        elif otp_record.otp_code != user_otp:
            otp_record.attempts += 1
            otp_record.save()
            if otp_record.attempts >= 5:
                error = "Too many incorrect attempts. Please request a new OTP."
            else:
                error = f"Invalid OTP. You have {5 - otp_record.attempts} attempts remaining."
        else:
            # Mark OTP as verified in database
            otp_record.is_verified = True
            otp_record.save()

            # Store verification state in Django session
            request.session["password_reset_verified"] = True
            request.session["password_reset_email"] = target_email

            return redirect("reset_password")

    return render(
        request,
        "accounts/verify_otp.html",
        {
            "error": error,
            "email": target_email,
        }
    )


# =========================
# RESEND OTP
# =========================

def resend_otp(request):
    target_email = request.session.get("reset_email")
    user_id = request.session.get("reset_user_id")

    if not target_email or not user_id:
        return JsonResponse({"success": False, "message": "Session expired. Please restart the process."}, status=400)

    # 60-second rate limiting cooldown check
    latest_otp = OTPVerification.objects.filter(
        email=target_email,
        purpose="forgot_password"
    ).order_by("-created_at").first()

    if latest_otp:
        elapsed = (timezone.now() - latest_otp.created_at).total_seconds()
        if elapsed < 60:
            remaining = int(60 - elapsed)
            return JsonResponse({
                "success": False,
                "message": f"Please wait {remaining} seconds before requesting a new OTP."
            }, status=429)

    try:
        user = User.objects.get(id=user_id)

        # Invalidate previous unverified OTPs
        OTPVerification.objects.filter(
            email=target_email,
            purpose="forgot_password",
            is_verified=False
        ).update(is_verified=True)

        # Generate new 6-digit numeric OTP
        otp_code = f"{secrets.randbelow(1000000):06d}"
        expires_at = timezone.now() + timedelta(minutes=5)

        # Create new DB record
        OTPVerification.objects.create(
            user=user,
            email=target_email,
            otp_code=otp_code,
            purpose="forgot_password",
            expires_at=expires_at,
            is_verified=False,
            attempts=0
        )

        # Send email
        try:
            send_mail(
                subject="Password Reset OTP (Resent) - Advance Billing System",
                message=(
                    f"Your OTP is: {otp_code}\n\n"
                    f"This OTP is valid for 5 minutes.\n\n"
                    f"Do not share this OTP with anyone."
                ),
                from_email=None,
                recipient_list=[target_email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Error resending OTP email: {e}")

        return JsonResponse({"success": True, "message": "OTP sent successfully."})
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": "User not found."}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "message": "Something went wrong. Please try again."}, status=500)


# =========================
# RESET PASSWORD
# =========================

def reset_password(request):
    user_id = request.session.get("reset_user_id")
    is_verified = request.session.get("password_reset_verified")

    # Security Check: Require successful OTP verification
    if not user_id or not is_verified:
        return redirect("forgot_password")

    error = None
    success = None

    if request.method == "POST":
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not new_password or not confirm_password:
            error = "Both password fields are required."
        elif new_password != confirm_password:
            error = "Passwords do not match."
        elif len(new_password) < 6:
            error = "Password must be at least 6 characters long."
        else:
            try:
                user = User.objects.get(id=user_id)
                user.set_password(new_password)
                user.save()

                # Invalidate any remaining active OTP records in DB
                OTPVerification.objects.filter(
                    email=user.email,
                    purpose="forgot_password",
                    is_verified=False
                ).update(is_verified=True)

                # Clear reset session variables
                for key in ["reset_user_id", "reset_email", "password_reset_verified", "password_reset_email"]:
                    if key in request.session:
                        del request.session[key]

                success = "Your password has been reset successfully! You can now login with your new password."
            except User.DoesNotExist:
                error = "User not found."

    return render(
        request,
        "accounts/reset_password.html",
        {
            "error": error,
            "success": success
        }
    )
