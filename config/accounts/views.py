import csv
import json
import secrets
from decimal import Decimal
from datetime import datetime, date, timedelta
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum, Count, Avg, F, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import OTPVerification, DistributorProfile
from .forms import DistributorRegistrationForm, DistributorProfileUpdateForm
from billing.models import Customer, Product, Invoice, InvoiceItem


def is_distributor(user):
    return user.groups.filter(name="Distributor").exists()


# =========================
# ADMIN LOGIN
# =========================

def admin_login(request):

    # Already logged-in admin
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("admin_dashboard")

        if is_distributor(request.user):
            return redirect("distributor_dashboard")

    error = None

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            error = "Username and password are required."

        else:
            user = authenticate(
                request,
                username=username,
                password=password
            )

            if user is not None:

                # Only staff users can access Admin
                if user.is_staff:
                    login(request, user)

                    return redirect("admin_dashboard")

                error = "You are not authorized to login as Admin."

            else:
                error = "Invalid username or password."

    return render(
        request,
        "accounts/admin_login.html",
        {
            "error": error
        }
    )


# =========================
# DISTRIBUTOR LOGIN
# =========================

def distributor_login(request):

    # Already logged-in distributor
    if request.user.is_authenticated:
        if is_distributor(request.user):
            return redirect("distributor_dashboard")

        if request.user.is_staff:
            return redirect("admin_dashboard")

    error = None

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            error = "Username and password are required."

        else:
            user = authenticate(
                request,
                username=username,
                password=password
            )

            if user is not None:

                # Only Distributor group users can access Distributor
                if is_distributor(user):
                    login(request, user)

                    return redirect("distributor_dashboard")

                error = "You are not authorized to login as Distributor."

            else:
                error = "Invalid username or password."

    return render(
        request,
        "accounts/distributor_login.html",
        {
            "error": error
        }
    )


# =========================
# DISTRIBUTOR REGISTRATION
# =========================

def distributor_register(request):
    if request.user.is_authenticated:
        if is_distributor(request.user):
            return redirect("distributor_dashboard")

    error = None
    form = DistributorRegistrationForm()

    if request.method == "POST":
        form = DistributorRegistrationForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data.get("full_name", "").strip()
            email = form.cleaned_data.get("email", "").strip()
            phone = form.cleaned_data.get("phone", "").strip()
            password = form.cleaned_data.get("password", "")

            try:
                with transaction.atomic():
                    name_parts = full_name.split(" ", 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ""

                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name
                    )

                    distributor_group, _ = Group.objects.get_or_create(name="Distributor")
                    user.groups.add(distributor_group)

                    # Save profile details in DistributorProfile model
                    DistributorProfile.objects.create(
                        user=user,
                        full_name=full_name,
                        email=email,
                        phone=phone
                    )

                messages.success(
                    request,
                    "Distributor account created successfully. Please login."
                )
                return redirect("distributor_login")
            except Exception as e:
                error = "Unable to create your account right now. Please try again."
        else:
            for field, errors in form.errors.items():
                error = errors[0]
                break

    return render(
        request,
        "accounts/distributor_register.html",
        {
            "error": error,
            "form": form
        }
    )



# =========================
# ADMIN DASHBOARD
# =========================

@login_required(login_url="/admin/login/")
def admin_dashboard(request):

    if not request.user.is_staff:
        return redirect("distributor_login")

    return render(
        request,
        "dashboard/admin_dashboard.html"
    )


# =========================
# ADMIN REGISTRATION FRONTEND
# =========================

@login_required(login_url="/admin/login/")
def admin_register_view(request):
    """
    Renders the Admin Registration Frontend page.
    Protected view accessible only by authenticated staff/admin users.
    """
    if not request.user.is_staff:
        return redirect("admin_login")

    return render(
        request,
        "adminpanel/admin_register.html"
    )


# =========================
# ADMIN REPORTS & EXPORT
# =========================

def parse_date_filters(request):
    """
    Parses and validates date range filters from GET request.
    Supports preset shortcuts: 'all_time', 'today', 'last_7_days', 'this_month', 'this_year'.
    Or custom start_date and end_date inputs.
    Returns:
        filter_preset (str)
        start_date (date or None)
        end_date (date or None)
        field_errors (dict)
        raw_start (str)
        raw_end (str)
    """
    today = timezone.localdate()
    filter_preset = request.GET.get("filter", "").strip().lower()
    raw_start = request.GET.get("start_date", "").strip()
    raw_end = request.GET.get("end_date", "").strip()

    field_errors = {}
    start_date = None
    end_date = None

    if filter_preset == "today":
        start_date = today
        end_date = today
        raw_start = start_date.strftime("%Y-%m-%d")
        raw_end = end_date.strftime("%Y-%m-%d")
    elif filter_preset == "last_7_days":
        start_date = today - timedelta(days=6)
        end_date = today
        raw_start = start_date.strftime("%Y-%m-%d")
        raw_end = end_date.strftime("%Y-%m-%d")
    elif filter_preset == "this_month":
        start_date = today.replace(day=1)
        end_date = today
        raw_start = start_date.strftime("%Y-%m-%d")
        raw_end = end_date.strftime("%Y-%m-%d")
    elif filter_preset == "this_year":
        start_date = today.replace(month=1, day=1)
        end_date = today
        raw_start = start_date.strftime("%Y-%m-%d")
        raw_end = end_date.strftime("%Y-%m-%d")
    elif filter_preset == "all_time":
        start_date = None
        end_date = None
        raw_start = ""
        raw_end = ""
    else:
        # Custom or direct input from form
        if raw_start:
            try:
                start_date = datetime.strptime(raw_start, "%Y-%m-%d").date()
            except ValueError:
                field_errors["start_date"] = "Please enter a valid Start Date (YYYY-MM-DD)."
        if raw_end:
            try:
                end_date = datetime.strptime(raw_end, "%Y-%m-%d").date()
            except ValueError:
                field_errors["end_date"] = "Please enter a valid End Date (YYYY-MM-DD)."

        if start_date and end_date:
            if start_date > end_date:
                field_errors["start_date"] = "Start Date must not be later than End Date."
                field_errors["end_date"] = "End Date must not be earlier than Start Date."
                field_errors["general"] = "Start Date must not be later than End Date."
            filter_preset = "custom"
        elif start_date or end_date:
            filter_preset = "custom"
        else:
            filter_preset = "all_time"

    return filter_preset, start_date, end_date, field_errors, raw_start, raw_end


@login_required(login_url="/admin/login/")
def admin_reports(request):
    """
    Dedicated Reports dashboard for authorized Admin users.
    Displays comprehensive sales, invoices, customers, and product metrics,
    with interactive date range filters, distributor filters, Chart.js visualizations,
    and paginated data tables.
    """
    if not request.user.is_staff:
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect("admin_login")

    filter_preset, start_date, end_date, field_errors, raw_start, raw_end = parse_date_filters(request)
    if field_errors:
        if "general" in field_errors:
            messages.error(request, field_errors["general"])
        elif "start_date" in field_errors:
            messages.error(request, field_errors["start_date"])
        elif "end_date" in field_errors:
            messages.error(request, field_errors["end_date"])

    # Optional Invoice Status Filter
    status_filter = request.GET.get("status", "all").strip().lower()

    # Distributor filter
    distributor_id_str = request.GET.get("distributor_id", "").strip()
    selected_distributor = None
    if distributor_id_str:
        try:
            selected_distributor = User.objects.get(id=int(distributor_id_str))
        except (ValueError, User.DoesNotExist):
            selected_distributor = None
            distributor_id_str = ""

    # Base querysets
    invoices_qs = (
        Invoice.objects.select_related("customer", "distributor", "distributor__distributor_profile")
        .order_by("-invoice_date", "-created_at")
    )

    if field_errors:
        invoices_qs = Invoice.objects.none()
    else:
        if start_date:
            invoices_qs = invoices_qs.filter(invoice_date__gte=start_date)
        if end_date:
            invoices_qs = invoices_qs.filter(invoice_date__lte=end_date)
        if selected_distributor:
            invoices_qs = invoices_qs.filter(distributor=selected_distributor)
        if status_filter == "pending":
            invoices_qs = invoices_qs.none()

    # Search filter on the invoices table
    search_query = request.GET.get("q", "").strip()
    table_invoices_qs = invoices_qs
    if search_query and not field_errors:
        table_invoices_qs = table_invoices_qs.filter(
            Q(invoice_number__icontains=search_query) |
            Q(customer__name__icontains=search_query) |
            Q(customer__phone__icontains=search_query) |
            Q(distributor__username__icontains=search_query) |
            Q(distributor__distributor_profile__full_name__icontains=search_query)
        )

    # Human-readable report period label
    if start_date and end_date:
        if start_date == end_date:
            report_period_label = start_date.strftime("%d %b %Y")
        else:
            report_period_label = f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"
    elif start_date:
        report_period_label = f"From {start_date.strftime('%d %b %Y')}"
    elif end_date:
        report_period_label = f"Up to {end_date.strftime('%d %b %Y')}"
    else:
        report_period_label = "All Time"

    # KPI Aggregations
    invoice_aggregates = invoices_qs.aggregate(
        total_sales=Coalesce(Sum("grand_total"), Value(Decimal("0.00"))),
        total_subtotal=Coalesce(Sum("subtotal"), Value(Decimal("0.00"))),
        total_gst=Coalesce(Sum("total_gst"), Value(Decimal("0.00"))),
        total_invoices=Count("id")
    )
    total_sales = invoice_aggregates["total_sales"]
    total_invoices = invoice_aggregates["total_invoices"]
    total_subtotal = invoice_aggregates["total_subtotal"]
    total_gst = invoice_aggregates["total_gst"]
    avg_invoice_value = (total_sales / total_invoices) if total_invoices > 0 else Decimal("0.00")

    # Catalog and customer stats
    products_qs = Product.objects.all()
    customers_qs = Customer.objects.all()
    if selected_distributor:
        products_qs = products_qs.filter(distributor=selected_distributor)
        customers_qs = customers_qs.filter(distributor=selected_distributor)

    total_products = products_qs.count()
    active_products = products_qs.filter(is_active=True).count()
    low_stock_products = products_qs.filter(stock__lte=5).count()
    out_of_stock_products = products_qs.filter(stock=0).count()
    total_customers = customers_qs.count()

    # Chart 1: Daily Sales Trend
    daily_sales_qs = (
        invoices_qs.values("invoice_date")
        .annotate(
            revenue=Coalesce(Sum("grand_total"), Value(Decimal("0.00"))),
            invoices_count=Count("id")
        )
        .order_by("invoice_date")
    )
    chart_labels = [entry["invoice_date"].strftime("%d %b %Y") for entry in daily_sales_qs]
    chart_revenue = [float(entry["revenue"]) for entry in daily_sales_qs]
    chart_invoices = [entry["invoices_count"] for entry in daily_sales_qs]

    # Chart 2: Revenue by Distributor
    distributor_sales_qs = (
        invoices_qs.values("distributor_id", "distributor__username", "distributor__distributor_profile__full_name")
        .annotate(
            revenue=Coalesce(Sum("grand_total"), Value(Decimal("0.00"))),
            invoices_count=Count("id")
        )
        .order_by("-revenue")[:6]
    )
    dist_labels = []
    dist_revenue = []
    for d in distributor_sales_qs:
        name = d["distributor__distributor_profile__full_name"] or d["distributor__username"]
        dist_labels.append(name)
        dist_revenue.append(float(d["revenue"]))

    # Chart 3 / Table: Top Selling Products
    top_products_qs = (
        InvoiceItem.objects.filter(invoice__in=invoices_qs)
        .values("product_id", "product_name")
        .annotate(
            units_sold=Coalesce(Sum("quantity"), Value(0)),
            revenue=Coalesce(Sum("line_total"), Value(Decimal("0.00")))
        )
        .order_by("-revenue")[:8]
    )
    top_product_names = [p["product_name"] for p in top_products_qs]
    top_product_revenues = [float(p["revenue"]) for p in top_products_qs]
    top_product_units = [p["units_sold"] for p in top_products_qs]

    # Table: Top Customers
    top_customers_qs = (
        invoices_qs.values(
            "customer_id",
            "customer__name",
            "customer__phone",
            "customer__email",
            "distributor__username",
            "distributor__distributor_profile__full_name"
        )
        .annotate(
            invoices_count=Count("id"),
            total_spent=Coalesce(Sum("grand_total"), Value(Decimal("0.00")))
        )
        .order_by("-total_spent")[:8]
    )

    # Pagination for Invoices breakdown table
    paginator = Paginator(table_invoices_qs, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # List of distributors for filter dropdown
    distributors = (
        User.objects.filter(Q(groups__name="Distributor") | Q(distributor_profile__isnull=False))
        .distinct()
        .select_related("distributor_profile")
        .order_by("username")
    )

    context = {
        "filter_preset": filter_preset,
        "start_date": raw_start if raw_start else (start_date.strftime("%Y-%m-%d") if start_date else ""),
        "end_date": raw_end if raw_end else (end_date.strftime("%Y-%m-%d") if end_date else ""),
        "field_errors": field_errors,
        "report_period_label": report_period_label,
        "status_filter": status_filter,
        "selected_distributor_id": int(distributor_id_str) if distributor_id_str else None,
        "selected_distributor": selected_distributor,
        "distributors": distributors,
        "search_query": search_query,

        # Metrics
        "total_sales": total_sales,
        "total_invoices": total_invoices,
        "total_subtotal": total_subtotal,
        "total_gst": total_gst,
        "avg_invoice_value": avg_invoice_value,
        "total_customers": total_customers,
        "total_products": total_products,
        "active_products": active_products,
        "low_stock_products": low_stock_products,
        "out_of_stock_products": out_of_stock_products,

        # Tables
        "page_obj": page_obj,
        "top_products": top_products_qs,
        "top_customers": top_customers_qs,

        # Chart.js JSON data
        "chart_labels_json": json.dumps(chart_labels),
        "chart_revenue_json": json.dumps(chart_revenue),
        "chart_invoices_json": json.dumps(chart_invoices),
        "dist_labels_json": json.dumps(dist_labels),
        "dist_revenue_json": json.dumps(dist_revenue),
        "top_product_names_json": json.dumps(top_product_names),
        "top_product_revenues_json": json.dumps(top_product_revenues),
        "top_product_units_json": json.dumps(top_product_units),
        "has_sales_data": total_invoices > 0,
    }

    return render(request, "adminpanel/admin_reports.html", context)


@login_required(login_url="/admin/login/")
def admin_reports_export_csv(request):
    """
    Exports filtered reports data to CSV.
    Supported types: 'invoices' (default), 'products', 'customers'.
    Includes formula sanitization and respects date & distributor filters.
    """
    if not request.user.is_staff:
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect("admin_login")

    report_type = request.GET.get("type", "invoices").strip().lower()
    filter_preset, start_date, end_date, field_errors, raw_start, raw_end = parse_date_filters(request)
    status_filter = request.GET.get("status", "all").strip().lower()

    distributor_id_str = request.GET.get("distributor_id", "").strip()
    selected_distributor = None
    if distributor_id_str:
        try:
            selected_distributor = User.objects.get(id=int(distributor_id_str))
        except (ValueError, User.DoesNotExist):
            selected_distributor = None

    invoices_qs = (
        Invoice.objects.select_related("customer", "distributor", "distributor__distributor_profile")
        .order_by("-invoice_date", "-created_at")
    )
    if field_errors:
        invoices_qs = Invoice.objects.none()
    else:
        if start_date:
            invoices_qs = invoices_qs.filter(invoice_date__gte=start_date)
        if end_date:
            invoices_qs = invoices_qs.filter(invoice_date__lte=end_date)
        if selected_distributor:
            invoices_qs = invoices_qs.filter(distributor=selected_distributor)
        if status_filter == "pending":
            invoices_qs = invoices_qs.none()

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")

    # Safe filename containing date range
    if start_date and end_date:
        date_filename_part = f"{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}"
    elif start_date:
        date_filename_part = f"from_{start_date.strftime('%Y-%m-%d')}"
    elif end_date:
        date_filename_part = f"until_{end_date.strftime('%Y-%m-%d')}"
    else:
        date_filename_part = f"all_time_{timestamp}"

    def sanitize_csv(value):
        if value is None:
            return ""
        s = str(value)
        if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + s
        return s

    if report_type == "products":
        response["Content-Disposition"] = f'attachment; filename="product_sales_report_{date_filename_part}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Product Name", "Units Sold", "Total Revenue (INR)", "Distributor"])

        items = (
            InvoiceItem.objects.filter(invoice__in=invoices_qs)
            .values("product_name", "invoice__distributor__username")
            .annotate(
                units_sold=Coalesce(Sum("quantity"), Value(0)),
                total_revenue=Coalesce(Sum("line_total"), Value(Decimal("0.00")))
            )
            .order_by("-total_revenue")
        )
        for item in items:
            writer.writerow([
                sanitize_csv(item["product_name"]),
                sanitize_csv(item["units_sold"]),
                sanitize_csv(f"{item['total_revenue']:.2f}"),
                sanitize_csv(item["invoice__distributor__username"]),
            ])

    elif report_type == "customers":
        response["Content-Disposition"] = f'attachment; filename="customer_sales_report_{date_filename_part}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Customer Name", "Phone", "Email", "Distributor", "Invoices Count", "Total Spent (INR)"])

        customers = (
            invoices_qs.values("customer_id", "customer__name", "customer__phone", "customer__email", "distributor__username")
            .annotate(
                inv_count=Count("id"),
                total_spent=Coalesce(Sum("grand_total"), Value(Decimal("0.00")))
            )
            .order_by("-total_spent")
        )
        for cust in customers:
            writer.writerow([
                sanitize_csv(cust["customer__name"]),
                sanitize_csv(cust["customer__phone"]),
                sanitize_csv(cust["customer__email"] or "N/A"),
                sanitize_csv(cust["distributor__username"]),
                sanitize_csv(cust["inv_count"]),
                sanitize_csv(f"{cust['total_spent']:.2f}"),
            ])

    else:  # 'invoices' default
        response["Content-Disposition"] = f'attachment; filename="invoices_report_{date_filename_part}.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "Invoice Number",
            "Date",
            "Distributor",
            "Customer Name",
            "Customer Phone",
            "Subtotal (INR)",
            "Total GST (INR)",
            "Grand Total (INR)",
            "Status"
        ])
        for inv in invoices_qs:
            dist_profile = getattr(inv.distributor, "distributor_profile", None)
            d_name = dist_profile.full_name if dist_profile and dist_profile.full_name else inv.distributor.username
            writer.writerow([
                sanitize_csv(inv.invoice_number),
                sanitize_csv(inv.invoice_date.strftime("%Y-%m-%d") if inv.invoice_date else ""),
                sanitize_csv(d_name),
                sanitize_csv(inv.customer.name if inv.customer else "N/A"),
                sanitize_csv(inv.customer.phone if inv.customer else "N/A"),
                sanitize_csv(f"{inv.subtotal:.2f}"),
                sanitize_csv(f"{inv.total_gst:.2f}"),
                sanitize_csv(f"{inv.grand_total:.2f}"),
                sanitize_csv("Finalized (Billed)"),
            ])

    return response



# =========================
# DISTRIBUTOR DASHBOARD
# =========================

@login_required(login_url="/distributor/login/")
def distributor_dashboard(request):

    if not is_distributor(request.user):
        return redirect("admin_login")

    return render(
        request,
        "dashboard/distributor_dashboard.html"
    )


# =========================
# DISTRIBUTOR PROFILE
# =========================

@login_required(login_url="/distributor/login/")
def distributor_profile(request):

    if not is_distributor(request.user):
        return redirect("distributor_login")

    profile = getattr(request.user, "distributor_profile", None)
    if not profile:
        profile = DistributorProfile.objects.filter(user=request.user).first()

    return render(
        request,
        "dashboard/distributor_profile.html",
        {
            "profile": profile
        }
    )


# =========================
# EDIT DISTRIBUTOR PROFILE
# =========================

@login_required(login_url="/distributor/login/")
def edit_distributor_profile(request):

    if not is_distributor(request.user):
        return redirect("distributor_login")

    profile = getattr(request.user, "distributor_profile", None)
    if not profile:
        profile = DistributorProfile.objects.filter(user=request.user).first()

    if not profile:
        profile = DistributorProfile.objects.create(
            user=request.user,
            full_name=request.user.get_full_name() or request.user.username,
            email=request.user.email or request.user.username,
            phone=""
        )

    error = None

    if request.method == "POST":
        form = DistributorProfileUpdateForm(request.POST, user=request.user)
        if form.is_valid():
            cleaned_name = form.cleaned_data["full_name"]
            cleaned_email = form.cleaned_data["email"]
            cleaned_phone = form.cleaned_data["phone"]

            try:
                with transaction.atomic():
                    profile.full_name = cleaned_name
                    profile.email = cleaned_email
                    profile.phone = cleaned_phone
                    profile.save()

                    name_parts = cleaned_name.split(" ", 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ""

                    user = request.user
                    user.first_name = first_name
                    user.last_name = last_name
                    user.email = cleaned_email
                    user.username = cleaned_email
                    user.save()

                messages.success(request, "Profile updated successfully.")
                return redirect("distributor_profile")
            except Exception as e:
                error = "Unable to update your profile right now. Please try again."
    else:
        initial_data = {
            "full_name": profile.full_name,
            "email": profile.email,
            "phone": profile.phone,
        }
        form = DistributorProfileUpdateForm(initial=initial_data, user=request.user)

    return render(
        request,
        "dashboard/edit_distributor_profile.html",
        {
            "form": form,
            "profile": profile,
            "error": error
        }
    )



# =========================
# LOGOUT
# =========================

def logout_view(request):

    logout(request)

    return redirect("admin_login")


# =========================
# FORGOT PASSWORD
# =========================

def forgot_password(request):
    error = None
    if request.method == "POST":
        email_or_username = request.POST.get("email", "").strip()

        if not email_or_username:
            error = "Email address or username is required."
        else:
            user = User.objects.filter(email__iexact=email_or_username).first() or \
                   User.objects.filter(username__iexact=email_or_username).first()

            if user:
                target_email = user.email if user.email else email_or_username

                # Invalidate prior active OTPs for same email & purpose
                OTPVerification.objects.filter(
                    email=target_email,
                    purpose="forgot_password",
                    is_verified=False
                ).update(is_verified=True)

                # Secure 6-digit OTP generation using secrets
                otp_code = f"{secrets.randbelow(1000000):06d}"
                expires_at = timezone.now() + timedelta(minutes=5)

                # Save OTP in database
                OTPVerification.objects.create(
                    user=user,
                    email=target_email,
                    otp_code=otp_code,
                    purpose="forgot_password",
                    expires_at=expires_at,
                    is_verified=False,
                    attempts=0
                )

                # Store minimal session metadata for tracking reset flow
                request.session["reset_user_id"] = user.id
                request.session["reset_email"] = target_email
                request.session["password_reset_verified"] = False

                # Send Email
                try:
                    send_mail(
                        subject="Password Reset OTP - Advance Billing System",
                        message=(
                            f"Your OTP is: {otp_code}\n\n"
                            f"This OTP is valid for 5 minutes.\n\n"
                            f"Do not share this OTP with anyone."
                        ),
                        from_email=None,
                        recipient_list=[target_email],
                        fail_silently=False,
                    )
                except Exception as e:
                    print(f"Error sending OTP email: {e}")

                return redirect("verify_otp")
            else:
                error = "No account found with that email address or username."

    return render(
        request,
        "accounts/forgot_password.html",
        {"error": error}
    )


# =========================
# VERIFY OTP
# =========================

def verify_otp(request):
    target_email = request.session.get("reset_email")
    if not target_email or not request.session.get("reset_user_id"):
        return redirect("forgot_password")

    error = None

    if request.method == "POST":
        user_otp = request.POST.get("otp", "").strip()

        # Find latest active OTP record from DB
        otp_record = OTPVerification.objects.filter(
            email=target_email,
            purpose="forgot_password",
            is_verified=False
        ).order_by("-created_at").first()

        if not otp_record:
            error = "No active OTP found. Please request a new OTP."
        elif timezone.now() > otp_record.expires_at:
            error = "OTP has expired. Please request a new OTP."
        elif otp_record.attempts >= 5:
            error = "Too many incorrect attempts. Please request a new OTP."
        elif otp_record.otp_code != user_otp:
            otp_record.attempts += 1
            otp_record.save()
            if otp_record.attempts >= 5:
                error = "Too many incorrect attempts. Please request a new OTP."
            else:
                error = f"Invalid OTP. You have {5 - otp_record.attempts} attempts remaining."
        else:
            # Mark OTP as verified in database
            otp_record.is_verified = True
            otp_record.save()

            # Store verification state in Django session
            request.session["password_reset_verified"] = True
            request.session["password_reset_email"] = target_email

            return redirect("reset_password")

    return render(
        request,
        "accounts/verify_otp.html",
        {
            "error": error,
            "email": target_email,
        }
    )


# =========================
# RESEND OTP
# =========================

def resend_otp(request):
    target_email = request.session.get("reset_email")
    user_id = request.session.get("reset_user_id")

    if not target_email or not user_id:
        return JsonResponse({"success": False, "message": "Session expired. Please restart the process."}, status=400)

    # 60-second rate limiting cooldown check
    latest_otp = OTPVerification.objects.filter(
        email=target_email,
        purpose="forgot_password"
    ).order_by("-created_at").first()

    if latest_otp:
        elapsed = (timezone.now() - latest_otp.created_at).total_seconds()
        if elapsed < 60:
            remaining = int(60 - elapsed)
            return JsonResponse({
                "success": False,
                "message": f"Please wait {remaining} seconds before requesting a new OTP."
            }, status=429)

    try:
        user = User.objects.get(id=user_id)

        # Invalidate previous unverified OTPs
        OTPVerification.objects.filter(
            email=target_email,
            purpose="forgot_password",
            is_verified=False
        ).update(is_verified=True)

        # Generate new 6-digit numeric OTP
        otp_code = f"{secrets.randbelow(1000000):06d}"
        expires_at = timezone.now() + timedelta(minutes=5)

        # Create new DB record
        OTPVerification.objects.create(
            user=user,
            email=target_email,
            otp_code=otp_code,
            purpose="forgot_password",
            expires_at=expires_at,
            is_verified=False,
            attempts=0
        )

        # Send email
        try:
            send_mail(
                subject="Password Reset OTP (Resent) - Advance Billing System",
                message=(
                    f"Your OTP is: {otp_code}\n\n"
                    f"This OTP is valid for 5 minutes.\n\n"
                    f"Do not share this OTP with anyone."
                ),
                from_email=None,
                recipient_list=[target_email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Error resending OTP email: {e}")

        return JsonResponse({"success": True, "message": "OTP sent successfully."})
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": "User not found."}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "message": "Something went wrong. Please try again."}, status=500)


# =========================
# RESET PASSWORD
# =========================

def reset_password(request):
    user_id = request.session.get("reset_user_id")
    is_verified = request.session.get("password_reset_verified")

    # Security Check: Require successful OTP verification
    if not user_id or not is_verified:
        return redirect("forgot_password")

    error = None
    success = None

    if request.method == "POST":
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not new_password or not confirm_password:
            error = "Both password fields are required."
        elif new_password != confirm_password:
            error = "Passwords do not match."
        elif len(new_password) < 6:
            error = "Password must be at least 6 characters long."
        else:
            try:
                user = User.objects.get(id=user_id)
                user.set_password(new_password)
                user.save()

                # Invalidate any remaining active OTP records in DB
                OTPVerification.objects.filter(
                    email=user.email,
                    purpose="forgot_password",
                    is_verified=False
                ).update(is_verified=True)

                # Clear reset session variables
                for key in ["reset_user_id", "reset_email", "password_reset_verified", "password_reset_email"]:
                    if key in request.session:
                        del request.session[key]

                success = "Your password has been reset successfully! You can now login with your new password."
            except User.DoesNotExist:
                error = "User not found."

    return render(
        request,
        "accounts/reset_password.html",
        {
            "error": error,
            "success": success
        }
    )
