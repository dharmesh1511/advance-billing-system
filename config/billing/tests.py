from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from billing.models import Customer


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


