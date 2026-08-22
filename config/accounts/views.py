from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.shortcuts import render, redirect


def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("admin_dashboard")

    error = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None and user.is_staff:
            login(request, user)
            return redirect("admin_dashboard")

        error = "Invalid Admin username or password."

    return render(
        request,
        "accounts/admin_login.html",
        {"error": error}
    )


def distributor_login(request):
    if request.user.is_authenticated and is_distributor(request.user):
        return redirect("distributor_dashboard")

    error = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None and is_distributor(user):
            login(request, user)
            return redirect("distributor_dashboard")

        error = "Invalid Distributor username or password."

    return render(
        request,
        "accounts/distributor_login.html",
        {"error": error}
    )


def is_distributor(user):
    return user.groups.filter(name="Distributor").exists()


@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect("distributor_login")

    return render(
        request,
        "dashboard/admin_dashboard.html"
    )


@login_required
def distributor_dashboard(request):
    if not is_distributor(request.user):
        return redirect("admin_login")

    return render(
        request,
        "dashboard/distributor_dashboard.html"
    )


def logout_view(request):
    logout(request)
    return redirect("admin_login")