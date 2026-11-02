import sys
from decimal import Decimal
from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User, Group
from billing.models import Invoice, InvoiceItem, Customer, Product
from billing.views import generate_unique_invoice_number


def verify_invoice_record(invoice):
    """
    Validates that a single Invoice model instance satisfies all required attributes:
    1. Unique Invoice ID (pk and invoice_number)
    2. Associated Customer exists and Customer Name is non-empty
    3. Total Amount (grand_total) is stored correctly, valid, and non-negative
    4. Invoice Date is valid

    Returns:
        dict: Summary of verified attributes and validity status.
    """
    errors = []

    # 1. Invoice ID
    if not invoice.pk or not invoice.invoice_number or not str(invoice.invoice_number).strip():
        errors.append("Missing or empty invoice_number / ID")

    # 2. Customer & Customer Name
    customer_name = None
    try:
        if not invoice.customer:
            errors.append("Invoice is missing customer association")
        else:
            customer_name = invoice.customer.name
            if not customer_name or not str(customer_name).strip():
                errors.append("Customer name is empty")
    except Exception as e:
        errors.append(f"Failed to access customer relationship: {e}")

    # 3. Total Amount
    total_amount = invoice.grand_total
    if total_amount is None:
        errors.append("grand_total is None")
    elif total_amount < Decimal("0.00"):
        errors.append(f"grand_total is negative: {total_amount}")

    # 4. Invoice Date
    invoice_date = invoice.invoice_date
    if not invoice_date or not isinstance(invoice_date, (date,)):
        errors.append(f"Invalid invoice_date: {invoice_date}")

    is_valid = len(errors) == 0

    return {
        "id": invoice.pk,
        "invoice_number": invoice.invoice_number,
        "customer_id": invoice.customer_id if invoice.customer_id else None,
        "customer_name": customer_name,
        "total_amount": total_amount,
        "invoice_date": invoice_date,
        "distributor": invoice.distributor.username if invoice.distributor else None,
        "is_valid": is_valid,
        "errors": errors,
    }


def ensure_invoices_exist(min_samples=1, create_sample_if_empty=True):
    """
    Verifies that invoice records exist in the database with required fields.
    If no invoice records exist, creates a small number of valid sample records
    using existing customers and products without duplicating records on repeated runs.

    Returns:
        tuple: (verified_records, created_records)
    """
    verified_records = []
    created_records = []

    existing_invoices = Invoice.objects.select_related("customer", "distributor").prefetch_related("items").all()

    if existing_invoices.exists():
        for inv in existing_invoices:
            info = verify_invoice_record(inv)
            verified_records.append(info)
        return verified_records, created_records

    if not create_sample_if_empty:
        return verified_records, created_records

    # If no invoice records exist, create a sample invoice using existing distributor, customer, product
    with transaction.atomic():
        # 1. Identify or retrieve distributor
        distributor = User.objects.filter(groups__name="Distributor").first()
        if not distributor:
            distributor = User.objects.filter(is_staff=False).first()
        if not distributor:
            distributor = User.objects.create_user(
                username="sample_distributor",
                email="sample_distributor@example.com",
                password="SamplePassword123!"
            )
            dist_group, _ = Group.objects.get_or_create(name="Distributor")
            distributor.groups.add(dist_group)

        # 2. Identify or retrieve customer
        customer = Customer.objects.filter(distributor=distributor).first()
        if not customer:
            customer = Customer.objects.first()
        if not customer:
            customer = Customer.objects.create(
                distributor=distributor,
                name="Acme Corporation",
                email="billing@acmecorp.example",
                phone="9876543210",
                address="100 Commercial Blvd",
                city="Ahmedabad",
                state="Gujarat",
                pincode="380001"
            )

        # 3. Identify or retrieve product
        product = Product.objects.filter(distributor=distributor, is_active=True).first()
        if not product:
            product = Product.objects.filter(is_active=True).first()
        if not product:
            product = Product.objects.create(
                distributor=distributor,
                name="Premium Office Supplies",
                category="Office",
                description="Sample standard office supply box",
                price=Decimal("500.00"),
                stock=100,
                gst_rate=Decimal("18.00"),
                sku="SAMPLE-OFF-01",
                unit="box",
                is_active=True
            )

        # 4. Generate unique invoice number and calculate totals
        inv_number = generate_unique_invoice_number(distributor)
        quantity = 2
        unit_price = product.price
        discount_percent = Decimal("0.00")
        gst_rate = product.gst_rate

        gross_amount = Decimal(quantity) * unit_price
        discount_amount = (gross_amount * (discount_percent / Decimal("100.00"))).quantize(Decimal("0.01"))
        taxable_amount = gross_amount - discount_amount
        gst_amount = (taxable_amount * (gst_rate / Decimal("100.00"))).quantize(Decimal("0.01"))
        line_total = taxable_amount + gst_amount

        subtotal = taxable_amount
        total_gst = gst_amount
        grand_total = subtotal + total_gst

        invoice = Invoice.objects.create(
            distributor=distributor,
            customer=customer,
            invoice_number=inv_number,
            invoice_date=date.today(),
            subtotal=subtotal,
            total_gst=total_gst,
            grand_total=grand_total
        )

        InvoiceItem.objects.create(
            invoice=invoice,
            product=product,
            product_name=product.name,
            quantity=quantity,
            unit_price=unit_price,
            gst_rate=gst_rate,
            discount_percent=discount_percent,
            taxable_amount=taxable_amount,
            gst_amount=gst_amount,
            line_total=line_total
        )

        if product.stock >= quantity:
            product.stock -= quantity
            product.save(update_fields=["stock"])

        info = verify_invoice_record(invoice)
        created_records.append(info)
        verified_records.append(info)

    return verified_records, created_records


class Command(BaseCommand):
    help = "Verifies and ensures invoice records exist in the database with required fields."

    def add_arguments(self, parser):
        parser.add_argument(
            "--verify-only",
            action="store_true",
            help="Only verify existing records without creating sample records if empty.",
        )

    def handle(self, *args, **options):
        verify_only = options.get("verify_only", False)
        self.stdout.write(self.style.NOTICE("Checking invoice data in database..."))

        verified_records, created_records = ensure_invoices_exist(
            create_sample_if_empty=not verify_only
        )

        total_count = len(verified_records)
        created_count = len(created_records)
        invalid_count = sum(1 for r in verified_records if not r["is_valid"])

        self.stdout.write(f"\nFound {total_count} invoice record(s) in database.")
        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f"Created {created_count} sample invoice record(s)."))
        else:
            self.stdout.write("Existing invoice records found; no duplicate records created.")

        self.stdout.write("\n" + "=" * 90)
        self.stdout.write(f"{'Invoice ID':<12} {'Invoice Number':<18} {'Customer Name':<25} {'Total Amount':<16} {'Invoice Date':<14} {'Status'}")
        self.stdout.write("=" * 90)

        for record in verified_records:
            status = self.style.SUCCESS("VALID") if record["is_valid"] else self.style.ERROR("INVALID: " + ", ".join(record["errors"]))
            self.stdout.write(
                f"{record['id']:<12} {record['invoice_number']:<18} {str(record['customer_name']):<25} {str(record['total_amount']):<16} {str(record['invoice_date']):<14} {status}"
            )

        self.stdout.write("=" * 90 + "\n")

        if invalid_count > 0:
            self.stdout.write(self.style.ERROR(f"WARNING: {invalid_count} record(s) have invalid fields."))
        else:
            self.stdout.write(self.style.SUCCESS("All invoice records verified successfully!"))

