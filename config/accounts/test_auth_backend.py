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

    # -------------------------------------------------------------
    # 10. Login UI Element Verification Tests
    # -------------------------------------------------------------
    def test_admin_login_ui_elements(self):
        """Verify Admin login template renders all required professional UI elements."""
        response = self.client.get(reverse("admin_login"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Headings & branding
        self.assertIn("Admin Login", content)
        self.assertIn("Admin Console", content)
        self.assertIn("Sign in to access admin controls", content)

        # Inputs with attributes
        self.assertIn('name="username"', content)
        self.assertIn('name="password"', content)
        self.assertIn('id="togglePassword"', content)
        self.assertIn('id="eyeIcon"', content)
        self.assertIn('id="eyeOffIcon"', content)

        # Remember Me & Forgot Password
        self.assertIn('name="remember_me"', content)
        self.assertIn(reverse("forgot_password"), content)

        # Submit button & loading spinner
        self.assertIn('id="submitBtn"', content)
        self.assertIn('id="btnSpinner"', content)
        self.assertIn('id="btnText"', content)

        # Switch link to distributor login
        self.assertIn(reverse("distributor_login"), content)

    def test_distributor_login_ui_elements(self):
        """Verify Distributor login template renders all required professional UI elements."""
        response = self.client.get(reverse("distributor_login"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Headings & branding
        self.assertIn("Distributor Login", content)
        self.assertIn("Distributor Portal", content)
        self.assertIn("Sign in to manage customers, products", content)

        # Inputs with attributes
        self.assertIn('name="username"', content)
        self.assertIn('name="password"', content)
        self.assertIn('id="togglePassword"', content)
        self.assertIn('id="eyeIcon"', content)
        self.assertIn('id="eyeOffIcon"', content)

        # Remember Me & Forgot Password
        self.assertIn('name="remember_me"', content)
        self.assertIn(reverse("forgot_password"), content)

        # Submit button & loading spinner
        self.assertIn('id="submitBtn"', content)
        self.assertIn('id="btnSpinner"', content)
        self.assertIn('id="btnText"', content)

        # Switch links to register and admin login
        self.assertIn(reverse("distributor_register"), content)
        self.assertIn(reverse("admin_login"), content)


from django.contrib.sessions.models import Session
from django.conf import settings


class SessionBasedAuthenticationTests(TestCase):
    """
    Dedicated tests verifying Django session-based authentication:
    1. Session middleware and engine configuration.
    2. Admin and Distributor login session creation in DB.
    3. Session regeneration upon login (session fixation prevention).
    4. Authenticated users access their own dashboard (200 OK).
    5. Cross-role dashboard access prevention with redirect.
    6. Unauthenticated dashboard access redirect to login.
    7. POST logout with CSRF clearing session from DB.
    8. Back navigation prevention (@never_cache headers).
    9. Remember Me session expiry configuration.
    10. Expired/invalid session requires re-login.
    """

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin_sess",
            email="admin_sess@example.com",
            password="AdminPassword@123",
            is_staff=True
        )
        self.distributor_group, _ = Group.objects.get_or_create(name="Distributor")
        self.distributor_user = User.objects.create_user(
            username="dist_sess",
            email="dist_sess@example.com",
            password="DistPassword@123"
        )
        self.distributor_user.groups.add(self.distributor_group)
        self.distributor_profile = DistributorProfile.objects.create(
            user=self.distributor_user,
            full_name="Distributor Sess",
            email="dist_sess@example.com",
            phone="9876543219"
        )

    def test_session_settings_and_middleware(self):
        """Verify session engine, cookie security settings, and required middleware."""
        self.assertEqual(settings.SESSION_ENGINE, "django.contrib.sessions.backends.db")
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertFalse(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertIn("django.contrib.sessions.middleware.SessionMiddleware", settings.MIDDLEWARE)
        self.assertIn("django.contrib.auth.middleware.AuthenticationMiddleware", settings.MIDDLEWARE)
        self.assertIn("django.middleware.csrf.CsrfViewMiddleware", settings.MIDDLEWARE)

    def test_admin_login_creates_database_session_and_regenerates_key(self):
        """Admin login creates a database-backed session and regenerates session key."""
        self.client.get(reverse("admin_login"))
        pre_login_key = self.client.session.session_key

        response = self.client.post(
            reverse("admin_login"),
            {"username": "admin_sess", "password": "AdminPassword@123"}
        )
        self.assertEqual(response.status_code, 302)
        post_login_key = self.client.session.session_key

        self.assertIsNotNone(post_login_key)
        if pre_login_key:
            self.assertNotEqual(pre_login_key, post_login_key)

        self.assertTrue(Session.objects.filter(session_key=post_login_key).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.admin_user.id)

    def test_distributor_login_creates_database_session_and_regenerates_key(self):
        """Distributor login creates a database-backed session and regenerates session key."""
        self.client.get(reverse("distributor_login"))
        pre_login_key = self.client.session.session_key

        response = self.client.post(
            reverse("distributor_login"),
            {"username": "dist_sess", "password": "DistPassword@123"}
        )
        self.assertEqual(response.status_code, 302)
        post_login_key = self.client.session.session_key

        self.assertIsNotNone(post_login_key)
        if pre_login_key:
            self.assertNotEqual(pre_login_key, post_login_key)

        self.assertTrue(Session.objects.filter(session_key=post_login_key).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.distributor_user.id)

    def test_authenticated_users_access_own_dashboards(self):
        """Authenticated Admin and Distributor can access their own dashboards."""
        self.client.force_login(self.admin_user)
        admin_res = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(admin_res.status_code, 200)

        self.client.force_login(self.distributor_user)
        dist_res = self.client.get(reverse("distributor_dashboard"))
        self.assertEqual(dist_res.status_code, 200)

    def test_cross_role_dashboard_access_prevented(self):
        """Admin cannot access distributor dashboard; Distributor cannot access admin dashboard."""
        self.client.force_login(self.admin_user)
        res1 = self.client.get(reverse("distributor_dashboard"))
        self.assertEqual(res1.status_code, 302)
        self.assertIn(reverse("admin_dashboard"), res1.url)

        self.client.force_login(self.distributor_user)
        res2 = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(res2.status_code, 302)
        self.assertIn(reverse("distributor_dashboard"), res2.url)

    def test_unauthenticated_dashboard_access_redirects_to_login(self):
        """Unauthenticated requests to protected dashboards redirect to respective login."""
        res_admin = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(res_admin.status_code, 302)
        self.assertIn(reverse("admin_login"), res_admin.url)

        res_dist = self.client.get(reverse("distributor_dashboard"))
        self.assertEqual(res_dist.status_code, 302)
        self.assertIn(reverse("distributor_login"), res_dist.url)

    def test_post_logout_clears_session(self):
        """POST logout clears session from DB and redirects correctly."""
        self.client.login(username="admin_sess", password="AdminPassword@123")
        admin_sess_key = self.client.session.session_key
        self.assertTrue(Session.objects.filter(session_key=admin_sess_key).exists())

        res_admin = self.client.post(reverse("logout"))
        self.assertEqual(res_admin.status_code, 302)
        self.assertIn(reverse("admin_login"), res_admin.url)
        self.assertNotIn("_auth_user_id", self.client.session)

        self.client.login(username="dist_sess", password="DistPassword@123")
        dist_sess_key = self.client.session.session_key
        self.assertTrue(Session.objects.filter(session_key=dist_sess_key).exists())

        res_dist = self.client.post(reverse("logout"))
        self.assertEqual(res_dist.status_code, 302)
        self.assertIn(reverse("distributor_login"), res_dist.url)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_dashboard_and_logout_never_cache_headers(self):
        """Dashboard views and logout endpoint return Cache-Control: no-cache, no-store headers."""
        self.client.force_login(self.admin_user)
        admin_dash_res = self.client.get(reverse("admin_dashboard"))
        cache_control = admin_dash_res.headers.get("Cache-Control", "")
        self.assertIn("no-cache", cache_control)
        self.assertIn("no-store", cache_control)

        self.client.force_login(self.distributor_user)
        dist_dash_res = self.client.get(reverse("distributor_dashboard"))
        cache_control_dist = dist_dash_res.headers.get("Cache-Control", "")
        self.assertIn("no-cache", cache_control_dist)
        self.assertIn("no-store", cache_control_dist)

        logout_res = self.client.get(reverse("logout"))
        cache_control_logout = logout_res.headers.get("Cache-Control", "")
        self.assertIn("no-cache", cache_control_logout)
        self.assertIn("no-store", cache_control_logout)

    def test_remember_me_session_expiry(self):
        """Remember Me sets 14-day expiry; unchecking expires on browser close."""
        self.client.post(
            reverse("admin_login"),
            {"username": "admin_sess", "password": "AdminPassword@123", "remember_me": "on"}
        )
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertEqual(self.client.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)
        self.client.logout()

        self.client.post(
            reverse("admin_login"),
            {"username": "admin_sess", "password": "AdminPassword@123"}
        )
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_expired_session_requires_relogin(self):
        """Expired or deleted session forces user to log in again."""
        self.client.login(username="admin_sess", password="AdminPassword@123")
        self.assertEqual(self.client.get(reverse("admin_dashboard")).status_code, 200)

        Session.objects.all().delete()

        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin_login"), response.url)
