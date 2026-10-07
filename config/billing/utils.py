import os
import logging
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
