from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from accounts.models import DistributorProfile


class AdminAndDistributorAuthBackendTests(TestCase):
    """
    Focused verification tests for Admin and Distributor login backend:
    1. Admin login success (username, email, redirects).
    2. Distributor login success (username, email, redirects).
    3. Invalid credentials rejection.
    4. Wrong role login attempt prevention.
    5. Inactive account handling.
    6. Empty required fields handling.
    7. Unauthorized dashboard access protection.
    8. Safe redirect (prevention of open redirect).
    9. Logout functionality for both roles.
    """

    def setUp(self):
        self.client = Client()

        # 1. Active Admin User (staff, non-distributor)
        self.admin_user = User.objects.create_user(
            username="admin_user",
            email="admin@example.com",
            password="AdminPassword@123",
            is_staff=True,
            is_superuser=False
        )

        # 2. Active Superuser Admin
        self.super_admin = User.objects.create_superuser(
            username="super_admin",
            email="superadmin@example.com",
            password="SuperPassword@123"
        )

        # 3. Active Distributor User (in Distributor group & has profile)
        self.distributor_group = Group.objects.create(name="Distributor")
        self.distributor_user = User.objects.create_user(
            username="distributor_user",
            email="distributor@example.com",
            password="DistributorPassword@123"
        )
        self.distributor_user.groups.add(self.distributor_group)
        self.distributor_profile = DistributorProfile.objects.create(
            user=self.distributor_user,
            full_name="Verified Distributor",
            email="distributor@example.com",
            phone="9876543210"
        )

        # 4. Inactive Admin User
        self.inactive_admin = User.objects.create_user(
            username="inactive_admin",
            email="inactive_admin@example.com",
            password="InactiveAdmin@123",
            is_staff=True,
            is_active=False
        )

        # 5. Inactive Distributor User
        self.inactive_distributor = User.objects.create_user(
            username="inactive_dist",
            email="inactive_dist@example.com",
            password="InactiveDist@123",
            is_active=False
        )
        self.inactive_distributor.groups.add(self.distributor_group)
        DistributorProfile.objects.create(
            user=self.inactive_distributor,
            full_name="Inactive Distributor",
            email="inactive_dist@example.com",
            phone="9876543211"
        )

        # 6. Regular User (neither Admin nor Distributor)
        self.regular_user = User.objects.create_user(
            username="regular_user",
            email="regular@example.com",
            password="RegularPassword@123"
        )

    # -------------------------------------------------------------
    # 1. Admin Login Success Tests
    # -------------------------------------------------------------
    def test_admin_login_success_with_username(self):
        """Staff admin logs in with username and redirects to admin dashboard."""
        response = self.client.post(
            reverse("admin_login"),
            {"username": "admin_user", "password": "AdminPassword@123"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/dashboard/", response.url)
        # Verify session is authenticated
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.admin_user.id)

    def test_admin_login_success_with_email(self):
        """Staff admin logs in using email address instead of username."""
        response = self.client.post(
            reverse("admin_login"),
            {"username": "admin@example.com", "password": "AdminPassword@123"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/dashboard/", response.url)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.admin_user.id)

    def test_superuser_admin_login_success(self):
        """Superuser admin logs in successfully at admin login."""
        response = self.client.post(
            reverse("admin_login"),
            {"username": "super_admin", "password": "SuperPassword@123"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/dashboard/", response.url)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.super_admin.id)

    # -------------------------------------------------------------
    # 2. Distributor Login Success Tests
    # -------------------------------------------------------------
    def test_distributor_login_success_with_username(self):
        """Distributor logs in with username and redirects to distributor dashboard."""
        response = self.client.post(
            reverse("distributor_login"),
            {"username": "distributor_user", "password": "DistributorPassword@123"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/dashboard/", response.url)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.distributor_user.id)

    def test_distributor_login_success_with_email(self):
        """Distributor logs in with email address."""
        response = self.client.post(
            reverse("distributor_login"),
            {"username": "distributor@example.com", "password": "DistributorPassword@123"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/dashboard/", response.url)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.distributor_user.id)

    # -------------------------------------------------------------
    # 3. Invalid Credentials Tests
    # -------------------------------------------------------------
    def test_admin_login_invalid_password(self):
        """Admin login with wrong password is rejected."""
        response = self.client.post(
            reverse("admin_login"),
            {"username": "admin_user", "password": "WrongPassword!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Invalid username or password.", response.content.decode("utf-8"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_distributor_login_invalid_password(self):
        """Distributor login with wrong password is rejected."""
        response = self.client.post(
            reverse("distributor_login"),
            {"username": "distributor_user", "password": "WrongPassword!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Invalid username or password.", response.content.decode("utf-8"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_nonexistent_user_login(self):
        """Nonexistent username is rejected with Invalid username or password."""
        response = self.client.post(
            reverse("admin_login"),
            {"username": "no_such_user", "password": "AnyPassword123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Invalid username or password.", response.content.decode("utf-8"))

    # -------------------------------------------------------------
    # 4. Role Prevention Tests (Wrong Role Login Attempt)
    # -------------------------------------------------------------
    def test_distributor_cannot_access_admin_login(self):
        """Distributor account is prevented from logging in via Admin Login."""
        response = self.client.post(
            reverse("admin_login"),
            {"username": "distributor_user", "password": "DistributorPassword@123"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertTrue(
            "Distributor accounts are not permitted" in content or "not authorized to login as Admin" in content
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_cannot_access_distributor_login(self):
        """Admin account is prevented from logging in via Distributor Login."""
        response = self.client.post(
            reverse("distributor_login"),
            {"username": "admin_user", "password": "AdminPassword@123"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertTrue(
            "Admin accounts are not permitted" in content or "not authorized to login as Distributor" in content
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_regular_user_cannot_login_as_admin_or_distributor(self):
        """Regular non-staff, non-distributor user cannot log in to either portal."""
        res_admin = self.client.post(
            reverse("admin_login"),
            {"username": "regular_user", "password": "RegularPassword@123"}
        )
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn("not authorized to login as Admin", res_admin.content.decode("utf-8"))

        res_dist = self.client.post(
            reverse("distributor_login"),
            {"username": "regular_user", "password": "RegularPassword@123"}
        )
        self.assertEqual(res_dist.status_code, 200)
        self.assertIn("not authorized to login as Distributor", res_dist.content.decode("utf-8"))

    # -------------------------------------------------------------
    # 5. Inactive Account Tests
    # -------------------------------------------------------------
    def test_inactive_admin_account_rejected(self):
        """Inactive admin user is rejected with specific inactive message."""
        response = self.client.post(
            reverse("admin_login"),
            {"username": "inactive_admin", "password": "InactiveAdmin@123"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("inactive", content.lower())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_distributor_account_rejected(self):
        """Inactive distributor user is rejected with specific inactive message."""
        response = self.client.post(
            reverse("distributor_login"),
            {"username": "inactive_dist", "password": "InactiveDist@123"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("inactive", content.lower())
        self.assertNotIn("_auth_user_id", self.client.session)

    # -------------------------------------------------------------
    # 6. Empty Required Fields Tests
    # -------------------------------------------------------------
    def test_empty_fields_rejected(self):
        """Submitting empty username or password displays required field error."""
        # Both empty
        res1 = self.client.post(reverse("admin_login"), {"username": "", "password": ""})
        self.assertEqual(res1.status_code, 200)
        self.assertIn("required", res1.content.decode("utf-8").lower())

        # Only password empty
        res2 = self.client.post(reverse("admin_login"), {"username": "admin_user", "password": ""})
        self.assertEqual(res2.status_code, 200)
        self.assertIn("required", res2.content.decode("utf-8").lower())

        # Only username empty
        res3 = self.client.post(reverse("distributor_login"), {"username": "", "password": "AnyPassword"})
        self.assertEqual(res3.status_code, 200)
        self.assertIn("required", res3.content.decode("utf-8").lower())

    # -------------------------------------------------------------
    # 7. Dashboard Authorization & Protection Tests
    # -------------------------------------------------------------
    def test_unauthenticated_user_cannot_access_dashboards(self):
        """Unauthenticated visitor is redirected to corresponding login page."""
        admin_dash_res = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(admin_dash_res.status_code, 302)
        self.assertIn("/admin/login/", admin_dash_res.url)

        dist_dash_res = self.client.get(reverse("distributor_dashboard"))
        self.assertEqual(dist_dash_res.status_code, 302)
        self.assertIn("/distributor/login/", dist_dash_res.url)

    def test_distributor_blocked_from_admin_dashboard(self):
        """Authenticated distributor attempting to view admin dashboard is redirected to distributor dashboard."""
        self.client.force_login(self.distributor_user)
        response = self.client.get(reverse("admin_dashboard"), follow=True)
        # Should be redirected away to distributor dashboard
        self.assertRedirects(response, reverse("distributor_dashboard"))
        # Error message passed in messages
        messages = list(response.context["messages"])
        self.assertTrue(any("not authorized" in str(m).lower() for m in messages))

    def test_admin_blocked_from_distributor_dashboard(self):
        """Authenticated admin attempting to view distributor dashboard is redirected to admin dashboard."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("distributor_dashboard"), follow=True)
        self.assertRedirects(response, reverse("admin_dashboard"))
        messages = list(response.context["messages"])
        self.assertTrue(any("not authorized" in str(m).lower() for m in messages))

    # -------------------------------------------------------------
    # 8. Safe Redirect Tests (Open Redirect Prevention)
    # -------------------------------------------------------------
    def test_safe_internal_next_redirect(self):
        """Legitimate internal next parameter is respected."""
        response = self.client.post(
            reverse("admin_login") + "?next=/admin/reports/",
            {"username": "admin_user", "password": "AdminPassword@123"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/admin/reports/")

    def test_open_redirect_attack_prevented(self):
        """External URL in next parameter is ignored and user is safely redirected to dashboard."""
        response = self.client.post(
            reverse("admin_login") + "?next=https://malicious-external-site.com",
            {"username": "admin_user", "password": "AdminPassword@123"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/dashboard/", response.url)
        self.assertNotIn("malicious-external-site", response.url)

    # -------------------------------------------------------------
    # 9. Logout Functionality Tests
    # -------------------------------------------------------------
    def test_admin_logout(self):
        """Admin user logs out, session is destroyed, and redirected to admin login."""
        self.client.force_login(self.admin_user)
        self.assertIn("_auth_user_id", self.client.session)

        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_distributor_logout(self):
        """Distributor user logs out, session is destroyed, and redirected to distributor login."""
        self.client.force_login(self.distributor_user)
        self.assertIn("_auth_user_id", self.client.session)

        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)
        self.assertNotIn("_auth_user_id", self.client.session)

