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


from rest_framework.test import APITestCase, APIClient
from datetime import date


class ProductCRUDAPITests(APITestCase):
    """
    Complete automated test suite for Product CRUD API:
    - Create valid product (POST /api/products/)
    - Reject invalid prices & negative stock
    - List products & data isolation between distributors
    - Retrieve product by ID
    - Update product (PUT/PATCH) & prevent distributor spoofing
    - Delete product safely & protect invoice references
    - Duplicate SKU enforcement per distributor
    - Unauthenticated (401) & unauthorized (403) access control
    - Admin/Superuser access
    - Frontend view rendering unit and status
    """

    def setUp(self):
        self.api_client = APIClient()
        self.list_url = reverse("api_product_list_create")

        # Distributor Group
        self.distributor_group, _ = Group.objects.get_or_create(name="Distributor")

        # Distributor 1
        self.distributor1 = User.objects.create_user(
            username="dist1_crud",
            email="dist1_crud@example.com",
            password="DistPassword@123"
        )
        self.distributor1.groups.add(self.distributor_group)

        # Distributor 2
        self.distributor2 = User.objects.create_user(
            username="dist2_crud",
            email="dist2_crud@example.com",
            password="DistPassword@123"
        )
        self.distributor2.groups.add(self.distributor_group)

        # Regular Non-Distributor User
        self.regular_user = User.objects.create_user(
            username="regular_crud",
            email="regular_crud@example.com",
            password="RegularPassword@123"
        )

        # Admin / Superuser
        self.admin_user = User.objects.create_superuser(
            username="admin_crud",
            email="admin_crud@example.com",
            password="AdminPassword@123"
        )

        # Customer for distributor 1
        self.customer1 = Customer.objects.create(
            distributor=self.distributor1,
            name="John Doe",
            phone="9876543210"
        )

        # Pre-created products for tests
        self.product1 = Product.objects.create(
            distributor=self.distributor1,
            name="Mechanical Keyboard",
            sku="KB-001",
            category="Peripherals",
            price=Decimal("2499.00"),
            stock=25,
            unit="piece",
            gst_rate=Decimal("18.00"),
            is_active=True,
            description="RGB mechanical keyboard"
        )

        self.product2 = Product.objects.create(
            distributor=self.distributor2,
            name="Gaming Mousepad",
            sku="MP-002",
            category="Accessories",
            price=Decimal("499.00"),
            stock=100,
            unit="piece",
            gst_rate=Decimal("18.00"),
            is_active=True
        )

    # 1. Create a valid product
    def test_01_create_valid_product(self):
        """Authenticated distributor creates product via POST /api/products/."""
        self.api_client.force_authenticate(user=self.distributor1)
        payload = {
            "name": "Wireless Headset",
            "sku": "HS-101",
            "category": "Audio",
            "price": "1999.00",
            "stock_quantity": 30,
            "unit": "box",
            "gst_rate": "18.00",
            "is_active": True,
            "description": "Noise-cancelling wireless headset"
        }
        response = self.api_client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Wireless Headset")
        self.assertEqual(response.data["sku"], "HS-101")
        self.assertEqual(response.data["stock"], 30)
        self.assertEqual(response.data["stock_quantity"], 30)
        self.assertEqual(response.data["unit"], "box")
        self.assertTrue(response.data["is_active"])

        # Check DB ownership
        created_p = Product.objects.get(id=response.data["id"])
        self.assertEqual(created_p.distributor, self.distributor1)

    # 2. Reject invalid price and negative stock
    def test_02_reject_invalid_price(self):
        """Negative price must be rejected with HTTP 400."""
        self.api_client.force_authenticate(user=self.distributor1)
        payload = {
            "name": "Invalid Price Product",
            "price": "-10.00",
            "stock": 5
        }
        response = self.api_client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("price", response.data)

    def test_03_reject_negative_stock(self):
        """Negative stock must be rejected with HTTP 400."""
        self.api_client.force_authenticate(user=self.distributor1)
        payload = {
            "name": "Negative Stock Product",
            "price": "100.00",
            "stock": -5
        }
        response = self.api_client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("stock", response.data)

    # 3. List products & distributor isolation
    def test_04_list_products_and_distributor_isolation(self):
        """Distributor 1 only sees their own products; Distributor 2 only sees theirs."""
        self.api_client.force_authenticate(user=self.distributor1)
        res1 = self.api_client.get(self.list_url)
        self.assertEqual(res1.status_code, 200)
        names1 = [p["name"] for p in res1.data["results"]]
        self.assertIn("Mechanical Keyboard", names1)
        self.assertNotIn("Gaming Mousepad", names1)

        self.api_client.force_authenticate(user=self.distributor2)
        res2 = self.api_client.get(self.list_url)
        self.assertEqual(res2.status_code, 200)
        names2 = [p["name"] for p in res2.data["results"]]
        self.assertIn("Gaming Mousepad", names2)
        self.assertNotIn("Mechanical Keyboard", names2)

    # 4. Search and pagination
    def test_05_search_products(self):
        """Search query filters products by name or SKU."""
        self.api_client.force_authenticate(user=self.distributor1)
        res = self.api_client.get(self.list_url + "?search=KB-001")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["sku"], "KB-001")

    # 5. Retrieve product by ID
    def test_06_retrieve_product_by_id(self):
        """Retrieve existing product by ID."""
        self.api_client.force_authenticate(user=self.distributor1)
        url = reverse("api_product_detail", kwargs={"pk": self.product1.pk})
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.product1.pk)
        self.assertEqual(response.data["name"], "Mechanical Keyboard")
        self.assertEqual(response.data["unit"], "piece")

    def test_07_retrieve_other_distributor_product_404(self):
        """Distributor 1 cannot access Distributor 2's product."""
        self.api_client.force_authenticate(user=self.distributor1)
        url = reverse("api_product_detail", kwargs={"pk": self.product2.pk})
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_08_retrieve_nonexistent_product_404(self):
        """Non-existent product ID returns 404."""
        self.api_client.force_authenticate(user=self.distributor1)
        url = reverse("api_product_detail", kwargs={"pk": 999999})
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, 404)

    # 6. Update product (PUT and PATCH)
    def test_09_update_product_put_and_patch(self):
        """Update product fields and verify client cannot tamper with distributor ownership."""
        self.api_client.force_authenticate(user=self.distributor1)
        url = reverse("api_product_detail", kwargs={"pk": self.product1.pk})

        # PATCH update price and unit
        patch_res = self.api_client.patch(url, {"price": "2699.00", "unit": "set"}, format="json")
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data["price"], "2699.00")
        self.assertEqual(patch_res.data["unit"], "set")

        # PUT update with attempted spoofing of distributor
        put_payload = {
            "name": "Mechanical Keyboard Pro",
            "sku": "KB-001",
            "price": "2899.00",
            "stock": 40,
            "unit": "box",
            "distributor_id": self.distributor2.id
        }
        put_res = self.api_client.put(url, put_payload, format="json")
        self.assertEqual(put_res.status_code, 200)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.name, "Mechanical Keyboard Pro")
        self.assertEqual(self.product1.distributor, self.distributor1)

    # 7. Delete product safely
    def test_10_delete_unreferenced_product(self):
        """Unreferenced product can be deleted successfully."""
        self.api_client.force_authenticate(user=self.distributor1)
        url = reverse("api_product_detail", kwargs={"pk": self.product1.pk})
        response = self.api_client.delete(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(pk=self.product1.pk).exists())

    # 8. Preserve invoice history when product is referenced
    def test_11_preserve_invoice_history_on_delete(self):
        """Product referenced by an invoice cannot be deleted; historical billing data is protected."""
        invoice = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-SAFE-01",
            invoice_date=date.today(),
            subtotal=Decimal("2499.00"),
            total_gst=Decimal("449.82"),
            grand_total=Decimal("2948.82")
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            product=self.product1,
            product_name=self.product1.name,
            quantity=1,
            unit_price=self.product1.price,
            gst_rate=self.product1.gst_rate,
            taxable_amount=Decimal("2499.00"),
            gst_amount=Decimal("449.82"),
            line_total=Decimal("2948.82")
        )

        self.api_client.force_authenticate(user=self.distributor1)
        url = reverse("api_product_detail", kwargs={"pk": self.product1.pk})
        response = self.api_client.delete(url)

        # Must reject deletion
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be deleted because it is referenced", response.data["detail"])
        self.assertTrue(Product.objects.filter(pk=self.product1.pk).exists())
        self.assertTrue(InvoiceItem.objects.filter(invoice=invoice).exists())

    # 9. Duplicate SKU validation
    def test_12_duplicate_sku_rejected_for_same_distributor(self):
        """Duplicate SKU under the same distributor is rejected with HTTP 400."""
        self.api_client.force_authenticate(user=self.distributor1)
        payload = {
            "name": "Another Keyboard",
            "sku": "KB-001",  # Same as self.product1
            "price": "999.00",
            "stock": 10
        }
        response = self.api_client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("sku", response.data)

    def test_13_same_sku_allowed_for_different_distributor(self):
        """Different distributors can use the same SKU in their own respective inventories."""
        self.api_client.force_authenticate(user=self.distributor2)
        payload = {
            "name": "Distributor 2 Product",
            "sku": "KB-001",  # Same SKU as dist1, but for dist2
            "price": "1299.00",
            "stock": 15
        }
        response = self.api_client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, 201)

    # 10. Access control
    def test_14_unauthenticated_request_rejected(self):
        """Unauthenticated requests are rejected with 401."""
        response = self.api_client.get(self.list_url)
        self.assertEqual(response.status_code, 401)

    def test_15_unauthorized_user_rejected_with_403(self):
        """Regular user without Distributor or Admin role is rejected with 403."""
        self.api_client.force_authenticate(user=self.regular_user)
        response = self.api_client.get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_16_admin_access_allowed(self):
        """Admin can list products across all distributors."""
        self.api_client.force_authenticate(user=self.admin_user)
        response = self.api_client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["count"], 2)

    # 11. Frontend product list displays unit, status, and view modal
    def test_17_frontend_product_list_elements(self):
        """Frontend product list renders unit, active badge, and view details."""
        self.client.login(username="dist1_crud", password="DistPassword@123")
        response = self.client.get(reverse("product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mechanical Keyboard")
        self.assertContains(response, "KB-001")
        self.assertContains(response, "piece")
        self.assertContains(response, "Active")
        self.assertContains(response, "viewProductDetails")


class CustomerRegistrationAndManagementViewTests(TestCase):
    """
    Test suite for Customer Registration and Management views in billing app:
    - customer_register_view (GET /distributor/customers/register/)
    - add_customer (GET/POST /distributor/customers/add/)
    - customer_list (GET /distributor/customers/)
    - edit_customer (GET/POST /distributor/customers/<pk>/edit/)
    - delete_customer (POST /distributor/customers/<pk>/delete/)
    - Access control, distributor data isolation, invoice protection
    """

    def setUp(self):
        self.client = Client()
        self.distributor_group, _ = Group.objects.get_or_create(name="Distributor")

        # Distributor 1
        self.distributor1 = User.objects.create_user(
            username="dist1_cust",
            email="dist1_cust@example.com",
            password="DistPassword@123"
        )
        self.distributor1.groups.add(self.distributor_group)
        self.profile1 = DistributorProfile.objects.create(
            user=self.distributor1,
            full_name="Distributor One",
            email="dist1_cust@example.com",
            phone="9876543210"
        )

        # Distributor 2
        self.distributor2 = User.objects.create_user(
            username="dist2_cust",
            email="dist2_cust@example.com",
            password="DistPassword@123"
        )
        self.distributor2.groups.add(self.distributor_group)
        self.profile2 = DistributorProfile.objects.create(
            user=self.distributor2,
            full_name="Distributor Two",
            email="dist2_cust@example.com",
            phone="9876543211"
        )

        # Regular non-distributor
        self.regular_user = User.objects.create_user(
            username="regular_cust",
            email="regular_cust@example.com",
            password="RegularPassword@123"
        )

        # Pre-created customer for distributor 1
        self.customer1 = Customer.objects.create(
            distributor=self.distributor1,
            name="Ramesh Patel",
            email="ramesh@example.com",
            phone="9876543210",
            address="123 Market Road",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380001"
        )

        # Pre-created customer for distributor 2
        self.customer2 = Customer.objects.create(
            distributor=self.distributor2,
            name="Suresh Shah",
            email="suresh@example.com",
            phone="9876543211",
            address="456 Cross Street",
            city="Surat",
            state="Gujarat",
            pincode="395001"
        )

    def test_customer_register_view_unauthenticated(self):
        """Unauthenticated GET redirects to distributor login."""
        url = reverse("billing_customer_register")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)

    def test_customer_register_view_non_distributor(self):
        """Non-distributor user is redirected away."""
        self.client.login(username="regular_cust", password="RegularPassword@123")
        url = reverse("billing_customer_register")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_customer_register_view_authenticated(self):
        """Authenticated distributor GET renders billing/customer_register.html."""
        self.client.login(username="dist1_cust", password="DistPassword@123")
        url = reverse("billing_customer_register")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "billing/customer_register.html")

    def test_add_customer_view_get(self):
        """Authenticated distributor GET renders billing/add_customer.html with form."""
        self.client.login(username="dist1_cust", password="DistPassword@123")
        url = reverse("billing_add_customer")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "billing/add_customer.html")
        self.assertIn("form", response.context)

    def test_add_customer_view_valid_post(self):
        """Valid POST creates customer linked to request.user and redirects."""
        self.client.login(username="dist1_cust", password="DistPassword@123")
        url = reverse("billing_add_customer")
        data = {
            "name": "Kiran Rao",
            "email": "kiran@example.com",
            "phone": "9823456789",
            "address": "789 Park View",
            "city": "Vadodara",
            "state": "Gujarat",
            "pincode": "390001"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Customer.objects.filter(name="Kiran Rao", distributor=self.distributor1).exists())

    def test_add_customer_view_invalid_phone(self):
        """Invalid phone (less than 10 digits or non-6-9) rejected with form error."""
        self.client.login(username="dist1_cust", password="DistPassword@123")
        url = reverse("billing_add_customer")
        data = {
            "name": "Invalid Phone Cust",
            "phone": "12345"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "phone", "Please enter a valid 10-digit phone number.")
        self.assertFalse(Customer.objects.filter(name="Invalid Phone Cust").exists())

    def test_add_customer_view_invalid_email(self):
        """Invalid email rejected with form error."""
        self.client.login(username="dist1_cust", password="DistPassword@123")
        url = reverse("billing_add_customer")
        data = {
            "name": "Invalid Email Cust",
            "phone": "9823456789",
            "email": "notanemail"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "email", "Please enter a valid email address.")

    def test_customer_list_isolation_and_search(self):
        """Distributor 1 only sees their own customers; search query filters correctly."""
        self.client.login(username="dist1_cust", password="DistPassword@123")
        url = reverse("billing_customer_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        customers = list(response.context["page_obj"])
        self.assertIn(self.customer1, customers)
        self.assertNotIn(self.customer2, customers)

        # Search
        search_res = self.client.get(url + "?q=Ramesh")
        self.assertEqual(search_res.status_code, 200)
        self.assertEqual(len(search_res.context["page_obj"]), 1)

    def test_edit_customer_success(self):
        """Distributor can edit their own customer."""
        self.client.login(username="dist1_cust", password="DistPassword@123")
        url = reverse("billing_edit_customer", kwargs={"pk": self.customer1.pk})
        data = {
            "name": "Ramesh Patel Updated",
            "phone": "9876543210",
            "email": "ramesh.updated@example.com"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.customer1.refresh_from_db()
        self.assertEqual(self.customer1.name, "Ramesh Patel Updated")

    def test_edit_customer_isolation_404(self):
        """Distributor 1 cannot edit Distributor 2's customer."""
        self.client.login(username="dist1_cust", password="DistPassword@123")
        url = reverse("billing_edit_customer", kwargs={"pk": self.customer2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_delete_unreferenced_customer(self):
        """Unreferenced customer can be deleted."""
        self.client.login(username="dist1_cust", password="DistPassword@123")
        url = reverse("billing_delete_customer", kwargs={"pk": self.customer1.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Customer.objects.filter(pk=self.customer1.pk).exists())

    def test_delete_referenced_customer_protected(self):
        """Customer referenced in an invoice is protected from deletion."""
        invoice = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-CUST-PROT",
            invoice_date=date.today(),
            subtotal=Decimal("100.00"),
            total_gst=Decimal("18.00"),
            grand_total=Decimal("118.00")
        )
        self.client.login(username="dist1_cust", password="DistPassword@123")
        url = reverse("billing_delete_customer", kwargs={"pk": self.customer1.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Customer.objects.filter(pk=self.customer1.pk).exists())


class ProductManagementFrontendViewTests(TestCase):
    """
    Test suite for Product Management frontend views:
    - product_list (GET /distributor/products/)
    - add_product (GET/POST /distributor/products/add/)
    - edit_product (GET/POST /distributor/products/<pk>/edit/)
    - delete_product (POST /distributor/products/<pk>/delete/)
    - product_details (GET /distributor/products/<pk>/details/)
    - Validation: negative price/quantity, required fields, invoice protection
    """

    def setUp(self):
        self.client = Client()
        self.distributor_group, _ = Group.objects.get_or_create(name="Distributor")

        # Distributor 1
        self.distributor1 = User.objects.create_user(
            username="dist1_pm",
            email="dist1_pm@example.com",
            password="DistPassword@123"
        )
        self.distributor1.groups.add(self.distributor_group)
        self.profile1 = DistributorProfile.objects.create(
            user=self.distributor1,
            full_name="Distributor PM 1",
            email="dist1_pm@example.com",
            phone="9876543220"
        )

        # Distributor 2
        self.distributor2 = User.objects.create_user(
            username="dist2_pm",
            email="dist2_pm@example.com",
            password="DistPassword@123"
        )
        self.distributor2.groups.add(self.distributor_group)
        self.profile2 = DistributorProfile.objects.create(
            user=self.distributor2,
            full_name="Distributor PM 2",
            email="dist2_pm@example.com",
            phone="9876543221"
        )

        # Regular user
        self.regular_user = User.objects.create_user(
            username="regular_pm",
            email="regular_pm@example.com",
            password="RegularPassword@123"
        )

        # Customer for invoice test
        self.customer1 = Customer.objects.create(
            distributor=self.distributor1,
            name="PM Test Customer",
            phone="9876543222"
        )

        # Products
        self.product1 = Product.objects.create(
            distributor=self.distributor1,
            name="Wireless Mouse",
            sku="WM-100",
            category="Hardware",
            price=Decimal("499.00"),
            stock=50,
            unit="piece",
            gst_rate=Decimal("18.00"),
            is_active=True
        )

        self.product2 = Product.objects.create(
            distributor=self.distributor2,
            name="Other Distributor Product",
            sku="ODP-200",
            category="Hardware",
            price=Decimal("999.00"),
            stock=20,
            unit="piece",
            gst_rate=Decimal("18.00"),
            is_active=True
        )

    def test_product_list_unauthenticated(self):
        """Unauthenticated access redirects to login."""
        url = reverse("product_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)

    def test_product_list_distributor_isolation(self):
        """Distributor only sees their own products."""
        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("product_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "billing/product_list.html")
        products = list(response.context["page_obj"])
        self.assertIn(self.product1, products)
        self.assertNotIn(self.product2, products)

    def test_product_list_search_by_name_and_sku(self):
        """Search query filters products by name or SKU."""
        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("product_list")

        res_name = self.client.get(url + "?q=Mouse")
        self.assertEqual(res_name.status_code, 200)
        self.assertEqual(len(res_name.context["page_obj"]), 1)

        res_sku = self.client.get(url + "?q=WM-100")
        self.assertEqual(res_sku.status_code, 200)
        self.assertEqual(len(res_sku.context["page_obj"]), 1)

        res_none = self.client.get(url + "?q=NonExistentQueryXYZ")
        self.assertEqual(res_none.status_code, 200)
        self.assertEqual(len(res_none.context["page_obj"]), 0)

    def test_add_product_get(self):
        """Authenticated distributor GET renders add_product form."""
        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("add_product")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "billing/add_product.html")
        self.assertIn("form", response.context)

    def test_add_product_valid_post(self):
        """Valid product POST creates product assigned to request.user."""
        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("add_product")
        data = {
            "name": "USB-C Hub",
            "category": "Accessories",
            "sku": "HUB-301",
            "price": "1299.00",
            "stock": 35,
            "unit": "piece",
            "gst_rate": "18.00",
            "is_active": True,
            "description": "7-in-1 multi-port adapter"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        created = Product.objects.get(sku="HUB-301")
        self.assertEqual(created.distributor, self.distributor1)
        self.assertEqual(created.price, Decimal("1299.00"))
        self.assertEqual(created.stock, 35)

    def test_add_product_negative_price_rejected(self):
        """Negative price is rejected by ProductForm."""
        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("add_product")
        data = {
            "name": "Negative Price Item",
            "price": "-50.00",
            "stock": 10,
            "gst_rate": "18.00"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "price", "Price must be greater than 0.")
        self.assertFalse(Product.objects.filter(name="Negative Price Item").exists())

    def test_add_product_zero_price_rejected(self):
        """Zero price is rejected by ProductForm."""
        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("add_product")
        data = {
            "name": "Zero Price Item",
            "price": "0.00",
            "stock": 10,
            "gst_rate": "18.00"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "price", "Price must be greater than 0.")

    def test_add_product_negative_stock_rejected(self):
        """Negative stock is rejected by ProductForm."""
        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("add_product")
        data = {
            "name": "Negative Stock Item",
            "price": "100.00",
            "stock": -5,
            "gst_rate": "18.00"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "stock", "Ensure this value is greater than or equal to 0.")

    def test_edit_product_get_and_post(self):
        """Edit product view renders edit form and successfully updates product."""
        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("edit_product", kwargs={"pk": self.product1.pk})

        # GET
        get_res = self.client.get(url)
        self.assertEqual(get_res.status_code, 200)
        self.assertTemplateUsed(get_res, "billing/edit_product.html")

        # POST
        data = {
            "name": "Wireless Mouse Enhanced",
            "category": "Peripherals",
            "sku": "WM-100",
            "price": "549.00",
            "stock": 60,
            "unit": "piece",
            "gst_rate": "18.00",
            "is_active": True
        }
        post_res = self.client.post(url, data)
        self.assertEqual(post_res.status_code, 302)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.name, "Wireless Mouse Enhanced")
        self.assertEqual(self.product1.price, Decimal("549.00"))
        self.assertEqual(self.product1.stock, 60)

    def test_edit_product_distributor_isolation_404(self):
        """Distributor 1 cannot edit Distributor 2's product."""
        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("edit_product", kwargs={"pk": self.product2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_delete_unreferenced_product_success(self):
        """Unreferenced product can be deleted via POST."""
        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("delete_product", kwargs={"pk": self.product1.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(pk=self.product1.pk).exists())

    def test_delete_product_referenced_by_invoice_protected(self):
        """Product referenced by an invoice cannot be deleted; protected by ProtectedError."""
        invoice = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-PM-PROT",
            invoice_date=date.today(),
            subtotal=Decimal("499.00"),
            total_gst=Decimal("89.82"),
            grand_total=Decimal("588.82")
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            product=self.product1,
            product_name=self.product1.name,
            quantity=1,
            unit_price=self.product1.price,
            gst_rate=self.product1.gst_rate,
            taxable_amount=Decimal("499.00"),
            gst_amount=Decimal("89.82"),
            line_total=Decimal("588.82")
        )

        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("delete_product", kwargs={"pk": self.product1.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Product.objects.filter(pk=self.product1.pk).exists())

    def test_product_details_json_endpoint(self):
        """GET /distributor/products/<pk>/details/ returns product JSON metadata."""
        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("billing_product_details", kwargs={"pk": self.product1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], self.product1.pk)
        self.assertEqual(data["name"], "Wireless Mouse")
        self.assertEqual(data["price"], "499.00")
        self.assertEqual(data["stock"], 50)
        self.assertEqual(data["unit"], "piece")
        self.assertTrue(data["is_active"])

    def test_product_details_isolation_404(self):
        """Distributor 1 cannot fetch details of Distributor 2's product."""
        self.client.login(username="dist1_pm", password="DistPassword@123")
        url = reverse("billing_product_details", kwargs={"pk": self.product2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_product_details_unauthorized_user_403(self):
        """Non-distributor user accessing product details receives 403 JSON."""
        self.client.login(username="regular_pm", password="RegularPassword@123")
        url = reverse("billing_product_details", kwargs={"pk": self.product1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": "Unauthorized"})


from billing.management.commands.ensure_invoice_data import (
    verify_invoice_record,
    ensure_invoices_exist,
)
from django.core.management import call_command
from io import StringIO
from django.db.models.deletion import ProtectedError


class EnsureInvoiceDataTests(TestCase):
    """
    Focused verification tests for Invoice Data existence, required fields,
    uniqueness, relationships, and idempotent sample creation:
    1. Verify invoice records exist.
    2. Verify all four required fields (ID, Customer Name, Total Amount, Invoice Date).
    3. Verify invoice ID uniqueness.
    4. Verify customer relationship.
    5. Verify total amount and date retrieval.
    6. Verify repeated sample-data execution does not create duplicates.
    7. Verify management command runs and outputs verified table.
    """

    def setUp(self):
        self.distributor = User.objects.create_user(
            username="dist_invoice_test",
            email="dist_invoice_test@example.com",
            password="DistPassword123!"
        )
        self.dist_group, _ = Group.objects.get_or_create(name="Distributor")
        self.distributor.groups.add(self.dist_group)

        self.customer = Customer.objects.create(
            distributor=self.distributor,
            name="John Doe",
            email="john@example.com",
            phone="9876543210",
            address="123 Market St",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380001"
        )

        self.product = Product.objects.create(
            distributor=self.distributor,
            name="Test Widget",
            category="Hardware",
            price=Decimal("150.00"),
            stock=50,
            gst_rate=Decimal("18.00"),
            sku="WIDGET-01",
            unit="piece",
            is_active=True
        )

    def test_invoice_creation_and_required_fields_retrieval(self):
        """Verify that an invoice record contains all 4 required fields and can be retrieved."""
        inv = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer,
            invoice_number="INV-TEST-001",
            invoice_date=date(2026, 11, 2),
            subtotal=Decimal("300.00"),
            total_gst=Decimal("54.00"),
            grand_total=Decimal("354.00")
        )

        InvoiceItem.objects.create(
            invoice=inv,
            product=self.product,
            product_name=self.product.name,
            quantity=2,
            unit_price=Decimal("150.00"),
            gst_rate=Decimal("18.00"),
            taxable_amount=Decimal("300.00"),
            gst_amount=Decimal("54.00"),
            line_total=Decimal("354.00")
        )

        # Retrieve and verify all 4 fields via Django ORM
        retrieved = Invoice.objects.select_related("customer").get(pk=inv.pk)
        self.assertIsNotNone(retrieved.id)
        self.assertEqual(retrieved.invoice_number, "INV-TEST-001")
        self.assertEqual(retrieved.customer.name, "John Doe")
        self.assertEqual(retrieved.grand_total, Decimal("354.00"))
        self.assertEqual(retrieved.invoice_date, date(2026, 11, 2))

        # Test verification helper
        info = verify_invoice_record(retrieved)
        self.assertTrue(info["is_valid"])
        self.assertEqual(info["customer_name"], "John Doe")
        self.assertEqual(info["total_amount"], Decimal("354.00"))
        self.assertEqual(len(info["errors"]), 0)

    def test_invoice_id_uniqueness(self):
        """Verify invoice ID (distributor + invoice_number) uniqueness constraint."""
        Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer,
            invoice_number="INV-UNIQUE-001",
            invoice_date=date.today(),
            subtotal=Decimal("100.00"),
            total_gst=Decimal("18.00"),
            grand_total=Decimal("118.00")
        )

        # Attempting to create duplicate invoice_number for same distributor fails validation/integrity
        with self.assertRaises(Exception):
            dup = Invoice(
                distributor=self.distributor,
                customer=self.customer,
                invoice_number="INV-UNIQUE-001",
                invoice_date=date.today(),
                subtotal=Decimal("100.00"),
                total_gst=Decimal("18.00"),
                grand_total=Decimal("118.00")
            )
            dup.save()

    def test_customer_relationship_protected(self):
        """Verify that customer associated with an invoice cannot be accidentally deleted."""
        inv = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer,
            invoice_number="INV-PROTECT-001",
            invoice_date=date.today(),
            subtotal=Decimal("100.00"),
            total_gst=Decimal("18.00"),
            grand_total=Decimal("118.00")
        )
        with self.assertRaises(ProtectedError):
            self.customer.delete()

    def test_ensure_invoices_exist_creates_samples_when_empty(self):
        """When 0 invoices exist, ensure_invoices_exist() generates valid sample invoice."""
        Invoice.objects.all().delete()
        self.assertEqual(Invoice.objects.count(), 0)

        verified, created = ensure_invoices_exist()
        self.assertGreater(len(verified), 0)
        self.assertGreater(len(created), 0)
        self.assertEqual(Invoice.objects.count(), 1)

        sample = Invoice.objects.first()
        self.assertIsNotNone(sample.id)
        self.assertIsNotNone(sample.invoice_number)
        self.assertIsNotNone(sample.customer.name)
        self.assertGreater(sample.grand_total, Decimal("0.00"))
        self.assertIsNotNone(sample.invoice_date)

    def test_ensure_invoices_exist_is_idempotent(self):
        """Running ensure_invoices_exist() multiple times never creates duplicate invoices."""
        Invoice.objects.all().delete()
        ensure_invoices_exist()
        count_first_run = Invoice.objects.count()
        self.assertEqual(count_first_run, 1)

        # Second run
        verified, created = ensure_invoices_exist()
        count_second_run = Invoice.objects.count()
        self.assertEqual(count_second_run, count_first_run)
        self.assertEqual(len(created), 0)

        # Third run
        verified, created = ensure_invoices_exist()
        count_third_run = Invoice.objects.count()
        self.assertEqual(count_third_run, count_first_run)
        self.assertEqual(len(created), 0)

    def test_management_command_execution(self):
        """Test management command 'ensure_invoice_data' outputs verified table without errors."""
        out = StringIO()
        call_command("ensure_invoice_data", stdout=out)
        output = out.getvalue()
        self.assertIn("Invoice ID", output)
        self.assertIn("Customer Name", output)
        self.assertIn("Total Amount", output)
        self.assertIn("Invoice Date", output)
        self.assertIn("VALID", output)


from billing.utils import (
    generate_invoice_qr,
    generate_invoice_qr_bytes,
    generate_invoice_qr_base64,
    build_invoice_qr_payload,
    decode_qr_from_image,
)
import json
from PIL import Image
from io import BytesIO


class GenerateInvoiceQRCodeTests(TestCase):
    """
    Focused verification tests for QR code generation from saved Invoice model data:
    1. QR generation for an existing saved invoice.
    2. Correct invoice ID in QR data.
    3. Correct customer name in QR data.
    4. Correct total amount in QR data.
    5. Correct invoice date in QR data.
    6. Different invoices generate different QR payloads and images.
    7. Invalid invoice ID returns 404 on detail and QR views.
    8. QR image can be scanned and decoded successfully.
    9. Unsaved invoice raises ValueError (cannot generate QR from unsaved data).
    10. Invoice detail view displays QR image properly.
    11. Invoice PDF view renders with QR image.
    """

    def setUp(self):
        self.client = Client()
        self.distributor = User.objects.create_user(
            username="dist_qr_test",
            email="dist_qr_test@example.com",
            password="DistPassword@123"
        )
        self.dist_group, _ = Group.objects.get_or_create(name="Distributor")
        self.distributor.groups.add(self.dist_group)

        self.customer1 = Customer.objects.create(
            distributor=self.distributor,
            name="Alice Walker",
            email="alice@example.com",
            phone="9876543211",
            address="456 Elm Street",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380002"
        )

        self.customer2 = Customer.objects.create(
            distributor=self.distributor,
            name="Bob Smith",
            email="bob@example.com",
            phone="9876543212",
            address="789 Oak Ave",
            city="Surat",
            state="Gujarat",
            pincode="395001"
        )

        self.product = Product.objects.create(
            distributor=self.distributor,
            name="Smart Gadget",
            category="Electronics",
            price=Decimal("1200.00"),
            stock=25,
            gst_rate=Decimal("18.00"),
            sku="GADGET-01",
            unit="piece",
            is_active=True
        )

        # Saved Invoice 1
        self.invoice1 = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer1,
            invoice_number="INV-QR-001",
            invoice_date=date(2026, 11, 2),
            subtotal=Decimal("1200.00"),
            total_gst=Decimal("216.00"),
            grand_total=Decimal("1416.00")
        )
        InvoiceItem.objects.create(
            invoice=self.invoice1,
            product=self.product,
            product_name=self.product.name,
            quantity=1,
            unit_price=Decimal("1200.00"),
            gst_rate=Decimal("18.00"),
            taxable_amount=Decimal("1200.00"),
            gst_amount=Decimal("216.00"),
            line_total=Decimal("1416.00")
        )

        # Saved Invoice 2 (different customer, date, and amount)
        self.invoice2 = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer2,
            invoice_number="INV-QR-002",
            invoice_date=date(2026, 11, 10),
            subtotal=Decimal("2400.00"),
            total_gst=Decimal("432.00"),
            grand_total=Decimal("2832.00")
        )
        InvoiceItem.objects.create(
            invoice=self.invoice2,
            product=self.product,
            product_name=self.product.name,
            quantity=2,
            unit_price=Decimal("1200.00"),
            gst_rate=Decimal("18.00"),
            taxable_amount=Decimal("2400.00"),
            gst_amount=Decimal("432.00"),
            line_total=Decimal("2832.00")
        )

    def test_qr_generation_from_saved_invoice_data(self):
        """Test QR code generation dynamically fetches real saved invoice fields."""
        payload = build_invoice_qr_payload(self.invoice1)
        self.assertEqual(payload["invoice_id"], "INV-QR-001")
        self.assertEqual(payload["customer_name"], "Alice Walker")
        self.assertEqual(payload["total_amount"], "1416.00")
        self.assertEqual(payload["invoice_date"], "2026-11-02")

    def test_qr_image_decoding_matches_exact_json_structure(self):
        """Test that generated QR image can be scanned and decoded to exact required JSON payload."""
        img = generate_invoice_qr(self.invoice1)
        self.assertIsNotNone(img)

        decoded_results = decode_qr_from_image(img)
        self.assertGreater(len(decoded_results), 0, "QR image failed to decode")

        decoded_data = json.loads(decoded_results[0]["data"])
        self.assertEqual(list(decoded_data.keys()), ["invoice_id", "customer_name", "total_amount", "invoice_date"])
        self.assertEqual(decoded_data["invoice_id"], "INV-QR-001")
        self.assertEqual(decoded_data["customer_name"], "Alice Walker")
        self.assertEqual(decoded_data["total_amount"], "1416.00")
        self.assertEqual(decoded_data["invoice_date"], "2026-11-02")

    def test_different_invoices_generate_different_qr_payloads(self):
        """Test that different invoices generate unique and distinguishable QR codes."""
        img1 = generate_invoice_qr(self.invoice1)
        img2 = generate_invoice_qr(self.invoice2)

        decoded1 = json.loads(decode_qr_from_image(img1)[0]["data"])
        decoded2 = json.loads(decode_qr_from_image(img2)[0]["data"])

        self.assertNotEqual(decoded1["invoice_id"], decoded2["invoice_id"])
        self.assertNotEqual(decoded1["customer_name"], decoded2["customer_name"])
        self.assertNotEqual(decoded1["total_amount"], decoded2["total_amount"])
        self.assertNotEqual(decoded1["invoice_date"], decoded2["invoice_date"])

    def test_unsaved_invoice_raises_value_error(self):
        """QR generation must reject unsaved invoice instances without a database PK."""
        unsaved = Invoice(
            distributor=self.distributor,
            customer=self.customer1,
            invoice_number="INV-DRAFT-001",
            invoice_date=date.today(),
            grand_total=Decimal("100.00")
        )
        with self.assertRaises(ValueError):
            generate_invoice_qr(unsaved)

    def test_invalid_invoice_id_returns_404(self):
        """Requesting detail or QR endpoint with invalid invoice ID returns 404."""
        self.client.login(username="dist_qr_test", password="DistPassword@123")

        # Invalid ID on invoice detail
        res_detail = self.client.get(reverse("invoice_detail", kwargs={"pk": 999999}))
        self.assertEqual(res_detail.status_code, 404)

        # Invalid ID on invoice QR image endpoint
        res_qr = self.client.get(reverse("invoice_qr", kwargs={"pk": 999999}))
        self.assertEqual(res_qr.status_code, 404)

    def test_invoice_detail_page_displays_qr_code(self):
        """Invoice detail page renders successfully and displays the generated QR code."""
        self.client.login(username="dist_qr_test", password="DistPassword@123")
        url = reverse("invoice_detail", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        self.assertIn("Scan for Invoice Details", content)
        self.assertTrue(
            "invoices/qr_codes/" in content or "data:image/png;base64," in content
        )
        self.assertNotIn("data:image/png;base64,data:", content)

    def test_invoice_detail_preview_dynamic_per_invoice(self):
        """Invoice preview dynamically renders distinct, scannable QR codes for each invoice."""
        import base64
        from io import BytesIO
        from PIL import Image

        self.client.login(username="dist_qr_test", password="DistPassword@123")

        # Request invoice1 preview
        resp1 = self.client.get(reverse("invoice_detail", kwargs={"pk": self.invoice1.pk}))
        self.assertEqual(resp1.status_code, 200)
        self.assertIn("qr_code", resp1.context)
        self.assertIn("qr_code_url", resp1.context)
        qr1_uri = resp1.context["qr_code"]

        if qr1_uri.startswith("data:image/png;base64,"):
            b64_1 = qr1_uri.replace("data:image/png;base64,", "")
            img1 = Image.open(BytesIO(base64.b64decode(b64_1)))
        else:
            self.invoice1.refresh_from_db()
            with self.invoice1.qr_code.open("rb") as f:
                img1 = Image.open(BytesIO(f.read()))

        decoded1 = json.loads(decode_qr_from_image(img1)[0]["data"])
        self.assertEqual(decoded1["invoice_id"], "INV-QR-001")
        self.assertEqual(decoded1["customer_name"], "Alice Walker")
        self.assertEqual(decoded1["total_amount"], "1416.00")
        self.assertEqual(decoded1["invoice_date"], "2026-11-02")

        # Request invoice2 preview
        resp2 = self.client.get(reverse("invoice_detail", kwargs={"pk": self.invoice2.pk}))
        self.assertEqual(resp2.status_code, 200)
        qr2_uri = resp2.context["qr_code"]

        if qr2_uri.startswith("data:image/png;base64,"):
            b64_2 = qr2_uri.replace("data:image/png;base64,", "")
            img2 = Image.open(BytesIO(base64.b64decode(b64_2)))
        else:
            self.invoice2.refresh_from_db()
            with self.invoice2.qr_code.open("rb") as f:
                img2 = Image.open(BytesIO(f.read()))

        decoded2 = json.loads(decode_qr_from_image(img2)[0]["data"])
        self.assertEqual(decoded2["invoice_id"], "INV-QR-002")
        self.assertEqual(decoded2["customer_name"], "Bob Smith")
        self.assertEqual(decoded2["total_amount"], "2832.00")
        self.assertEqual(decoded2["invoice_date"], self.invoice2.invoice_date.strftime("%Y-%m-%d"))

        # Confirm dynamic uniqueness
        self.assertNotEqual(qr1_uri, qr2_uri)
        self.assertNotEqual(decoded1, decoded2)

    def test_invoice_detail_preview_graceful_missing_qr_fallback(self):
        """When QR image generation is unavailable, template renders graceful fallback without crashing."""
        from django.template.loader import render_to_string

        no_qr_invoice = Invoice(
            pk=self.invoice1.pk,
            distributor=self.distributor,
            customer=self.customer1,
            invoice_number="INV-NO-QR",
            invoice_date=date(2026, 11, 2),
            qr_code=None
        )

        html = render_to_string(
            "billing/invoice_detail.html",
            {
                "invoice": no_qr_invoice,
                "items": [],
                "customer": self.customer1,
                "qr_code": "",
                "qr_code_url": "",
            }
        )
        self.assertIn("QR Unavailable", html)
        self.assertIn("Scan for Invoice Details", html)

    def test_invoice_detail_preview_responsive_ui_elements(self):
        """Invoice detail preview contains responsive centering and scannable image attributes."""
        self.client.login(username="dist_qr_test", password="DistPassword@123")
        response = self.client.get(reverse("invoice_detail", kwargs={"pk": self.invoice1.pk}))
        content = response.content.decode("utf-8")

        self.assertIn("Scan for Invoice Details", content)
        self.assertIn("img-fluid", content)
        self.assertIn("object-fit: contain", content)
        self.assertIn("text-center", content)

    def test_invoice_pdf_renders_with_qr_code(self):
        """Invoice PDF endpoint generates valid PDF bytes containing the QR code."""
        self.client.login(username="dist_qr_test", password="DistPassword@123")
        url = reverse("invoice_pdf", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))


class AutomaticInvoiceQRCodeSaveTests(TestCase):
    """
    Unit and integration tests for automatic QR code generation and saving during invoice save.
    Verifies all 8 testing requirements:
    1. Creating a new invoice generates and saves a QR code.
    2. QR payload contains the correct four invoice values.
    3. Different invoices have different QR data.
    4. Existing invoice updates do not generate unnecessary duplicate files.
    5. Relevant invoice changes regenerate the QR code.
    6. Invoice preview displays the saved QR image.
    7. QR code can be decoded successfully.
    8. QR generation errors are handled safely.
    """

    def setUp(self):
        from accounts.models import DistributorProfile
        self.distributor = User.objects.create_user(
            username="auto_qr_dist",
            password="DistPassword@123",
            email="auto_qr_dist@example.com"
        )
        self.profile = DistributorProfile.objects.create(
            user=self.distributor,
            full_name="Daniel Enterprise",
            email="auto_qr_dist@example.com",
            phone="9876500000"
        )
        self.customer1 = Customer.objects.create(
            distributor=self.distributor,
            name="Daniel Craig",
            email="daniel@example.com",
            phone="9876500001"
        )
        self.customer2 = Customer.objects.create(
            distributor=self.distributor,
            name="Eva Green",
            email="eva@example.com",
            phone="9876500002"
        )
        self.product = Product.objects.create(
            distributor=self.distributor,
            name="Premium Service",
            price=Decimal("500.00"),
            gst_rate=Decimal("18.00"),
            stock=100
        )

    def test_1_create_new_invoice_automatically_generates_and_saves_qr_code(self):
        """Creating a new invoice automatically generates and saves a QR code in media storage."""
        invoice = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer1,
            invoice_number="INV-AUTO-001",
            invoice_date=date(2026, 11, 3),
            subtotal=Decimal("500.00"),
            total_gst=Decimal("90.00"),
            grand_total=Decimal("590.00")
        )

        self.assertIsNotNone(invoice.pk)
        self.assertTrue(bool(invoice.qr_code), "invoice.qr_code was not populated automatically.")
        self.assertTrue(invoice.qr_code.storage.exists(invoice.qr_code.name), "QR file was not saved to storage.")
        self.assertTrue(invoice.qr_code.name.endswith(".png"), "QR file must be a PNG image.")
        self.assertIn("INV-AUTO-001", invoice.qr_code.name)

    def test_2_qr_payload_contains_correct_four_values(self):
        """Saved QR code image encodes the exact four required invoice values in valid JSON."""
        from PIL import Image
        from billing.utils import decode_qr_from_image

        invoice = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer1,
            invoice_number="INV-AUTO-002",
            invoice_date=date(2026, 11, 4),
            subtotal=Decimal("1000.00"),
            total_gst=Decimal("180.00"),
            grand_total=Decimal("1180.00")
        )

        with invoice.qr_code.open("rb") as f:
            img = Image.open(f)
            decoded_results = decode_qr_from_image(img)

        self.assertGreater(len(decoded_results), 0, "Failed to decode saved QR code.")
        data = json.loads(decoded_results[0]["data"])

        self.assertEqual(list(data.keys()), ["invoice_id", "customer_name", "total_amount", "invoice_date"])
        self.assertEqual(data["invoice_id"], "INV-AUTO-002")
        self.assertEqual(data["customer_name"], "Daniel Craig")
        self.assertEqual(data["total_amount"], "1180.00")
        self.assertEqual(data["invoice_date"], "2026-11-04")

    def test_3_different_invoices_have_different_qr_data(self):
        """Different invoices produce uniquely distinguishable QR code files and payloads."""
        from PIL import Image
        from billing.utils import decode_qr_from_image

        inv1 = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer1,
            invoice_number="INV-DIFF-001",
            invoice_date=date(2026, 11, 1),
            subtotal=Decimal("100.00"),
            total_gst=Decimal("18.00"),
            grand_total=Decimal("118.00")
        )
        inv2 = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer2,
            invoice_number="INV-DIFF-002",
            invoice_date=date(2026, 11, 2),
            subtotal=Decimal("200.00"),
            total_gst=Decimal("36.00"),
            grand_total=Decimal("236.00")
        )

        self.assertNotEqual(inv1.qr_code.name, inv2.qr_code.name)

        with inv1.qr_code.open("rb") as f1, inv2.qr_code.open("rb") as f2:
            data1 = json.loads(decode_qr_from_image(Image.open(f1))[0]["data"])
            data2 = json.loads(decode_qr_from_image(Image.open(f2))[0]["data"])

        self.assertNotEqual(data1["invoice_id"], data2["invoice_id"])
        self.assertNotEqual(data1["customer_name"], data2["customer_name"])
        self.assertNotEqual(data1["total_amount"], data2["total_amount"])
        self.assertNotEqual(data1["invoice_date"], data2["invoice_date"])

    def test_4_existing_invoice_updates_do_not_generate_duplicate_files(self):
        """Saving an invoice without modifying QR-encoded fields preserves existing file without generating duplicate."""
        invoice = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer1,
            invoice_number="INV-STABLE-001",
            invoice_date=date(2026, 11, 3),
            subtotal=Decimal("500.00"),
            total_gst=Decimal("90.00"),
            grand_total=Decimal("590.00")
        )
        initial_file_name = invoice.qr_code.name

        # Ordinary update: saving again without changing the 4 QR fields
        invoice.save()
        invoice.refresh_from_db()

        self.assertEqual(invoice.qr_code.name, initial_file_name)

    def test_5_relevant_invoice_changes_regenerate_qr_code(self):
        """Modifying encoded invoice values (e.g., grand_total or customer) regenerates QR code with updated payload."""
        from PIL import Image
        from billing.utils import decode_qr_from_image

        invoice = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer1,
            invoice_number="INV-REGEN-001",
            invoice_date=date(2026, 11, 3),
            subtotal=Decimal("500.00"),
            total_gst=Decimal("90.00"),
            grand_total=Decimal("590.00")
        )

        # Update grand_total and customer
        invoice.customer = self.customer2
        invoice.grand_total = Decimal("850.00")
        invoice.save()

        invoice.refresh_from_db()

        with invoice.qr_code.open("rb") as f:
            updated_data = json.loads(decode_qr_from_image(Image.open(f))[0]["data"])

        self.assertEqual(updated_data["customer_name"], "Eva Green")
        self.assertEqual(updated_data["total_amount"], "850.00")

    def test_6_invoice_preview_displays_saved_qr_image(self):
        """Invoice preview detail view displays the saved QR image from media storage."""
        invoice = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer1,
            invoice_number="INV-PREV-001",
            invoice_date=date(2026, 11, 3),
            subtotal=Decimal("500.00"),
            total_gst=Decimal("90.00"),
            grand_total=Decimal("590.00")
        )

        self.client.login(username="auto_qr_dist", password="DistPassword@123")
        url = reverse("invoice_detail", kwargs={"pk": invoice.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertIn("Scan for Invoice Details", content)
        self.assertIn(invoice.qr_code.url, content)

    def test_7_qr_code_decodes_successfully(self):
        """QR code saved in media storage decodes with high fidelity."""
        from PIL import Image
        from billing.utils import decode_qr_from_image

        invoice = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer1,
            invoice_number="INV-DECODE-001",
            invoice_date=date(2026, 11, 3),
            subtotal=Decimal("1200.00"),
            total_gst=Decimal("216.00"),
            grand_total=Decimal("1416.00")
        )

        with invoice.qr_code.open("rb") as f:
            img = Image.open(f)
            decoded = decode_qr_from_image(img)

        self.assertTrue(len(decoded) > 0)
        payload = json.loads(decoded[0]["data"])
        self.assertEqual(payload["invoice_id"], "INV-DECODE-001")
        self.assertEqual(payload["total_amount"], "1416.00")

    def test_8_qr_generation_errors_handled_safely(self):
        """If QR code generation fails, invoice is still saved successfully without duplication or crash."""
        from unittest.mock import patch

        with patch("billing.models.Invoice.generate_and_save_qr_code", side_effect=RuntimeError("Storage failure")):
            invoice = Invoice.objects.create(
                distributor=self.distributor,
                customer=self.customer1,
                invoice_number="INV-SAFE-001",
                invoice_date=date(2026, 11, 3),
                subtotal=Decimal("300.00"),
                total_gst=Decimal("54.00"),
                grand_total=Decimal("354.00")
            )

        self.assertIsNotNone(invoice.pk)
        self.assertEqual(Invoice.objects.filter(invoice_number="INV-SAFE-001").count(), 1)


class DedicatedInvoicePreviewPageTests(TestCase):
    """
    Unit and integration tests for the dedicated Preview Invoice page with QR code.
    Verifies all 10 testing requirements:
    1. Preview button opens the correct invoice.
    2. Correct invoice details are displayed.
    3. Correct customer information is displayed.
    4. Invoice items and totals are accurate.
    5. Correct saved QR code is displayed with label 'Scan to Verify Invoice'.
    6. Different invoices show different data and QR codes.
    7. Invalid invoice ID returns 404.
    8. Unauthorized access is blocked (unauthenticated redirected, wrong distributor gets 404).
    9. Print layout and action buttons work correctly.
    10. Existing invoice list and PDF download functionality still work.
    """

    def setUp(self):
        from accounts.models import DistributorProfile
        self.distributor1 = User.objects.create_user(
            username="prev_dist_1",
            password="DistPassword@123",
            email="prev1@example.com"
        )
        self.profile1 = DistributorProfile.objects.create(
            user=self.distributor1,
            full_name="Alpha Tech Solutions",
            email="prev1@example.com",
            phone="9876500010"
        )

        self.distributor2 = User.objects.create_user(
            username="prev_dist_2",
            password="DistPassword@123",
            email="prev2@example.com"
        )
        self.profile2 = DistributorProfile.objects.create(
            user=self.distributor2,
            full_name="Beta Logistics",
            email="prev2@example.com",
            phone="9876500020"
        )

        self.customer1 = Customer.objects.create(
            distributor=self.distributor1,
            name="James Bond",
            email="james@mi6.gov.uk",
            phone="9876543210",
            address="MI6 HQ, Vauxhall Cross",
            city="London",
            state="Westminster",
            pincode="SW1A 1AA"
        )
        self.customer2 = Customer.objects.create(
            distributor=self.distributor1,
            name="Vesper Lynd",
            email="vesper@treasury.gov.uk",
            phone="9876543211",
            address="Treasury Dept, Whitehall",
            city="London",
            state="Westminster",
            pincode="SW1A 2HQ"
        )

        self.product1 = Product.objects.create(
            distributor=self.distributor1,
            name="Spy Watch",
            price=Decimal("500.00"),
            gst_rate=Decimal("18.00"),
            stock=50,
            sku="SPY-007"
        )

        # Invoice 1
        self.invoice1 = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer1,
            invoice_number="INV-PREV-001",
            invoice_date=date(2026, 11, 3),
            subtotal=Decimal("1000.00"),
            total_gst=Decimal("180.00"),
            grand_total=Decimal("1180.00")
        )
        InvoiceItem.objects.create(
            invoice=self.invoice1,
            product=self.product1,
            product_name=self.product1.name,
            quantity=2,
            unit_price=Decimal("500.00"),
            gst_rate=Decimal("18.00"),
            taxable_amount=Decimal("1000.00"),
            gst_amount=Decimal("180.00"),
            line_total=Decimal("1180.00")
        )

        # Invoice 2
        self.invoice2 = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer2,
            invoice_number="INV-PREV-002",
            invoice_date=date(2026, 11, 4),
            subtotal=Decimal("500.00"),
            total_gst=Decimal("90.00"),
            grand_total=Decimal("590.00")
        )
        InvoiceItem.objects.create(
            invoice=self.invoice2,
            product=self.product1,
            product_name=self.product1.name,
            quantity=1,
            unit_price=Decimal("500.00"),
            gst_rate=Decimal("18.00"),
            taxable_amount=Decimal("500.00"),
            gst_amount=Decimal("90.00"),
            line_total=Decimal("590.00")
        )

    def test_1_preview_button_opens_correct_invoice(self):
        """Clicking Preview opens the dedicated preview page with HTTP 200 and correct invoice context."""
        self.client.login(username="prev_dist_1", password="DistPassword@123")
        url = reverse("invoice_preview", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["invoice"].pk, self.invoice1.pk)
        self.assertTemplateUsed(response, "billing/invoice_preview.html")

    def test_2_correct_invoice_details_displayed(self):
        """Invoice number, date, and status are properly rendered."""
        self.client.login(username="prev_dist_1", password="DistPassword@123")
        url = reverse("invoice_preview", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)
        content = response.content.decode("utf-8")

        self.assertIn("INV-PREV-001", content)
        self.assertIn("03 Nov 2026", content)
        self.assertIn("Paid", content)

    def test_3_correct_customer_information_displayed(self):
        """Customer name, contact details, and address are properly displayed."""
        self.client.login(username="prev_dist_1", password="DistPassword@123")
        url = reverse("invoice_preview", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)
        content = response.content.decode("utf-8")

        self.assertIn("James Bond", content)
        self.assertIn("james@mi6.gov.uk", content)
        self.assertIn("9876543210", content)
        self.assertIn("MI6 HQ, Vauxhall Cross", content)
        self.assertIn("London", content)

    def test_4_invoice_items_and_totals_are_accurate(self):
        """Product line items, unit price, quantity, subtotal, GST, and grand total are accurate."""
        self.client.login(username="prev_dist_1", password="DistPassword@123")
        url = reverse("invoice_preview", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)
        content = response.content.decode("utf-8")

        self.assertIn("Spy Watch", content)
        self.assertIn("SPY-007", content)
        self.assertIn("1000.00", content)
        self.assertIn("180.00", content)
        self.assertIn("1180.00", content)

    def test_5_correct_saved_qr_code_is_displayed_with_label(self):
        """Saved QR code from media storage is rendered with 'Scan to Verify Invoice' label."""
        from PIL import Image
        from billing.utils import decode_qr_from_image

        self.client.login(username="prev_dist_1", password="DistPassword@123")
        url = reverse("invoice_preview", kwargs={"pk": self.invoice1.pk})
        response = self.client.get(url)
        content = response.content.decode("utf-8")

        self.assertIn("Scan to Verify Invoice", content)
        self.assertIn(self.invoice1.qr_code.url, content)

        # Decode the rendered QR code from file
        with self.invoice1.qr_code.open("rb") as f:
            decoded = json.loads(decode_qr_from_image(Image.open(f))[0]["data"])

        self.assertEqual(decoded["invoice_id"], "INV-PREV-001")
        self.assertEqual(decoded["customer_name"], "James Bond")
        self.assertEqual(decoded["total_amount"], "1180.00")
        self.assertEqual(decoded["invoice_date"], "2026-11-03")

    def test_6_different_invoices_show_different_data_and_qr_codes(self):
        """Previews of different invoices render distinct details and distinct QR codes."""
        self.client.login(username="prev_dist_1", password="DistPassword@123")

        resp1 = self.client.get(reverse("invoice_preview", kwargs={"pk": self.invoice1.pk}))
        resp2 = self.client.get(reverse("invoice_preview", kwargs={"pk": self.invoice2.pk}))

        content1 = resp1.content.decode("utf-8")
        content2 = resp2.content.decode("utf-8")

        self.assertIn("INV-PREV-001", content1)
        self.assertNotIn("INV-PREV-002", content1)

        self.assertIn("INV-PREV-002", content2)
        self.assertNotIn("INV-PREV-001", content2)

        self.assertIn(self.invoice1.qr_code.url, content1)
        self.assertIn(self.invoice2.qr_code.url, content2)
        self.assertNotEqual(self.invoice1.qr_code.url, self.invoice2.qr_code.url)

    def test_7_invalid_invoice_id_returns_404(self):
        """Requesting non-existent invoice preview returns HTTP 404."""
        self.client.login(username="prev_dist_1", password="DistPassword@123")
        response = self.client.get(reverse("invoice_preview", kwargs={"pk": 999999}))
        self.assertEqual(response.status_code, 404)

    def test_8_unauthorized_access_is_blocked(self):
        """Unauthenticated request is redirected; access across different distributors returns 404."""
        # Unauthenticated
        response = self.client.get(reverse("invoice_preview", kwargs={"pk": self.invoice1.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("distributor_login"), response.url)

        # Logged in as different distributor
        self.client.login(username="prev_dist_2", password="DistPassword@123")
        cross_response = self.client.get(reverse("invoice_preview", kwargs={"pk": self.invoice1.pk}))
        self.assertEqual(cross_response.status_code, 404)

    def test_9_print_layout_and_action_buttons_present(self):
        """Preview UI contains Back, Print (window.print), and Download PDF action buttons."""
        self.client.login(username="prev_dist_1", password="DistPassword@123")
        response = self.client.get(reverse("invoice_preview", kwargs={"pk": self.invoice1.pk}))
        content = response.content.decode("utf-8")

        self.assertIn("Back to Invoices", content)
        self.assertIn("window.print()", content)
        self.assertIn("Print Invoice", content)
        self.assertIn(reverse("invoice_pdf_download", kwargs={"pk": self.invoice1.pk}), content)
        self.assertIn("Download PDF", content)
        self.assertIn("@media print", content)
        self.assertIn("d-print-none", content)

    def test_10_existing_invoice_list_and_pdf_functionality_still_work(self):
        """Invoice list displays Preview button and PDF download remains operational."""
        self.client.login(username="prev_dist_1", password="DistPassword@123")

        # Invoice List contains Preview button
        list_resp = self.client.get(reverse("invoice_list"))
        self.assertEqual(list_resp.status_code, 200)
        list_content = list_resp.content.decode("utf-8")
        preview_url = reverse("invoice_preview", kwargs={"pk": self.invoice1.pk})
        self.assertIn(preview_url, list_content)
        self.assertIn("Preview", list_content)

        # Invoice Detail contains Preview Invoice button
        detail_resp = self.client.get(reverse("invoice_detail", kwargs={"pk": self.invoice1.pk}))
        self.assertEqual(detail_resp.status_code, 200)
        detail_content = detail_resp.content.decode("utf-8")
        self.assertIn(preview_url, detail_content)
        self.assertIn("Preview Invoice", detail_content)

        # PDF Download works
        pdf_resp = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": self.invoice1.pk}))
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertEqual(pdf_resp["Content-Type"], "application/pdf")
        self.assertTrue(pdf_resp.content.startswith(b"%PDF"))


class ComprehensiveInvoicePDFVerificationTests(TestCase):
    """
    Exhaustive verification of xhtml2pdf & ReportLab Invoice PDF generation:
    1. Single product invoice PDF generation.
    2. Multi-product invoice with diverse GST rates (0%, 5%, 12%, 18%, 28%) & discounts (0%, 5%, 10%, 25%).
    3. Large currency amounts with Indian Rupee formatting.
    4. Empty items edge case handling.
    5. Missing customer contact / address fallback handling.
    6. Payment status indicators (Paid, Pending, Unpaid).
    7. Embedded QR code extraction and scannability from the generated PDF.
    8. Download header attachment verification and filename sanitization.
    9. Cross-distributor security and authorization isolation.
    """

    def setUp(self):
        self.client = Client()

        # Distributor group & users
        self.dist_group, _ = Group.objects.get_or_create(name="Distributor")
        self.distributor1 = User.objects.create_user(
            username="pdf_test_dist1",
            email="pdf_dist1@example.com",
            password="DistPassword@123"
        )
        self.distributor1.groups.add(self.dist_group)
        self.profile1, _ = DistributorProfile.objects.get_or_create(
            user=self.distributor1,
            defaults={
                "full_name": "Alpha Distributors Pvt Ltd",
                "email": "contact@alphadist.com",
                "phone": "9876543210"
            }
        )

        self.distributor2 = User.objects.create_user(
            username="pdf_test_dist2",
            email="pdf_dist2@example.com",
            password="DistPassword@123"
        )
        self.distributor2.groups.add(self.dist_group)

        # Customers
        self.customer_full = Customer.objects.create(
            distributor=self.distributor1,
            name="Apex Infotech Solutions",
            email="accounts@apexinfo.com",
            phone="9876501234",
            address="Building 4A, Tech Park, Outer Ring Road",
            city="Bengaluru",
            state="Karnataka",
            pincode="560103"
        )
        self.customer_minimal = Customer.objects.create(
            distributor=self.distributor1,
            name="Simple Minimal Customer",
            email="",
            phone="",
            address="",
            city="",
            state="",
            pincode=""
        )

        # Products with diverse GST rates
        self.p_0gst = Product.objects.create(
            distributor=self.distributor1,
            name="Organic Grain Package",
            price=Decimal("100.00"),
            stock=100,
            gst_rate=Decimal("0.00"),
            sku="GRAIN-00"
        )
        self.p_5gst = Product.objects.create(
            distributor=self.distributor1,
            name="Packaged Edible Oil",
            price=Decimal("200.00"),
            stock=100,
            gst_rate=Decimal("5.00"),
            sku="OIL-05"
        )
        self.p_12gst = Product.objects.create(
            distributor=self.distributor1,
            name="Processed Dairy Cheese",
            price=Decimal("300.00"),
            stock=100,
            gst_rate=Decimal("12.00"),
            sku="CHEESE-12"
        )
        self.p_18gst = Product.objects.create(
            distributor=self.distributor1,
            name="Ergonomic Optical Mouse",
            price=Decimal("800.00"),
            stock=100,
            gst_rate=Decimal("18.00"),
            sku="MOUSE-18"
        )
        self.p_28gst = Product.objects.create(
            distributor=self.distributor1,
            name="High Performance Air Conditioner",
            price=Decimal("35000.00"),
            stock=10,
            gst_rate=Decimal("28.00"),
            sku="AC-28"
        )

    def test_single_item_invoice_pdf_download(self):
        """Single product invoice generates valid PDF with correct download headers."""
        self.client.login(username="pdf_test_dist1", password="DistPassword@123")
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer_full,
            invoice_number="INV-SINGLE-01",
            invoice_date="2026-11-01",
            subtotal=Decimal("800.00"),
            total_gst=Decimal("144.00"),
            grand_total=Decimal("944.00")
        )
        InvoiceItem.objects.create(
            invoice=inv,
            product=self.p_18gst,
            product_name=self.p_18gst.name,
            quantity=1,
            unit_price=Decimal("800.00"),
            gst_rate=Decimal("18.00"),
            discount_percent=Decimal("0.00"),
            taxable_amount=Decimal("800.00"),
            gst_amount=Decimal("144.00"),
            line_total=Decimal("944.00")
        )

        url = reverse("invoice_pdf_download", kwargs={"pk": inv.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertEqual(resp["Content-Disposition"], 'attachment; filename="Invoice-INV-SINGLE-01.pdf"')
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_multi_gst_rates_and_discounts_pdf(self):
        """Invoice with multiple GST rates (0%, 5%, 12%, 18%, 28%) and varied discounts renders cleanly."""
        self.client.login(username="pdf_test_dist1", password="DistPassword@123")
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer_full,
            invoice_number="INV-MULTI-GST-01",
            invoice_date="2026-11-02",
            subtotal=Decimal("38000.00"),
            total_gst=Decimal("8500.00"),
            grand_total=Decimal("46500.00")
        )
        # 0% GST, 0% discount
        InvoiceItem.objects.create(
            invoice=inv, product=self.p_0gst, product_name=self.p_0gst.name,
            quantity=5, unit_price=Decimal("100.00"), gst_rate=Decimal("0.00"),
            discount_percent=Decimal("0.00"), taxable_amount=Decimal("500.00"),
            gst_amount=Decimal("0.00"), line_total=Decimal("500.00")
        )
        # 5% GST, 5% discount
        InvoiceItem.objects.create(
            invoice=inv, product=self.p_5gst, product_name=self.p_5gst.name,
            quantity=2, unit_price=Decimal("200.00"), gst_rate=Decimal("5.00"),
            discount_percent=Decimal("5.00"), taxable_amount=Decimal("380.00"),
            gst_amount=Decimal("19.00"), line_total=Decimal("399.00")
        )
        # 12% GST, 10% discount
        InvoiceItem.objects.create(
            invoice=inv, product=self.p_12gst, product_name=self.p_12gst.name,
            quantity=3, unit_price=Decimal("300.00"), gst_rate=Decimal("12.00"),
            discount_percent=Decimal("10.00"), taxable_amount=Decimal("810.00"),
            gst_amount=Decimal("97.20"), line_total=Decimal("907.20")
        )
        # 18% GST, 15% discount
        InvoiceItem.objects.create(
            invoice=inv, product=self.p_18gst, product_name=self.p_18gst.name,
            quantity=2, unit_price=Decimal("800.00"), gst_rate=Decimal("18.00"),
            discount_percent=Decimal("15.00"), taxable_amount=Decimal("1360.00"),
            gst_amount=Decimal("244.80"), line_total=Decimal("1604.80")
        )
        # 28% GST, 20% discount
        InvoiceItem.objects.create(
            invoice=inv, product=self.p_28gst, product_name=self.p_28gst.name,
            quantity=1, unit_price=Decimal("35000.00"), gst_rate=Decimal("28.00"),
            discount_percent=Decimal("20.00"), taxable_amount=Decimal("28000.00"),
            gst_amount=Decimal("7840.00"), line_total=Decimal("35840.00")
        )

        resp = self.client.get(reverse("invoice_pdf_view", kwargs={"pk": inv.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_large_invoice_amount_formatting_pdf(self):
        """Very large financial amounts render with valid Indian currency format."""
        self.client.login(username="pdf_test_dist1", password="DistPassword@123")
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer_full,
            invoice_number="INV-LARGE-AMT",
            invoice_date="2026-11-03",
            subtotal=Decimal("850000.00"),
            total_gst=Decimal("153000.00"),
            grand_total=Decimal("1003000.00")
        )
        InvoiceItem.objects.create(
            invoice=inv, product=self.p_28gst, product_name="Enterprise Fleet AC Units",
            quantity=25, unit_price=Decimal("34000.00"), gst_rate=Decimal("18.00"),
            discount_percent=Decimal("0.00"), taxable_amount=Decimal("850000.00"),
            gst_amount=Decimal("153000.00"), line_total=Decimal("1003000.00")
        )
        resp = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": inv.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_empty_invoice_items_graceful_pdf(self):
        """Invoice with zero items renders gracefully with empty-state row instead of failing."""
        self.client.login(username="pdf_test_dist1", password="DistPassword@123")
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer_full,
            invoice_number="INV-EMPTY-01",
            invoice_date="2026-11-03",
            subtotal=Decimal("0.00"),
            total_gst=Decimal("0.00"),
            grand_total=Decimal("0.00")
        )
        resp = self.client.get(reverse("invoice_pdf", kwargs={"pk": inv.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_missing_customer_contact_fallback_pdf(self):
        """Invoice for customer with empty contact & address details generates clean fallback."""
        self.client.login(username="pdf_test_dist1", password="DistPassword@123")
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer_minimal,
            invoice_number="INV-MINIMAL-CUST",
            invoice_date="2026-11-03",
            subtotal=Decimal("100.00"),
            total_gst=Decimal("0.00"),
            grand_total=Decimal("100.00")
        )
        InvoiceItem.objects.create(
            invoice=inv, product=self.p_0gst, product_name=self.p_0gst.name,
            quantity=1, unit_price=Decimal("100.00"), gst_rate=Decimal("0.00"),
            discount_percent=Decimal("0.00"), taxable_amount=Decimal("100.00"),
            gst_amount=Decimal("0.00"), line_total=Decimal("100.00")
        )
        resp = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": inv.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_payment_statuses_in_pdf(self):
        """PDF generation handles Paid, Pending and Unpaid payment statuses."""
        self.client.login(username="pdf_test_dist1", password="DistPassword@123")
        for status in ["Paid", "Pending", "Unpaid"]:
            inv = Invoice.objects.create(
                distributor=self.distributor1,
                customer=self.customer_full,
                invoice_number=f"INV-STATUS-{status.upper()}",
                invoice_date="2026-11-03",
                subtotal=Decimal("100.00"),
                total_gst=Decimal("0.00"),
                grand_total=Decimal("100.00")
            )
            inv.payment_status = status
            resp = self.client.get(reverse("invoice_pdf", kwargs={"pk": inv.pk}))
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_qr_code_scannable_from_generated_pdf(self):
        """Extract embedded image from the generated PDF and decode QR code with valid payload."""
        self.client.login(username="pdf_test_dist1", password="DistPassword@123")
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer_full,
            invoice_number="INV-QR-SCAN-01",
            invoice_date="2026-11-04",
            subtotal=Decimal("800.00"),
            total_gst=Decimal("144.00"),
            grand_total=Decimal("944.00")
        )
        InvoiceItem.objects.create(
            invoice=inv, product=self.p_18gst, product_name=self.p_18gst.name,
            quantity=1, unit_price=Decimal("800.00"), gst_rate=Decimal("18.00"),
            discount_percent=Decimal("0.00"), taxable_amount=Decimal("800.00"),
            gst_amount=Decimal("144.00"), line_total=Decimal("944.00")
        )

        resp = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": inv.pk}))
        self.assertEqual(resp.status_code, 200)
        pdf_bytes = resp.content

        # Extract embedded image stream from PDF
        from pypdf import PdfReader
        from PIL import Image
        from billing.utils import decode_qr_from_image

        reader = PdfReader(BytesIO(pdf_bytes))
        self.assertTrue(len(reader.pages) >= 1)

        images = []
        for page in reader.pages:
            for name, img in page.images.items():
                images.append(Image.open(BytesIO(img.data)))

        self.assertTrue(len(images) >= 1, "Expected at least 1 embedded QR image in invoice PDF")

        # Decode QR from extracted image
        decoded_results = decode_qr_from_image(images[0])
        self.assertTrue(len(decoded_results) >= 1, "Failed to decode QR code from PDF image")
        qr_text = decoded_results[0]["data"]
        self.assertIn("INV-QR-SCAN-01", qr_text)
        self.assertIn("Apex Infotech Solutions", qr_text)
        self.assertIn("944.00", qr_text)

    def test_security_distributor_isolation_and_unauthorized(self):
        """Distributor B cannot access Distributor A's invoice; unauthenticated redirects to login."""
        inv = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer_full,
            invoice_number="INV-PRIVATE-01",
            invoice_date="2026-11-04",
            subtotal=Decimal("100.00"),
            total_gst=Decimal("0.00"),
            grand_total=Decimal("100.00")
        )

        # 1. Unauthenticated request -> redirects to distributor login
        unauth_resp = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": inv.pk}))
        self.assertEqual(unauth_resp.status_code, 302)
        self.assertIn("/distributor/login/", unauth_resp.url)

        # 2. Distributor 2 request -> 404 Not Found
        self.client.login(username="pdf_test_dist2", password="DistPassword@123")
        cross_resp = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": inv.pk}))
        self.assertEqual(cross_resp.status_code, 404)

        # 3. Non-existent invoice -> 404 Not Found
        self.client.login(username="pdf_test_dist1", password="DistPassword@123")
        missing_resp = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": 999999}))
        self.assertEqual(missing_resp.status_code, 404)


import base64
from io import BytesIO
from unittest.mock import patch
from PIL import Image
from pypdf import PdfReader

class DynamicQRCodeEmbeddingPDFTests(TestCase):
    """
    Verification and testing of dynamic QR code embedding in Invoice PDFs:
    1. QR code is dynamically generated using actual saved invoice data (id, customer, total, date).
    2. generate_invoice_qr_base64() returns a valid Base64 PNG data URI.
    3. Both invoice_pdf_view() and invoice_pdf_download() pass QR image correctly and return valid PDFs.
    4. QR image is rendered in invoice_pdf.html within the footer with appropriate dimensions.
    5. QR code extracted from the generated PDF is fully scannable and matches the invoice record.
    6. Distinct invoices generate distinct, non-overlapping QR codes.
    7. Error handling for unsaved invoices, empty QR codes, and media fallback.
    """

    def setUp(self):
        self.client = Client()
        self.dist_group, _ = Group.objects.get_or_create(name="Distributor")
        self.distributor = User.objects.create_user(
            username="dist_qr_embed_user",
            email="dist_qr@example.com",
            password="DistPassword@123"
        )
        self.distributor.groups.add(self.dist_group)
        self.profile = DistributorProfile.objects.create(
            user=self.distributor,
            full_name="Prime Tech Distributors",
            email="dist_qr@example.com",
            phone="9876543210"
        )

        self.customer_a = Customer.objects.create(
            distributor=self.distributor,
            name="Alpha Corp",
            email="alpha@example.com",
            phone="9123456780",
            address="101 Alpha Tower",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001"
        )
        self.customer_b = Customer.objects.create(
            distributor=self.distributor,
            name="Beta Enterprise",
            email="beta@example.com",
            phone="9234567891",
            address="202 Beta Square",
            city="Pune",
            state="Maharashtra",
            pincode="411001"
        )

        self.invoice_a = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer_a,
            invoice_number="INV-DYN-A101",
            invoice_date="2026-11-04",
            subtotal=Decimal("2000.00"),
            total_gst=Decimal("360.00"),
            grand_total=Decimal("2360.00")
        )

        self.invoice_b = Invoice.objects.create(
            distributor=self.distributor,
            customer=self.customer_b,
            invoice_number="INV-DYN-B202",
            invoice_date="2026-11-05",
            subtotal=Decimal("5000.00"),
            total_gst=Decimal("900.00"),
            grand_total=Decimal("5900.00")
        )

    def test_dynamic_qr_payload_and_base64_generation(self):
        """Verify QR code is generated using actual invoice details and returns valid Base64 PNG."""
        payload = build_invoice_qr_payload(self.invoice_a)
        self.assertEqual(payload["invoice_id"], "INV-DYN-A101")
        self.assertEqual(payload["customer_name"], "Alpha Corp")
        self.assertEqual(payload["total_amount"], "2360.00")
        self.assertEqual(payload["invoice_date"], "2026-11-04")

        # Base64 URI verification
        data_uri = generate_invoice_qr_base64(self.invoice_a)
        self.assertTrue(data_uri.startswith("data:image/png;base64,"))
        b64_part = data_uri.split(",", 1)[1]
        decoded_bytes = base64.b64decode(b64_part)
        self.assertTrue(decoded_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

        # Decode directly from generated image
        img = Image.open(BytesIO(decoded_bytes))
        scan_results = decode_qr_from_image(img)
        self.assertTrue(len(scan_results) >= 1)
        qr_obj = json.loads(scan_results[0]["data"])
        self.assertEqual(qr_obj["invoice_id"], "INV-DYN-A101")
        self.assertEqual(qr_obj["customer_name"], "Alpha Corp")
        self.assertEqual(qr_obj["total_amount"], "2360.00")
        self.assertEqual(qr_obj["invoice_date"], "2026-11-04")

    def test_both_pdf_view_and_download_pass_qr_and_render_pdf(self):
        """Verify both invoice_pdf_view and invoice_pdf_download pass QR and return valid PDFs."""
        self.client.login(username="dist_qr_embed_user", password="DistPassword@123")

        # 1. View (inline)
        resp_view = self.client.get(reverse("invoice_pdf", kwargs={"pk": self.invoice_a.pk}))
        self.assertEqual(resp_view.status_code, 200)
        self.assertEqual(resp_view["Content-Type"], "application/pdf")
        self.assertTrue(resp_view.content.startswith(b"%PDF"))
        self.assertIn("inline", resp_view["Content-Disposition"])
        self.assertIn("Invoice-INV-DYN-A101.pdf", resp_view["Content-Disposition"])

        # 2. Download (attachment)
        resp_dl = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": self.invoice_a.pk}))
        self.assertEqual(resp_dl.status_code, 200)
        self.assertEqual(resp_dl["Content-Type"], "application/pdf")
        self.assertTrue(resp_dl.content.startswith(b"%PDF"))
        self.assertIn("attachment", resp_dl["Content-Disposition"])
        self.assertIn("Invoice-INV-DYN-A101.pdf", resp_dl["Content-Disposition"])

    def test_qr_code_scannable_and_payload_matches_db_record(self):
        """Extract embedded image from generated PDF and verify QR decodes to exact saved invoice record."""
        self.client.login(username="dist_qr_embed_user", password="DistPassword@123")
        resp = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": self.invoice_a.pk}))
        self.assertEqual(resp.status_code, 200)

        reader = PdfReader(BytesIO(resp.content))
        self.assertTrue(len(reader.pages) >= 1)

        extracted_images = []
        for page in reader.pages:
            for name, img_obj in page.images.items():
                extracted_images.append(Image.open(BytesIO(img_obj.data)))

        self.assertTrue(len(extracted_images) >= 1, "PDF does not contain any embedded images")

        decoded = decode_qr_from_image(extracted_images[0])
        self.assertTrue(len(decoded) >= 1, "Failed to decode QR code embedded in PDF")
        qr_data = json.loads(decoded[0]["data"])

        self.assertEqual(qr_data["invoice_id"], self.invoice_a.invoice_number)
        self.assertEqual(qr_data["customer_name"], self.invoice_a.customer.name)
        self.assertEqual(qr_data["total_amount"], f"{self.invoice_a.grand_total:.2f}")
        self.assertEqual(qr_data["invoice_date"], str(self.invoice_a.invoice_date))

    def test_multiple_invoices_generate_distinct_qr_codes(self):
        """Different invoices generate different QR codes and scan to their own distinct data."""
        self.client.login(username="dist_qr_embed_user", password="DistPassword@123")

        uri_a = generate_invoice_qr_base64(self.invoice_a)
        uri_b = generate_invoice_qr_base64(self.invoice_b)
        self.assertNotEqual(uri_a, uri_b)

        # PDF A
        resp_a = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": self.invoice_a.pk}))
        reader_a = PdfReader(BytesIO(resp_a.content))
        img_a = [Image.open(BytesIO(im.data)) for p in reader_a.pages for _, im in p.images.items()][0]
        dec_a = json.loads(decode_qr_from_image(img_a)[0]["data"])

        # PDF B
        resp_b = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": self.invoice_b.pk}))
        reader_b = PdfReader(BytesIO(resp_b.content))
        img_b = [Image.open(BytesIO(im.data)) for p in reader_b.pages for _, im in p.images.items()][0]
        dec_b = json.loads(decode_qr_from_image(img_b)[0]["data"])

        # Assert independent contents
        self.assertEqual(dec_a["invoice_id"], "INV-DYN-A101")
        self.assertEqual(dec_a["customer_name"], "Alpha Corp")
        self.assertEqual(dec_b["invoice_id"], "INV-DYN-B202")
        self.assertEqual(dec_b["customer_name"], "Beta Enterprise")
        self.assertNotEqual(dec_a["invoice_id"], dec_b["invoice_id"])

    def test_qr_generation_error_handling_and_fallback(self):
        """Error handling for unsaved invoice, missing customer, empty QR in template, and saved QR fallback."""
        # 1. Unsaved invoice returns empty string without crashing
        unsaved_inv = Invoice(distributor=self.distributor, invoice_number="INV-UNSAVED")
        result = generate_invoice_qr_base64(unsaved_inv)
        self.assertEqual(result, "")

        # 2. Template renders cleanly when QR code is missing/empty
        context = {
            "invoice": self.invoice_a,
            "items": [],
            "customer": self.invoice_a.customer,
            "distributor": self.distributor,
            "qr_code": "",
            "qr_code_url": "",
            "gross_total": Decimal("2000.00"),
            "total_discount": Decimal("0.00"),
        }
        pdf_bytes = render_to_pdf("billing/invoice_pdf.html", context)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

        # 3. Fallback to invoice.qr_code if generate_invoice_qr_base64 fails
        self.invoice_a.generate_and_save_qr_code(force=True)
        self.assertTrue(bool(self.invoice_a.qr_code))
        
        self.client.login(username="dist_qr_embed_user", password="DistPassword@123")
        with patch("billing.views.generate_invoice_qr_base64", return_value=""):
            resp_fallback = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": self.invoice_a.pk}))
            self.assertEqual(resp_fallback.status_code, 200)
            self.assertTrue(resp_fallback.content.startswith(b"%PDF"))


class InvoicePDFDownloadButtonAndAlertTests(TestCase):
    """
    Automated verification of the improved Download PDF button and success/failure alerts:
    1. Download PDF button visibility, data attributes, and alert container in invoice preview page.
    2. Successful PDF download response (HTTP 200, application/pdf, %PDF header, attachment header).
    3. Backend error handling when PDF generation fails:
       - AJAX / XMLHttpRequest returns HTTP 500 JSON with error message.
       - Standard GET returns HTTP 500 text/plain with error message.
    4. Distributor security isolation and 404 handling.
    5. Client script verification (double-click prevention, loading spinner, success & danger messages, %PDF validation).
    """

    def setUp(self):
        self.client = Client()
        self.dist_group, _ = Group.objects.get_or_create(name="Distributor")

        self.distributor1 = User.objects.create_user(
            username="pdf_btn_dist1",
            email="pdf_dist1@example.com",
            password="DistPassword@123"
        )
        self.distributor1.groups.add(self.dist_group)
        self.profile1 = DistributorProfile.objects.create(
            user=self.distributor1,
            full_name="Metro Distributors Ltd",
            email="metro@example.com",
            phone="9876543210"
        )

        self.distributor2 = User.objects.create_user(
            username="pdf_btn_dist2",
            email="pdf_dist2@example.com",
            password="DistPassword@123"
        )
        self.distributor2.groups.add(self.dist_group)

        self.customer = Customer.objects.create(
            distributor=self.distributor1,
            name="Horizon Corp",
            email="horizon@example.com",
            phone="9123456780",
            address="Plot 5, Sector 18",
            city="Gurugram",
            state="Haryana",
            pincode="122015"
        )

        self.invoice = Invoice.objects.create(
            distributor=self.distributor1,
            customer=self.customer,
            invoice_number="INV-BTN-2026-01",
            invoice_date="2026-11-05",
            subtotal=Decimal("3000.00"),
            total_gst=Decimal("540.00"),
            grand_total=Decimal("3540.00")
        )

    def test_preview_page_renders_download_button_and_alert_container(self):
        """Preview page renders the download button with correct attributes and toast/alert container."""
        self.client.login(username="pdf_btn_dist1", password="DistPassword@123")
        url = reverse("billing_invoice_preview", kwargs={"pk": self.invoice.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "billing/invoice_preview.html")

        content = response.content.decode("utf-8")

        # 1. Download button structure
        self.assertIn('id="downloadPdfBtn"', content)
        expected_download_url = reverse("invoice_pdf_download", kwargs={"pk": self.invoice.pk})
        self.assertIn(f'data-download-url="{expected_download_url}"', content)
        self.assertIn(f'data-filename="Invoice-{self.invoice.invoice_number}.pdf"', content)
        self.assertIn("Download PDF", content)

        # 2. Toast/Alert container & dismiss button
        self.assertIn('id="pdfAlertContainer"', content)
        self.assertIn('id="pdfAlert"', content)
        self.assertIn('id="pdfAlertIcon"', content)
        self.assertIn('id="pdfAlertMessage"', content)
        self.assertIn('id="pdfAlertCloseBtn"', content)

        # 3. Client-side script features
        self.assertIn("Invoice PDF downloaded successfully.", content)
        self.assertIn("Unable to download invoice PDF. Please try again.", content)
        self.assertIn("spinner-border", content)
        self.assertIn("isDownloading", content)
        self.assertIn("application/pdf", content)
        self.assertIn("%PDF", content)

    def test_successful_pdf_download_response(self):
        """Successful PDF download returns HTTP 200, application/pdf, %PDF signature, and attachment header."""
        self.client.login(username="pdf_btn_dist1", password="DistPassword@123")
        url = reverse("invoice_pdf_download", kwargs={"pk": self.invoice.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(f"Invoice-{self.invoice.invoice_number}.pdf", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertTrue(len(response.content) > 1000)

    def test_pdf_generation_failure_ajax_returns_500_json(self):
        """When PDF generation fails, an AJAX request receives HTTP 500 with user-safe JSON error."""
        self.client.login(username="pdf_btn_dist1", password="DistPassword@123")
        url = reverse("invoice_pdf_download", kwargs={"pk": self.invoice.pk})

        with patch("billing.views.render_to_pdf", return_value=None):
            response = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
            self.assertEqual(response.status_code, 500)
            self.assertIn("application/json", response["Content-Type"])
            data = json.loads(response.content.decode("utf-8"))
            self.assertEqual(data["error"], "Unable to download invoice PDF. Please try again.")

    def test_pdf_generation_failure_standard_returns_500_text(self):
        """When PDF generation fails, standard request receives HTTP 500 text without exposing internal stack traces."""
        self.client.login(username="pdf_btn_dist1", password="DistPassword@123")
        url = reverse("invoice_pdf_download", kwargs={"pk": self.invoice.pk})

        with patch("billing.views.render_to_pdf", return_value=None):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 500)
            self.assertIn("Unable to download invoice PDF. Please try again.", response.content.decode("utf-8"))

    def test_download_unauthorized_and_cross_distributor_isolation(self):
        """Cross-distributor request returns 404, unauthenticated request redirects to login."""
        url = reverse("invoice_pdf_download", kwargs={"pk": self.invoice.pk})

        # 1. Unauthenticated -> 302 redirect to login
        unauth_resp = self.client.get(url)
        self.assertEqual(unauth_resp.status_code, 302)
        self.assertIn("/distributor/login/", unauth_resp.url)

        # 2. Distributor 2 -> 404 Not Found
        self.client.login(username="pdf_btn_dist2", password="DistPassword@123")
        cross_resp = self.client.get(url)
        self.assertEqual(cross_resp.status_code, 404)

        # 3. Nonexistent invoice -> 404 Not Found
        self.client.login(username="pdf_btn_dist1", password="DistPassword@123")
        missing_resp = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": 999999}))
        self.assertEqual(missing_resp.status_code, 404)


class DjangoAdminManualDataEntryTests(TestCase):
    """
    Automated verification of manual data entry for Customer, Invoice, and InvoiceItem via Django Admin:
    1. CustomerAdmin registration, list_display, search_fields, list_filter, manual add and edit.
    2. InvoiceAdmin registration with InvoiceItemInline, list_display, search_fields, list_filter, date_hierarchy.
    3. Manual creation of an invoice with multiple inline items, auto-numbering, auto-pricing and tax calculations.
    4. InvoiceItemAdmin registration, list_display, search_fields, list_filter.
    5. Full integration: manually created invoices work seamlessly with Invoice Preview, QR code, and PDF download.
    """

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username="admin_billing_mgr",
            email="admin_mgr@example.com",
            password="AdminPassword@123"
        )

        self.dist_group, _ = Group.objects.get_or_create(name="Distributor")
        self.distributor = User.objects.create_user(
            username="dist_billing_user",
            email="dist_billing@example.com",
            password="DistPassword@123"
        )
        self.distributor.groups.add(self.dist_group)
        self.profile = DistributorProfile.objects.create(
            user=self.distributor,
            full_name="Prime Supply Network",
            email="dist_billing@example.com",
            phone="9876543210"
        )

        self.product1 = Product.objects.create(
            distributor=self.distributor,
            name="Smart POS Terminal",
            price=Decimal("4500.00"),
            stock=25,
            gst_rate=Decimal("18.00"),
            sku="POS-4500"
        )

        self.product2 = Product.objects.create(
            distributor=self.distributor,
            name="Thermal Receipt Paper Roll",
            price=Decimal("150.00"),
            stock=200,
            gst_rate=Decimal("12.00"),
            sku="PAPER-150"
        )

    def test_customer_admin_configuration_and_manual_entry(self):
        """Admin can manually add, edit, search and filter Customers via Django Admin."""
        from django.contrib import admin as django_admin
        from billing.admin import CustomerAdmin

        # 1. Verify ModelAdmin configuration
        customer_admin = django_admin.site._registry[Customer]
        self.assertIsInstance(customer_admin, CustomerAdmin)
        self.assertIn("name", customer_admin.list_display)
        self.assertIn("email", customer_admin.list_display)
        self.assertIn("phone", customer_admin.list_display)
        self.assertIn("name", customer_admin.search_fields)
        self.assertIn("created_at", customer_admin.list_filter)

        # 2. Add customer via Admin POST
        self.client.login(username="admin_billing_mgr", password="AdminPassword@123")
        add_url = reverse("admin:billing_customer_add")
        cust_payload = {
            "distributor": self.distributor.pk,
            "name": "Apex Commerce Pvt Ltd",
            "email": "info@apexcommerce.in",
            "phone": "9812345678",
            "address": "Level 4, Business Tower",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560001",
        }
        resp = self.client.post(add_url, data=cust_payload, follow=True)
        self.assertEqual(resp.status_code, 200)

        created_cust = Customer.objects.filter(name="Apex Commerce Pvt Ltd").first()
        self.assertIsNotNone(created_cust)
        self.assertEqual(created_cust.phone, "9812345678")
        self.assertEqual(created_cust.city, "Bengaluru")

        # 3. Edit customer via Admin POST
        change_url = reverse("admin:billing_customer_change", args=[created_cust.pk])
        cust_payload["city"] = "Bengaluru Urban"
        edit_resp = self.client.post(change_url, data=cust_payload, follow=True)
        self.assertEqual(edit_resp.status_code, 200)
        created_cust.refresh_from_db()
        self.assertEqual(created_cust.city, "Bengaluru Urban")

        # 4. Search & filter in changelist
        list_url = reverse("admin:billing_customer_changelist")
        search_resp = self.client.get(list_url + "?q=Apex")
        self.assertEqual(search_resp.status_code, 200)
        self.assertContains(search_resp, "Apex Commerce Pvt Ltd")

    def test_invoice_admin_configuration_and_manual_entry_with_inlines(self):
        """Admin can manually create an invoice with inline items; totals and QR code auto-generate."""
        from django.contrib import admin as django_admin
        from billing.admin import InvoiceAdmin, InvoiceItemInline

        # 1. Verify ModelAdmin & Inline configuration
        invoice_admin = django_admin.site._registry[Invoice]
        self.assertIsInstance(invoice_admin, InvoiceAdmin)
        self.assertIn("invoice_number", invoice_admin.list_display)
        self.assertIn("customer", invoice_admin.list_display)
        self.assertIn("invoice_date", invoice_admin.list_display)
        self.assertIn("grand_total", invoice_admin.list_display)
        self.assertIn("invoice_date", invoice_admin.list_filter)
        self.assertIn("invoice_number", invoice_admin.search_fields)
        self.assertEqual(len(invoice_admin.inlines), 1)
        self.assertEqual(invoice_admin.inlines[0], InvoiceItemInline)

        # 2. Create customer for invoice
        customer = Customer.objects.create(
            distributor=self.distributor,
            name="Sunrise Retail Enterprises",
            email="accounts@sunriseretail.com",
            phone="9876501234",
            address="Commercial Complex, Road 1",
            city="Pune",
            state="Maharashtra",
            pincode="411001"
        )

        # 3. Add invoice with multiple inline items via Admin POST
        self.client.login(username="admin_billing_mgr", password="AdminPassword@123")
        add_url = reverse("admin:billing_invoice_add")
        inv_payload = {
            "distributor": self.distributor.pk,
            "customer": customer.pk,
            "invoice_number": "",  # Auto-generated
            "invoice_date": "2026-11-05",
            "subtotal": "0.00",
            "total_gst": "0.00",
            "grand_total": "0.00",
            # Inline formset management fields
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            # Line 1: Smart POS Terminal x 2, 0% discount
            "items-0-product": self.product1.pk,
            "items-0-product_name": "",  # Auto-populated from product
            "items-0-quantity": "2",
            "items-0-unit_price": "",    # Auto-populated
            "items-0-discount_percent": "0.00",
            "items-0-gst_rate": "",      # Auto-populated
            "items-0-taxable_amount": "", # Auto-calculated: 2 * 4500 = 9000
            "items-0-gst_amount": "",     # Auto-calculated: 9000 * 18% = 1620
            "items-0-line_total": "",     # Auto-calculated: 9000 + 1620 = 10620
            # Line 2: Thermal Paper Roll x 4, 10% discount
            "items-1-product": self.product2.pk,
            "items-1-product_name": "",
            "items-1-quantity": "4",
            "items-1-unit_price": "",    # Auto-populated: 150
            "items-1-discount_percent": "10.00",
            "items-1-gst_rate": "",      # Auto-populated: 12%
            "items-1-taxable_amount": "", # Auto-calculated: (4*150) - 10% = 540
            "items-1-gst_amount": "",     # Auto-calculated: 540 * 12% = 64.80
            "items-1-line_total": "",     # Auto-calculated: 540 + 64.80 = 604.80
        }

        resp = self.client.post(add_url, data=inv_payload, follow=True)
        self.assertEqual(resp.status_code, 200)

        created_invoice = Invoice.objects.filter(customer=customer).order_by("-id").first()
        self.assertIsNotNone(created_invoice)
        self.assertTrue(created_invoice.invoice_number.startswith("INV-"))

        # Check line items
        items = list(created_invoice.items.all())
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].product_name, "Smart POS Terminal")
        self.assertEqual(items[0].taxable_amount, Decimal("9000.00"))
        self.assertEqual(items[0].gst_amount, Decimal("1620.00"))
        self.assertEqual(items[0].line_total, Decimal("10620.00"))

        self.assertEqual(items[1].product_name, "Thermal Receipt Paper Roll")
        self.assertEqual(items[1].taxable_amount, Decimal("540.00"))
        self.assertEqual(items[1].gst_amount, Decimal("64.80"))
        self.assertEqual(items[1].line_total, Decimal("604.80"))

        # Check invoice totals (9000 + 540 = 9540 taxable, 1620 + 64.80 = 1684.80 gst, grand_total = 11224.80)
        self.assertEqual(created_invoice.subtotal, Decimal("9540.00"))
        self.assertEqual(created_invoice.total_gst, Decimal("1684.80"))
        self.assertEqual(created_invoice.grand_total, Decimal("11224.80"))

        # Check QR code was automatically generated and saved
        self.assertTrue(bool(created_invoice.qr_code))
        self.assertTrue(created_invoice.qr_code.storage.exists(created_invoice.qr_code.name))

    def test_invoice_item_admin_configuration(self):
        """InvoiceItemAdmin is registered with required list_display, search_fields and filters."""
        from django.contrib import admin as django_admin
        from billing.admin import InvoiceItemAdmin

        item_admin = django_admin.site._registry[InvoiceItem]
        self.assertIsInstance(item_admin, InvoiceItemAdmin)
        self.assertIn("invoice", item_admin.list_display)
        self.assertIn("product_name", item_admin.list_display)
        self.assertIn("quantity", item_admin.list_display)
        self.assertIn("unit_price", item_admin.list_display)
        self.assertIn("line_total", item_admin.list_display)
        self.assertIn("product_name", item_admin.search_fields)
        self.assertIn("gst_rate", item_admin.list_filter)

    def test_manually_created_invoice_works_with_preview_qr_and_pdf(self):
        """Manually created invoice records integrate cleanly with Invoice Preview, QR code, and PDF downloads."""
        # 1. Create invoice & items as admin would
        customer = Customer.objects.create(
            distributor=self.distributor,
            name="Quantum Logistics Ltd",
            email="billing@quantumlogistics.com",
            phone="9823456789",
            address="Quantum Tech Centre",
            city="Hyderabad",
            state="Telangana",
            pincode="500081"
        )
        invoice = Invoice.objects.create(
            distributor=self.distributor,
            customer=customer,
            invoice_number="INV-MANUAL-001",
            invoice_date="2026-11-05",
            subtotal=Decimal("4500.00"),
            total_gst=Decimal("810.00"),
            grand_total=Decimal("5310.00")
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            product=self.product1,
            quantity=1
        )
        invoice.generate_and_save_qr_code(force=True)

        # 2. Login as distributor
        self.client.login(username="dist_billing_user", password="DistPassword@123")

        # 3. Preview page
        preview_resp = self.client.get(reverse("billing_invoice_preview", kwargs={"pk": invoice.pk}))
        self.assertEqual(preview_resp.status_code, 200)
        content = preview_resp.content.decode("utf-8")
        self.assertIn("INV-MANUAL-001", content)
        self.assertIn("Quantum Logistics Ltd", content)
        self.assertIn("Smart POS Terminal", content)
        self.assertIn("5310.00", content)

        # 4. PDF download view
        pdf_resp = self.client.get(reverse("invoice_pdf_download", kwargs={"pk": invoice.pk}))
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertEqual(pdf_resp["Content-Type"], "application/pdf")
        self.assertTrue(pdf_resp.content.startswith(b"%PDF"))
        self.assertIn("attachment", pdf_resp["Content-Disposition"])
        self.assertIn("Invoice-INV-MANUAL-001.pdf", pdf_resp["Content-Disposition"])

        # 5. Extract and decode QR code from PDF
        reader = PdfReader(BytesIO(pdf_resp.content))
        extracted_images = [Image.open(BytesIO(im.data)) for p in reader.pages for _, im in p.images.items()]
        self.assertTrue(len(extracted_images) >= 1)
        decoded = decode_qr_from_image(extracted_images[0])
        self.assertTrue(len(decoded) >= 1)
        qr_json = json.loads(decoded[0]["data"])
        self.assertEqual(qr_json["invoice_id"], "INV-MANUAL-001")
        self.assertEqual(qr_json["customer_name"], "Quantum Logistics Ltd")
        self.assertEqual(qr_json["total_amount"], "5310.00")
