import logging
import re
from decimal import Decimal

logger = logging.getLogger(__name__)
from django.shortcuts import render, redirect, get_object_or_404

from django.contrib import messages
from django.db.models import Q, Count, Sum, Value, IntegerField, ProtectedError, RestrictedError, F
from django.db.models.functions import Coalesce
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from .forms import CustomerForm, ProductForm, InvoiceForm, InvoiceItemFormSet
from .models import Customer, Product, Invoice, InvoiceItem
from .utils import (
    render_to_pdf,
    build_invoice_qr_payload,
    generate_invoice_qr_bytes,
    generate_invoice_qr_base64,
    calculate_invoice_totals,
    get_or_create_invoice_qr_url,
)




from accounts.models import DistributorProfile
from accounts.decorators import (
    is_distributor,
    is_admin,
    distributor_required,
    admin_or_distributor_required,
)


@admin_or_distributor_required
def customer_register_view(request):
    """
    Renders the modern frontend Customer Registration form for authenticated Distributors and Admins.
    """
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    return render(request, "billing/customer_register.html")



@admin_or_distributor_required
def add_customer(request):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    error = None

    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            try:
                customer = form.save(commit=False)
                customer.distributor = request.user
                customer.save()

                messages.success(request, "Customer added successfully.")
                if is_admin(request.user):
                    return redirect("customer_list")
                return redirect("distributor_dashboard")
            except Exception as e:
                error = "Unable to add customer right now. Please try again."
    else:
        form = CustomerForm()

    return render(
        request,
        "billing/add_customer.html",
        {
            "form": form,
            "error": error
        }
    )


@admin_or_distributor_required
def customer_list(request):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        return redirect("admin_customer_list")

    queryset = Customer.objects.filter(distributor=request.user).order_by("-id")
    total_count = queryset.count()

    query = request.GET.get("q", "").strip()

    if query:
        queryset = queryset.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(address__icontains=query) |
            Q(city__icontains=query) |
            Q(state__icontains=query) |
            Q(pincode__icontains=query)
        )

    filtered_count = queryset.count()

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "billing/customer_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "total_count": total_count,
            "filtered_count": filtered_count,
        }
    )


@admin_or_distributor_required
def customer_detail(request, pk):
    """
    Renders customer details and recent invoices.
    Enforces distributor ownership filtering: returns 404 if distributor does not own this customer.
    """
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        customer = get_object_or_404(Customer.objects.select_related("distributor"), pk=pk)
        invoices = Invoice.objects.filter(customer=customer).select_related("distributor").order_by("-invoice_date", "-id")[:10]
    else:
        customer = get_object_or_404(Customer, pk=pk, distributor=request.user)
        invoices = Invoice.objects.filter(customer=customer, distributor=request.user).order_by("-invoice_date", "-id")[:10]

    return render(
        request,
        "billing/customer_detail.html",
        {
            "customer": customer,
            "invoices": invoices,
        }
    )


@admin_or_distributor_required
def edit_customer(request, pk):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        customer = get_object_or_404(Customer, pk=pk)
    else:
        customer = get_object_or_404(Customer, pk=pk, distributor=request.user)
    error = None

    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Customer updated successfully.")
                return redirect("customer_list")
            except Exception as e:
                error = "Unable to update customer information right now. Please try again."
    else:
        form = CustomerForm(instance=customer)

    return render(
        request,
        "billing/edit_customer.html",
        {
            "form": form,
            "customer": customer,
            "error": error
        }
    )


@admin_or_distributor_required
def delete_customer(request, pk):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        customer = get_object_or_404(Customer, pk=pk)
    else:
        customer = get_object_or_404(Customer, pk=pk, distributor=request.user)

    if request.method == "POST":
        customer_name = customer.name
        try:
            customer.delete()
            messages.success(request, f'"{customer_name}" deleted successfully.')
        except (ProtectedError, RestrictedError):
            messages.error(request, f'"{customer_name}" cannot be deleted because it is used in existing billing records.')
        except Exception as e:
            messages.error(request, f'Unable to delete "{customer_name}" right now. Please try again.')
        return redirect("customer_list")

    return redirect("customer_list")



@admin_or_distributor_required
def add_product(request):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    error = None

    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            try:
                product = form.save(commit=False)
                product.distributor = request.user
                product.save()

                messages.success(request, "Product added successfully.")
                if is_admin(request.user):
                    return redirect("product_list")
                return redirect("distributor_dashboard")
            except Exception as e:
                error = "Unable to add product right now. Please try again."
    else:
        form = ProductForm()

    return render(
        request,
        "billing/add_product.html",
        {
            "form": form,
            "error": error
        }
    )


@admin_or_distributor_required
def product_list(request):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        return redirect("admin_product_list")

    queryset = Product.objects.filter(distributor=request.user).order_by("-id")
    total_count = queryset.count()

    query = request.GET.get("q", "").strip()

    if query:
        queryset = queryset.filter(
            Q(name__icontains=query) |
            Q(category__icontains=query) |
            Q(sku__icontains=query) |
            Q(description__icontains=query)
        )

    filtered_count = queryset.count()

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "billing/product_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "total_count": total_count,
            "filtered_count": filtered_count,
        }
    )


@admin_or_distributor_required
def edit_product(request, pk):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        product = get_object_or_404(Product, pk=pk)
    else:
        product = get_object_or_404(Product, pk=pk, distributor=request.user)
    error = None

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Product updated successfully.")
                return redirect("product_list")
            except Exception as e:
                error = "Unable to update product right now. Please try again."
    else:
        form = ProductForm(instance=product)

    return render(
        request,
        "billing/edit_product.html",
        {
            "form": form,
            "product": product,
            "error": error
        }
    )


@admin_or_distributor_required
def delete_product(request, pk):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        product = get_object_or_404(Product, pk=pk)
    else:
        product = get_object_or_404(Product, pk=pk, distributor=request.user)

    if request.method == "POST":
        product_name = product.name
        try:
            product.delete()
            messages.success(request, f'"{product_name}" deleted successfully.')
        except (ProtectedError, RestrictedError):
            messages.error(request, f'"{product_name}" cannot be deleted because it is used in existing billing records.')
        except Exception:
            messages.error(request, f'Unable to delete "{product_name}" right now. Please try again.')
        return redirect("product_list")

    return redirect("product_list")


def generate_unique_invoice_number(user):
    last_invoice = Invoice.objects.filter(distributor=user).order_by("-id").first()
    num = 1
    if last_invoice and last_invoice.invoice_number:
        parts = last_invoice.invoice_number.split("-")
        if len(parts) >= 2 and parts[-1].isdigit():
            num = int(parts[-1]) + 1
        else:
            num = Invoice.objects.filter(distributor=user).count() + 1
    else:
        num = Invoice.objects.filter(distributor=user).count() + 1

    inv_num = f"INV-{num:06d}"
    while Invoice.objects.filter(distributor=user, invoice_number=inv_num).exists():
        num += 1
        inv_num = f"INV-{num:06d}"
    return inv_num


@admin_or_distributor_required
def create_invoice(request):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        customers_count = Customer.objects.count()
        products_count = Product.objects.count()
    else:
        customers_count = Customer.objects.filter(distributor=request.user).count()
        products_count = Product.objects.filter(distributor=request.user).count()

    error = None

    if request.method == "POST":
        form = InvoiceForm(request.POST, user=request.user)
        formset = InvoiceItemFormSet(request.POST, user=request.user)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    customer = form.cleaned_data.get("customer")
                    if is_admin(request.user):
                        dist_user = customer.distributor if (customer and customer.distributor) else request.user
                    else:
                        if not customer or customer.distributor_id != request.user.id:
                            raise ValueError("Selected customer does not belong to your account.")
                        dist_user = request.user

                    form.instance.distributor = dist_user
                    form.instance.invoice_number = generate_unique_invoice_number(dist_user)
                    form.instance.subtotal = Decimal("0.00")
                    form.instance.total_gst = Decimal("0.00")
                    form.instance.grand_total = Decimal("0.00")

                    invoice = form.save(commit=False)
                    invoice.save()

                    subtotal = Decimal("0.00")
                    total_gst = Decimal("0.00")
                    valid_item_count = 0
                    seen_product_ids = set()

                    for item_form in formset:
                        if item_form.cleaned_data and not item_form.cleaned_data.get("DELETE", False):
                            form_product = item_form.cleaned_data.get("product")
                            quantity = item_form.cleaned_data.get("quantity")
                            discount_percent = item_form.cleaned_data.get("discount_percent")

                            if not form_product:
                                continue

                            try:
                                if is_admin(request.user):
                                    product = Product.objects.select_for_update().get(id=form_product.id)
                                else:
                                    product = Product.objects.select_for_update().get(
                                        id=form_product.id,
                                        distributor=request.user
                                    )
                            except Product.DoesNotExist:
                                raise ValueError("Invalid product selection.")

                            if product.id in seen_product_ids:
                                raise ValueError(f'Product "{product.name}" has been selected multiple times. Please update quantity in existing row.')
                            seen_product_ids.add(product.id)

                            if discount_percent is None:
                                discount_percent = Decimal("0.00")

                            if not quantity or quantity < 1:
                                raise ValueError("Quantity must be at least 1.")

                            if quantity > product.stock:
                                raise ValueError(f'Only {product.stock} units are available for "{product.name}".')

                            if discount_percent < Decimal("0.00") or discount_percent > Decimal("100.00"):
                                raise ValueError("Discount percentage must be between 0% and 100%.")

                            # Authoritative snapshot from DB product
                            unit_price = product.price
                            gst_rate = product.gst_rate
                            product_name = product.name

                            gross_amount = Decimal(quantity) * unit_price
                            discount_amount = (gross_amount * (discount_percent / Decimal("100.00"))).quantize(Decimal("0.01"))
                            taxable_amount = gross_amount - discount_amount
                            gst_amount = (taxable_amount * (gst_rate / Decimal("100.00"))).quantize(Decimal("0.01"))
                            line_total = taxable_amount + gst_amount

                            InvoiceItem.objects.create(
                                invoice=invoice,
                                product=product,
                                product_name=product_name,
                                quantity=quantity,
                                unit_price=unit_price,
                                gst_rate=gst_rate,
                                discount_percent=discount_percent,
                                taxable_amount=taxable_amount,
                                gst_amount=gst_amount,
                                line_total=line_total
                            )

                            product.stock -= quantity
                            product.save(update_fields=["stock"])

                            subtotal += taxable_amount
                            total_gst += gst_amount
                            valid_item_count += 1

                    if valid_item_count == 0:
                        raise ValueError("Please add at least one product item to the invoice.")

                    invoice.subtotal = subtotal
                    invoice.total_gst = total_gst
                    invoice.grand_total = subtotal + total_gst
                    invoice.save()

                    messages.success(request, f'Invoice "{invoice.invoice_number}" created successfully with QR code.')
                    return redirect("invoice_list")
            except Exception as e:
                error = str(e) if isinstance(e, ValueError) else "Unable to create invoice right now. Please check your input and try again."
        else:
            error = "Please correct errors in the invoice form."
    else:
        form = InvoiceForm(user=request.user)
        formset = InvoiceItemFormSet(user=request.user)

    if is_admin(request.user):
        user_products = Product.objects.all()
    else:
        user_products = Product.objects.filter(distributor=request.user)
    products_dict = {
        p.id: {
            "id": p.id,
            "name": p.name,
            "price": float(p.price),
            "gst_rate": float(p.gst_rate),
            "stock": p.stock,
            "sku": p.sku or ""
        }
        for p in user_products
    }

    return render(
        request,
        "billing/create_invoice.html",
        {
            "form": form,
            "formset": formset,
            "customers_count": customers_count,
            "products_count": products_count,
            "products_json": products_dict,
            "error": error
        }
    )


@admin_or_distributor_required
def product_detail(request, pk):
    """
    Renders product detail HTML view or returns JSON if requested via AJAX.
    Enforces distributor ownership filtering: returns 404 if distributor does not own this product.
    """
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        product = get_object_or_404(Product.objects.select_related("distributor"), pk=pk)
    else:
        product = get_object_or_404(Product, pk=pk, distributor=request.user)

    is_ajax = (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
        or request.GET.get("format") == "json"
    )
    if is_ajax:
        return JsonResponse({
            "id": product.id,
            "name": product.name,
            "category": product.category or "",
            "sku": product.sku or "",
            "price": str(product.price),
            "gst_rate": str(product.gst_rate),
            "stock": product.stock,
            "stock_quantity": product.stock,
            "unit": product.unit or "piece",
            "is_active": product.is_active,
            "description": product.description or "",
            "created_at": product.created_at.strftime("%b %d, %Y, %I:%M %p") if product.created_at else "",
        })

    return render(
        request,
        "billing/product_detail.html",
        {"product": product}
    )


@admin_or_distributor_required(return_403=True)
def product_details(request, pk):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return JsonResponse({"error": "Unauthorized"}, status=403)

    if is_admin(request.user):
        product = get_object_or_404(Product, pk=pk)
    else:
        product = get_object_or_404(Product, pk=pk, distributor=request.user)

    return JsonResponse({
        "id": product.id,
        "name": product.name,
        "category": product.category or "",
        "sku": product.sku or "",
        "price": str(product.price),
        "gst_rate": str(product.gst_rate),
        "stock": product.stock,
        "stock_quantity": product.stock,
        "unit": product.unit or "piece",
        "is_active": product.is_active,
        "description": product.description or "",
        "created_at": product.created_at.strftime("%b %d, %Y, %I:%M %p") if product.created_at else "",
    })


def _generate_invoice_pdf_response(request, pk, as_attachment=False):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        invoice = get_object_or_404(
            Invoice.objects.select_related("customer", "distributor").prefetch_related("items", "items__product"),
            pk=pk
        )
    else:
        invoice = get_object_or_404(
            Invoice.objects.select_related("customer", "distributor").prefetch_related("items", "items__product"),
            pk=pk,
            distributor=request.user
        )

    items = invoice.items.all()
    gross_total, total_discount = calculate_invoice_totals(items)
    dist_user = invoice.distributor or request.user
    distributor_profile = getattr(dist_user, "distributor_profile", None)
    if not distributor_profile:
        distributor_profile = DistributorProfile.objects.filter(user=dist_user).first()
    qr_uri = generate_invoice_qr_base64(invoice)
    if not qr_uri and getattr(invoice, "qr_code", None) and invoice.qr_code.name:
        try:
            if invoice.qr_code.storage.exists(invoice.qr_code.name):
                qr_uri = invoice.qr_code.url
        except Exception as e:
            logger.warning(f"Failed to access saved QR image fallback for invoice {invoice.pk}: {e}")

    context = {
        "invoice": invoice,
        "items": items,
        "customer": invoice.customer,
        "distributor": dist_user,
        "profile": distributor_profile,
        "gross_total": gross_total,
        "total_discount": total_discount,
        "qr_code": qr_uri,
        "qr_code_url": qr_uri,
        "payment_status": getattr(invoice, "payment_status", "Paid"),
        "due_date": getattr(invoice, "due_date", None),
    }

    try:
        pdf_bytes = render_to_pdf("billing/invoice_pdf.html", context)
    except Exception as e:
        logger.error(f"Unexpected error rendering PDF invoice {invoice.pk}: {e}", exc_info=True)
        pdf_bytes = None

    if not pdf_bytes:
        logger.error(f"Unable to generate PDF invoice for invoice {invoice.pk} (user={request.user.pk})")
        is_ajax = (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            or "application/json" in request.headers.get("Accept", "")
            or request.GET.get("format") == "json"
        )
        if is_ajax:
            return JsonResponse({"error": "Unable to download invoice PDF. Please try again."}, status=500)
        return HttpResponse("Unable to download invoice PDF. Please try again.", status=500, content_type="text/plain; charset=utf-8")

    raw_num = str(invoice.invoice_number or invoice.pk or "doc")
    safe_inv_num = re.sub(r'[^A-Za-z0-9_\-]', '', raw_num) or str(invoice.pk)
    disposition_type = "attachment" if as_attachment else "inline"

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'{disposition_type}; filename="Invoice-{safe_inv_num}.pdf"'
    return response


@admin_or_distributor_required
def invoice_pdf_view(request, pk):
    as_attachment = (request.GET.get("download") == "1")
    return _generate_invoice_pdf_response(request, pk, as_attachment=as_attachment)


@admin_or_distributor_required
def invoice_pdf_download(request, pk):
    """
    Dedicated view for downloading the Invoice PDF with Content-Disposition: attachment.
    """
    return _generate_invoice_pdf_response(request, pk, as_attachment=True)


@admin_or_distributor_required
def invoice_detail(request, pk):
    """
    Invoice Detail / View page displaying full invoice details, items, customer info,
    and a prominent 'Download PDF' button.
    """
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        invoice = get_object_or_404(
            Invoice.objects.select_related("customer", "distributor").prefetch_related("items", "items__product"),
            pk=pk
        )
    else:
        invoice = get_object_or_404(
            Invoice.objects.select_related("customer", "distributor").prefetch_related("items", "items__product"),
            pk=pk,
            distributor=request.user
        )

    items = invoice.items.all()
    gross_total, total_discount = calculate_invoice_totals(items)
    dist_user = invoice.distributor or request.user
    distributor_profile = getattr(dist_user, "distributor_profile", None)
    qr_code_url = get_or_create_invoice_qr_url(invoice)
    qr_payload = build_invoice_qr_payload(invoice)

    return render(
        request,
        "billing/invoice_detail.html",
        {
            "invoice": invoice,
            "items": items,
            "customer": invoice.customer,
            "distributor": dist_user,
            "profile": distributor_profile,
            "gross_total": gross_total,
            "total_discount": total_discount,
            "qr_code": qr_code_url,
            "qr_code_url": qr_code_url,
            "qr_payload": qr_payload,
        }
    )


@admin_or_distributor_required
def invoice_edit(request, pk):
    """
    Invoice edit view.
    Enforces distributor ownership filtering: returns 404 if distributor does not own this invoice.
    Invoices with verified cryptographic QR codes are protected audit records.
    """
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        invoice = get_object_or_404(Invoice, pk=pk)
    else:
        invoice = get_object_or_404(Invoice, pk=pk, distributor=request.user)

    messages.info(request, f'Invoice "{invoice.invoice_number}" is a tax-compliant record with embedded QR code verification.')
    return redirect("invoice_detail", pk=invoice.pk)


@admin_or_distributor_required
def invoice_delete(request, pk):
    """
    Allows deleting an invoice.
    Enforces distributor ownership filtering: returns 404 if distributor does not own this invoice.
    """
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        invoice = get_object_or_404(Invoice, pk=pk)
    else:
        invoice = get_object_or_404(Invoice, pk=pk, distributor=request.user)

    if request.method == "POST":
        inv_num = invoice.invoice_number
        try:
            with transaction.atomic():
                for item in invoice.items.select_related("product"):
                    if item.product:
                        Product.objects.filter(pk=item.product.pk).update(stock=F("stock") + item.quantity)
                invoice.delete()
            messages.success(request, f'Invoice "{inv_num}" deleted successfully.')
        except Exception as e:
            logger.error(f"Error deleting invoice {pk}: {e}")
            messages.error(request, f'Unable to delete invoice "{inv_num}".')
        return redirect("invoice_list")

    return render(
        request,
        "billing/invoice_confirm_delete.html",
        {"invoice": invoice}
    )


@admin_or_distributor_required
def invoice_preview_view(request, pk):
    """
    Dedicated preview page for an invoice.
    Retrieves the invoice using select_related('customer', 'distributor')
    and prefetch_related('items', 'items__product').
    Reuses the saved QR image from media storage without regenerating.
    Returns 404 for non-existent or unauthorized invoices.
    """
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        invoice = get_object_or_404(
            Invoice.objects.select_related("customer", "distributor").prefetch_related("items", "items__product"),
            pk=pk
        )
    else:
        invoice = get_object_or_404(
            Invoice.objects.select_related("customer", "distributor").prefetch_related("items", "items__product"),
            pk=pk,
            distributor=request.user
        )

    items = invoice.items.all()
    gross_total, total_discount = calculate_invoice_totals(items)
    dist_user = invoice.distributor or request.user
    distributor_profile = getattr(dist_user, "distributor_profile", None)
    qr_code_url = get_or_create_invoice_qr_url(invoice)
    qr_payload = build_invoice_qr_payload(invoice)

    return render(
        request,
        "billing/invoice_preview.html",
        {
            "invoice": invoice,
            "items": items,
            "customer": invoice.customer,
            "distributor": dist_user,
            "profile": distributor_profile,
            "gross_total": gross_total,
            "total_discount": total_discount,
            "qr_code_url": qr_code_url,
            "qr_code": qr_code_url,
            "qr_payload": qr_payload,
        }
    )



@admin_or_distributor_required
def invoice_list(request):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        return redirect("admin_invoice_list")

    from django.db.models import Count
    queryset = Invoice.objects.filter(
        distributor=request.user
    ).select_related(
        "customer"
    ).prefetch_related(
        "items"
    ).annotate(
        item_count=Count("items", distinct=True),
        total_quantity=Coalesce(Sum("items__quantity"), Value(0), output_field=IntegerField()),
        total_item_qty=Coalesce(Sum("items__quantity"), Value(0), output_field=IntegerField())
    ).order_by("-created_at")

    total_count = queryset.count()
    query = request.GET.get("q", "").strip()

    if query:
        queryset = queryset.filter(
            Q(invoice_number__icontains=query) |
            Q(customer__name__icontains=query) |
            Q(customer__email__icontains=query)
        )

    filtered_count = queryset.count()

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "billing/invoice_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "total_count": total_count,
            "filtered_count": filtered_count,
        }
    )


@admin_or_distributor_required
def invoice_qr_view(request, pk):
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        invoice = get_object_or_404(
            Invoice.objects.select_related("customer").prefetch_related("items"),
            pk=pk
        )
    else:
        invoice = get_object_or_404(
            Invoice.objects.select_related("customer").prefetch_related("items"),
            pk=pk,
            distributor=request.user
        )

    if request.GET.get("format") == "json":
        payload = build_invoice_qr_payload(invoice)
        base64_qr = generate_invoice_qr_base64(invoice)
        return JsonResponse({
            "success": True,
            "payload": payload,
            "qr_code": base64_qr
        })

    if invoice.qr_code and invoice.qr_code.name and invoice.qr_code.storage.exists(invoice.qr_code.name):
        try:
            with invoice.qr_code.open("rb") as f:
                png_bytes = f.read()
            response = HttpResponse(png_bytes, content_type="image/png")
            response["Content-Disposition"] = f'inline; filename="Invoice_{invoice.invoice_number}_QR.png"'
            return response
        except Exception:
            pass

    png_bytes = generate_invoice_qr_bytes(invoice)
    response = HttpResponse(png_bytes, content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="Invoice_{invoice.invoice_number}_QR.png"'
    return response


@admin_or_distributor_required
def qr_decoder_view(request):
    """
    Renders the modern QR Code Decoder & Invoice Inspection interface.
    Allows distributors and admins to upload/scan invoice QR codes,
    decoding their payloads and displaying rich database-verified invoice details.
    """
    if not (is_distributor(request.user) or is_admin(request.user)):
        return redirect("distributor_login")

    if is_admin(request.user):
        return redirect("admin_qr_decoder")

    return render(
        request,
        "billing/qr_decoder.html",
        {
            "distributor": request.user,
            "profile": getattr(request.user, "distributor_profile", None),
        }
    )




