from django.contrib.auth.models import User, Group
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient


class AdminRegistrationAPITests(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api_admin_register")

        # Superuser
        self.superuser = User.objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password="SuperPassword@123"
        )

        # Distributor User
        self.distributor_group = Group.objects.create(name="Distributor")
        self.distributor = User.objects.create_user(
            username="distributor_user",
            email="distributor@example.com",
            password="DistPassword@123"
        )
        self.distributor.groups.add(self.distributor_group)

        # Regular Non-Staff Non-Distributor User
        self.regular_user = User.objects.create_user(
            username="regularuser",
            email="regular@example.com",
            password="RegularPassword@123"
        )

        # Existing Staff Admin (non-superuser)
        self.staff_admin = User.objects.create_user(
            username="staffadmin",
            email="staffadmin@example.com",
            password="StaffPassword@123",
            is_staff=True,
            is_superuser=False
        )

    def test_superuser_creates_valid_admin(self):
        """Superuser can register a new Admin user via API (201 Created)."""
        self.client.force_authenticate(user=self.superuser)
        payload = {
            "username": "admin2",
            "email": "admin2@example.com",
            "first_name": "Rahul",
            "last_name": "Patel",
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Admin user registered successfully.")
        self.assertEqual(response.data["admin"]["username"], "admin2")
        self.assertEqual(response.data["admin"]["email"], "admin2@example.com")
        self.assertNotIn("password", response.data["admin"])

        # Check DB
        created_user = User.objects.get(username="admin2")
        self.assertTrue(created_user.is_staff)
        self.assertFalse(created_user.is_superuser)
        self.assertTrue(created_user.check_password("StrongPassword@123"))

    def test_anonymous_user_attempts_registration(self):
        """Unauthenticated user cannot access endpoint (401 Unauthorized)."""
        payload = {
            "username": "admin_anon",
            "email": "anon@example.com",
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(User.objects.filter(username="admin_anon").exists())

    def test_distributor_attempts_admin_registration(self):
        """Distributor user cannot register Admin user (403 Forbidden)."""
        self.client.force_authenticate(user=self.distributor)
        payload = {
            "username": "admin_dist",
            "email": "dist_attempt@example.com",
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="admin_dist").exists())

    def test_regular_user_attempts_admin_registration(self):
        """Regular non-superuser user cannot register Admin user (403 Forbidden)."""
        self.client.force_authenticate(user=self.regular_user)
        payload = {
            "username": "admin_reg",
            "email": "reg_attempt@example.com",
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="admin_reg").exists())

    def test_duplicate_username(self):
        """Registering with an existing username returns 400 Bad Request."""
        self.client.force_authenticate(user=self.superuser)
        payload = {
            "username": "superadmin",  # Already exists
            "email": "newadmin@example.com",
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)

    def test_duplicate_email(self):
        """Registering with an existing email returns 400 Bad Request."""
        self.client.force_authenticate(user=self.superuser)
        payload = {
            "username": "uniqueadmin",
            "email": "superadmin@example.com",  # Already exists
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_password_mismatch(self):
        """Password mismatch returns 400 Bad Request."""
        self.client.force_authenticate(user=self.superuser)
        payload = {
            "username": "admin_mismatch",
            "email": "mismatch@example.com",
            "password": "StrongPassword@123",
            "confirm_password": "DifferentPassword@123"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("confirm_password", response.data)

    def test_weak_password(self):
        """Weak password returns 400 Bad Request."""
        self.client.force_authenticate(user=self.superuser)
        payload = {
            "username": "admin_weak",
            "email": "weak@example.com",
            "password": "123",  # Too short / common
            "confirm_password": "123"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)

    def test_client_sends_is_superuser(self):
        """Client sending is_superuser: true cannot grant superuser privileges."""
        self.client.force_authenticate(user=self.superuser)
        payload = {
            "username": "admin_hack",
            "email": "hack@example.com",
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123",
            "is_superuser": True,
            "role": "superuser"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)

        created_user = User.objects.get(username="admin_hack")
        self.assertTrue(created_user.is_staff)
        self.assertFalse(created_user.is_superuser)

    def test_password_hashing_and_permissions(self):
        """Admin password is hashed and permissions are is_staff=True, is_superuser=False."""
        self.client.force_authenticate(user=self.superuser)
        payload = {
            "username": "admin_hashed",
            "email": "hashed@example.com",
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)

        user = User.objects.get(username="admin_hashed")
        self.assertNotEqual(user.password, "StrongPassword@123")
        self.assertTrue(user.check_password("StrongPassword@123"))
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_existing_login_and_distributor_registration(self):
        """Verify standard distributor login and admin login endpoints continue functioning."""
        admin_login_res = self.client.get(reverse("admin_login"))
        self.assertEqual(admin_login_res.status_code, 200)

        dist_reg_res = self.client.get(reverse("distributor_register"))
        self.assertEqual(dist_reg_res.status_code, 200)
