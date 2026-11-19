from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User, Group
from accounts.models import DistributorProfile
from billing.models import Customer, Product, Invoice, InvoiceItem
from billing.views import generate_unique_invoice_number


class Command(BaseCommand):
    help = "Idempotently seed at least 5 Customers, 5 Products, 5 Invoices with InvoiceItems"

    def handle(self, *args, **options):
        self.stdout.write("Checking database record counts...")

        # 1. Identify or retrieve primary distributor
        dist_user = (
            User.objects.filter(distributor_profile__isnull=False, is_superuser=False).first()
            or User.objects.filter(groups__name="Distributor", is_superuser=False).first()
        )
        if not dist_user:
            # Fallback to any non-staff user
            dist_user = User.objects.filter(is_staff=False, is_superuser=False).first()

        if not dist_user:
            dist_user = User.objects.create_user(
                username="prime_distributor",
                email="prime.distributor@example.com",
                first_name="Prime",
                last_name="Distributor"
            )
            dist_user.set_password("Distributor@123")
            dist_user.save()

        dist_group, _ = Group.objects.get_or_create(name="Distributor")
        dist_user.groups.add(dist_group)

        profile, _ = DistributorProfile.objects.get_or_create(
            user=dist_user,
            defaults={
                "full_name": dist_user.get_full_name() or "Prime Distribution Services",
                "email": dist_user.email or "prime.distributor@example.com",
                "phone": "+91 9876543210",
                "business_name": "Prime Distribution Network Pvt Ltd",
                "address": "Plot 101, Industrial Corridor, Sector 18, Gurugram"
            }
        )

        # 2. Ensure at least 5 Customers
        sample_customers_data = [
            {
                "name": "Acme Retail Enterprises",
                "email": "contact@acmeretail.in",
                "phone": "+91 9810123456",
                "city": "Mumbai",
                "state": "Maharashtra",
                "pincode": "400001",
                "address": "Plot 101, Bandra Kurla Complex"
            },
            {
                "name": "Metro Electronics & Gadgets",
                "email": "billing@metroelectronics.com",
                "phone": "+91 9820234567",
                "city": "Bengaluru",
                "state": "Karnataka",
                "pincode": "560001",
                "address": "45 MG Road, Commercial Plaza"
            },
            {
                "name": "Zenith Supermart & Grocery",
                "email": "orders@zenithmart.co.in",
                "phone": "+91 9830345678",
                "city": "New Delhi",
                "state": "Delhi",
                "pincode": "110020",
                "address": "B-12 Okhla Phase 2"
            },
            {
                "name": "Sunrise Wholesale Traders",
                "email": "info@sunrisetraders.org",
                "phone": "+91 9840456789",
                "city": "Chennai",
                "state": "Tamil Nadu",
                "pincode": "600001",
                "address": "78 Anna Salai"
            },
            {
                "name": "Global Infotech Solutions",
                "email": "accounts@globalinfotech.in",
                "phone": "+91 9850567890",
                "city": "Pune",
                "state": "Maharashtra",
                "pincode": "411001",
                "address": "Building 4, Hinjewadi IT Park"
            },
        ]

        customers_created = 0
        if Customer.objects.count() < 5:
            for c_data in sample_customers_data:
                cust, created = Customer.objects.get_or_create(
                    name=c_data["name"],
                    defaults={
                        "distributor": dist_user,
                        "email": c_data["email"],
                        "phone": c_data["phone"],
                        "city": c_data["city"],
                        "state": c_data["state"],
                        "pincode": c_data["pincode"],
                        "address": c_data["address"],
                    }
                )
                if created:
                    customers_created += 1
                if Customer.objects.count() >= 5:
                    break

        self.stdout.write(f"Customers in DB: {Customer.objects.count()} (New: {customers_created})")

        # 3. Ensure at least 5 Products
        sample_products_data = [
            {
                "name": "Thermal Billing Roll (80mm x 50m)",
                "category": "Stationery",
                "price": Decimal("150.00"),
                "stock": 250,
                "gst_rate": Decimal("18.00"),
                "sku": "SKU-TBR-080",
                "unit": "roll",
                "description": "High-density thermal billing paper for POS receipt printers."
            },
            {
                "name": "Omnidirectional Barcode Scanner",
                "category": "Hardware",
                "price": Decimal("3200.00"),
                "stock": 45,
                "gst_rate": Decimal("18.00"),
                "sku": "SKU-OBS-200",
                "unit": "piece",
                "description": "High-accuracy 1D/2D QR & Barcode hands-free scanner."
            },
            {
                "name": "High-Speed POS Thermal Printer 80mm",
                "category": "Hardware",
                "price": Decimal("5800.00"),
                "stock": 30,
                "gst_rate": Decimal("18.00"),
                "sku": "SKU-POS-80P",
                "unit": "piece",
                "description": "250mm/sec auto-cutter heavy duty POS receipt printer."
            },
            {
                "name": "Smart QR Code Acrylic Display Stand",
                "category": "Accessories",
                "price": Decimal("450.00"),
                "stock": 120,
                "gst_rate": Decimal("12.00"),
                "sku": "SKU-QRS-100",
                "unit": "piece",
                "description": "Premium acrylic QR payment stand with non-slip base."
            },
            {
                "name": "Programmable Commercial Billing Keyboard",
                "category": "Peripherals",
                "price": Decimal("2450.00"),
                "stock": 60,
                "gst_rate": Decimal("18.00"),
                "sku": "SKU-KB-PROG",
                "unit": "piece",
                "description": "68-key mechanical POS keyboard with spill-resistant casing."
            },
        ]

        products_created = 0
        if Product.objects.count() < 5:
            for p_data in sample_products_data:
                prod, created = Product.objects.get_or_create(
                    name=p_data["name"],
                    defaults={
                        "distributor": dist_user,
                        "category": p_data["category"],
                        "price": p_data["price"],
                        "stock": p_data["stock"],
                        "gst_rate": p_data["gst_rate"],
                        "sku": p_data["sku"],
                        "unit": p_data["unit"],
                        "description": p_data["description"],
                        "is_active": True,
                    }
                )
                if created:
                    products_created += 1
                if Product.objects.count() >= 5:
                    break

        self.stdout.write(f"Products in DB: {Product.objects.count()} (New: {products_created})")

        # 4. Ensure at least 5 Invoices with InvoiceItems
        invoices_created = 0
        all_customers = list(Customer.objects.all())
        all_products = list(Product.objects.all())

        if Invoice.objects.count() < 5 and all_customers and all_products:
            today = timezone.localdate()
            for idx in range(Invoice.objects.count(), 5):
                with transaction.atomic():
                    customer = all_customers[idx % len(all_customers)]
                    invoice_dist = customer.distributor or dist_user
                    inv_date = today - timedelta(days=idx)
                    inv_number = generate_unique_invoice_number(invoice_dist)

                    inv = Invoice.objects.create(
                        distributor=invoice_dist,
                        customer=customer,
                        invoice_number=inv_number,
                        invoice_date=inv_date,
                        subtotal=Decimal("0.00"),
                        total_gst=Decimal("0.00"),
                        grand_total=Decimal("0.00")
                    )

                    # Create 1-2 invoice items for this invoice
                    subtotal = Decimal("0.00")
                    total_gst = Decimal("0.00")

                    prod1 = all_products[idx % len(all_products)]
                    qty1 = (idx % 3) + 1
                    rate1 = prod1.gst_rate
                    taxable1 = (prod1.price * Decimal(qty1)).quantize(Decimal("0.01"))
                    gst1 = ((taxable1 * rate1) / Decimal("100.00")).quantize(Decimal("0.01"))
                    total1 = taxable1 + gst1

                    InvoiceItem.objects.create(
                        invoice=inv,
                        product=prod1,
                        product_name=prod1.name,
                        quantity=qty1,
                        unit_price=prod1.price,
                        gst_rate=rate1,
                        discount_percent=Decimal("0.00"),
                        taxable_amount=taxable1,
                        gst_amount=gst1,
                        line_total=total1
                    )
                    subtotal += taxable1
                    total_gst += gst1

                    # Optional 2nd product item
                    if len(all_products) > 1:
                        prod2 = all_products[(idx + 1) % len(all_products)]
                        qty2 = 2
                        rate2 = prod2.gst_rate
                        taxable2 = (prod2.price * Decimal(qty2)).quantize(Decimal("0.01"))
                        gst2 = ((taxable2 * rate2) / Decimal("100.00")).quantize(Decimal("0.01"))
                        total2 = taxable2 + gst2

                        InvoiceItem.objects.create(
                            invoice=inv,
                            product=prod2,
                            product_name=prod2.name,
                            quantity=qty2,
                            unit_price=prod2.price,
                            gst_rate=rate2,
                            discount_percent=Decimal("0.00"),
                            taxable_amount=taxable2,
                            gst_amount=gst2,
                            line_total=total2
                        )
                        subtotal += taxable2
                        total_gst += gst2

                    inv.subtotal = subtotal
                    inv.total_gst = total_gst
                    inv.grand_total = subtotal + total_gst
                    inv.save()

                    # Generate QR code
                    try:
                        inv.generate_and_save_qr_code(force=True)
                    except Exception as e:
                        self.stderr.write(f"Warning: QR generation: {e}")

                    invoices_created += 1

        self.stdout.write(f"Invoices in DB: {Invoice.objects.count()} (New: {invoices_created})")
        self.stdout.write(f"InvoiceItems in DB: {InvoiceItem.objects.count()}")
        self.stdout.write(self.style.SUCCESS("Sample data seeding verified successfully!"))
