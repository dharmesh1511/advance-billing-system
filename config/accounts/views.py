from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
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