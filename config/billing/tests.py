from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from billing.models import Customer, Product



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
        self.assertContains(response, "You haven&#x27;t added any customers yet.")

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
        self.assertContains(list_response, "Customer deleted successfully.")


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
        self.assertContains(response, "Stock cannot be negative.")
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
        self.assertContains(response, "GST rate must be between 0% and 100%.")
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






