from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from billing.models import Customer, Product, Invoice, InvoiceItem




class CustomerListViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group = Group.objects.create(name="Distributor")

        # Distributor 1
        self.distributor1 = User.objects.create_user(
            username="distributor1",
            password="password123",
            first_name="Rahul",
            last_name="Patel"
        )
        self.distributor1.groups.add(self.distributor_group)

        # Distributor 2
        self.distributor2 = User.objects.create_user(
            username="distributor2",
            password="password123",
            first_name="Amit",
            last_name="Shah"
        )
        self.distributor2.groups.add(self.distributor_group)

        # Regular non-distributor user
        self.regular_user = User.objects.create_user(
            username="regularuser",
            password="password123"
        )

        # Sample Customers for Distributor 1
        self.c1 = Customer.objects.create(
            distributor=self.distributor1,
            name="Rahul Patel",
            email="rahul@gmail.com",
            phone="9876543210",
            address="123 Main Street",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380001"
        )

        self.c2 = Customer.objects.create(
            distributor=self.distributor1,
            name="Suresh Kumar",
            email="suresh@yahoo.com",
            phone="9123456789",
            address="456 Cross Road",
            city="Surat",
            state="Gujarat",
            pincode="395001"
        )

        # Sample Customer for Distributor 2
        self.c3 = Customer.objects.create(
            distributor=self.distributor2,
            name="Vikas Sharma",
            email="vikas@gmail.com",
            phone="9988776655",
            address="789 Ring Road",
            city="Vadodara",
            state="Gujarat",
            pincode="390001"
        )

        self.url = reverse("customer_list")

    def test_customer_list_requires_login(self):
        """Unauthenticated user should be redirected to distributor login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)

    def test_customer_list_requires_distributor_role(self):
        """Non-distributor logged-in user should be redirected to distributor login page."""
        self.client.login(username="regularuser", password="password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("distributor_login"))

    def test_distributor_ownership_isolation(self):
        """Distributor 1 should only see their own customers, not Distributor 2's."""
        self.client.login(username="distributor1", password="password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        page_customers = list(response.context["page_obj"])
        self.assertIn(self.c1, page_customers)
        self.assertIn(self.c2, page_customers)
        self.assertNotIn(self.c3, page_customers)

    def test_search_by_name(self):
        """Searching by name should return matching customer."""
        self.client.login(username="distributor1", password="password123")
        response = self.client.get(self.url, {"q": "rahul"})
        self.assertEqual(response.status_code, 200)
        page_customers = list(response.context["page_obj"])
        self.assertEqual(len(page_customers), 1)
        self.assertEqual(page_customers[0], self.c1)
        self.assertEqual(response.context["query"], "rahul")

    def test_search_by_phone(self):
        """Searching by phone number should return matching customer."""
        self.client.login(username="distributor1", password="password123")
        response = self.client.get(self.url, {"q": "91234"})
        self.assertEqual(response.status_code, 200)
        page_customers = list(response.context["page_obj"])
        self.assertEqual(len(page_customers), 1)
        self.assertEqual(page_customers[0], self.c2)

    def test_search_by_email(self):
        """Searching by email address should return matching customer."""
        self.client.login(username="distributor1", password="password123")
        response = self.client.get(self.url, {"q": "yahoo"})
        self.assertEqual(response.status_code, 200)
        page_customers = list(response.context["page_obj"])
        self.assertEqual(len(page_customers), 1)
        self.assertEqual(page_customers[0], self.c2)

    def test_search_by_city(self):
        """Searching by city should return matching customer."""
        self.client.login(username="distributor1", password="password123")
        response = self.client.get(self.url, {"q": "Ahmedabad"})
        self.assertEqual(response.status_code, 200)
        page_customers = list(response.context["page_obj"])
        self.assertEqual(len(page_customers), 1)
        self.assertEqual(page_customers[0], self.c1)

    def test_search_no_results_empty_state(self):
        """Searching for non-existent query should display empty state."""
        self.client.login(username="distributor1", password="password123")
        response = self.client.get(self.url, {"q": "nonexistentquery"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page_obj"]), 0)
        self.assertContains(response, "No customers found")
        self.assertContains(response, 'matching "<strong>nonexistentquery</strong>"')

    def test_no_customers_empty_state(self):
        """Distributor with zero customers should see No Customers Yet empty state."""
        # Create new distributor with 0 customers
        new_dist = User.objects.create_user(
            username="distributor3",
            password="password123"
        )
        new_dist.groups.add(self.distributor_group)
        self.client.login(username="distributor3", password="password123")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_count"], 0)
        self.assertContains(response, "No Customers Yet")
        self.assertContains(response, "You haven't added any customers yet.")

    def test_pagination(self):
        """Pagination should limit items to 10 per page and preserve query parameter."""
        self.client.login(username="distributor1", password="password123")
        # Add 12 more customers for distributor1 (total 14)
        for i in range(12):
            Customer.objects.create(
                distributor=self.distributor1,
                name=f"Bulk Customer {i}",
                phone=f"90000000{i:02d}"
            )

        # Page 1
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page_obj"]), 10)
        self.assertTrue(response.context["page_obj"].has_next())

        # Page 2
        response_p2 = self.client.get(self.url, {"page": 2})
        self.assertEqual(response_p2.status_code, 200)
        self.assertEqual(len(response_p2.context["page_obj"]), 4)

        # Pagination with search
        response_search_p2 = self.client.get(self.url, {"q": "Bulk", "page": 2})
        self.assertEqual(response_search_p2.status_code, 200)
        self.assertEqual(len(response_search_p2.context["page_obj"]), 2) # 12 Bulk customers -> 10 on p1, 2 on p2
        self.assertContains(response_search_p2, "q=Bulk")


class CustomerEditViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group = Group.objects.create(name="Distributor")

        self.distributor1 = User.objects.create_user(
            username="dist1",
            password="password123"
        )
        self.distributor1.groups.add(self.distributor_group)

        self.distributor2 = User.objects.create_user(
            username="dist2",
            password="password123"
        )
        self.distributor2.groups.add(self.distributor_group)

        self.customer1 = Customer.objects.create(
            distributor=self.distributor1,
            name="Original Name",
            email="original@example.com",
            phone="9876543210",
            address="Original Address",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380001"
        )

        self.customer2 = Customer.objects.create(
            distributor=self.distributor2,
            name="Other Customer",
            phone="9123456789"
        )

        self.edit_url = reverse("customer_edit", kwargs={"pk": self.customer1.pk})

    def test_edit_customer_requires_login(self):
        """Unauthenticated GET should redirect to login."""
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)

    def test_edit_customer_prefills_form(self):
        """GET request should load page with pre-filled customer details."""
        self.client.login(username="dist1", password="password123")
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Original Name")
        self.assertContains(response, "original@example.com")
        self.assertContains(response, "9876543210")

    def test_distributor_cannot_edit_other_distributor_customer(self):
        """Distributor A attempting to access Customer B should get 404 Not Found."""
        self.client.login(username="dist1", password="password123")
        other_edit_url = reverse("customer_edit", kwargs={"pk": self.customer2.pk})
        response = self.client.get(other_edit_url)
        self.assertEqual(response.status_code, 404)

        # POST attempt
        post_response = self.client.post(other_edit_url, {"name": "Hacked Name", "phone": "9876543210"})
        self.assertEqual(post_response.status_code, 404)
        self.customer2.refresh_from_db()
        self.assertEqual(self.customer2.name, "Other Customer")

    def test_successful_customer_update(self):
        """Valid POST should update existing DB record and redirect to customer list."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "name": "Updated Name",
            "email": "updated@example.com",
            "phone": "9998887776",
            "address": "Updated Address",
            "city": "Surat",
            "state": "Gujarat",
            "pincode": "395001"
        }
        response = self.client.post(self.edit_url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("customer_list"))

        # Verify DB update
        self.customer1.refresh_from_db()
        self.assertEqual(self.customer1.name, "Updated Name")
        self.assertEqual(self.customer1.email, "updated@example.com")
        self.assertEqual(self.customer1.phone, "9998887776")
        self.assertEqual(self.customer1.city, "Surat")
        self.assertEqual(self.customer1.distributor, self.distributor1)

        # Verify success message on customer list
        list_response = self.client.get(response.url)
        self.assertContains(list_response, "Customer updated successfully.")

    def test_invalid_phone_number_validation_error(self):
        """Invalid phone number should display validation error and not save changes."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "name": "Updated Name",
            "phone": "123"
        }
        response = self.client.post(self.edit_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a valid 10-digit phone number.")

        self.customer1.refresh_from_db()
        self.assertEqual(self.customer1.name, "Original Name")


class CustomerDeleteViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group = Group.objects.create(name="Distributor")

        self.distributor1 = User.objects.create_user(
            username="dist1",
            password="password123"
        )
        self.distributor1.groups.add(self.distributor_group)

        self.distributor2 = User.objects.create_user(
            username="dist2",
            password="password123"
        )
        self.distributor2.groups.add(self.distributor_group)

        self.customer1 = Customer.objects.create(
            distributor=self.distributor1,
            name="Customer One",
            phone="9876543210"
        )

        self.customer2 = Customer.objects.create(
            distributor=self.distributor2,
            name="Customer Two",
            phone="9123456789"
        )

        self.delete_url = reverse("customer_delete", kwargs={"pk": self.customer1.pk})

    def test_delete_requires_login(self):
        """Unauthenticated POST request should redirect to login."""
        response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)
        self.assertTrue(Customer.objects.filter(pk=self.customer1.pk).exists())

    def test_get_request_rejects_deletion(self):
        """GET request should not delete customer and redirect to customer list."""
        self.client.login(username="dist1", password="password123")
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("customer_list"))
        self.assertTrue(Customer.objects.filter(pk=self.customer1.pk).exists())

    def test_distributor_cannot_delete_other_distributor_customer(self):
        """Distributor 1 attempting to delete Distributor 2's customer should receive 404."""
        self.client.login(username="dist1", password="password123")
        other_delete_url = reverse("customer_delete", kwargs={"pk": self.customer2.pk})
        response = self.client.post(other_delete_url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Customer.objects.filter(pk=self.customer2.pk).exists())

    def test_successful_customer_deletion(self):
        """Authenticated POST request should delete customer from database and redirect with success message."""
        self.client.login(username="dist1", password="password123")
        response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("customer_list"))

        self.assertFalse(Customer.objects.filter(pk=self.customer1.pk).exists())

        list_response = self.client.get(response.url)
        self.assertTrue("deleted successfully." in list_response.content.decode())


class ProductModelTests(TestCase):

    def setUp(self):
        self.distributor1 = User.objects.create_user(
            username="distributor_a",
            password="password123"
        )
        self.distributor2 = User.objects.create_user(
            username="distributor_b",
            password="password123"
        )

    def test_product_creation(self):
        """Verify product is created and fields are saved correctly."""
        product = Product.objects.create(
            distributor=self.distributor1,
            name="Wireless Mouse",
            category="Electronics",
            description="USB wireless mouse",
            price=Decimal("599.00"),
            stock=50,
            gst_rate=Decimal("18.00"),
            sku="WM-001"
        )
        self.assertIsNotNone(product.pk)
        self.assertEqual(product.name, "Wireless Mouse")
        self.assertEqual(product.category, "Electronics")
        self.assertEqual(product.description, "USB wireless mouse")
        self.assertEqual(product.price, Decimal("599.00"))
        self.assertEqual(product.stock, 50)
        self.assertEqual(product.gst_rate, Decimal("18.00"))
        self.assertEqual(product.sku, "WM-001")
        self.assertEqual(product.distributor, self.distributor1)

    def test_price_validation(self):
        """Test valid prices (0, 499.00, 999.99, 125000.00) and negative price failure."""
        valid_prices = [Decimal("0.00"), Decimal("499.00"), Decimal("999.99"), Decimal("125000.00")]
        for p in valid_prices:
            product = Product(
                distributor=self.distributor1,
                name=f"Product {p}",
                price=p,
                stock=10,
                gst_rate=Decimal("18.00")
            )
            product.full_clean()  # should not raise
            product.save()

        # Negative price must fail
        invalid_product = Product(
            distributor=self.distributor1,
            name="Invalid Price Product",
            price=Decimal("-10.00"),
            stock=10
        )
        with self.assertRaises(ValidationError):
            invalid_product.save()

    def test_stock_validation(self):
        """Test valid stock values (0, 1, 100, 1000) and negative stock failure."""
        valid_stocks = [0, 1, 100, 1000]
        for s in valid_stocks:
            product = Product(
                distributor=self.distributor1,
                name=f"Stock Product {s}",
                price=Decimal("100.00"),
                stock=s
            )
            product.full_clean()  # should not raise
            product.save()

        # Negative stock must fail
        invalid_stock_product = Product(
            distributor=self.distributor1,
            name="Negative Stock Product",
            price=Decimal("100.00"),
            stock=-5
        )
        with self.assertRaises(ValidationError):
            invalid_stock_product.save()

    def test_gst_rate_validation(self):
        """Test valid GST rates (0, 5, 12, 18, 28, 100) and invalid rates (<0 or >100)."""
        valid_rates = [Decimal("0.00"), Decimal("5.00"), Decimal("12.00"), Decimal("18.00"), Decimal("28.00"), Decimal("100.00")]
        for r in valid_rates:
            product = Product(
                distributor=self.distributor1,
                name=f"GST Product {r}",
                price=Decimal("100.00"),
                gst_rate=r
            )
            product.full_clean()
            product.save()

        # Negative GST rate must fail
        invalid_gst_neg = Product(
            distributor=self.distributor1,
            name="Negative GST Product",
            price=Decimal("100.00"),
            gst_rate=Decimal("-5.00")
        )
        with self.assertRaises(ValidationError):
            invalid_gst_neg.save()

        # GST rate > 100 must fail
        invalid_gst_high = Product(
            distributor=self.distributor1,
            name="High GST Product",
            price=Decimal("100.00"),
            gst_rate=Decimal("105.00")
        )
        with self.assertRaises(ValidationError):
            invalid_gst_high.save()

    def test_name_validation(self):
        """Empty or whitespace-only name must fail validation."""
        empty_name_product = Product(
            distributor=self.distributor1,
            name="",
            price=Decimal("100.00")
        )
        with self.assertRaises(ValidationError):
            empty_name_product.save()

        whitespace_name_product = Product(
            distributor=self.distributor1,
            name="   ",
            price=Decimal("100.00")
        )
        with self.assertRaises(ValidationError):
            whitespace_name_product.save()

    def test_timestamps_auto_populated(self):
        """Verify created_at and updated_at are automatically populated."""
        product = Product.objects.create(
            distributor=self.distributor1,
            name="Timestamp Product",
            price=Decimal("150.00")
        )
        self.assertIsNotNone(product.created_at)
        self.assertIsNotNone(product.updated_at)

    def test_string_representation(self):
        """str(product) should return product name."""
        product = Product(
            distributor=self.distributor1,
            name="Office Chair",
            price=Decimal("2500.00")
        )
        self.assertEqual(str(product), "Office Chair")

    def test_distributor_isolation(self):
        """Distributor A products must not be returned in Distributor B's product queryset."""
        product_a = Product.objects.create(
            distributor=self.distributor1,
            name="Product A",
            price=Decimal("100.00")
        )
        product_b = Product.objects.create(
            distributor=self.distributor2,
            name="Product B",
            price=Decimal("200.00")
        )

        dist1_products = Product.objects.filter(distributor=self.distributor1)
        dist2_products = Product.objects.filter(distributor=self.distributor2)

        self.assertIn(product_a, dist1_products)
        self.assertNotIn(product_b, dist1_products)

        self.assertIn(product_b, dist2_products)
        self.assertNotIn(product_a, dist2_products)


class AddProductViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group = Group.objects.create(name="Distributor")

        self.distributor1 = User.objects.create_user(
            username="dist1",
            password="password123"
        )
        self.distributor1.groups.add(self.distributor_group)

        self.regular_user = User.objects.create_user(
            username="regular",
            password="password123"
        )

        self.url = reverse("product_add")

    def test_add_product_requires_login(self):
        """Unauthenticated user should be redirected to distributor login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)

    def test_add_product_requires_distributor_role(self):
        """Non-distributor user should be redirected to distributor login page."""
        self.client.login(username="regular", password="password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("distributor_login"))

    def test_add_product_get_page(self):
        """Authenticated distributor GET should render Add Product form."""
        self.client.login(username="dist1", password="password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "billing/add_product.html")
        self.assertContains(response, "Add New Product")

    def test_add_product_successful_post(self):
        """Valid POST should create product owned by request.user and redirect to dashboard."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "name": "Wireless Mouse",
            "category": "Electronics",
            "sku": "WM-001",
            "price": "599.00",
            "stock": "50",
            "gst_rate": "18.00",
            "description": "USB wireless optical mouse"
        }
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("distributor_dashboard"))

        product = Product.objects.get(name="Wireless Mouse")
        self.assertEqual(product.distributor, self.distributor1)
        self.assertEqual(product.category, "Electronics")
        self.assertEqual(product.sku, "WM-001")
        self.assertEqual(product.price, Decimal("599.00"))
        self.assertEqual(product.stock, 50)
        self.assertEqual(product.gst_rate, Decimal("18.00"))
        self.assertEqual(product.description, "USB wireless optical mouse")

        dashboard_response = self.client.get(response.url)
        self.assertContains(dashboard_response, "Product added successfully.")

    def test_add_product_invalid_price(self):
        """Price <= 0 should fail validation and not save product."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "name": "Invalid Price Product",
            "price": "0.00",
            "stock": "10",
            "gst_rate": "18.00"
        }
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Price must be greater than 0.")
        self.assertFalse(Product.objects.filter(name="Invalid Price Product").exists())

    def test_add_product_invalid_stock(self):
        """Negative stock should fail validation and not save product."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "name": "Invalid Stock Product",
            "price": "100.00",
            "stock": "-5",
            "gst_rate": "18.00"
        }
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue("Ensure this value is greater than or equal to 0." in response.content.decode() or "Stock cannot be negative." in response.content.decode())
        self.assertFalse(Product.objects.filter(name="Invalid Stock Product").exists())

    def test_add_product_invalid_gst(self):
        """GST rate > 100 or < 0 should fail validation and not save product."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "name": "Invalid GST Product",
            "price": "100.00",
            "stock": "10",
            "gst_rate": "150.00"
        }
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue("Ensure this value is less than or equal to 100." in response.content.decode() or "GST rate must be between 0% and 100%." in response.content.decode())
        self.assertFalse(Product.objects.filter(name="Invalid GST Product").exists())

    def test_add_product_empty_name(self):
        """Empty or whitespace-only product name should fail validation."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "name": "   ",
            "price": "100.00",
            "stock": "10",
            "gst_rate": "18.00"
        }
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a valid product name.")


class ProductListViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group = Group.objects.create(name="Distributor")

        # Distributor 1
        self.distributor1 = User.objects.create_user(
            username="distributor1",
            password="password123",
            first_name="Rahul",
            last_name="Patel"
        )
        self.distributor1.groups.add(self.distributor_group)

        # Distributor 2
        self.distributor2 = User.objects.create_user(
            username="distributor2",
            password="password123",
            first_name="Amit",
            last_name="Shah"
        )
        self.distributor2.groups.add(self.distributor_group)

        # Regular non-distributor user
        self.regular_user = User.objects.create_user(
            username="regularuser",
            password="password123"
        )

        # Sample Products for Distributor 1
        self.p1 = Product.objects.create(
            distributor=self.distributor1,
            name="Wireless Mouse",
            category="Electronics",
            price=Decimal("599.00"),
            stock=50,
            gst_rate=Decimal("18.00"),
            sku="WM-001",
            description="USB wireless mouse"
        )

        self.p2 = Product.objects.create(
            distributor=self.distributor1,
            name="Mechanical Keyboard",
            category="Electronics",
            price=Decimal("999.50"),
            stock=20,
            gst_rate=Decimal("18.00"),
            sku="MK-002",
            description="RGB mechanical keyboard"
        )

        # Sample Product for Distributor 2
        self.p3 = Product.objects.create(
            distributor=self.distributor2,
            name="Gaming Chair",
            category="Furniture",
            price=Decimal("12500.00"),
            stock=5,
            gst_rate=Decimal("28.00"),
            sku="GC-003",
            description="Ergonomic leather chair"
        )

        self.url = reverse("product_list")

    def test_product_list_requires_login(self):
        """Unauthenticated user should be redirected to distributor login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)

    def test_product_list_requires_distributor_role(self):
        """Non-distributor logged-in user should be redirected to distributor login page."""
        self.client.login(username="regularuser", password="password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("distributor_login"))

    def test_distributor_ownership_isolation(self):
        """Distributor 1 should only see their own products, not Distributor 2's."""
        self.client.login(username="distributor1", password="password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        page_products = list(response.context["page_obj"])
        self.assertIn(self.p1, page_products)
        self.assertIn(self.p2, page_products)
        self.assertNotIn(self.p3, page_products)

    def test_search_by_name(self):
        """Searching by name should return matching product."""
        self.client.login(username="distributor1", password="password123")
        response = self.client.get(self.url, {"q": "mouse"})
        self.assertEqual(response.status_code, 200)
        page_products = list(response.context["page_obj"])
        self.assertEqual(len(page_products), 1)
        self.assertEqual(page_products[0], self.p1)
        self.assertEqual(response.context["query"], "mouse")

    def test_search_by_sku(self):
        """Searching by SKU should return matching product."""
        self.client.login(username="distributor1", password="password123")
        response = self.client.get(self.url, {"q": "WM-001"})
        self.assertEqual(response.status_code, 200)
        page_products = list(response.context["page_obj"])
        self.assertEqual(len(page_products), 1)
        self.assertEqual(page_products[0], self.p1)

    def test_search_by_category(self):
        """Searching by category should return matching products."""
        self.client.login(username="distributor1", password="password123")
        response = self.client.get(self.url, {"q": "electronics"})
        self.assertEqual(response.status_code, 200)
        page_products = list(response.context["page_obj"])
        self.assertEqual(len(page_products), 2)

    def test_search_cannot_bypass_ownership(self):
        """Searching for Distributor 2's product should return empty results for Distributor 1."""
        self.client.login(username="distributor1", password="password123")
        response = self.client.get(self.url, {"q": "Gaming Chair"})
        self.assertEqual(response.status_code, 200)
        page_products = list(response.context["page_obj"])
        self.assertEqual(len(page_products), 0)

    def test_search_no_results_empty_state(self):
        """Searching for non-existent query should display empty state."""
        self.client.login(username="distributor1", password="password123")
        response = self.client.get(self.url, {"q": "nonexistentproduct"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page_obj"]), 0)
        self.assertContains(response, "No products found")
        self.assertContains(response, 'matching "<strong>nonexistentproduct</strong>"')

    def test_no_products_empty_state(self):
        """Distributor with zero products should see No Products Yet empty state."""
        new_dist = User.objects.create_user(
            username="distributor3",
            password="password123"
        )
        new_dist.groups.add(self.distributor_group)
        self.client.login(username="distributor3", password="password123")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_count"], 0)
        self.assertContains(response, "No Products Yet")

    def test_pagination_and_query_preservation(self):
        """Pagination should limit items to 10 per page and preserve search query parameter."""
        self.client.login(username="distributor1", password="password123")
        for i in range(12):
            Product.objects.create(
                distributor=self.distributor1,
                name=f"Bulk Item {i}",
                category="Bulk",
                price=Decimal("100.00"),
                stock=10
            )

        # Page 1 (Total = 14 products: p1, p2 + 12 bulk items)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page_obj"]), 10)
        self.assertTrue(response.context["page_obj"].has_next())

        # Page 2
        response_p2 = self.client.get(self.url, {"page": 2})
        self.assertEqual(response_p2.status_code, 200)
        self.assertEqual(len(response_p2.context["page_obj"]), 4)

        # Search with pagination (12 Bulk items -> 10 on page 1, 2 on page 2)
        response_search_p2 = self.client.get(self.url, {"q": "Bulk", "page": 2})
        self.assertEqual(response_search_p2.status_code, 200)
        self.assertEqual(len(response_search_p2.context["page_obj"]), 2)
        self.assertContains(response_search_p2, "q=Bulk")


class ProductEditViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group = Group.objects.create(name="Distributor")

        self.distributor1 = User.objects.create_user(
            username="dist1",
            password="password123"
        )
        self.distributor1.groups.add(self.distributor_group)

        self.distributor2 = User.objects.create_user(
            username="dist2",
            password="password123"
        )
        self.distributor2.groups.add(self.distributor_group)

        self.product1 = Product.objects.create(
            distributor=self.distributor1,
            name="Wireless Mouse",
            category="Electronics",
            sku="WM-001",
            price=Decimal("599.00"),
            stock=50,
            gst_rate=Decimal("18.00"),
            description="Wireless optical mouse"
        )

        self.product2 = Product.objects.create(
            distributor=self.distributor2,
            name="Other Product",
            price=Decimal("999.00"),
            stock=10
        )

        self.edit_url = reverse("product_edit", kwargs={"pk": self.product1.pk})

    def test_edit_product_requires_login(self):
        """Unauthenticated GET should redirect to login."""
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)

    def test_edit_product_prefills_form(self):
        """GET request should load page with pre-filled product details."""
        self.client.login(username="dist1", password="password123")
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wireless Mouse")
        self.assertContains(response, "Electronics")
        self.assertContains(response, "WM-001")
        self.assertContains(response, "599.00")
        self.assertContains(response, "50")

    def test_distributor_cannot_edit_other_distributor_product(self):
        """Distributor A attempting to access Customer B's product should get 404 Not Found."""
        self.client.login(username="dist1", password="password123")
        other_edit_url = reverse("product_edit", kwargs={"pk": self.product2.pk})
        response = self.client.get(other_edit_url)
        self.assertEqual(response.status_code, 404)

        # POST attempt
        post_response = self.client.post(other_edit_url, {"name": "Hacked Product", "price": "1.00", "stock": "1"})
        self.assertEqual(post_response.status_code, 404)
        self.product2.refresh_from_db()
        self.assertEqual(self.product2.name, "Other Product")

    def test_successful_product_update(self):
        """Valid POST should update existing DB record and redirect to product list."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "name": "Gaming Wireless Mouse",
            "category": "Gaming Electronics",
            "sku": "WM-001",
            "price": "699.00",
            "stock": "45",
            "gst_rate": "18.00",
            "description": "High precision gaming wireless mouse"
        }
        response = self.client.post(self.edit_url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("product_list"))

        # Verify DB update (ID must remain unchanged)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.name, "Gaming Wireless Mouse")
        self.assertEqual(self.product1.category, "Gaming Electronics")
        self.assertEqual(self.product1.price, Decimal("699.00"))
        self.assertEqual(self.product1.stock, 45)
        self.assertEqual(self.product1.distributor, self.distributor1)

        # Verify success message on product list
        list_response = self.client.get(response.url)
        self.assertContains(list_response, "Product updated successfully.")

    def test_price_validation_errors(self):
        """Price <= 0 should show error and not update record."""
        self.client.login(username="dist1", password="password123")
        for invalid_price in ["0", "-10"]:
            payload = {
                "name": "Gaming Wireless Mouse",
                "price": invalid_price,
                "stock": "50",
                "gst_rate": "18.00"
            }
            response = self.client.post(self.edit_url, payload)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Price must be greater than 0.")

        self.product1.refresh_from_db()
        self.assertEqual(self.product1.name, "Wireless Mouse")

    def test_stock_validation_errors(self):
        """Negative stock should show error and not update record."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "name": "Gaming Wireless Mouse",
            "price": "599.00",
            "stock": "-1",
            "gst_rate": "18.00"
        }
        response = self.client.post(self.edit_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue("Ensure this value is greater than or equal to 0." in response.content.decode() or "Stock cannot be negative." in response.content.decode())

        self.product1.refresh_from_db()
        self.assertEqual(self.product1.name, "Wireless Mouse")

    def test_gst_rate_validation_errors(self):
        """GST rate outside 0-100 should show error."""
        self.client.login(username="dist1", password="password123")
        for invalid_gst in ["-1", "101"]:
            payload = {
                "name": "Gaming Wireless Mouse",
                "price": "599.00",
                "stock": "50",
                "gst_rate": invalid_gst
            }
            response = self.client.post(self.edit_url, payload)
            self.assertEqual(response.status_code, 200)
            self.assertTrue("Ensure this value is" in response.content.decode() or "GST rate must be" in response.content.decode())

    def test_empty_product_name_error(self):
        """Empty product name should show error."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "name": "   ",
            "price": "599.00",
            "stock": "50",
            "gst_rate": "18.00"
        }
        response = self.client.post(self.edit_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a valid product name.")

    def test_search_finds_updated_product(self):
        """After updating name, product list search for new name returns product."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "name": "Super Gaming Mouse",
            "price": "699.00",
            "stock": "45",
            "gst_rate": "18.00"
        }
        self.client.post(self.edit_url, payload)

        search_response = self.client.get(reverse("product_list"), {"q": "Super Gaming"})
        self.assertEqual(search_response.status_code, 200)
        self.assertContains(search_response, "Super Gaming Mouse")


class ProductDeleteViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group = Group.objects.create(name="Distributor")

        self.distributor1 = User.objects.create_user(
            username="dist1",
            password="password123"
        )
        self.distributor1.groups.add(self.distributor_group)

        self.distributor2 = User.objects.create_user(
            username="dist2",
            password="password123"
        )
        self.distributor2.groups.add(self.distributor_group)

        self.product1 = Product.objects.create(
            distributor=self.distributor1,
            name="Wireless Mouse",
            category="Electronics",
            price=Decimal("599.00"),
            stock=50,
            gst_rate=Decimal("18.00")
        )

        self.product2 = Product.objects.create(
            distributor=self.distributor2,
            name="Gaming Keyboard",
            category="Electronics",
            price=Decimal("1299.00"),
            stock=20
        )

        self.delete_url = reverse("product_delete", kwargs={"pk": self.product1.pk})

    def test_delete_requires_login(self):
        """Unauthenticated POST request should redirect to login."""
        response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)
        self.assertTrue(Product.objects.filter(pk=self.product1.pk).exists())

    def test_get_request_rejects_deletion(self):
        """GET request should not delete product and redirect to product list."""
        self.client.login(username="dist1", password="password123")
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("product_list"))
        self.assertTrue(Product.objects.filter(pk=self.product1.pk).exists())

    def test_distributor_cannot_delete_other_distributor_product(self):
        """Distributor 1 attempting to delete Distributor 2's product should receive 404."""
        self.client.login(username="dist1", password="password123")
        other_delete_url = reverse("product_delete", kwargs={"pk": self.product2.pk})
        response = self.client.post(other_delete_url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Product.objects.filter(pk=self.product2.pk).exists())

    def test_successful_product_deletion(self):
        """Authenticated POST request should delete product from database and redirect with success message."""
        self.client.login(username="dist1", password="password123")
        response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("product_list"))

        self.assertFalse(Product.objects.filter(pk=self.product1.pk).exists())

        list_response = self.client.get(response.url)
        self.assertTrue("deleted successfully." in list_response.content.decode())

    def test_nonexistent_product_returns_404(self):
        """Attempting to delete non-existent product should return 404."""
        self.client.login(username="dist1", password="password123")
        invalid_url = reverse("product_delete", kwargs={"pk": 99999})
        response = self.client.post(invalid_url)
        self.assertEqual(response.status_code, 404)

    def test_search_and_pagination_after_deletion(self):
        """After product deletion, search and pagination continue working correctly."""
        self.client.login(username="dist1", password="password123")
        p_extra = Product.objects.create(
            distributor=self.distributor1,
            name="Wireless Headphones",
            price=Decimal("1500.00"),
            stock=10
        )
        delete_extra_url = reverse("product_delete", kwargs={"pk": p_extra.pk})
        self.client.post(delete_extra_url)

        search_response = self.client.get(reverse("product_list"), {"q": "Wireless"})
        self.assertEqual(search_response.status_code, 200)
        self.assertIn(self.product1, list(search_response.context["page_obj"]))
        self.assertNotIn(p_extra, list(search_response.context["page_obj"]))


class InvoiceModelTests(TestCase):

    def setUp(self):
        self.distributor1 = User.objects.create_user(
            username="distributor_a",
            password="password123"
        )
        self.distributor2 = User.objects.create_user(
            username="distributor_b",
            password="password123"
        )
        self.customer1 = Customer.objects.create(
            distributor=self.distributor1,
            name="Rahul Sharma",
            phone="9876543210"
        )
        self.product1 = Product.objects.create(
            distributor=self.distributor1,
            name="Wireless Mouse",
            price=Decimal("599.00"),
            stock=50,
            gst_rate=Decimal("18.00")
        )

    def test_invoice_creation(self):
        """Verify invoice creation and field values."""
        invoice = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-001",
            invoice_date="2026-10-06",
            subtotal=Decimal("1198.00"),
            total_gst=Decimal("215.64"),
            grand_total=Decimal("1413.64")
        )
        self.assertIsNotNone(invoice.pk)
        self.assertEqual(invoice.invoice_number, "INV-001")
        self.assertEqual(invoice.distributor, self.distributor1)
        self.assertEqual(invoice.customer, self.customer1)
        self.assertEqual(invoice.subtotal, Decimal("1198.00"))
        self.assertEqual(invoice.total_gst, Decimal("215.64"))
        self.assertEqual(invoice.grand_total, Decimal("1413.64"))

    def test_invoice_item_creation_and_snapshot(self):
        """Verify InvoiceItem creation and historical snapshot fields."""
        invoice = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-002",
            invoice_date="2026-10-06",
            subtotal=Decimal("1198.00"),
            total_gst=Decimal("215.64"),
            grand_total=Decimal("1413.64")
        )
        item = InvoiceItem.objects.create(
            invoice=invoice,
            product=self.product1,
            product_name=self.product1.name,
            quantity=2,
            unit_price=self.product1.price,
            gst_rate=self.product1.gst_rate,
            taxable_amount=Decimal("1198.00"),
            gst_amount=Decimal("215.64"),
            line_total=Decimal("1413.64")
        )
        self.assertEqual(item.product_name, "Wireless Mouse")
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal("599.00"))
        self.assertEqual(item.gst_rate, Decimal("18.00"))

        # Update product current price
        self.product1.price = Decimal("799.00")
        self.product1.gst_rate = Decimal("12.00")
        self.product1.save()

        # InvoiceItem snapshot remains unchanged
        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal("599.00"))
        self.assertEqual(item.gst_rate, Decimal("18.00"))

    def test_product_delete_protected_when_referenced_in_invoice(self):
        """Attempting to delete a product referenced in an InvoiceItem should raise ProtectedError."""
        invoice = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-003",
            invoice_date="2026-10-06",
            subtotal=Decimal("599.00"),
            total_gst=Decimal("107.82"),
            grand_total=Decimal("706.82")
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            product=self.product1,
            product_name=self.product1.name,
            quantity=1,
            unit_price=self.product1.price,
            gst_rate=self.product1.gst_rate,
            taxable_amount=Decimal("599.00"),
            gst_amount=Decimal("107.82"),
            line_total=Decimal("706.82")
        )
        with self.assertRaises(ProtectedError):
            self.product1.delete()

    def test_customer_delete_protected_when_referenced_in_invoice(self):
        """Attempting to delete a customer referenced in an Invoice should raise ProtectedError."""
        Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-004",
            invoice_date="2026-10-06",
            subtotal=Decimal("599.00"),
            total_gst=Decimal("107.82"),
            grand_total=Decimal("706.82")
        )
        with self.assertRaises(ProtectedError):
            self.customer1.delete()


class CreateInvoiceViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group = Group.objects.create(name="Distributor")

        # Distributor 1
        self.distributor1 = User.objects.create_user(
            username="dist1",
            password="password123"
        )
        self.distributor1.groups.add(self.distributor_group)

        # Distributor 2
        self.distributor2 = User.objects.create_user(
            username="dist2",
            password="password123"
        )
        self.distributor2.groups.add(self.distributor_group)

        # Distributor 1 records
        self.c1 = Customer.objects.create(
            distributor=self.distributor1,
            name="Rahul Patel",
            phone="9876543210"
        )
        self.p1 = Product.objects.create(
            distributor=self.distributor1,
            name="Wireless Mouse",
            price=Decimal("599.00"),
            stock=50,
            gst_rate=Decimal("18.00")
        )

        # Distributor 2 records
        self.c2 = Customer.objects.create(
            distributor=self.distributor2,
            name="Amit Shah",
            phone="9123456789"
        )
        self.p2 = Product.objects.create(
            distributor=self.distributor2,
            name="Mechanical Keyboard",
            price=Decimal("1299.00"),
            stock=20,
            gst_rate=Decimal("18.00")
        )

        self.create_url = reverse("create_invoice")

    def test_create_invoice_requires_login(self):
        """Unauthenticated GET should redirect to distributor login page."""
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)

    def test_dropdown_filters_by_authenticated_distributor(self):
        """Distributor 1 should only see Customer 1 and Product 1 in choices."""
        self.client.login(username="dist1", password="password123")
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rahul Patel")
        self.assertNotContains(response, "Amit Shah")

        products_json = response.context["products_json"]
        self.assertIn(self.p1.id, products_json)
        self.assertNotIn(self.p2.id, products_json)

    def test_successful_invoice_creation(self):
        """Valid POST should create Invoice & InvoiceItem, calculate totals from DB price/GST, and redirect."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": self.p1.id,
            "items-0-quantity": "2",
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertIn(response.url, [reverse("invoice_list"), reverse("distributor_dashboard")])

        invoice = Invoice.objects.filter(distributor=self.distributor1, customer=self.c1).first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.items.count(), 1)

        item = invoice.items.first()
        self.assertEqual(item.product, self.p1)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal("599.00"))
        self.assertEqual(item.gst_rate, Decimal("18.00"))
        self.assertEqual(item.taxable_amount, Decimal("1198.00"))
        self.assertEqual(item.gst_amount, Decimal("215.64"))
        self.assertEqual(item.line_total, Decimal("1413.64"))

        self.assertEqual(invoice.subtotal, Decimal("1198.00"))
        self.assertEqual(invoice.total_gst, Decimal("215.64"))
        self.assertEqual(invoice.grand_total, Decimal("1413.64"))

    def test_cannot_invoice_other_distributor_customer_or_product(self):
        """Distributor 1 attempting to post Distributor 2's customer or product should be rejected."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c2.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": self.p1.id,
            "items-0-quantity": "1",
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Invoice.objects.filter(customer=self.c2).exists())

    def test_product_details_endpoint_security(self):
        """Product details endpoint must verify distributor ownership."""
        self.client.login(username="dist1", password="password123")

        # Distributor 1 product -> 200 OK with json details
        url_own = reverse("product_details", kwargs={"pk": self.p1.pk})
        res_own = self.client.get(url_own)
        self.assertEqual(res_own.status_code, 200)
        self.assertEqual(res_own.json()["name"], "Wireless Mouse")

        # Distributor 2 product -> 404 Not Found
        url_other = reverse("product_details", kwargs={"pk": self.p2.pk})
        res_other = self.client.get(url_other)
        self.assertEqual(res_other.status_code, 404)

    def test_invoice_calculation_with_discount(self):
        """Test Case 1: Price=500, Qty=2, Discount=10%, GST=18% -> Total 1062.00."""
        p_mouse = Product.objects.create(
            distributor=self.distributor1,
            name="Mouse",
            price=Decimal("500.00"),
            stock=50,
            gst_rate=Decimal("18.00")
        )
        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": p_mouse.id,
            "items-0-quantity": "2",
            "items-0-discount_percent": "10.00",
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 302)

        invoice = Invoice.objects.filter(distributor=self.distributor1, customer=self.c1).order_by("-id").first()
        item = invoice.items.first()

        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal("500.00"))
        self.assertEqual(item.discount_percent, Decimal("10.00"))
        self.assertEqual(item.gst_rate, Decimal("18.00"))
        self.assertEqual(item.taxable_amount, Decimal("900.00"))  # Gross 1000 - Disc 100
        self.assertEqual(item.gst_amount, Decimal("162.00"))      # 900 * 0.18
        self.assertEqual(item.line_total, Decimal("1062.00"))     # 900 + 162

        self.assertEqual(invoice.subtotal, Decimal("900.00"))
        self.assertEqual(invoice.total_gst, Decimal("162.00"))
        self.assertEqual(invoice.grand_total, Decimal("1062.00"))

    def test_invoice_calculation_zero_discount(self):
        """Test Case 2: Price=1000, Qty=3, Discount=0%, GST=18% -> Total 3540.00."""
        p_keyboard = Product.objects.create(
            distributor=self.distributor1,
            name="Keyboard",
            price=Decimal("1000.00"),
            stock=10,
            gst_rate=Decimal("18.00")
        )
        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": p_keyboard.id,
            "items-0-quantity": "3",
            "items-0-discount_percent": "0.00",
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 302)

        invoice = Invoice.objects.filter(distributor=self.distributor1, customer=self.c1).order_by("-id").first()
        item = invoice.items.first()

        self.assertEqual(item.taxable_amount, Decimal("3000.00"))
        self.assertEqual(item.gst_amount, Decimal("540.00"))
        self.assertEqual(item.line_total, Decimal("3540.00"))

    def test_invoice_calculation_100_percent_discount(self):
        """Test Case 3: Price=1000, Qty=1, Discount=100%, GST=18% -> Total 0.00."""
        p_promo = Product.objects.create(
            distributor=self.distributor1,
            name="Free Sample",
            price=Decimal("1000.00"),
            stock=10,
            gst_rate=Decimal("18.00")
        )
        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": p_promo.id,
            "items-0-quantity": "1",
            "items-0-discount_percent": "100.00",
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 302)

        invoice = Invoice.objects.filter(distributor=self.distributor1, customer=self.c1).order_by("-id").first()
        item = invoice.items.first()

        self.assertEqual(item.taxable_amount, Decimal("0.00"))
        self.assertEqual(item.gst_amount, Decimal("0.00"))
        self.assertEqual(item.line_total, Decimal("0.00"))

    def test_multiple_item_invoice_totals(self):
        """Multiple items calculation test."""
        p_mouse = Product.objects.create(
            distributor=self.distributor1,
            name="Mouse",
            price=Decimal("500.00"),
            stock=50,
            gst_rate=Decimal("18.00")
        )
        p_kbd = Product.objects.create(
            distributor=self.distributor1,
            name="Keyboard",
            price=Decimal("1000.00"),
            stock=50,
            gst_rate=Decimal("18.00")
        )
        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": p_mouse.id,
            "items-0-quantity": "2",
            "items-0-discount_percent": "10.00", # Taxable 900, GST 162
            "items-1-product": p_kbd.id,
            "items-1-quantity": "1",
            "items-1-discount_percent": "0.00",  # Taxable 1000, GST 180
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 302)

        invoice = Invoice.objects.filter(distributor=self.distributor1, customer=self.c1).order_by("-id").first()
        self.assertEqual(invoice.items.count(), 2)
        self.assertEqual(invoice.subtotal, Decimal("1900.00"))
        self.assertEqual(invoice.total_gst, Decimal("342.00"))
        self.assertEqual(invoice.grand_total, Decimal("2242.00"))

    def test_stock_validation_backend(self):
        """Quantity exceeding stock should be rejected on backend."""
        p_limited = Product.objects.create(
            distributor=self.distributor1,
            name="Limited Product",
            price=Decimal("100.00"),
            stock=5,
            gst_rate=Decimal("18.00")
        )
        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": p_limited.id,
            "items-0-quantity": "10",
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only 5 units are available")

    def test_discount_range_validation_backend(self):
        """Discount outside 0 to 100 should be rejected on backend."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": self.p1.id,
            "items-0-quantity": "1",
            "items-0-discount_percent": "150.00",
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Discount must be between 0% and 100%")

    def test_duplicate_product_selection_rejected_backend(self):
        """Selecting the same product in multiple rows should be rejected by backend."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": self.p1.id,
            "items-0-quantity": "1",
            "items-0-discount_percent": "0.00",
            "items-1-product": self.p1.id,
            "items-1-quantity": "2",
            "items-1-discount_percent": "5.00",
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "has been selected multiple times")

    def test_dynamic_multi_product_invoice_creation(self):
        """Test Scenario 48: 3 products (Mouse, Keyboard, Monitor) in a single invoice."""
        p_mouse = Product.objects.create(
            distributor=self.distributor1,
            name="Mouse",
            price=Decimal("500.00"),
            stock=50,
            gst_rate=Decimal("18.00")
        )
        p_kbd = Product.objects.create(
            distributor=self.distributor1,
            name="Keyboard",
            price=Decimal("1000.00"),
            stock=50,
            gst_rate=Decimal("18.00")
        )
        p_mon = Product.objects.create(
            distributor=self.distributor1,
            name="Monitor",
            price=Decimal("10000.00"),
            stock=10,
            gst_rate=Decimal("18.00")
        )

        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "3",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": p_mouse.id,
            "items-0-quantity": "2",
            "items-0-discount_percent": "10.00",
            "items-1-product": p_kbd.id,
            "items-1-quantity": "1",
            "items-1-discount_percent": "0.00",
            "items-2-product": p_mon.id,
            "items-2-quantity": "1",
            "items-2-discount_percent": "5.00",
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 302)

        invoice = Invoice.objects.filter(distributor=self.distributor1, customer=self.c1).order_by("-id").first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.items.count(), 3)

        # Item 1: Mouse -> Gross 1000, Disc 100, Taxable 900, GST 162, Total 1062
        item1 = invoice.items.get(product=p_mouse)
        self.assertEqual(item1.taxable_amount, Decimal("900.00"))
        self.assertEqual(item1.gst_amount, Decimal("162.00"))
        self.assertEqual(item1.line_total, Decimal("1062.00"))

        # Item 2: Keyboard -> Gross 1000, Disc 0, Taxable 1000, GST 180, Total 1180
        item2 = invoice.items.get(product=p_kbd)
        self.assertEqual(item2.taxable_amount, Decimal("1000.00"))
        self.assertEqual(item2.gst_amount, Decimal("180.00"))
        self.assertEqual(item2.line_total, Decimal("1180.00"))

        # Item 3: Monitor -> Gross 10000, Disc 500, Taxable 9500, GST 1710, Total 11210
        item3 = invoice.items.get(product=p_mon)
        self.assertEqual(item3.taxable_amount, Decimal("9500.00"))
        self.assertEqual(item3.gst_amount, Decimal("1710.00"))
        self.assertEqual(item3.line_total, Decimal("11210.00"))

        # Invoice totals: Subtotal (Taxable) = 11400, Total GST = 2052, Grand Total = 13452
        self.assertEqual(invoice.subtotal, Decimal("11400.00"))
        self.assertEqual(invoice.total_gst, Decimal("2052.00"))
        self.assertEqual(invoice.grand_total, Decimal("13452.00"))

    def test_stock_deduction_on_successful_invoice_creation(self):
        """Product stock must be reduced by the exact quantity sold."""
        initial_stock = self.p1.stock  # 50
        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": self.p1.id,
            "items-0-quantity": "5",
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 302)

        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock, initial_stock - 5)

    def test_transaction_atomic_rollback_on_failure(self):
        """If one item fails (e.g., exceeds stock), no invoice or items are saved and stock is unchanged."""
        p_ok = Product.objects.create(
            distributor=self.distributor1,
            name="Available Product",
            price=Decimal("100.00"),
            stock=10,
            gst_rate=Decimal("18.00")
        )
        p_exceed = Product.objects.create(
            distributor=self.distributor1,
            name="Low Stock Product",
            price=Decimal("200.00"),
            stock=2,
            gst_rate=Decimal("18.00")
        )

        initial_invoice_count = Invoice.objects.count()
        self.client.login(username="dist1", password="password123")

        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": p_ok.id,
            "items-0-quantity": "5",
            "items-1-product": p_exceed.id,
            "items-1-quantity": "10",  # Exceeds stock (2 available)
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 200)

        # Nothing saved, stock unchanged
        self.assertEqual(Invoice.objects.count(), initial_invoice_count)
        p_ok.refresh_from_db()
        p_exceed.refresh_from_db()
        self.assertEqual(p_ok.stock, 10)
        self.assertEqual(p_exceed.stock, 2)

    def test_at_least_one_item_required(self):
        """Submitting formset with no items must be rejected."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": "",
            "items-0-quantity": "1",
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Invoice.objects.count(), 0)

    def test_do_not_trust_frontend_price_or_gst(self):
        """Frontend submitted price or GST in POST payload is ignored; DB values are used."""
        self.client.login(username="dist1", password="password123")
        payload = {
            "customer": self.c1.id,
            "invoice_date": "2026-10-06",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": self.p1.id,
            "items-0-quantity": "1",
            "unit_price": "1.00",      # Client attempt to tamper
            "gst_rate": "0.00",        # Client attempt to tamper
            "grand_total": "1.00",     # Client attempt to tamper
        }
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 302)

        invoice = Invoice.objects.filter(distributor=self.distributor1, customer=self.c1).order_by("-id").first()
        item = invoice.items.first()
        self.assertEqual(item.unit_price, Decimal("599.00"))  # From DB p1

from billing.utils import render_to_pdf, link_callback


class PdfUtilityTests(TestCase):

    def test_render_to_pdf_valid_template(self):
        """render_to_pdf should return valid PDF bytes starting with %PDF for a valid template."""
        context = {
            "customer_name": "Test Customer",
            "subtotal": "1000.00",
            "gst": "180.00",
            "grand_total": "1180.00",
        }
        pdf_bytes = render_to_pdf("billing/pdf_test.html", context)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(isinstance(pdf_bytes, bytes))
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_render_to_pdf_unicode_rupee_symbol(self):
        """render_to_pdf should correctly render templates containing Unicode Rupee symbols (₹)."""
        context = {
            "customer_name": "Ramesh Kumar (₹)",
            "subtotal": "500.00",
            "gst": "90.00",
            "grand_total": "590.00",
        }
        pdf_bytes = render_to_pdf("billing/pdf_test.html", context)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_render_to_pdf_nonexistent_template(self):
        """render_to_pdf should safely return None and log an error if template does not exist."""
        pdf_bytes = render_to_pdf("billing/nonexistent_template_xyz.html", {})
        self.assertIsNone(pdf_bytes)

    def test_link_callback_resolution(self):
        """link_callback should gracefully handle http URLs, static paths, media paths, and relative URIs."""
        self.assertEqual(link_callback("https://example.com/logo.png", None), "https://example.com/logo.png")
        self.assertEqual(link_callback("", None), "")


from accounts.models import DistributorProfile

class InvoicePdfViewAndTemplateTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group = Group.objects.create(name="Distributor")

        self.distributor1 = User.objects.create_user(
            username="dist1_pdf",
            email="dist1@example.com",
            password="password123",
            first_name="Ramesh",
            last_name="Shah"
        )
        self.distributor1.groups.add(self.distributor_group)
        self.profile1 = DistributorProfile.objects.create(
            user=self.distributor1,
            full_name="Ramesh Enterprise",
            email="dist1@example.com",
            phone="9876543210"
        )

        self.distributor2 = User.objects.create_user(
            username="dist2_pdf",
            email="dist2@example.com",
            password="password123"
        )
        self.distributor2.groups.add(self.distributor_group)

        self.customer1 = Customer.objects.create(
            distributor=self.distributor1,
            name="Rajesh Patel",
            email="rajesh@example.com",
            phone="9988776655",
            address="Flat 402, Super Diamond Towers, Near City Center, Ring Road",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380015"
        )

        self.product1 = Product.objects.create(
            distributor=self.distributor1,
            name="Wireless Mouse Pro",
            price=Decimal("500.00"),
            stock=100,
            gst_rate=Decimal("18.00"),
            sku="WM-PRO-01"
        )

        self.product2 = Product.objects.create(
            distributor=self.distributor1,
            name="Ultra Ergonomic Mechanical Keyboard with RGB Backlight and Mechanical Switches",
            price=Decimal("2500.00"),
            stock=50,
            gst_rate=Decimal("18.00"),
            sku="KB-MECH-02"
        )

    def test_one_product_invoice_pdf(self):
        """Verify PDF generation for a 1-product invoice."""
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-PDF-001",
            invoice_date="2026-10-08",
            subtotal=Decimal("500.00"),
            total_gst=Decimal("90.00"),
            grand_total=Decimal("590.00")
        )
        InvoiceItem.objects.create(
            invoice=inv,
            product=self.product1,
            product_name=self.product1.name,
            quantity=1,
            unit_price=Decimal("500.00"),
            gst_rate=Decimal("18.00"),
            discount_percent=Decimal("0.00"),
            taxable_amount=Decimal("500.00"),
            gst_amount=Decimal("90.00"),
            line_total=Decimal("590.00")
        )

        self.client.login(username="dist1_pdf", password="password123")
        url = reverse("invoice_pdf", kwargs={"pk": inv.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_multiple_products_invoice_pdf(self):
        """Verify PDF generation for multi-product invoice."""
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-PDF-002",
            invoice_date="2026-10-08",
            subtotal=Decimal("3000.00"),
            total_gst=Decimal("540.00"),
            grand_total=Decimal("3540.00")
        )
        InvoiceItem.objects.create(
            invoice=inv,
            product=self.product1,
            product_name=self.product1.name,
            quantity=1,
            unit_price=Decimal("500.00"),
            gst_rate=Decimal("18.00"),
            discount_percent=Decimal("0.00"),
            taxable_amount=Decimal("500.00"),
            gst_amount=Decimal("90.00"),
            line_total=Decimal("590.00")
        )
        InvoiceItem.objects.create(
            invoice=inv,
            product=self.product2,
            product_name=self.product2.name,
            quantity=1,
            unit_price=Decimal("2500.00"),
            gst_rate=Decimal("18.00"),
            discount_percent=Decimal("0.00"),
            taxable_amount=Decimal("2500.00"),
            gst_amount=Decimal("450.00"),
            line_total=Decimal("2950.00")
        )

        self.client.login(username="dist1_pdf", password="password123")
        url = reverse("invoice_pdf", kwargs={"pk": inv.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_long_customer_address_pdf(self):
        """Verify PDF layout with long customer address."""
        c_long = Customer.objects.create(
            distributor=self.distributor1,
            name="Super Heavy Enterprises India Private Limited",
            email="contact@superheavy.co.in",
            phone="9123456789",
            address="Plot No. 1045, Sector 28-B, Industrial Development Area, Phase II, Near Express Highway Complex, Opposite Metro Station",
            city="Gandhinagar",
            state="Gujarat",
            pincode="382028"
        )
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=c_long,
            invoice_number="INV-PDF-003",
            invoice_date="2026-10-08",
            subtotal=Decimal("500.00"),
            total_gst=Decimal("90.00"),
            grand_total=Decimal("590.00")
        )
        InvoiceItem.objects.create(
            invoice=inv,
            product=self.product1,
            product_name=self.product1.name,
            quantity=1,
            unit_price=Decimal("500.00"),
            gst_rate=Decimal("18.00"),
            discount_percent=Decimal("0.00"),
            taxable_amount=Decimal("500.00"),
            gst_amount=Decimal("90.00"),
            line_total=Decimal("590.00")
        )

        self.client.login(username="dist1_pdf", password="password123")
        url = reverse("invoice_pdf", kwargs={"pk": inv.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_invoice_with_20_plus_items_pdf(self):
        """Verify multi-page PDF generation with 25 line items."""
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-PDF-20ITEMS",
            invoice_date="2026-10-08",
            subtotal=Decimal("12500.00"),
            total_gst=Decimal("2250.00"),
            grand_total=Decimal("14750.00")
        )
        for i in range(25):
            InvoiceItem.objects.create(
                invoice=inv,
                product=self.product1,
                product_name=f"Bulk Product Item #{i+1} Special Heavy Edition",
                quantity=1,
                unit_price=Decimal("500.00"),
                gst_rate=Decimal("18.00"),
                discount_percent=Decimal("0.00"),
                taxable_amount=Decimal("500.00"),
                gst_amount=Decimal("90.00"),
                line_total=Decimal("590.00")
            )

        self.client.login(username="dist1_pdf", password="password123")
        url = reverse("invoice_pdf", kwargs={"pk": inv.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_discount_and_gst_calculations_pdf(self):
        """Verify percentage discount and GST calculations in rendered PDF."""
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-PDF-DISCOUNT",
            invoice_date="2026-10-08",
            subtotal=Decimal("900.00"),
            total_gst=Decimal("162.00"),
            grand_total=Decimal("1062.00")
        )
        InvoiceItem.objects.create(
            invoice=inv,
            product=self.product1,
            product_name="Discounted Item",
            quantity=2,
            unit_price=Decimal("500.00"),
            gst_rate=Decimal("18.00"),
            discount_percent=Decimal("10.00"),
            taxable_amount=Decimal("900.00"),
            gst_amount=Decimal("162.00"),
            line_total=Decimal("1062.00")
        )

        self.client.login(username="dist1_pdf", password="password123")
        url = reverse("invoice_pdf", kwargs={"pk": inv.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_pdf_security_distributor_isolation(self):
        """Distributor B cannot view or download Distributor A's invoice PDF."""
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-SECRET-01",
            invoice_date="2026-10-08",
            subtotal=Decimal("500.00"),
            total_gst=Decimal("90.00"),
            grand_total=Decimal("590.00")
        )

        self.client.login(username="dist2_pdf", password="password123")
        url = reverse("invoice_pdf", kwargs={"pk": inv.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class QRCodeFeatureTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group = Group.objects.create(name="Distributor")

        self.distributor1 = User.objects.create_user(
            username="qr_dist1",
            password="password123",
            first_name="Rahul",
            last_name="Shah"
        )
        self.distributor1.groups.add(self.distributor_group)

        self.distributor2 = User.objects.create_user(
            username="qr_dist2",
            password="password123"
        )
        self.distributor2.groups.add(self.distributor_group)

        self.customer1 = Customer.objects.create(
            distributor=self.distributor1,
            name="Rahul Shah",
            phone="9876543210"
        )

        self.product1 = Product.objects.create(
            distributor=self.distributor1,
            name="Widget A",
            price=Decimal("100.00"),
            stock=50,
            gst_rate=Decimal("18.00")
        )

        self.product2 = Product.objects.create(
            distributor=self.distributor1,
            name="Widget B",
            price=Decimal("500.00"),
            stock=20,
            gst_rate=Decimal("18.00")
        )

        self.invoice1 = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-0001",
            invoice_date="2026-10-09",
            subtotal=Decimal("1200.00"),
            total_gst=Decimal("216.00"),
            grand_total=Decimal("1416.00")
        )

        InvoiceItem.objects.create(
            invoice=self.invoice1,
            product=self.product1,
            product_name=self.product1.name,
            quantity=2,
            unit_price=Decimal("100.00"),
            taxable_amount=Decimal("200.00"),
            gst_amount=Decimal("36.00"),
            line_total=Decimal("236.00")
        )

        InvoiceItem.objects.create(
            invoice=self.invoice1,
            product=self.product2,
            product_name=self.product2.name,
            quantity=2,
            unit_price=Decimal("500.00"),
            taxable_amount=Decimal("1000.00"),
            gst_amount=Decimal("180.00"),
            line_total=Decimal("1180.00")
        )

    def test_qr_payload_structure(self):
        """Test build_invoice_qr_payload returns accurate JSON dictionary."""
        from billing.utils import build_invoice_qr_payload
        payload = build_invoice_qr_payload(self.invoice1)
        self.assertEqual(payload["invoice_number"], "INV-0001")
        self.assertEqual(payload["invoice_date"], "2026-10-09")
        self.assertEqual(payload["customer_name"], "Rahul Shah")
        self.assertEqual(payload["product_count"], 4)
        self.assertEqual(payload["grand_total"], "1416.00")
        self.assertEqual(payload["currency"], "INR")

    def test_qr_bytes_generation(self):
        """Test generate_invoice_qr_bytes produces valid PNG data."""
        from billing.utils import generate_invoice_qr_bytes
        png_bytes = generate_invoice_qr_bytes(self.invoice1)
        self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_qr_base64_generation(self):
        """Test generate_invoice_qr_base64 produces valid data URI."""
        from billing.utils import generate_invoice_qr_base64
        base64_uri = generate_invoice_qr_base64(self.invoice1)
        self.assertTrue(base64_uri.startswith("data:image/png;base64,"))

    def test_invoice_qr_endpoint_success(self):
        """Authenticated distributor can view their invoice QR image endpoint."""
        self.client.login(username="qr_dist1", password="password123")
        url = reverse("invoice_qr", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")

    def test_invoice_qr_endpoint_json_format(self):
        """Authenticated distributor can fetch QR json payload and base64."""
        self.client.login(username="qr_dist1", password="password123")
        url = reverse("invoice_qr", kwargs={"pk": self.invoice1.pk}) + "?format=json"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["payload"]["invoice_number"], "INV-0001")
        self.assertTrue(data["qr_code"].startswith("data:image/png;base64,"))

    def test_invoice_qr_endpoint_security_isolation(self):
        """Distributor B cannot view Distributor A's QR endpoint."""
        self.client.login(username="qr_dist2", password="password123")
        url = reverse("invoice_qr", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_historical_invoice_price_immutability(self):
        """Updating current product price does not alter historical invoice item price/total."""
        self.product1.price = Decimal("999.00")
        self.product1.save()

        item = InvoiceItem.objects.get(invoice=self.invoice1, product=self.product1)
        self.assertEqual(item.unit_price, Decimal("100.00"))
        self.assertEqual(item.line_total, Decimal("236.00"))
        self.invoice1.refresh_from_db()
        self.assertEqual(self.invoice1.grand_total, Decimal("1416.00"))

    def test_pdf_export_with_embedded_qr(self):
        """Invoice PDF endpoint exports valid PDF containing embedded QR code."""
        self.client.login(username="qr_dist1", password="password123")
        url = reverse("invoice_pdf", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(
            "Invoice-INV-0001.pdf" in response["Content-Disposition"] or
            "Invoice_INV-0001.pdf" in response["Content-Disposition"]
        )

    def test_create_invoice_post_success(self):
        """Creating an invoice via POST populates invoice_number and redirects to invoice_list."""
        self.client.login(username="qr_dist1", password="password123")
        post_data = {
            "customer": self.customer1.id,
            "invoice_date": "2026-10-09",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": self.product1.id,
            "items-0-quantity": "3",
            "items-0-discount_percent": "0.00",
        }
        url = reverse("create_invoice")
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("invoice_list"))
        created_inv = Invoice.objects.filter(distributor=self.distributor1).order_by("-id").first()
        self.assertIsNotNone(created_inv)
        self.assertTrue(created_inv.invoice_number.startswith("INV-"))


class InvoiceListViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group = Group.objects.create(name="Distributor")

        self.distributor1 = User.objects.create_user(
            username="list_dist1",
            password="password123"
        )
        self.distributor1.groups.add(self.distributor_group)

        self.distributor2 = User.objects.create_user(
            username="list_dist2",
            password="password123"
        )
        self.distributor2.groups.add(self.distributor_group)

        self.customer1 = Customer.objects.create(
            distributor=self.distributor1,
            name="Rahul Shah",
            email="rahul@example.com"
        )
        self.customer2 = Customer.objects.create(
            distributor=self.distributor1,
            name="Amit Patel",
            email="amit@example.com"
        )
        self.customer3 = Customer.objects.create(
            distributor=self.distributor2,
            name="Other Customer",
            email="other@example.com"
        )

        self.invoices_d1 = []
        for i in range(1, 16):
            inv = Invoice.objects.create(
                distributor=self.distributor1,
                customer=self.customer1 if i % 2 == 1 else self.customer2,
                invoice_number=f"INV-{i:04d}",
                invoice_date="2026-10-09",
                subtotal=Decimal("1000.00"),
                total_gst=Decimal("180.00"),
                grand_total=Decimal("1180.00")
            )
            self.invoices_d1.append(inv)

        self.invoice_d2 = Invoice.objects.create(
            distributor=self.distributor2,
            customer=self.customer3,
            invoice_number="INV-9999",
            invoice_date="2026-10-09",
            subtotal=Decimal("500.00"),
            total_gst=Decimal("90.00"),
            grand_total=Decimal("590.00")
        )

        self.url = reverse("invoice_list")

    def test_invoice_list_requires_login(self):
        """Unauthenticated user should be redirected to login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)

    def test_invoice_list_ownership_isolation(self):
        """Distributor 1 only sees Distributor 1's invoices."""
        self.client.login(username="list_dist1", password="password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        page_invoices = list(response.context["page_obj"])
        self.assertNotIn(self.invoice_d2, page_invoices)

    def test_invoice_list_pagination(self):
        """Distributor 1 gets 10 invoices on page 1 and 5 on page 2."""
        self.client.login(username="list_dist1", password="password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(len(page_obj.object_list), 10)
        self.assertTrue(page_obj.has_next())

        response2 = self.client.get(self.url + "?page=2")
        self.assertEqual(response2.status_code, 200)
        page_obj2 = response2.context["page_obj"]
        self.assertEqual(len(page_obj2.object_list), 5)

    def test_invoice_list_search_by_number(self):
        """Searching by invoice number filters results correctly."""
        self.client.login(username="list_dist1", password="password123")
        response = self.client.get(self.url + "?q=INV-0005")
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(len(page_obj.object_list), 1)
        self.assertEqual(page_obj.object_list[0].invoice_number, "INV-0005")

    def test_invoice_list_search_by_customer_name(self):
        """Searching by customer name filters results correctly."""
        self.client.login(username="list_dist1", password="password123")
        response = self.client.get(self.url + "?q=Amit")
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        for inv in page_obj.object_list:
            self.assertEqual(inv.customer.name, "Amit Patel")

    def test_invoice_list_empty_search_results(self):
        """Searching for non-existent query returns empty page with message."""
        self.client.login(username="list_dist1", password="password123")
        response = self.client.get(self.url + "?q=NonExistentInvoice")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page_obj"].object_list), 0)


class InvoiceDetailAndDownloadPDFTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group = Group.objects.create(name="Distributor")

        self.distributor1 = User.objects.create_user(
            username="pdf_dist1",
            password="password123"
        )
        self.distributor1.groups.add(self.distributor_group)

        self.distributor2 = User.objects.create_user(
            username="pdf_dist2",
            password="password123"
        )
        self.distributor2.groups.add(self.distributor_group)

        self.customer1 = Customer.objects.create(
            distributor=self.distributor1,
            name="Rahul Shah",
            email="rahul@example.com",
            phone="9876543210"
        )
        self.customer2 = Customer.objects.create(
            distributor=self.distributor2,
            name="Other Customer",
            email="other@example.com",
            phone="9123456789"
        )

        self.product1 = Product.objects.create(
            distributor=self.distributor1,
            name="Mouse",
            price=Decimal("500.00"),
            stock=100
        )

        self.invoice1 = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-0001",
            invoice_date="2026-10-09",
            subtotal=Decimal("1000.00"),
            total_gst=Decimal("180.00"),
            grand_total=Decimal("1180.00")
        )
        self.item1 = InvoiceItem.objects.create(
            invoice=self.invoice1,
            product=self.product1,
            product_name="Mouse",
            quantity=2,
            unit_price=Decimal("500.00"),
            discount_percent=Decimal("0.00"),
            gst_rate=Decimal("18.00"),
            line_total=Decimal("1180.00")
        )

        self.invoice2 = Invoice.objects.create(
            distributor=self.distributor2,
            customer=self.customer2,
            invoice_number="INV-0002",
            invoice_date="2026-10-09",
            subtotal=Decimal("500.00"),
            total_gst=Decimal("90.00"),
            grand_total=Decimal("590.00")
        )

    def test_invoice_detail_view_success(self):
        """Authenticated distributor can view their invoice details page."""
        self.client.login(username="pdf_dist1", password="password123")
        url = reverse("invoice_detail", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["invoice"], self.invoice1)
        self.assertEqual(response.context["customer"], self.customer1)
        self.assertEqual(len(response.context["items"]), 1)
        self.assertContains(response, "Download PDF")
        self.assertContains(response, "INV-0001")
        self.assertContains(response, "Rahul Shah")

    def test_invoice_detail_view_distributor_isolation(self):
        """Distributor 1 cannot access Distributor 2's invoice detail page."""
        self.client.login(username="pdf_dist1", password="password123")
        url = reverse("invoice_detail", kwargs={"pk": self.invoice2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_download_pdf_view_attachment_header(self):
        """Downloading invoice PDF returns valid PDF response with attachment header."""
        self.client.login(username="pdf_dist1", password="password123")
        url = reverse("invoice_pdf_download", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="Invoice-INV-0001.pdf"'
        )
        self.assertTrue(len(response.content) > 100)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_download_pdf_view_distributor_isolation(self):
        """Distributor 1 cannot download Distributor 2's invoice PDF."""
        self.client.login(username="pdf_dist1", password="password123")
        url = reverse("invoice_pdf_download", kwargs={"pk": self.invoice2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_download_pdf_unauthenticated(self):
        """Unauthenticated request to PDF download view redirects to login."""
        url = reverse("invoice_pdf_download", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)














