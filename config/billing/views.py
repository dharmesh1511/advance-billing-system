from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Value, IntegerField, ProtectedError, RestrictedError
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
    generate_invoice_qr_base64
)




def is_distributor(user):
    return user.groups.filter(name="Distributor").exists()


@login_required(login_url="/distributor/login/")
def add_customer(request):
    if not is_distributor(request.user):
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


@login_required(login_url="/distributor/login/")
def customer_list(request):
    if not is_distributor(request.user):
        return redirect("distributor_login")

    queryset = Customer.objects.filter(distributor=request.user)
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


@login_required(login_url="/distributor/login/")
def edit_customer(request, pk):
    if not is_distributor(request.user):
        return redirect("distributor_login")

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


@login_required(login_url="/distributor/login/")
def delete_customer(request, pk):
    if not is_distributor(request.user):
        return redirect("distributor_login")

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



@login_required(login_url="/distributor/login/")
def add_product(request):
    if not is_distributor(request.user):
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


@login_required(login_url="/distributor/login/")
def product_list(request):
    if not is_distributor(request.user):
        return redirect("distributor_login")

    queryset = Product.objects.filter(distributor=request.user)
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


@login_required(login_url="/distributor/login/")
def edit_product(request, pk):
    if not is_distributor(request.user):
        return redirect("distributor_login")

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


@login_required(login_url="/distributor/login/")
def delete_product(request, pk):
    if not is_distributor(request.user):
        return redirect("distributor_login")

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


@login_required(login_url="/distributor/login/")
def create_invoice(request):
    if not is_distributor(request.user):
        return redirect("distributor_login")

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
                    if not customer or customer.distributor != request.user:
                        raise ValueError("Selected customer does not belong to your account.")

                    invoice = form.save(commit=False)
                    invoice.distributor = request.user
                    invoice.invoice_number = generate_unique_invoice_number(request.user)
                    invoice.subtotal = Decimal("0.00")
                    invoice.total_gst = Decimal("0.00")
                    invoice.grand_total = Decimal("0.00")
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


@login_required(login_url="/distributor/login/")
def product_details(request, pk):
    if not is_distributor(request.user):
        return JsonResponse({"error": "Unauthorized"}, status=403)

    product = get_object_or_404(Product, pk=pk, distributor=request.user)

    return JsonResponse({
        "id": product.id,
        "name": product.name,
        "category": product.category or "",
        "sku": product.sku or "",
        "price": str(product.price),
        "gst_rate": str(product.gst_rate),
        "stock": product.stock,
    })


@login_required(login_url="/distributor/login/")
def invoice_pdf_view(request, pk):
    if not is_distributor(request.user):
        return redirect("distributor_login")

    invoice = get_object_or_404(
        Invoice.objects.select_related("customer", "distributor").prefetch_related("items", "items__product"),
        pk=pk,
        distributor=request.user
    )

    items = invoice.items.all()
    gross_total = Decimal("0.00")
    total_discount = Decimal("0.00")

    for item in items:
        line_gross = Decimal(item.quantity) * item.unit_price
        gross_total += line_gross
        total_discount += (line_gross - item.taxable_amount)

    distributor_profile = getattr(request.user, "distributor_profile", None)

    context = {
        "invoice": invoice,
        "items": items,
        "customer": invoice.customer,
        "distributor": request.user,
        "profile": distributor_profile,
        "gross_total": gross_total,
        "total_discount": total_discount,
        "qr_code_url": generate_invoice_qr_base64(invoice),
    }

    pdf_bytes = render_to_pdf("billing/invoice_pdf.html", context)
    if not pdf_bytes:
        messages.error(request, "Unable to generate PDF invoice at this time.")
        return redirect("distributor_dashboard")

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="Invoice_{invoice.invoice_number}.pdf"'
    return response


@login_required(login_url="/distributor/login/")
def invoice_list(request):
    if not is_distributor(request.user):
        return redirect("distributor_login")

    queryset = Invoice.objects.filter(
        distributor=request.user
    ).select_related(
        "customer"
    ).prefetch_related(
        "items"
    ).annotate(
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


@login_required(login_url="/distributor/login/")
def invoice_qr_view(request, pk):
    if not is_distributor(request.user):
        return redirect("distributor_login")

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

    png_bytes = generate_invoice_qr_bytes(invoice)
    response = HttpResponse(png_bytes, content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="Invoice_{invoice.invoice_number}_QR.png"'
    return response



