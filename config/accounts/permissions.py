from rest_framework.permissions import BasePermission
from .models import DistributorProfile


class IsDistributor(BasePermission):
    """
    Allows access only to authenticated users who are verified Distributors.
    Admins, staff, superusers, and regular users without distributor role are rejected.
    """
    message = "You do not have permission to perform this action. Distributor access required."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        # Verify whether user is an eligible distributor
        if user.groups.filter(name="Distributor").exists():
            return True

        if hasattr(user, "distributor_profile"):
            return True

        if DistributorProfile.objects.filter(user=user).exists():
            return True

        return False
