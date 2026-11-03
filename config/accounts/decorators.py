"""
Reusable role-based authentication and route protection decorators and CBV mixins
for Admin and Distributor portals.
"""

from functools import wraps
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.contrib.auth.mixins import AccessMixin
from accounts.models import DistributorProfile


def is_distributor(user):
    """
    Check if a user is a verified Distributor:
    - Must be authenticated
    - Must NOT be staff or superuser
    - Must belong to the 'Distributor' group OR have a DistributorProfile
    """
    if not (user and user.is_authenticated):
        return False
    if user.is_superuser or user.is_staff:
        return False
    if user.groups.filter(name="Distributor").exists():
        return True
    try:
        if getattr(user, "distributor_profile", None) is not None:
            return True
    except Exception:
        pass
    return DistributorProfile.objects.filter(user=user).exists()


def is_admin(user):
    """
    Check if a user is a verified Admin:
    - Must be authenticated
    - Must be staff or superuser
    - Must NOT belong to the 'Distributor' group
    - Must NOT have a DistributorProfile
    """
    if not (user and user.is_authenticated):
        return False
    if not (user.is_staff or user.is_superuser):
        return False
    if user.groups.filter(name="Distributor").exists():
        return False
    try:
        if getattr(user, "distributor_profile", None) is not None:
            return False
    except Exception:
        pass
    return not DistributorProfile.objects.filter(user=user).exists()


def admin_required(view_func=None, login_url="/admin/login/", return_403=False):
    """
    Decorator for views that checks that the user is logged in and has the Admin role:
    - Unauthenticated users: redirected to admin login with next parameter.
    - Wrong role (Distributor): redirected to distributor dashboard with permission error.
    - Wrong role (Other): redirected to admin login with permission error.
    - AJAX/JSON or return_403: returns HTTP 403 Forbidden.
    """
    def decorator(func):
        @wraps(func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), login_url)

            if not is_admin(request.user):
                if return_403 or request.headers.get("x-requested-with") == "XMLHttpRequest" or request.GET.get("format") == "json":
                    return HttpResponseForbidden("403 Forbidden: Admin privileges required.")

                msg = (
                    "You are not authorized to access the Admin Dashboard."
                    if request.path == "/admin/dashboard/"
                    else "Access denied. Admin privileges required."
                )
                messages.error(request, msg)

                if request.path.rstrip("/") == "/admin/dashboard" and is_distributor(request.user):
                    return redirect("distributor_dashboard")
                return redirect_to_login(request.get_full_path(), login_url)

            return func(request, *args, **kwargs)

        return _wrapped_view

    if view_func is not None:
        return decorator(view_func)
    return decorator


def distributor_required(view_func=None, login_url="/distributor/login/", return_403=False):
    """
    Decorator for views that checks that the user is logged in and has the Distributor role:
    - Unauthenticated users: redirected to distributor login with next parameter.
    - Wrong role (Admin): redirected to admin dashboard with permission error.
    - Wrong role (Other): redirected to distributor login with permission error.
    - AJAX/JSON or return_403: returns HTTP 403 Forbidden or JSON error.
    """
    def decorator(func):
        @wraps(func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), login_url)

            if not is_distributor(request.user):
                if return_403 or request.headers.get("x-requested-with") == "XMLHttpRequest" or request.GET.get("format") == "json":
                    if return_403 or request.headers.get("x-requested-with") == "XMLHttpRequest" or request.GET.get("format") == "json":
                        return JsonResponse({"error": "Unauthorized"}, status=403)
                    return HttpResponseForbidden("403 Forbidden: Distributor privileges required.")

                msg = (
                    "You are not authorized to access the Distributor Dashboard."
                    if request.path == "/distributor/dashboard/"
                    else "Access denied. Distributor privileges required."
                )
                messages.error(request, msg)

                if request.path.rstrip("/") == "/distributor/dashboard" and is_admin(request.user):
                    return redirect("admin_dashboard")
                return redirect_to_login(request.get_full_path(), login_url)

            return func(request, *args, **kwargs)

        return _wrapped_view

    if view_func is not None:
        return decorator(view_func)
    return decorator


class AdminRequiredMixin(AccessMixin):
    """Class-based view mixin that verifies the current user has the Admin role."""
    login_url = "/admin/login/"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not is_admin(request.user):
            if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.GET.get("format") == "json":
                return HttpResponseForbidden("403 Forbidden: Admin privileges required.")
            messages.error(request, "Access denied. Admin privileges required.")
            if is_distributor(request.user):
                return redirect("distributor_dashboard")
            return redirect("admin_login")
        return super().dispatch(request, *args, **kwargs)


class DistributorRequiredMixin(AccessMixin):
    """Class-based view mixin that verifies the current user has the Distributor role."""
    login_url = "/distributor/login/"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not is_distributor(request.user):
            if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.GET.get("format") == "json":
                return JsonResponse({"error": "Distributor privileges required."}, status=403)
            messages.error(request, "Access denied. Distributor privileges required.")
            if is_admin(request.user):
                return redirect("admin_dashboard")
            return redirect("distributor_login")
        return super().dispatch(request, *args, **kwargs)

