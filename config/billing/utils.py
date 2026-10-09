import os
import logging
import json
import base64
from io import BytesIO
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
