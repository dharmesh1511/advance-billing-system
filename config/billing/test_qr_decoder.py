import io
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from PIL import Image
import qrcode


class QRCodeDecoderAPITests(TestCase):
    """
    Automated test suite for the QR Code Decoder API endpoint (/api/qr/decode/).
    Covers all required scenarios:
    1. Valid image with a QR code.
    2. Valid image with no QR code.
    3. Missing image field.
    4. Unsupported file formats (415).
    5. Corrupted or invalid image files (400).
    6. Upload exceeding configured size limit (413).
    7. Multiple QR codes in a single image.
    8. Unauthorized requests (401).
    9. JSON response structure and HTTP status codes.
    10. Dimension limits / safe in-memory processing.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testdistributor",
            email="distributor@example.com",
            password="SecurePassword123!"
        )
        self.client.force_authenticate(user=self.user)
        self.endpoint = "/api/qr/decode/"

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

    def test_unauthorized_request_rejected(self):
        """Unauthenticated requests must return 401 Unauthorized."""
        unauthenticated_client = APIClient()
        img_bytes = self._generate_qr_image_bytes("https://billing.example.com")
        uploaded = SimpleUploadedFile("qr.png", img_bytes, content_type="image/png")

        response = unauthenticated_client.post(
            self.endpoint,
            {"image": uploaded},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_image_with_single_qr_code(self):
        """A valid PNG with a QR code should be decoded with 200 OK."""
        test_payload = "https://billing.example.com/invoice/INV-2026-001"
        img_bytes = self._generate_qr_image_bytes(test_payload, fmt="PNG")
        uploaded = SimpleUploadedFile("invoice_qr.png", img_bytes, content_type="image/png")

        response = self.client.post(
            self.endpoint,
            {"image": uploaded},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("message"), "QR code decoded successfully.")
        self.assertIsInstance(data.get("results"), list)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["data"], test_payload)
        self.assertEqual(data["results"][0]["type"], "QRCODE")

    def test_valid_jpeg_and_webp_images_decode_successfully(self):
        """Supported formats (JPEG, WEBP, BMP) decode properly."""
        for fmt, ext, mime in [
            ("JPEG", "jpg", "image/jpeg"),
            ("WEBP", "webp", "image/webp"),
            ("BMP", "bmp", "image/bmp")
        ]:
            with self.subTest(fmt=fmt):
                payload = f"https://example.com/item-{fmt}"
                img_bytes = self._generate_qr_image_bytes(payload, fmt=fmt)
                uploaded = SimpleUploadedFile(f"test.{ext}", img_bytes, content_type=mime)

                response = self.client.post(
                    self.endpoint,
                    {"image": uploaded},
                    format="multipart"
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                data = response.json()
                self.assertTrue(data["success"])
                self.assertEqual(len(data["results"]), 1)
                self.assertEqual(data["results"][0]["data"], payload)

    def test_image_with_no_qr_code(self):
        """A valid image with no QR code returns 200 OK with empty results array."""
        blank_bytes = self._generate_blank_image_bytes(fmt="PNG")
        uploaded = SimpleUploadedFile("blank.png", blank_bytes, content_type="image/png")

        response = self.client.post(
            self.endpoint,
            {"image": uploaded},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("message"), "No QR code detected.")
        self.assertEqual(data.get("results"), [])

    def test_multiple_qr_codes_in_one_image(self):
        """Image containing multiple QR codes returns all decoded entries."""
        payload1 = "https://example.com/qr1"
        payload2 = "https://example.com/qr2"

        qr1 = qrcode.make(payload1, box_size=6, border=4).get_image()
        qr2 = qrcode.make(payload2, box_size=6, border=4).get_image()

        combined = Image.new("RGB", (qr1.width, qr1.height * 2 + 50), color="white")
        combined.paste(qr1, (0, 0))
        combined.paste(qr2, (0, qr1.height + 50))

        buf = io.BytesIO()
        combined.save(buf, format="PNG")
        uploaded = SimpleUploadedFile("dual_qr.png", buf.getvalue(), content_type="image/png")

        response = self.client.post(
            self.endpoint,
            {"image": uploaded},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("2 QR codes decoded successfully", data["message"])
        self.assertEqual(len(data["results"]), 2)
        decoded_texts = [r["data"] for r in data["results"]]
        self.assertIn(payload1, decoded_texts)
        self.assertIn(payload2, decoded_texts)

    def test_missing_image_field_returns_400(self):
        """Requests missing the 'image' field return 400 Bad Request."""
        response = self.client.post(
            self.endpoint,
            {"wrong_field": "data"},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data.get("success"))
        self.assertIn("No image file provided", data.get("error", ""))

    def test_empty_image_file_returns_400(self):
        """Uploading a 0-byte file returns 400 Bad Request."""
        empty_file = SimpleUploadedFile("empty.png", b"", content_type="image/png")
        response = self.client.post(
            self.endpoint,
            {"image": empty_file},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data.get("success"))
        self.assertIn("empty", data.get("error", "").lower())

    def test_unsupported_file_extension_returns_415(self):
        """Unsupported file extensions (.txt, .pdf, .bin) return 415 Unsupported Media Type."""
        text_file = SimpleUploadedFile("document.txt", b"Hello text", content_type="text/plain")
        response = self.client.post(
            self.endpoint,
            {"image": text_file},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        data = response.json()
        self.assertFalse(data.get("success"))
        self.assertIn("Unsupported", data.get("error", ""))

    def test_unsupported_image_format_returns_415(self):
        """Unsupported image formats like GIF return 415 Unsupported Media Type."""
        gif_img = Image.new("P", (100, 100), color=1)
        buf = io.BytesIO()
        gif_img.save(buf, format="GIF")

        uploaded = SimpleUploadedFile("animation.gif", buf.getvalue(), content_type="image/gif")
        response = self.client.post(
            self.endpoint,
            {"image": uploaded},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        data = response.json()
        self.assertFalse(data["success"])

    def test_corrupted_image_returns_400(self):
        """Uploading corrupted bytes with an image filename returns 400 Bad Request."""
        corrupted_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRcorrupted_payload"
        uploaded = SimpleUploadedFile("corrupted.png", corrupted_bytes, content_type="image/png")

        response = self.client.post(
            self.endpoint,
            {"image": uploaded},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data.get("success"))
        self.assertIn("corrupted", data.get("error", "").lower())

    @override_settings(QR_DECODER_MAX_IMAGE_SIZE=500)  # Limit to 500 bytes for testing
    def test_oversized_image_returns_413(self):
        """Uploads exceeding the configured size limit return 413 Request Entity Too Large."""
        large_bytes = self._generate_qr_image_bytes("https://example.com/oversized")
        self.assertGreater(len(large_bytes), 500)

        uploaded = SimpleUploadedFile("large_qr.png", large_bytes, content_type="image/png")
        response = self.client.post(
            self.endpoint,
            {"image": uploaded},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        data = response.json()
        self.assertFalse(data.get("success"))
        self.assertIn("exceeds the maximum allowed limit", data.get("error", ""))

    @override_settings(QR_DECODER_MAX_IMAGE_DIMENSION=100)  # Limit dimension to 100px
    def test_excessive_dimensions_rejected_400(self):
        """Images exceeding allowed dimensions are rejected with 400 Bad Request."""
        img = Image.new("RGB", (250, 250), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        uploaded = SimpleUploadedFile("huge.png", buf.getvalue(), content_type="image/png")
        response = self.client.post(
            self.endpoint,
            {"image": uploaded},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("dimensions", data["error"].lower())

    def test_billing_app_url_alias_also_works(self):
        """The app-level route /billing/api/qr/decode/ is also available."""
        img_bytes = self._generate_qr_image_bytes("https://example.com/alias-test")
        uploaded = SimpleUploadedFile("qr.png", img_bytes, content_type="image/png")

        response = self.client.post(
            "/billing/api/qr/decode/",
            {"image": uploaded},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["results"][0]["data"], "https://example.com/alias-test")
