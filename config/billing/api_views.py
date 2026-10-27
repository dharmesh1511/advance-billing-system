import io
import os
import logging
from decimal import Decimal
from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.db import models
from django.db.models import Q, ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404
from rest_framework import status, generics, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import MultiPartParser, FormParser

from accounts.authentication import SecureJWTAuthentication
from .models import Product, InvoiceItem
from .serializers import (
    ProductSerializer,
    QRCodeUploadSerializer,
    QRCodeDecodeResponseSerializer,
)
from .utils import decode_qr_from_image

logger = logging.getLogger(__name__)

# Constants for QR Decoding validations
DEFAULT_MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
DEFAULT_MAX_IMAGE_PIXELS = 16_000_000     # 16 Megapixels
DEFAULT_MAX_DIMENSION = 4096              # 4096 px
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
ALLOWED_MIME_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/webp", "image/bmp", "image/tiff", "image/x-ms-bmp"
}
ALLOWED_PIL_FORMATS = {"PNG", "JPEG", "WEBP", "BMP", "TIFF"}


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


class QRCodeDecodeAPIView(APIView):
    """
    POST /api/qr/decode/

    Secure QR Code Decoder Endpoint:
    - Accepts uploaded image via multipart/form-data under the field name 'image'.
    - Validates file presence, size limits (5 MB max), format, dimensions, and image integrity.
    - Decodes single and multiple QR codes from the uploaded image.
    - Returns decoded content in a structured JSON response.
    - Requires authentication (JWT Bearer Token or Session Authentication).
    - Safely processes all files in-memory without saving them permanently.
    - Never executes or follows decoded content.
    """
    authentication_classes = [SecureJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        # 1. Validate file presence
        if "image" not in request.FILES:
            return Response(
                {
                    "success": False,
                    "error": "No image file provided. Please provide an image using the 'image' field."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_file = request.FILES["image"]

        # 2. Check for empty file
        if uploaded_file.size == 0:
            return Response(
                {
                    "success": False,
                    "error": "The uploaded image file is empty."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Enforce maximum file size (HTTP 413)
        max_size = getattr(settings, "QR_DECODER_MAX_IMAGE_SIZE", DEFAULT_MAX_IMAGE_SIZE)
        if uploaded_file.size > max_size:
            max_mb = max_size / (1024 * 1024)
            return Response(
                {
                    "success": False,
                    "error": f"Image file size exceeds the maximum allowed limit of {max_mb:.1f} MB."
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )

        # 4. Check file extension and client MIME type (HTTP 415)
        allowed_exts = getattr(settings, "QR_DECODER_ALLOWED_EXTENSIONS", ALLOWED_EXTENSIONS)
        file_name = uploaded_file.name or ""
        ext = os.path.splitext(file_name)[1].lower()

        if ext and ext not in allowed_exts:
            return Response(
                {
                    "success": False,
                    "error": "Unsupported file format. Supported formats are PNG, JPEG, WEBP, and BMP."
                },
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            )

        content_type = (uploaded_file.content_type or "").lower().split(";")[0].strip()
        if content_type and not content_type.startswith("image/") and content_type not in ALLOWED_MIME_TYPES:
            return Response(
                {
                    "success": False,
                    "error": "Unsupported media type. Supported formats are PNG, JPEG, WEBP, and BMP."
                },
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            )

        # 5. Read image into memory and validate content with Pillow
        try:
            file_bytes = uploaded_file.read()
        except Exception as e:
            logger.error(f"Failed to read uploaded file into memory: {e}")
            return Response(
                {
                    "success": False,
                    "error": "Unable to read uploaded file."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        in_memory_buf = io.BytesIO(file_bytes)

        # Pillow decompression bomb limits
        max_pixels = getattr(settings, "QR_DECODER_MAX_IMAGE_PIXELS", DEFAULT_MAX_IMAGE_PIXELS)
        Image.MAX_IMAGE_PIXELS = max_pixels

        try:
            pil_image = Image.open(in_memory_buf)
        except UnidentifiedImageError:
            if ext in allowed_exts or (content_type and content_type.startswith("image/")):
                return Response(
                    {
                        "success": False,
                        "error": "The uploaded file is corrupted or not a valid image."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {
                    "success": False,
                    "error": "Unsupported media type. Supported formats are PNG, JPEG, WEBP, and BMP."
                },
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            )
        except Image.DecompressionBombError:
            return Response(
                {
                    "success": False,
                    "error": "Image decompression bomb detected or image is too large to safely process."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception:
            return Response(
                {
                    "success": False,
                    "error": "The uploaded file is corrupted or not a valid image."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 6. Verify format detected by Pillow (HTTP 415)
        allowed_formats = getattr(settings, "QR_DECODER_ALLOWED_FORMATS", ALLOWED_PIL_FORMATS)
        detected_format = (pil_image.format or "").upper()
        if detected_format and detected_format not in allowed_formats:
            return Response(
                {
                    "success": False,
                    "error": f"Unsupported image format '{detected_format}'. Supported formats are PNG, JPEG, WEBP, and BMP."
                },
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            )

        # 7. Verify integrity and dimensions
        try:
            pil_image.verify()
        except Exception:
            return Response(
                {
                    "success": False,
                    "error": "The uploaded image file is corrupted."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Reopen after verify() to load pixel data
        in_memory_buf.seek(0)
        try:
            pil_image = Image.open(in_memory_buf)
            pil_image.load()
        except Image.DecompressionBombError:
            return Response(
                {
                    "success": False,
                    "error": "Image decompression bomb detected or image is too large to safely process."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception:
            return Response(
                {
                    "success": False,
                    "error": "The uploaded image file is corrupted or incomplete."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Dimension checks
        max_dim = getattr(settings, "QR_DECODER_MAX_IMAGE_DIMENSION", DEFAULT_MAX_DIMENSION)
        if pil_image.width > max_dim or pil_image.height > max_dim:
            return Response(
                {
                    "success": False,
                    "error": f"Image dimensions ({pil_image.width}x{pil_image.height}) exceed the maximum allowed limit of {max_dim}x{max_dim} pixels."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if (pil_image.width * pil_image.height) > max_pixels:
            return Response(
                {
                    "success": False,
                    "error": f"Image pixel count exceeds the maximum safe limit of {max_pixels} pixels."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 8. Transpose orientation if EXIF tags exist
        try:
            pil_image = ImageOps.exif_transpose(pil_image)
        except Exception:
            pass

        # 9. Decode QR code(s) safely
        try:
            results = decode_qr_from_image(pil_image)
        except Exception as e:
            logger.error(f"Unexpected error in QR code decoding: {e}")
            return Response(
                {
                    "success": False,
                    "error": "An error occurred while decoding the QR code."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Log decode count securely without exposing raw data
        logger.info("QR code decode request processed: %d code(s) found.", len(results))

        if results:
            msg = "QR code decoded successfully." if len(results) == 1 else f"{len(results)} QR codes decoded successfully."
        else:
            msg = "No QR code found in the uploaded image."

        return Response(
            {
                "success": True,
                "message": msg,
                "results": results
            },
            status=status.HTTP_200_OK
        )
