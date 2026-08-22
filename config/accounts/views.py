import random
import time
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import render, redirect


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
                otp = f"{random.randint(100000, 999999)}"
                request.session['reset_user_id'] = user.id
                request.session['reset_email'] = user.email or email_or_username
                request.session['reset_otp'] = otp
                request.session['otp_created_at'] = time.time()
                request.session['otp_verified'] = False

                recipient_email = user.email if user.email else email_or_username
                try:
                    send_mail(
                        subject="Password Reset OTP - Advance Billing System",
                        message=f"Hello,\n\nYour OTP to reset your password is: {otp}\n\nThis OTP is valid for 10 minutes.\nIf you did not request this, please ignore this email.",
                        from_email=None,
                        recipient_list=[recipient_email],
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
    if not request.session.get('reset_user_id') or not request.session.get('reset_otp'):
        return redirect("forgot_password")

    error = None
    email = request.session.get('reset_email', '')

    if request.method == "POST":
        user_otp = request.POST.get("otp", "").strip()

        stored_otp = request.session.get('reset_otp')
        created_at = request.session.get('otp_created_at', 0)

        if not user_otp:
            error = "Please enter the 6-digit OTP."
        elif time.time() - created_at > 600:
            error = "OTP has expired. Please click 'Resend OTP' to get a new code."
        elif user_otp != stored_otp:
            error = "Invalid OTP. Please check and try again."
        else:
            request.session['otp_verified'] = True
            return redirect("reset_password")

    return render(
        request,
        "accounts/verify_otp.html",
        {
            "error": error,
            "email": email,
        }
    )


# =========================
# RESEND OTP
# =========================

def resend_otp(request):
    user_id = request.session.get('reset_user_id')
    if not user_id:
        return JsonResponse({"success": False, "message": "Session expired. Please restart the process."}, status=400)

    try:
        user = User.objects.get(id=user_id)
        otp = f"{random.randint(100000, 999999)}"
        request.session['reset_otp'] = otp
        request.session['otp_created_at'] = time.time()

        recipient_email = user.email if user.email else request.session.get('reset_email', '')
        if recipient_email:
            try:
                send_mail(
                    subject="Password Reset OTP (Resent) - Advance Billing System",
                    message=f"Hello,\n\nYour new OTP to reset your password is: {otp}\n\nThis OTP is valid for 10 minutes.",
                    from_email=None,
                    recipient_list=[recipient_email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Error resending OTP email: {e}")

        return JsonResponse({"success": True, "message": "OTP sent successfully."})
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": "User not found."}, status=404)
    except Exception as e:
        return JsonResponse({"success": True, "message": "OTP regenerated successfully."})


# =========================
# RESET PASSWORD
# =========================

def reset_password(request):
    user_id = request.session.get('reset_user_id')
    if not user_id or not request.session.get('otp_verified'):
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

                # Clear reset session variables
                for key in ['reset_user_id', 'reset_email', 'reset_otp', 'otp_created_at', 'otp_verified']:
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