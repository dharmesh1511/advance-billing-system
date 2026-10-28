import io
import json
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from PIL import Image
import qrcode

from billing.models import Customer, Product, Invoice, InvoiceItem
from billing.utils import (
    extract_invoice_identifier_from_qr,
    resolve_invoice_from_identifier,
    format_invoice_for_response,
    parse_and_resolve_invoice_from_qr,
    InvalidQRPayloadError,
    InvoiceNotFoundError,
    InvoicePermissionDeniedError,
)


class QRCodeDecoderAPITests(TestCase):
    """
    Comprehensive automated test suite for the QR Code Decoder API endpoint (/api/qr/decode/)
    and invoice resolution functionality.
    Covers all 10 required scenarios:
    1. A valid QR code referencing an existing invoice.
    2. A valid QR code referencing a nonexistent invoice (404).
    3. Malformed or unsupported QR payloads (400).
    4. JSON payload parsing.
    5. Invoice URLs parsing.
    6. Correct rendering of invoice information (API and UI template).
    7. Correct totals, discounts, taxes, and payment status.
    8. Unauthorized invoice access (distributor isolation / 403).
    9. Invalid image uploads (corrupted, oversized, unsupported format, dimensions).
    10. Empty and unexpected API responses (empty file, missing field, blank image, decode-only).
    """

    def setUp(self):
        self.client = APIClient()
        self.endpoint = "/api/qr/decode/"

        # 1. Primary test distributor user
        self.distributor = User.objects.create_user(
            username="testdistributor",
            email="distributor@example.com",
            password="SecurePassword123!"
        )

        # 2. Secondary distributor user for permission/isolation testing
        self.other_distributor = User.objects.create_user(
            username="otherdistributor",
            email="other@example.com",
            password="SecurePassword123!"
        )

        # 3. Superuser
        self.admin_user = User.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="AdminPassword123!"
        )

        # Authenticate client as the primary distributor by default
        from accounts.models import DistributorProfile
        DistributorProfile.objects.create(
            user=self.distributor,
            full_name="Test Distributor",
            email="distributor@example.com",
            phone="9876543210"
        )
        DistributorProfile.objects.create(
            user=self.other_distributor,
            full_name="Other Distributor",
            email="other@example.com",
            phone="9123456780"
        )
        self.client.force_authenticate(user=self.distributor)
        self.client.force_login(self.distributor)


        # 4. Create customer for primary distributor
        self.customer = Customer.objects.create(
            distributor=self.distributor,
            name="Alpha Industries Ltd",
            email="contact@alphaindustries.com",
            phone="9876543210",
            address="123 Industrial Park, Phase 1",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380001"
        )

        # 5. Create products
        self.product1 = Product.objects.create(
            distributor=self.distributor,
            name="Industrial Cable 10m",
            price=Decimal("500.00"),
            stock=100,
            gst_rate=Decimal("18.00"),
            sku="CAB-10M"
        )
        self.product2 = Product.objects.create(
            distributor=self.distributor,
            name="LED High Bay Light 100W",
            price=Decimal("1500.00"),
            stock=50,
            gst_rate=Decimal("12.00"),
            sku="LED-100W"
        )

        # 6. Create invoice for primary distributor
        # Item 1: 2 x 500 = 1000 gross. Discount 10% = 100. Taxable = 900. GST 18% = 162. Line total = 1062.
        # Item 2: 1 x 1500 = 1500 gross. Discount 0% = 0. Taxable = 1500. GST 12% = 180. Line total = 1680.
        # Subtotal: 900 + 1500 = 2400.00
        # Total GST: 162 + 180 = 342.00
        # Grand Total: 2742.00
        self.invoice = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer,
            invoice_number="INV-2026-0001",
            invoice_date="2026-10-28",
            subtotal=Decimal("2400.00"),
            total_gst=Decimal("342.00"),
            grand_total=Decimal("2742.00")
        )

        self.item1 = InvoiceItem.objects.create(
            invoice=self.invoice,
            product=self.product1,
            product_name="Industrial Cable 10m",
            quantity=2,
            unit_price=Decimal("500.00"),
            discount_percent=Decimal("10.00"),
            taxable_amount=Decimal("900.00"),
            gst_rate=Decimal("18.00"),
            gst_amount=Decimal("162.00"),
            line_total=Decimal("1062.00")
        )

        self.item2 = InvoiceItem.objects.create(
            invoice=self.invoice,
            product=self.product2,
            product_name="LED High Bay Light 100W",
            quantity=1,
            unit_price=Decimal("1500.00"),
            discount_percent=Decimal("0.00"),
            taxable_amount=Decimal("1500.00"),
            gst_rate=Decimal("12.00"),
            gst_amount=Decimal("180.00"),
            line_total=Decimal("1680.00")
        )

        # 7. Create second invoice belonging to other_distributor
        self.other_customer = Customer.objects.create(
            distributor=self.other_distributor,
            name="Beta Enterprise",
            email="beta@example.com",
            phone="9123456780"
        )
        self.other_invoice = Invoice.objects.create(
            distributor=self.other_distributor,
            customer=self.other_customer,
            invoice_number="INV-OTHER-9999",
            invoice_date="2026-10-28",
            subtotal=Decimal("1000.00"),
            total_gst=Decimal("180.00"),
            grand_total=Decimal("1180.00")
        )

    def _generate_qr_image_bytes(self, data, fmt="PNG"):
        """Helper to generate an in-memory QR code image as bytes."""
        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=2,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").get_image()

        buf = io.BytesIO()
        mode = "RGB" if fmt in ("JPEG", "WEBP", "BMP") else img.mode
        img.convert(mode).save(buf, format=fmt)
        return buf.getvalue()

    def _generate_blank_image_bytes(self, fmt="PNG"):
        """Helper to generate an in-memory blank white image with no QR code."""
        img = Image.new("RGB", (200, 200), color="white")
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Test 1: Valid QR code referencing an existing invoice
    # ------------------------------------------------------------------
    def test_valid_qr_code_referencing_existing_invoice(self):
        """Uploading a QR image with an existing invoice identifier returns 200 OK and complete invoice info."""
        qr_bytes = self._generate_qr_image_bytes(self.invoice.invoice_number, fmt="PNG")
        uploaded = SimpleUploadedFile("invoice_qr.png", qr_bytes, content_type="image/png")

        response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("message"), "Invoice retrieved successfully.")
        self.assertIn("invoice", data)

        inv = data["invoice"]
        self.assertEqual(inv["invoice_number"], "INV-2026-0001")
        self.assertEqual(inv["customer_name"], "Alpha Industries Ltd")
        self.assertEqual(inv["grand_total"], "2742.00")
        self.assertEqual(inv["total_items"], 2)
        self.assertEqual(inv["payment_status"], "Paid")

    # ------------------------------------------------------------------
    # Test 2: Valid QR code referencing a nonexistent invoice
    # ------------------------------------------------------------------
    def test_valid_qr_code_referencing_nonexistent_invoice(self):
        """Uploading a QR code with an invoice reference not present in the DB returns 404 Not Found."""
        qr_bytes = self._generate_qr_image_bytes("INV-9999-NOTFOUND", fmt="PNG")
        uploaded = SimpleUploadedFile("missing_inv.png", qr_bytes, content_type="image/png")

        response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        data = response.json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "invoice_not_found")
        self.assertIn("INV-9999-NOTFOUND", data.get("error", ""))

    # ------------------------------------------------------------------
    # Test 3: Malformed or unsupported QR payloads
    # ------------------------------------------------------------------
    def test_malformed_or_unsupported_qr_payloads(self):
        """QR codes with arbitrary text, invalid characters, or unmapped URLs return 400 Bad Request."""
        malformed_samples = [
            "This is just random plain text with spaces",
            "https://www.google.com/search?q=test",
            "{\"unrelated_key\": \"some_data\"}",
            "<script>alert('xss')</script>",
        ]

        for sample in malformed_samples:
            with self.subTest(sample=sample):
                qr_bytes = self._generate_qr_image_bytes(sample, fmt="PNG")
                uploaded = SimpleUploadedFile("malformed.png", qr_bytes, content_type="image/png")

                response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

                data = response.json()
                self.assertFalse(data.get("success"))
                self.assertEqual(data.get("code"), "invalid_qr_payload")

    # ------------------------------------------------------------------
    # Test 4: JSON payload parsing
    # ------------------------------------------------------------------
    def test_json_payload_parsing(self):
        """Structured JSON payloads containing invoice_number resolve the matching invoice."""
        json_payload = json.dumps({
            "invoice_number": self.invoice.invoice_number,
            "invoice_date": "2026-10-28",
            "grand_total": "2742.00",
            "currency": "INR",
            "customer_name": "Alpha Industries Ltd"
        })

        qr_bytes = self._generate_qr_image_bytes(json_payload, fmt="PNG")
        uploaded = SimpleUploadedFile("json_qr.png", qr_bytes, content_type="image/png")

        response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["invoice"]["invoice_number"], self.invoice.invoice_number)
        self.assertEqual(data["invoice"]["customer_name"], "Alpha Industries Ltd")

    # ------------------------------------------------------------------
    # Test 5: Invoice URLs parsing
    # ------------------------------------------------------------------
    def test_invoice_urls_parsing(self):
        """Recognized invoice URLs with path segments or query parameters resolve correctly."""
        url_variations = [
            f"https://billing.example.com/invoice/{self.invoice.invoice_number}",
            f"http://localhost:8000/distributor/invoices/{self.invoice.pk}/",
            f"http://localhost:8000/billing/distributor/invoices/{self.invoice.pk}/details/",
            f"https://billing.example.com/distributor/invoices?invoice_number={self.invoice.invoice_number}",
        ]

        for url in url_variations:
            with self.subTest(url=url):
                qr_bytes = self._generate_qr_image_bytes(url, fmt="PNG")
                uploaded = SimpleUploadedFile("url_qr.png", qr_bytes, content_type="image/png")

                response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
                self.assertEqual(response.status_code, status.HTTP_200_OK)

                data = response.json()
                self.assertTrue(data["success"])
                self.assertEqual(data["invoice"]["invoice_number"], self.invoice.invoice_number)

    # ------------------------------------------------------------------
    # Test 6: Correct rendering of invoice information & UI View
    # ------------------------------------------------------------------
    def test_correct_rendering_of_invoice_information(self):
        """Verifies all detailed invoice fields and items are returned, and checks GET on QR decoder page."""
        # 1. API fields verification
        invoice_obj, formatted = parse_and_resolve_invoice_from_qr(self.invoice.invoice_number, user=self.distributor)
        self.assertEqual(formatted["invoice_number"], "INV-2026-0001")
        self.assertEqual(formatted["customer_name"], "Alpha Industries Ltd")
        self.assertEqual(formatted["customer_phone"], "9876543210")
        self.assertEqual(formatted["customer_email"], "contact@alphaindustries.com")
        self.assertIn("123 Industrial Park", formatted["customer_address"])

        self.assertEqual(len(formatted["items"]), 2)
        item1_data = formatted["items"][0]
        self.assertEqual(item1_data["product_name"], "Industrial Cable 10m")
        self.assertEqual(item1_data["quantity"], 2)
        self.assertEqual(item1_data["unit_price"], "500.00")
        self.assertEqual(item1_data["discount_percent"], "10.00")
        self.assertEqual(item1_data["gst_rate"], "18.00")
        self.assertEqual(item1_data["line_total"], "1062.00")

        # 2. Web UI View verification
        self.client.login(username="testdistributor", password="SecurePassword123!")
        ui_response = self.client.get("/billing/distributor/qr/decode/")
        self.assertEqual(ui_response.status_code, 200)
        self.assertContains(ui_response, "QR Code Decoder")
        self.assertContains(ui_response, "Decode &amp; Verify Invoice")

    # ------------------------------------------------------------------
    # Test 7: Correct totals and payment status
    # ------------------------------------------------------------------
    def test_correct_totals_and_payment_status(self):
        """Verifies accurate calculation of subtotal, tax, discount, grand total, and payment balance."""
        qr_bytes = self._generate_qr_image_bytes(self.invoice.invoice_number, fmt="PNG")
        uploaded = SimpleUploadedFile("invoice_qr.png", qr_bytes, content_type="image/png")

        response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        inv = response.json()["invoice"]
        self.assertEqual(inv["subtotal"], "2400.00")
        self.assertEqual(inv["tax_amount"], "342.00")
        self.assertEqual(inv["gross_total"], "2500.00")  # (2*500) + (1*1500) = 2500
        self.assertEqual(inv["total_discount"], "100.00")
        self.assertEqual(inv["grand_total"], "2742.00")
        self.assertEqual(inv["amount_paid"], "2742.00")
        self.assertEqual(inv["balance_due"], "0.00")
        self.assertEqual(inv["payment_status"], "Paid")

    # ------------------------------------------------------------------
    # Test 8: Unauthorized invoice access (Distributor Isolation)
    # ------------------------------------------------------------------
    def test_unauthorized_invoice_access_rejected_with_403(self):
        """A distributor attempting to decode another distributor's invoice receives 403 Forbidden."""
        # Authenticated as self.distributor, try to access other_invoice belonging to other_distributor
        qr_bytes = self._generate_qr_image_bytes(self.other_invoice.invoice_number, fmt="PNG")
        uploaded = SimpleUploadedFile("other_qr.png", qr_bytes, content_type="image/png")

        response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data.get("code"), "permission_denied")
        self.assertIn("permission", data.get("error", "").lower())

        # An Admin / Staff user CAN access cross-distributor invoices
        self.client.force_authenticate(user=self.admin_user)
        uploaded.seek(0)
        admin_response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_response.json()["invoice"]["invoice_number"], self.other_invoice.invoice_number)

    # ------------------------------------------------------------------
    # Test 9: Invalid image uploads
    # ------------------------------------------------------------------
    def test_corrupted_image_returns_400(self):
        """Uploading corrupted bytes with an image filename returns 400 Bad Request."""
        corrupted_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRcorrupted_payload"
        uploaded = SimpleUploadedFile("corrupted.png", corrupted_bytes, content_type="image/png")

        response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data.get("success"))
        self.assertIn("corrupted", data.get("error", "").lower())

    def test_unsupported_file_extension_returns_415(self):
        """Unsupported file extensions (.txt, .pdf) return 415 Unsupported Media Type."""
        text_file = SimpleUploadedFile("document.txt", b"Hello text", content_type="text/plain")
        response = self.client.post(self.endpoint, {"image": text_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_unsupported_image_format_returns_415(self):
        """Unsupported image formats like GIF return 415 Unsupported Media Type."""
        gif_img = Image.new("P", (100, 100), color=1)
        buf = io.BytesIO()
        gif_img.save(buf, format="GIF")

        uploaded = SimpleUploadedFile("animation.gif", buf.getvalue(), content_type="image/gif")
        response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    @override_settings(QR_DECODER_MAX_IMAGE_SIZE=300)
    def test_oversized_image_returns_413(self):
        """Uploads exceeding the configured size limit return 413 Request Entity Too Large."""
        large_bytes = self._generate_qr_image_bytes(self.invoice.invoice_number)
        self.assertGreater(len(large_bytes), 300)

        uploaded = SimpleUploadedFile("large_qr.png", large_bytes, content_type="image/png")
        response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

    @override_settings(QR_DECODER_MAX_IMAGE_DIMENSION=100)
    def test_excessive_dimensions_rejected_400(self):
        """Images exceeding allowed dimensions are rejected with 400 Bad Request."""
        img = Image.new("RGB", (250, 250), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        uploaded = SimpleUploadedFile("huge.png", buf.getvalue(), content_type="image/png")
        response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # Test 10: Empty and unexpected API responses
    # ------------------------------------------------------------------
    def test_missing_image_field_returns_400(self):
        """Requests missing the 'image' field return 400 Bad Request."""
        response = self.client.post(self.endpoint, {"wrong_field": "data"}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data.get("success"))
        self.assertIn("No image file provided", data.get("error", ""))

    def test_empty_image_file_returns_400(self):
        """Uploading a 0-byte file returns 400 Bad Request."""
        empty_file = SimpleUploadedFile("empty.png", b"", content_type="image/png")
        response = self.client.post(self.endpoint, {"image": empty_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data.get("success"))
        self.assertIn("empty", data.get("error", "").lower())

    def test_image_with_no_qr_code_detected(self):
        """A valid image with no QR code returns 200 OK with empty results and null invoice."""
        blank_bytes = self._generate_blank_image_bytes(fmt="PNG")
        uploaded = SimpleUploadedFile("blank.png", blank_bytes, content_type="image/png")

        response = self.client.post(self.endpoint, {"image": uploaded}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("message"), "No QR code detected.")
        self.assertEqual(data.get("results"), [])
        self.assertIsNone(data.get("invoice"))

    def test_decode_only_mode_returns_raw_results(self):
        """When ?decode_only=true is passed, raw decoded QR text is returned without invoice lookup."""
        payload = "https://example.com/arbitrary-unmapped-qr"
        qr_bytes = self._generate_qr_image_bytes(payload, fmt="PNG")
        uploaded = SimpleUploadedFile("qr.png", qr_bytes, content_type="image/png")

        response = self.client.post(
            f"{self.endpoint}?decode_only=true",
            {"image": uploaded},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["results"][0]["data"], payload)

    def test_unauthenticated_request_rejected(self):
        """Unauthenticated requests must return 401 Unauthorized."""
        unauthenticated_client = APIClient()
        qr_bytes = self._generate_qr_image_bytes(self.invoice.invoice_number, fmt="PNG")
        uploaded = SimpleUploadedFile("qr.png", qr_bytes, content_type="image/png")

        response = unauthenticated_client.post(self.endpoint, {"image": uploaded}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
