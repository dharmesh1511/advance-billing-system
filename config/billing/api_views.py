from decimal import Decimal
from django.db import models
from django.db.models import Q, ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404
from rest_framework import status, generics, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.authentication import SessionAuthentication

from accounts.authentication import SecureJWTAuthentication
from .models import Product, InvoiceItem
from .serializers import ProductSerializer


class IsDistributorOrAdmin(BasePermission):
    """
    Grants access only to authenticated Distributors and Admins (staff/superuser).
    Rejects unauthenticated requests with HTTP 401 and regular unauthorized users with HTTP 403.
    """
    message = "You do not have permission to perform this action. Distributor or Admin role required."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if user.is_superuser or user.is_staff:
            return True

        if user.groups.filter(name="Distributor").exists():
            return True

        if hasattr(user, "distributor_profile"):
            return True

        from accounts.models import DistributorProfile
        return DistributorProfile.objects.filter(user=user).exists()


class ProductPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class ProductListCreateAPIView(generics.ListCreateAPIView):
    """
    GET  /api/products/  - List products (with pagination, search, status filter)
    POST /api/products/  - Create a new product (ownership assigned to authenticated distributor)
    """
    serializer_class = ProductSerializer
    pagination_class = ProductPagination
    authentication_classes = [SecureJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, IsDistributorOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            queryset = Product.objects.all()
            dist_id = self.request.query_params.get("distributor_id")
            if dist_id and dist_id.isdigit():
                queryset = queryset.filter(distributor_id=int(dist_id))
        else:
            queryset = Product.objects.filter(distributor=user)

        # Search parameter (q or search)
        query = self.request.query_params.get("search") or self.request.query_params.get("q")
        if query:
            q_clean = query.strip()
            queryset = queryset.filter(
                Q(name__icontains=q_clean) |
                Q(sku__icontains=q_clean) |
                Q(category__icontains=q_clean) |
                Q(description__icontains=q_clean)
            )

        # Status filter
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            if is_active.lower() in ("true", "1", "yes"):
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() in ("false", "0", "no"):
                queryset = queryset.filter(is_active=False)

        # Category filter
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__iexact=category.strip())

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(distributor=self.request.user)


class ProductDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/products/<id>/  - Retrieve single product details
    PUT    /api/products/<id>/  - Full update of product
    PATCH  /api/products/<id>/  - Partial update of product
    DELETE /api/products/<id>/  - Delete product (safely handles invoice references)
    """
    serializer_class = ProductSerializer
    authentication_classes = [SecureJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, IsDistributorOrAdmin]
    lookup_field = "pk"

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return Product.objects.all()
        return Product.objects.filter(distributor=user)

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        product_name = product.name

        # Safe invoice integrity check before deletion
        if InvoiceItem.objects.filter(product=product).exists():
            return Response(
                {
                    "detail": f'Product "{product_name}" cannot be deleted because it is referenced in existing billing invoices.',
                    "code": "protected_product"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            self.perform_destroy(product)
            return Response(
                {
                    "message": f'Product "{product_name}" deleted successfully.'
                },
                status=status.HTTP_200_OK
            )
        except (ProtectedError, RestrictedError):
            return Response(
                {
                    "detail": f'Product "{product_name}" cannot be deleted because it is referenced in existing billing records.',
                    "code": "protected_product"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
