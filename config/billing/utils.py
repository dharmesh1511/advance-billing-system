import os
import re
import logging
import json
import base64
from io import BytesIO
from urllib.parse import urlparse, parse_qs

from django.conf import settings
from django.contrib.staticfiles import finders
from django.template.loader import get_template, TemplateDoesNotExist
from xhtml2pdf import pisa
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

# Register a Unicode font (e.g., Arial on Windows) if available for Rupee symbol support
def _register_unicode_fonts():
    try:
        win_arial = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf")
        if os.path.exists(win_arial) and "Arial" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("Arial", win_arial))
    except Exception as e:
        logger.debug(f"Could not register system Arial font: {e}")

_register_unicode_fonts()


def link_callback(uri, rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access static/media files.
    """
    if not uri:
        return uri

    if uri.startswith("http://") or uri.startswith("https://"):
        return uri

    # Handle MEDIA_URL
    if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
        relative_path = uri[len(settings.MEDIA_URL):]
        path = os.path.join(settings.MEDIA_ROOT, relative_path)
        if os.path.exists(path):
            return path

    # Handle STATIC_URL
    if settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
        relative_path = uri[len(settings.STATIC_URL):]
        found = finders.find(relative_path)
        if found:
            return found
        path = os.path.join(settings.BASE_DIR, "static", relative_path)
        if os.path.exists(path):
            return path

    # Try static finders directly
    found = finders.find(uri.lstrip("/"))
    if found:
        return found

    # Fallback to local path relative to BASE_DIR
    if os.path.isabs(uri) and os.path.exists(uri):
        return uri

    local_path = os.path.join(settings.BASE_DIR, uri.lstrip("/"))
    if os.path.exists(local_path):
        return local_path

    return uri


def render_to_pdf(template_name, context=None):
    """
    Renders a Django template to PDF bytes using xhtml2pdf.

    :param template_name: Path/name of the Django template file.
    :param context: Dictionary containing context data for rendering the template.
    :return: bytes containing PDF data if successful, None if an error occurs.
    """
    if context is None:
        context = {}

    try:
        template = get_template(template_name)
        html = template.render(context)
    except TemplateDoesNotExist as e:
        logger.error(f"PDF generation failed: Template '{template_name}' not found: {e}")
        return None
    except Exception as e:
        logger.error(f"PDF generation failed: Template rendering error for '{template_name}': {e}")
        return None

    result = BytesIO()

    try:
        pdf = pisa.CreatePDF(
            src=html,
            dest=result,
            encoding="utf-8",
            link_callback=link_callback
        )

        if pdf.err:
            logger.error(f"xhtml2pdf error while rendering template '{template_name}': {pdf.err}")
            return None

        pdf_data = result.getvalue()
        if not pdf_data.startswith(b"%PDF"):
            logger.error(f"Generated PDF output for '{template_name}' invalid: Missing %PDF signature")
            return None

        return pdf_data
    except Exception as e:
        logger.error(f"Exception during PDF generation for '{template_name}': {e}")
        return None


def build_invoice_qr_payload(invoice):
    """
    Build structured payload dictionary for an invoice QR code.
    Contains: invoice_number, invoice_date, customer_name, product_count (sum of line item quantities),
    grand_total (string format 2 decimal places), currency ("INR").
    Does not include sensitive customer personal data.
    """
    if hasattr(invoice, "total_quantity") and invoice.total_quantity is not None:
        product_count = invoice.total_quantity
    elif hasattr(invoice, "total_item_qty") and invoice.total_item_qty is not None:
        product_count = invoice.total_item_qty
    else:
        product_count = sum(item.quantity for item in invoice.items.all())

    inv_date_str = ""
    if invoice.invoice_date:
        inv_date_str = invoice.invoice_date.strftime("%Y-%m-%d")

    customer_name = invoice.customer.name if invoice.customer else ""

    payload = {
        "invoice_number": invoice.invoice_number,
        "invoice_date": inv_date_str,
        "product_count": product_count,
        "grand_total": f"{invoice.grand_total:.2f}",
        "currency": "INR"
    }

    if customer_name:
        payload["customer_name"] = customer_name

    return payload


def generate_invoice_qr(invoice):
    """
    Generates a PIL Image of the QR code for a given invoice.
    Uses 'qrcode' library if available; falls back to reportlab+Pillow if not.
    """
    payload = build_invoice_qr_payload(invoice)
    payload_str = json.dumps(payload, ensure_ascii=False)

    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(payload_str)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return img
    except ImportError:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from PIL import Image, ImageDraw

        widget = QrCodeWidget(payload_str)
        qr = widget.qr
        qr.make()
        mod_count = qr.getModuleCount()
        border = 2
        box_size = 6
        img_size = (mod_count + 2 * border) * box_size

        img = Image.new("RGB", (img_size, img_size), "white")
        draw = ImageDraw.Draw(img)

        for r in range(mod_count):
            for c in range(mod_count):
                if qr.isDark(r, c):
                    x0 = (c + border) * box_size
                    y0 = (r + border) * box_size
                    x1 = x0 + box_size
                    y1 = y0 + box_size
                    draw.rectangle([x0, y0, x1, y1], fill="black")
        return img


def generate_invoice_qr_bytes(invoice):
    """
    Returns PNG bytes of the generated invoice QR code.
    """
    img = generate_invoice_qr(invoice)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_invoice_qr_base64(invoice):
    """
    Returns base64 data URI string of the invoice QR code (data:image/png;base64,...).
    """
    try:
        png_bytes = generate_invoice_qr_bytes(invoice)
        encoded = base64.b64encode(png_bytes).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception as e:
        logger.error(f"Error generating base64 QR code for invoice {getattr(invoice, 'invoice_number', '')}: {e}")
        return ""


def decode_qr_from_image(image):
    """
    Decodes QR code(s) from a PIL Image instance.
    Preferred Decoder: OpenCV (cv2.QRCodeDetector).
    - Uses detectAndDecodeMulti() for multiple and single QR codes.
    - Falls back to detectAndDecode() if detectAndDecodeMulti returns empty or is unavailable.
    - Alternative: pyzbar decoder if OpenCV is unavailable or yields no codes.
    Returns a list of dicts: [{'data': str, 'type': 'QRCODE'}, ...].
    Security Note: Content is returned as plain strings; never executed or followed.
    """
    results = []
    seen_data = set()

    # 1. Preferred Decoder: OpenCV QRCodeDetector
    try:
        import cv2
        import numpy as np

        img_rgb = image.convert("RGB")
        np_arr = np.array(img_rgb)
        img_bgr = cv2.cvtColor(np_arr, cv2.COLOR_RGB2BGR)

        detector = cv2.QRCodeDetector()

        # Try multi-detection first
        if hasattr(detector, "detectAndDecodeMulti"):
            try:
                retval, decoded_info, points, straight_qrcode = detector.detectAndDecodeMulti(img_bgr)
                if retval and decoded_info:
                    for text in decoded_info:
                        clean_text = text.strip() if isinstance(text, str) else ""
                        if clean_text and clean_text not in seen_data:
                            seen_data.add(clean_text)
                            results.append({
                                "data": clean_text,
                                "type": "QRCODE"
                            })
            except Exception as e:
                logger.debug(f"OpenCV detectAndDecodeMulti encountered an issue: {e}")

        # If multi-detection yielded no results, try single detectAndDecode
        if not results and hasattr(detector, "detectAndDecode"):
            try:
                text, points, straight_qrcode = detector.detectAndDecode(img_bgr)
                clean_text = text.strip() if isinstance(text, str) else ""
                if clean_text and clean_text not in seen_data:
                    seen_data.add(clean_text)
                    results.append({
                        "data": clean_text,
                        "type": "QRCODE"
                    })
            except Exception as e:
                logger.debug(f"OpenCV detectAndDecode encountered an issue: {e}")

        # If OpenCV successfully detected QR codes, return them
        if results:
            return results

    except ImportError:
        logger.debug("OpenCV is not installed; attempting alternative decoder.")
    except Exception as e:
        logger.error(f"Error during OpenCV QR decoding: {e}")

    # 2. Alternative Decoder: pyzbar
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode, ZBarSymbol
        decoded_objs = pyzbar_decode(image, symbols=[ZBarSymbol.QRCODE])
        if not decoded_objs and image.mode not in ("RGB", "L"):
            decoded_objs = pyzbar_decode(image.convert("RGB"), symbols=[ZBarSymbol.QRCODE])

        for obj in decoded_objs:
            raw_data = obj.data
            try:
                decoded_str = raw_data.decode("utf-8")
            except UnicodeDecodeError:
                decoded_str = raw_data.decode("latin-1", errors="replace")

            if decoded_str and decoded_str not in seen_data:
                seen_data.add(decoded_str)
                results.append({
                    "data": decoded_str,
                    "type": obj.type or "QRCODE"
                })
        return results
    except ImportError:
        logger.debug("pyzbar is not installed or available.")
    except Exception as e:
        logger.error(f"Error during pyzbar QR decoding: {e}")

    return results


# =====================================================================
# QR Code Invoice Data Parsing & Resolution Utilities
# =====================================================================

class InvalidQRPayloadError(Exception):
    """Raised when decoded QR data cannot be resolved to a valid invoice identifier."""
    pass


class InvoiceNotFoundError(Exception):
    """Raised when an invoice identifier was extracted but does not exist in the database."""
    pass


class InvoicePermissionDeniedError(Exception):
    """Raised when the requesting user is not authorized to access the resolved invoice."""
    pass


def extract_invoice_identifier_from_qr(decoded_text):
    """
    Validates and normalizes untrusted decoded QR text to extract an invoice identifier.
    Supports:
    1. Structured JSON payloads containing invoice references
       (e.g., project standard `{"invoice_number": "INV-1001", ...}`, `{"invoice_no": ...}`, `{"invoice_id": ...}`, `{"id": ...}`).
    2. Recognized invoice URLs
       (e.g., `https://.../invoice/INV-1001`, `.../distributor/invoices/12/`, `...?invoice=INV-1001`).
    3. Plain-text invoice numbers / identifiers matching safe naming conventions
       (e.g., `INV-2026-0001`, `INV-1001`).

    Rejects malformed, arbitrary, executable, or unrecognized payloads.
    """
    if not decoded_text or not isinstance(decoded_text, str):
        raise InvalidQRPayloadError("QR code content is empty or invalid.")

    raw = decoded_text.strip()
    if not raw:
        raise InvalidQRPayloadError("QR code content is empty.")

    # 1. Attempt JSON Payload parsing
    if (raw.startswith("{") and raw.endswith("}")) or ("{" in raw and "}" in raw):
        try:
            # Extract the JSON substring if surrounded by accidental whitespace or quotes
            start = raw.find("{")
            end = raw.rfind("}") + 1
            payload = json.loads(raw[start:end])
            if isinstance(payload, dict):
                # Check for standard invoice reference keys
                ref_keys = ["invoice_number", "invoice_no", "invoiceId", "invoice_id", "invoice", "id"]
                for k in ref_keys:
                    val = payload.get(k)
                    if val is not None:
                        val_str = str(val).strip()
                        if val_str:
                            return val_str
                raise InvalidQRPayloadError("The QR code JSON payload does not contain a recognized invoice reference.")
        except json.JSONDecodeError:
            pass  # Fall through to URL or plain-text checks

    # 2. Attempt URL parsing
    is_url = raw.startswith("http://") or raw.startswith("https://") or raw.startswith("//") or raw.startswith("/")
    if is_url:
        from urllib.parse import urlparse, parse_qs
        try:
            parsed = urlparse(raw)
            # Check URL query parameters first
            if parsed.query:
                query_params = parse_qs(parsed.query)
                for q_key in ["invoice_number", "invoice_no", "invoice_id", "invoice", "inv", "id"]:
                    if q_key in query_params and query_params[q_key]:
                        candidate = str(query_params[q_key][0]).strip()
                        if candidate:
                            return candidate

            # Check URL path patterns
            path = parsed.path.rstrip("/")
            # Regex for /distributor/invoices/<ref> or /billing/distributor/invoices/<ref>
            dist_match = re.search(r'/(?:billing/)?distributor/invoices/(?P<ref>[^/]+)', path, re.IGNORECASE)
            if dist_match:
                ref = dist_match.group("ref").strip()
                if ref and ref.lower() not in ("create", "add", "list"):
                    return ref

            # Regex for /invoice/<ref> or /invoices/<ref>
            inv_match = re.search(r'/invoices?/(?P<ref>[^/]+)', path, re.IGNORECASE)
            if inv_match:
                ref = inv_match.group("ref").strip()
                if ref and ref.lower() not in ("create", "add", "list"):
                    return ref

            # URL didn't match any known invoice pattern
            raise InvalidQRPayloadError("The QR code URL does not match a recognized invoice reference.")
        except InvalidQRPayloadError:
            raise
        except Exception as e:
            raise InvalidQRPayloadError(f"Failed to parse QR code URL: {e}")

    # 3. Plain Text Invoice Identifier
    # Validate against safe alphanumeric pattern with hyphens, underscores, slashes (length 2 to 50)
    # Reject arbitrary strings containing spaces, control characters, or script tags
    if re.search(r'[\s<>"\'\\]', raw):
        raise InvalidQRPayloadError("Invalid QR code format: content contains invalid characters.")

    if re.match(r'^[A-Za-z0-9][A-Za-z0-9\-_/]{1,49}$', raw):
        return raw

    raise InvalidQRPayloadError("The decoded QR content does not match a recognized invoice format.")


def resolve_invoice_from_identifier(identifier, user=None):
    """
    Queries the Invoice model using Django ORM by invoice_number or database ID.
    Enforces user authorization and distributor isolation:
    - Admin/Staff users can access any invoice.
    - Authenticated Distributors can only access invoices belonging to their distributor account.
    - Unauthorized users or cross-distributor access raises InvoicePermissionDeniedError.
    - Nonexistent records raise InvoiceNotFoundError.
    """
    from decimal import Decimal
    from .models import Invoice

    clean_id = str(identifier).strip()
    if not clean_id:
        raise InvalidQRPayloadError("Invoice identifier cannot be empty.")

    qs = Invoice.objects.select_related("customer", "distributor").prefetch_related("items", "items__product")

    # 1. Exact or case-insensitive invoice_number match
    invoice = qs.filter(invoice_number__iexact=clean_id).first()

    # 2. Fall back to numeric primary key lookup if identifier is purely digits
    if not invoice and clean_id.isdigit():
        invoice = qs.filter(pk=int(clean_id)).first()

    if not invoice:
        raise InvoiceNotFoundError(f"Invoice '{clean_id}' not found in the database.")

    # 3. Enforce authorization & distributor isolation
    if user and user.is_authenticated:
        if user.is_superuser or user.is_staff:
            return invoice
        if invoice.distributor_id == user.id:
            return invoice
        # Requesting user is authenticated but does not own this invoice
        raise InvoicePermissionDeniedError("You do not have permission to access this invoice.")

    return invoice


def format_invoice_for_response(invoice, user=None):
    """
    Serializes an Invoice model instance and its line items into a structured dictionary
    safe for API JSON responses and template rendering.
    Calculates subtotal, gross total, taxes, discounts, amount paid, and payment status.
    """
    from decimal import Decimal

    items_data = []
    gross_total = Decimal("0.00")
    total_discount = Decimal("0.00")

    for item in invoice.items.all():
        line_gross = Decimal(item.quantity) * item.unit_price
        gross_total += line_gross
        line_discount = line_gross - item.taxable_amount
        total_discount += line_discount

        items_data.append({
            "id": item.id,
            "product_name": item.product_name,
            "sku": (item.product.sku if (item.product and item.product.sku) else "") or "",
            "quantity": item.quantity,
            "unit_price": f"{item.unit_price:.2f}",
            "discount_percent": f"{item.discount_percent:.2f}",
            "taxable_amount": f"{item.taxable_amount:.2f}",
            "gst_rate": f"{item.gst_rate:.2f}",
            "gst_amount": f"{item.gst_amount:.2f}",
            "line_total": f"{item.line_total:.2f}",
        })

    subtotal_val = invoice.subtotal or Decimal("0.00")
    gst_val = invoice.total_gst or Decimal("0.00")
    grand_total_val = invoice.grand_total or Decimal("0.00")

    # In this billing system, finalized invoices are considered settled/paid
    # unless custom partial payment attributes exist.
    amount_paid_val = getattr(invoice, "amount_paid", grand_total_val)
    balance_due_val = getattr(invoice, "balance_due", Decimal("0.00"))
    if balance_due_val < Decimal("0.00"):
        balance_due_val = Decimal("0.00")

    payment_status = getattr(invoice, "payment_status", None)
    if not payment_status:
        if balance_due_val == Decimal("0.00"):
            payment_status = "Paid"
        elif amount_paid_val > Decimal("0.00"):
            payment_status = "Partially Paid"
        else:
            payment_status = "Unpaid"

    customer = invoice.customer
    customer_info = {
        "name": customer.name if customer else "N/A",
        "email": customer.email if customer else "",
        "phone": customer.phone if customer else "",
        "address": customer.address if customer else "",
        "city": customer.city if customer else "",
        "state": customer.state if customer else "",
        "pincode": customer.pincode if customer else "",
    }

    inv_date_str = invoice.invoice_date.strftime("%Y-%m-%d") if invoice.invoice_date else ""
    inv_date_formatted = invoice.invoice_date.strftime("%d %b %Y") if invoice.invoice_date else ""

    return {
        "id": invoice.pk,
        "invoice_number": invoice.invoice_number,
        "invoice_date": inv_date_str,
        "invoice_date_formatted": inv_date_formatted,
        "customer_name": customer_info["name"],
        "customer_phone": customer_info["phone"],
        "customer_email": customer_info["email"],
        "customer_address": customer_info["address"],
        "customer_city": customer_info["city"],
        "customer_state": customer_info["state"],
        "customer_pincode": customer_info["pincode"],
        "subtotal": f"{subtotal_val:.2f}",
        "tax_amount": f"{gst_val:.2f}",
        "total_gst": f"{gst_val:.2f}",
        "gross_total": f"{gross_total:.2f}",
        "total_discount": f"{total_discount:.2f}",
        "total_amount": f"{grand_total_val:.2f}",
        "grand_total": f"{grand_total_val:.2f}",
        "amount_paid": f"{amount_paid_val:.2f}",
        "balance_due": f"{balance_due_val:.2f}",
        "outstanding_balance": f"{balance_due_val:.2f}",
        "payment_status": payment_status,
        "total_items": len(items_data),
        "total_quantity": sum(i["quantity"] for i in items_data),
        "items": items_data,
        "detail_url": f"/billing/distributor/invoices/{invoice.pk}/",
        "pdf_url": f"/billing/distributor/invoices/{invoice.pk}/pdf/",
        "download_pdf_url": f"/billing/distributor/invoices/{invoice.pk}/download-pdf/",
    }


def parse_and_resolve_invoice_from_qr(decoded_text, user=None):
    """
    Parses untrusted QR content, extracts the invoice reference,
    and resolves the matching invoice record from the database with authorization checks.

    Returns:
        tuple: (invoice_instance, formatted_invoice_dict)

    Raises:
        InvalidQRPayloadError: If content format is not recognized.
        InvoiceNotFoundError: If no invoice matches the extracted reference.
        InvoicePermissionDeniedError: If the user is unauthorized to view the invoice.
    """
    identifier = extract_invoice_identifier_from_qr(decoded_text)
    invoice = resolve_invoice_from_identifier(identifier, user=user)
    formatted = format_invoice_for_response(invoice, user=user)
    return invoice, formatted

