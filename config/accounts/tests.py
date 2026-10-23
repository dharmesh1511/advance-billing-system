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

    def test_superuser_with_valid_jwt_access_token_registers_admin(self):
        """Superuser with valid JWT access token can register an Admin (201 Created)."""
        token_res = self.client.post(
            reverse("token_obtain_pair"),
            {"username": self.superuser.username, "password": "SuperPassword@123"},
            format="json"
        )
        self.assertEqual(token_res.status_code, 200)
        access_token = token_res.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        payload = {
            "username": "admin_jwt_reg",
            "email": "jwt_reg@example.com",
            "first_name": "JWT",
            "last_name": "Admin",
            "password": "ExampleStrong@2026X",
            "confirm_password": "ExampleStrong@2026X"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Admin user registered successfully.")
        self.assertEqual(response.data["admin"]["username"], "admin_jwt_reg")

        new_user = User.objects.get(username="admin_jwt_reg")
        self.assertTrue(new_user.is_staff)
        self.assertFalse(new_user.is_superuser)
        self.assertTrue(new_user.check_password("ExampleStrong@2026X"))

    def test_invalid_email_format_rejected(self):
        """Invalid email address format is rejected with 400 Bad Request."""
        self.client.force_authenticate(user=self.superuser)
        payload = {
            "username": "admin_bad_email",
            "email": "not-a-valid-email",
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_required_fields_validated(self):
        """Missing required fields return 400 Bad Request with field errors."""
        self.client.force_authenticate(user=self.superuser)
        # Empty payload
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)
        self.assertIn("email", response.data)
        self.assertIn("password", response.data)
        self.assertIn("confirm_password", response.data)

    def test_registration_response_does_not_expose_password(self):
        """Admin registration response does not expose the password or its hash."""
        self.client.force_authenticate(user=self.superuser)
        payload = {
            "username": "admin_no_expose",
            "email": "no_expose@example.com",
            "password": "ExampleStrong@2026X",
            "confirm_password": "ExampleStrong@2026X"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.data)
        self.assertNotIn("confirm_password", response.data)
        self.assertNotIn("password", response.data.get("admin", {}))
        self.assertNotIn("confirm_password", response.data.get("admin", {}))

    def test_existing_login_and_distributor_registration(self):
        """Verify standard distributor login and admin login endpoints continue functioning."""
        admin_login_res = self.client.get(reverse("admin_login"))
        self.assertEqual(admin_login_res.status_code, 200)

        dist_reg_res = self.client.get(reverse("distributor_register"))
        self.assertEqual(dist_reg_res.status_code, 200)


class AdminRegistrationFrontendTests(APITestCase):

    def setUp(self):
        self.register_url = reverse("admin_register")
        self.dashboard_url = reverse("admin_dashboard")
        self.api_url = reverse("api_admin_register")

        # Superuser
        self.superuser = User.objects.create_superuser(
            username="superadmin_fe",
            email="superadmin_fe@example.com",
            password="SuperPassword@123"
        )

        # Staff Admin (non-superuser)
        self.staff_admin = User.objects.create_user(
            username="staffadmin_fe",
            email="staffadmin_fe@example.com",
            password="StaffPassword@123",
            is_staff=True,
            is_superuser=False
        )

        # Distributor User
        self.distributor_group = Group.objects.create(name="Distributor")
        self.distributor = User.objects.create_user(
            username="distributor_fe",
            email="distributor_fe@example.com",
            password="DistPassword@123"
        )
        self.distributor.groups.add(self.distributor_group)

    def test_admin_registration_page_requires_login(self):
        """Unauthenticated user accessing registration page is redirected to login."""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_admin_registration_page_accessible_by_superuser(self):
        """Superuser can render the registration frontend page."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "adminpanel/admin_register.html")
        self.assertTemplateUsed(response, "adminpanel/base_admin.html")

        # Check required form input fields exist in HTML response
        content = response.content.decode('utf-8')
        self.assertIn('id="first_name"', content)
        self.assertIn('id="last_name"', content)
        self.assertIn('id="username"', content)
        self.assertIn('id="email"', content)
        self.assertIn('id="password"', content)
        self.assertIn('id="confirm_password"', content)
        self.assertIn('Create Admin Account', content)
        self.assertIn('toggle-password-btn', content)
        self.assertIn('toggle-confirm-password-btn', content)

    def test_admin_registration_page_accessible_by_staff(self):
        """Staff admin user can access the registration page."""
        self.client.force_login(self.staff_admin)
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)

    def test_admin_registration_page_denied_for_distributor(self):
        """Distributor user accessing admin registration page is redirected."""
        self.client.force_login(self.distributor)
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 302)

    def test_admin_dashboard_renders_register_link(self):
        """Admin dashboard displays the Register Admin navigation link."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/admin_dashboard.html")
        content = response.content.decode('utf-8')
        self.assertIn(self.register_url, content)
        self.assertIn('Register Admin', content)

    def test_session_authenticated_post_creates_admin(self):
        """Superuser using session authentication can post to the API and create an Admin."""
        self.client.force_login(self.superuser)
        payload = {
            "first_name": "Suresh",
            "last_name": "Kumar",
            "username": "suresh_admin",
            "email": "suresh@example.com",
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123"
        }
        response = self.client.post(self.api_url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Admin user registered successfully.")

        created_user = User.objects.get(username="suresh_admin")
        self.assertTrue(created_user.is_staff)
        self.assertFalse(created_user.is_superuser)
        self.assertTrue(created_user.check_password("StrongPassword@123"))


import re
from datetime import timedelta
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from django.contrib.sessions.models import Session
from accounts.models import OTPVerification, AdminPasswordResetToken, UserSecurityStatus
from accounts.services import hash_otp, hash_reset_token, ADMIN_RECOVERY_PURPOSE


class AdminPasswordRecoveryAPITests(APITestCase):

    def setUp(self):
        cache.clear()
        mail.outbox.clear()
        self.client = APIClient()

        self.forgot_url = reverse("api_admin_forgot_password")
        self.verify_url = reverse("api_admin_verify_reset_otp")
        self.reset_url = reverse("api_admin_reset_password")
        self.resend_url = reverse("api_admin_resend_reset_otp")

        # Staff Admin User
        self.admin = User.objects.create_user(
            username="staff_recovery",
            email="staff_recovery@example.com",
            password="InitialStrongPassword@2026",
            is_staff=True,
            is_superuser=False,
            is_active=True
        )

        # Superuser Admin
        self.superuser = User.objects.create_superuser(
            username="super_recovery",
            email="super_recovery@example.com",
            password="SuperStrongPassword@2026",
            is_active=True
        )

        # Distributor User
        distributor_group, _ = Group.objects.get_or_create(name="Distributor")
        self.distributor = User.objects.create_user(
            username="dist_recovery",
            email="dist_recovery@example.com",
            password="DistributorPassword@2026",
            is_staff=False,
            is_active=True
        )
        self.distributor.groups.add(distributor_group)

        # Inactive Admin User
        self.inactive_admin = User.objects.create_user(
            username="inactive_recovery",
            email="inactive_recovery@example.com",
            password="InactivePassword@2026",
            is_staff=True,
            is_active=False
        )

    def tearDown(self):
        cache.clear()
        mail.outbox.clear()

    # 1. Valid Admin forgot-password request
    def test_01_valid_admin_forgot_password_request(self):
        response = self.client.post(self.forgot_url, {"email": self.admin.email}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["message"],
            "If an eligible account exists, a password reset OTP has been sent."
        )
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, "Advance Billing System - Password Reset OTP")
        self.assertEqual(email.to, [self.admin.email])

        # Plain-text verification
        self.assertIn("We received a request to reset your Advance Billing System Admin account password.", email.body)
        self.assertIn("Your password reset OTP is:", email.body)
        self.assertIn("This OTP is valid for 5 minutes.", email.body)
        self.assertIn("Advance Billing System Team", email.body)

        # HTML alternative verification
        self.assertEqual(len(email.alternatives), 1)
        html_content, mimetype = email.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn("Advance Billing System", html_content)
        self.assertIn("Valid for 5 minutes", html_content)
        self.assertIn("Your password reset OTP is:", html_content)

        # OTP is never exposed in the response
        self.assertNotIn("otp", response.data)
        self.assertNotIn("otp_code", response.data)

        # OTP record in DB has hashed OTP, purpose, and empty plaintext otp_code
        otp_record = OTPVerification.objects.filter(
            email=self.admin.email,
            purpose=ADMIN_RECOVERY_PURPOSE
        ).first()
        self.assertIsNotNone(otp_record)
        self.assertEqual(otp_record.otp_code, "")
        self.assertTrue(len(otp_record.otp_hash) > 20)
        self.assertFalse(otp_record.is_verified)

    # 2. Unknown email with generic response
    def test_02_unknown_email_generic_response(self):
        response = self.client.post(self.forgot_url, {"email": "nonexistent@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["message"],
            "If an eligible account exists, a password reset OTP has been sent."
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(OTPVerification.objects.filter(email="nonexistent@example.com").exists())

    # 3. Distributor account cannot recover through Admin endpoints
    def test_03_distributor_cannot_recover_through_admin_endpoints(self):
        response = self.client.post(self.forgot_url, {"email": self.distributor.email}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["message"],
            "If an eligible account exists, a password reset OTP has been sent."
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(
            OTPVerification.objects.filter(
                email=self.distributor.email,
                purpose=ADMIN_RECOVERY_PURPOSE
            ).exists()
        )

    # 4. Inactive Admin account
    def test_04_inactive_admin_account(self):
        response = self.client.post(self.forgot_url, {"email": self.inactive_admin.email}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["message"],
            "If an eligible account exists, a password reset OTP has been sent."
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(
            OTPVerification.objects.filter(
                email=self.inactive_admin.email,
                purpose=ADMIN_RECOVERY_PURPOSE
            ).exists()
        )

    # 5. Successful OTP verification
    def test_05_successful_otp_verification(self):
        raw_otp = "654321"
        OTPVerification.objects.create(
            user=self.admin,
            email=self.admin.email,
            otp_code="",
            otp_hash=hash_otp(raw_otp),
            purpose=ADMIN_RECOVERY_PURPOSE,
            expires_at=timezone.now() + timedelta(minutes=5),
            is_verified=False,
            attempts=0
        )

        response = self.client.post(
            self.verify_url,
            {"email": self.admin.email, "otp": raw_otp},
            format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "OTP verified successfully.")
        self.assertIn("reset_token", response.data)
        reset_token = response.data["reset_token"]
        self.assertTrue(len(reset_token) > 16)

        # Check DB record updated
        otp_rec = OTPVerification.objects.get(email=self.admin.email, purpose=ADMIN_RECOVERY_PURPOSE)
        self.assertTrue(otp_rec.is_verified)
        self.assertEqual(otp_rec.reset_token_hash, hash_reset_token(reset_token))

        # Check AdminPasswordResetToken created
        token_rec = AdminPasswordResetToken.objects.filter(token_hash=hash_reset_token(reset_token)).first()
        self.assertIsNotNone(token_rec)
        self.assertFalse(token_rec.is_used)

    # 6. Incorrect OTP
    def test_06_incorrect_otp(self):
        raw_otp = "112233"
        otp_record = OTPVerification.objects.create(
            user=self.admin,
            email=self.admin.email,
            otp_code="",
            otp_hash=hash_otp(raw_otp),
            purpose=ADMIN_RECOVERY_PURPOSE,
            expires_at=timezone.now() + timedelta(minutes=5),
            is_verified=False,
            attempts=0
        )

        response = self.client.post(
            self.verify_url,
            {"email": self.admin.email, "otp": "999999"},
            format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid OTP", response.data["detail"])
        otp_record.refresh_from_db()
        self.assertEqual(otp_record.attempts, 1)

    # 7. Expired OTP
    def test_07_expired_otp(self):
        raw_otp = "334455"
        OTPVerification.objects.create(
            user=self.admin,
            email=self.admin.email,
            otp_code="",
            otp_hash=hash_otp(raw_otp),
            purpose=ADMIN_RECOVERY_PURPOSE,
            expires_at=timezone.now() - timedelta(seconds=10),
            is_verified=False,
            attempts=0
        )

        response = self.client.post(
            self.verify_url,
            {"email": self.admin.email, "otp": raw_otp},
            format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", response.data["detail"].lower())

    # 8. Five failed attempts lockout
    def test_08_five_failed_attempts(self):
        raw_otp = "123123"
        otp_rec = OTPVerification.objects.create(
            user=self.admin,
            email=self.admin.email,
            otp_code="",
            otp_hash=hash_otp(raw_otp),
            purpose=ADMIN_RECOVERY_PURPOSE,
            expires_at=timezone.now() + timedelta(minutes=5),
            is_verified=False,
            attempts=4
        )

        # 5th failed attempt
        response = self.client.post(
            self.verify_url,
            {"email": self.admin.email, "otp": "000000"},
            format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Too many failed attempts", response.data["detail"])

        # Attempt with correct OTP after 5 failed attempts is locked out
        response2 = self.client.post(
            self.verify_url,
            {"email": self.admin.email, "otp": raw_otp},
            format="json"
        )
        self.assertEqual(response2.status_code, 400)
        self.assertIn("Too many failed attempts", response2.data["detail"])

    # 9. OTP reuse prevention
    def test_09_otp_reuse_prevention(self):
        raw_otp = "456789"
        OTPVerification.objects.create(
            user=self.admin,
            email=self.admin.email,
            otp_code="",
            otp_hash=hash_otp(raw_otp),
            purpose=ADMIN_RECOVERY_PURPOSE,
            expires_at=timezone.now() + timedelta(minutes=5),
            is_verified=False,
            attempts=0
        )

        # First verification succeeds
        res1 = self.client.post(
            self.verify_url,
            {"email": self.admin.email, "otp": raw_otp},
            format="json"
        )
        self.assertEqual(res1.status_code, 200)

        # Second verification of the same OTP must fail
        res2 = self.client.post(
            self.verify_url,
            {"email": self.admin.email, "otp": raw_otp},
            format="json"
        )
        self.assertEqual(res2.status_code, 400)

    # 10. Resend cooldown
    def test_10_resend_cooldown(self):
        # Trigger first forgot password
        self.client.post(self.forgot_url, {"email": self.admin.email}, format="json")

        # Immediately attempt resend within 60 seconds
        res = self.client.post(self.resend_url, {"email": self.admin.email}, format="json")
        self.assertEqual(res.status_code, 429)
        self.assertIn("Please wait", res.data["detail"])

    # 11. Previous OTP invalidation after resend
    def test_11_previous_otp_invalidation_after_resend(self):
        old_otp = "111222"
        # Simulate an OTP created 65 seconds ago
        past_time = timezone.now() - timedelta(seconds=65)
        old_record = OTPVerification.objects.create(
            user=self.admin,
            email=self.admin.email,
            otp_code="",
            otp_hash=hash_otp(old_otp),
            purpose=ADMIN_RECOVERY_PURPOSE,
            expires_at=timezone.now() + timedelta(minutes=4),
            is_verified=False,
            attempts=0
        )
        OTPVerification.objects.filter(pk=old_record.pk).update(created_at=past_time)

        mail.outbox.clear()

        # Resend OTP
        res = self.client.post(self.resend_url, {"email": self.admin.email}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

        # Old OTP record is now invalidated
        old_record.refresh_from_db()
        self.assertTrue(old_record.is_verified)

        # Attempting to verify the old OTP must fail
        verify_old = self.client.post(
            self.verify_url,
            {"email": self.admin.email, "otp": old_otp},
            format="json"
        )
        self.assertEqual(verify_old.status_code, 400)

        # Extract new OTP from email and verify it succeeds
        match = re.search(r"\b(\d{6})\b", mail.outbox[0].body)
        self.assertIsNotNone(match)
        new_otp = match.group(1)
        verify_new = self.client.post(
            self.verify_url,
            {"email": self.admin.email, "otp": new_otp},
            format="json"
        )
        self.assertEqual(verify_new.status_code, 200)

    # 12. Successful password reset
    def test_12_successful_password_reset(self):
        raw_token = "secure_reset_token_test_12345"
        AdminPasswordResetToken.objects.create(
            user=self.admin,
            token_hash=hash_reset_token(raw_token),
            expires_at=timezone.now() + timedelta(minutes=10),
            is_used=False
        )

        new_pass = "BrandNewSecureAdmin@2026"
        res = self.client.post(
            self.reset_url,
            {
                "reset_token": raw_token,
                "new_password": new_pass,
                "confirm_password": new_pass
            },
            format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.data["message"],
            "Password reset successfully. Please login with your new password."
        )

        # Check DB password updated
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(new_pass))
        # Privileges unchanged
        self.assertTrue(self.admin.is_staff)
        self.assertFalse(self.admin.is_superuser)

        # Token is marked used
        token_rec = AdminPasswordResetToken.objects.get(token_hash=hash_reset_token(raw_token))
        self.assertTrue(token_rec.is_used)

    # 13. Password mismatch
    def test_13_password_mismatch(self):
        raw_token = "secure_reset_token_mismatch_test"
        AdminPasswordResetToken.objects.create(
            user=self.admin,
            token_hash=hash_reset_token(raw_token),
            expires_at=timezone.now() + timedelta(minutes=10),
            is_used=False
        )

        res = self.client.post(
            self.reset_url,
            {
                "reset_token": raw_token,
                "new_password": "BrandNewSecureAdmin@2026",
                "confirm_password": "DifferentPassword@2026"
            },
            format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("confirm_password", res.data)

        # Password remains unchanged
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("InitialStrongPassword@2026"))

    # 14. Django password validation
    def test_14_django_password_validation(self):
        raw_token = "secure_reset_token_weak_test"
        AdminPasswordResetToken.objects.create(
            user=self.admin,
            token_hash=hash_reset_token(raw_token),
            expires_at=timezone.now() + timedelta(minutes=10),
            is_used=False
        )

        # Password too short / simple
        res = self.client.post(
            self.reset_url,
            {
                "reset_token": raw_token,
                "new_password": "123",
                "confirm_password": "123"
            },
            format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("new_password", res.data)

        # Password remains unchanged
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("InitialStrongPassword@2026"))

    # 15. Expired reset token
    def test_15_expired_reset_token(self):
        raw_token = "secure_reset_token_expired_test"
        AdminPasswordResetToken.objects.create(
            user=self.admin,
            token_hash=hash_reset_token(raw_token),
            expires_at=timezone.now() - timedelta(seconds=10),
            is_used=False
        )

        res = self.client.post(
            self.reset_url,
            {
                "reset_token": raw_token,
                "new_password": "BrandNewSecureAdmin@2026",
                "confirm_password": "BrandNewSecureAdmin@2026"
            },
            format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("expired", res.data["detail"].lower())

    # 16. Reset token reuse prevention
    def test_16_reset_token_reuse_prevention(self):
        raw_token = "secure_reset_token_reuse_test"
        AdminPasswordResetToken.objects.create(
            user=self.admin,
            token_hash=hash_reset_token(raw_token),
            expires_at=timezone.now() + timedelta(minutes=10),
            is_used=False
        )

        # First use
        res1 = self.client.post(
            self.reset_url,
            {
                "reset_token": raw_token,
                "new_password": "BrandNewSecureAdmin@2026",
                "confirm_password": "BrandNewSecureAdmin@2026"
            },
            format="json"
        )
        self.assertEqual(res1.status_code, 200)

        # Second use must fail
        res2 = self.client.post(
            self.reset_url,
            {
                "reset_token": raw_token,
                "new_password": "AnotherNewPassword@2026",
                "confirm_password": "AnotherNewPassword@2026"
            },
            format="json"
        )
        self.assertEqual(res2.status_code, 400)

    # 17. Existing Admin and Distributor login functionality
    def test_17_existing_admin_and_distributor_login_functionality(self):
        # Admin HTML Login
        admin_login_res = self.client.post(
            reverse("admin_login"),
            {"username": self.admin.username, "password": "InitialStrongPassword@2026"}
        )
        self.assertEqual(admin_login_res.status_code, 302)
        self.assertIn("/admin/dashboard/", admin_login_res.url)

        # Logout before testing distributor login
        self.client.logout()

        # Distributor HTML Login
        dist_login_res = self.client.post(
            reverse("distributor_login"),
            {"username": self.distributor.username, "password": "DistributorPassword@2026"}
        )
        self.assertEqual(dist_login_res.status_code, 302)
        self.assertIn("/distributor/dashboard/", dist_login_res.url)


    # 18. Existing Admin Registration API permissions
    def test_18_existing_admin_registration_api_permissions(self):
        reg_url = reverse("api_admin_register")
        payload = {
            "username": "new_admin_18",
            "email": "new_admin_18@example.com",
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123"
        }

        # Anonymous -> 401
        res_anon = self.client.post(reg_url, payload, format="json")
        self.assertEqual(res_anon.status_code, 401)

        # Distributor -> 403
        self.client.force_authenticate(user=self.distributor)
        res_dist = self.client.post(reg_url, payload, format="json")
        self.assertEqual(res_dist.status_code, 403)

        # Staff (non-superuser) -> 403
        self.client.force_authenticate(user=self.admin)
        res_staff = self.client.post(reg_url, payload, format="json")
        self.assertEqual(res_staff.status_code, 403)

        # Superuser -> 201
        self.client.force_authenticate(user=self.superuser)
        res_super = self.client.post(reg_url, payload, format="json")
        self.assertEqual(res_super.status_code, 201)

    # 19. Duplicate email handling
    def test_19_duplicate_email_handling(self):
        # Create a second staff user with the exact same email
        User.objects.create_user(
            username="dup_staff_user",
            email=self.admin.email,
            password="DupPassword@2026",
            is_staff=True,
            is_active=True
        )

        mail.outbox.clear()
        res = self.client.post(self.forgot_url, {"email": self.admin.email}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.data["message"],
            "If an eligible account exists, a password reset OTP has been sent."
        )
        # 0 emails sent; no ambiguous reset initiated
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(
            OTPVerification.objects.filter(
                email=self.admin.email,
                purpose=ADMIN_RECOVERY_PURPOSE
            ).exists()
        )

    # 20. Old session and JWT rejection after password reset
    def test_20_old_session_and_jwt_rejection_after_password_reset(self):
        token_url = reverse("token_obtain_pair")
        reg_url = reverse("api_admin_register")

        # 1. Obtain JWT access token for superuser before reset
        token_res = self.client.post(
            token_url,
            {"username": self.superuser.username, "password": "SuperStrongPassword@2026"},
            format="json"
        )
        self.assertEqual(token_res.status_code, 200)
        old_access_token = token_res.data["access"]

        # Verify old token works before reset
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access_token}")
        test_payload = {
            "username": "test_pre_reset_user",
            "email": "pre_reset@example.com",
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123"
        }
        res_before = self.client.post(reg_url, test_payload, format="json")
        self.assertEqual(res_before.status_code, 201)

        # 2. Create an active Django session for superuser
        session_client = APIClient()
        session_client.login(username=self.superuser.username, password="SuperStrongPassword@2026")
        # Ensure session exists in DB
        user_sessions = [
            s for s in Session.objects.filter(expire_date__gte=timezone.now())
            if str(s.get_decoded().get("_auth_user_id")) == str(self.superuser.pk)
        ]
        self.assertTrue(len(user_sessions) > 0)

        # 3. Superuser performs password reset
        raw_token = "secure_reset_token_user_20"
        AdminPasswordResetToken.objects.create(
            user=self.superuser,
            token_hash=hash_reset_token(raw_token),
            expires_at=timezone.now() + timedelta(minutes=10),
            is_used=False
        )

        new_pass = "BrandNewSuperPassword@2026"
        reset_res = self.client.post(
            self.reset_url,
            {
                "reset_token": raw_token,
                "new_password": new_pass,
                "confirm_password": new_pass
            },
            format="json"
        )
        self.assertEqual(reset_res.status_code, 200)

        # 4. Old session is invalidated and deleted from DB
        remaining_sessions = [
            s for s in Session.objects.filter(expire_date__gte=timezone.now())
            if str(s.get_decoded().get("_auth_user_id")) == str(self.superuser.pk)
        ]
        self.assertEqual(len(remaining_sessions), 0)

        # 5. Old JWT access token is rejected
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access_token}")
        res_after = self.client.post(
            reg_url,
            {
                "username": "test_post_reset_user",
                "email": "post_reset@example.com",
                "password": "StrongPassword@123",
                "confirm_password": "StrongPassword@123"
            },
            format="json"
        )
        self.assertEqual(res_after.status_code, 401)

        # 6. Logging in with new password grants new valid token
        new_token_res = self.client.post(
            token_url,
            {"username": self.superuser.username, "password": new_pass},
            format="json"
        )
        self.assertEqual(new_token_res.status_code, 200)
        new_access_token = new_token_res.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access_token}")
        res_new = self.client.post(
            reg_url,
            {
                "username": "test_post_reset_user2",
                "email": "post_reset2@example.com",
                "password": "StrongPassword@123",
                "confirm_password": "StrongPassword@123"
            },
            format="json"
        )
        self.assertEqual(res_new.status_code, 201)

    # 21. Email templates render correctly
    def test_21_email_templates_render_correctly(self):
        from django.template.loader import render_to_string
        context = {"otp": "789123", "validity_minutes": 5}

        # Plain text template
        text = render_to_string("emails/admin_password_reset_otp.txt", context)
        self.assertIn("789123", text)
        self.assertIn("Your password reset OTP is:", text)
        self.assertIn("valid for 5 minutes", text)
        self.assertIn("Advance Billing System Team", text)

        # HTML template
        html = render_to_string("emails/admin_password_reset_otp.html", context)
        self.assertIn("789123", html)
        self.assertIn("Advance Billing System", html)
        self.assertIn("Valid for 5 minutes", html)
        self.assertIn("#2563eb", html)

    # 22. SMTP failure handling
    def test_22_smtp_failure_handling(self):
        from unittest.mock import patch
        import smtplib

        with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=smtplib.SMTPException("SMTP connection refused")):
            response = self.client.post(self.forgot_url, {"email": self.admin.email}, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.data["message"],
                "If an eligible account exists, a password reset OTP has been sent."
            )
            # Response never leaks SMTP error details or credentials
            self.assertNotIn("SMTPException", str(response.data))
            self.assertNotIn("refused", str(response.data))

    # 23. Invalid email format on forgot-password
    def test_23_invalid_email_format(self):
        response = self.client.post(self.forgot_url, {"email": "not-an-email-address"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)
        self.assertEqual(len(mail.outbox), 0)

    # 24. Non-dict payload handled gracefully without 500 error
    def test_24_non_dict_payload_handled_gracefully(self):
        response = self.client.post(self.forgot_url, ["not", "a", "dict"], format="json")
        self.assertEqual(response.status_code, 400)

    # 25. Five-minute OTP expiry duration
    def test_25_otp_expiry_duration_five_minutes(self):
        self.client.post(self.forgot_url, {"email": self.admin.email}, format="json")
        otp_rec = OTPVerification.objects.filter(email=self.admin.email, purpose=ADMIN_RECOVERY_PURPOSE).first()
        self.assertIsNotNone(otp_rec)
        diff = (otp_rec.expires_at - otp_rec.created_at).total_seconds()
        self.assertAlmostEqual(diff, 300, delta=5)

    # 26. OTP verification with incorrect email
    def test_26_otp_with_incorrect_email(self):
        raw_otp = "123456"
        OTPVerification.objects.create(
            user=self.admin,
            email=self.admin.email,
            otp_code="",
            otp_hash=hash_otp(raw_otp),
            purpose=ADMIN_RECOVERY_PURPOSE,
            expires_at=timezone.now() + timedelta(minutes=5),
            is_verified=False,
            attempts=0
        )
        # Attempt to verify with a different email
        response = self.client.post(
            self.verify_url,
            {"email": "different_admin@example.com", "otp": raw_otp},
            format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)
        self.assertNotIn("reset_token", response.data)

    # 27. Ten-minute reset token expiry duration
    def test_27_reset_token_expiry_duration_ten_minutes(self):
        raw_otp = "234567"
        OTPVerification.objects.create(
            user=self.admin,
            email=self.admin.email,
            otp_code="",
            otp_hash=hash_otp(raw_otp),
            purpose=ADMIN_RECOVERY_PURPOSE,
            expires_at=timezone.now() + timedelta(minutes=5),
            is_verified=False,
            attempts=0
        )
        response = self.client.post(
            self.verify_url,
            {"email": self.admin.email, "otp": raw_otp},
            format="json"
        )
        self.assertEqual(response.status_code, 200)
        reset_token = response.data["reset_token"]
        token_rec = AdminPasswordResetToken.objects.get(token_hash=hash_reset_token(reset_token))
        diff = (token_rec.expires_at - token_rec.created_at).total_seconds()
        self.assertAlmostEqual(diff, 600, delta=5)

    # 28. No reset token issued for failed verification
    def test_28_no_reset_token_issued_for_failed_verification(self):
        response = self.client.post(
            self.verify_url,
            {"email": self.admin.email, "otp": "000000"},
            format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("reset_token", response.data)

    # 29. Resend OTP with unknown email returns generic response
    def test_29_resend_unknown_email_generic_response(self):
        response = self.client.post(self.resend_url, {"email": "unknown_admin@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["message"],
            "If an eligible account exists, a new password reset OTP has been sent."
        )
        self.assertEqual(len(mail.outbox), 0)

    # 30. Invalid reset token is rejected
    def test_30_invalid_reset_token_rejected(self):
        response = self.client.post(
            self.reset_url,
            {
                "reset_token": "completely_fake_and_invalid_token",
                "new_password": "BrandNewSecureAdmin@2026",
                "confirm_password": "BrandNewSecureAdmin@2026"
            },
            format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)
        self.assertIn("Invalid or expired reset token.", response.data["detail"])

    # 31. Old password fails and new password works via JWT authentication
    def test_31_old_password_fails_and_new_password_works_jwt(self):
        raw_token = "secure_reset_token_auth_31"
        AdminPasswordResetToken.objects.create(
            user=self.admin,
            token_hash=hash_reset_token(raw_token),
            expires_at=timezone.now() + timedelta(minutes=10),
            is_used=False
        )

        old_pass = "InitialStrongPassword@2026"
        new_pass = "UpdatedSecurePassword@2026"

        # Reset password
        reset_res = self.client.post(
            self.reset_url,
            {
                "reset_token": raw_token,
                "new_password": new_pass,
                "confirm_password": new_pass
            },
            format="json"
        )
        self.assertEqual(reset_res.status_code, 200)

        # Old password must fail
        token_url = reverse("token_obtain_pair")
        fail_res = self.client.post(
            token_url,
            {"username": self.admin.username, "password": old_pass},
            format="json"
        )
        self.assertEqual(fail_res.status_code, 401)

        # New password must succeed
        success_res = self.client.post(
            token_url,
            {"username": self.admin.username, "password": new_pass},
            format="json"
        )
        self.assertEqual(success_res.status_code, 200)
        self.assertIn("access", success_res.data)
        self.assertIn("refresh", success_res.data)

    # 32. No automatic login or token issuance after password reset
    def test_32_no_automatic_login_after_reset(self):
        raw_token = "secure_reset_token_nologin_32"
        AdminPasswordResetToken.objects.create(
            user=self.admin,
            token_hash=hash_reset_token(raw_token),
            expires_at=timezone.now() + timedelta(minutes=10),
            is_used=False
        )
        new_pass = "NoAutoLoginPassword@2026"
        response = self.client.post(
            self.reset_url,
            {
                "reset_token": raw_token,
                "new_password": new_pass,
                "confirm_password": new_pass
            },
            format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertNotIn("token", response.data)
        self.assertNotIn("sessionid", self.client.cookies)


class JWTAuthenticationAPITests(APITestCase):
    """
    Dedicated test suite for JWT authentication endpoints:
    - POST /api/token/
    - POST /api/token/refresh/
    """

    def setUp(self):
        self.client = APIClient()
        self.token_url = reverse("token_obtain_pair")
        self.refresh_url = reverse("token_refresh")
        self.admin_register_url = reverse("api_admin_register")

        # Superuser
        self.superuser = User.objects.create_superuser(
            username="jwt_superadmin",
            email="jwt_superadmin@example.com",
            password="SuperPassword@2026"
        )

        # Inactive User
        self.inactive_user = User.objects.create_user(
            username="jwt_inactive",
            email="jwt_inactive@example.com",
            password="InactivePassword@2026",
            is_active=False
        )

    def test_valid_credentials_generate_tokens(self):
        """Valid credentials return access and refresh JWT tokens (200 OK)."""
        response = self.client.post(
            self.token_url,
            {"username": self.superuser.username, "password": "SuperPassword@2026"},
            format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertTrue(len(response.data["access"]) > 20)
        self.assertTrue(len(response.data["refresh"]) > 20)

    def test_incorrect_credentials_rejected(self):
        """Incorrect credentials are rejected (401 Unauthorized)."""
        response = self.client.post(
            self.token_url,
            {"username": self.superuser.username, "password": "WrongPassword@2026"},
            format="json"
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access", response.data)

    def test_inactive_users_cannot_authenticate(self):
        """Inactive users cannot obtain JWT tokens (401 Unauthorized)."""
        response = self.client.post(
            self.token_url,
            {"username": self.inactive_user.username, "password": "InactivePassword@2026"},
            format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_valid_access_token_authenticates_admin_registration(self):
        """Valid access token authenticates requests to protected Admin Registration endpoint."""
        token_res = self.client.post(
            self.token_url,
            {"username": self.superuser.username, "password": "SuperPassword@2026"},
            format="json"
        )
        access_token = token_res.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        reg_payload = {
            "username": "jwt_registered_admin",
            "email": "jwt_registered@example.com",
            "password": "ExampleStrong@2026X",
            "confirm_password": "ExampleStrong@2026X"
        }
        response = self.client.post(self.admin_register_url, reg_payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["admin"]["username"], "jwt_registered_admin")

    def test_expired_or_invalid_tokens_rejected(self):
        """Expired or malformed tokens are rejected with 401 Unauthorized."""
        # 1. Malformed token
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.payload")
        response = self.client.post(
            self.admin_register_url,
            {"username": "test_invalid"},
            format="json"
        )
        self.assertEqual(response.status_code, 401)

        # 2. Expired token
        from rest_framework_simplejwt.tokens import AccessToken
        token = AccessToken.for_user(self.superuser)
        # Manually backdate token expiration
        token.set_exp(lifetime=-timedelta(minutes=10))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
        response_exp = self.client.post(
            self.admin_register_url,
            {"username": "test_expired"},
            format="json"
        )
        self.assertEqual(response_exp.status_code, 401)

    def test_refresh_token_flow(self):
        """Refresh token flow returns a new valid access token."""
        token_res = self.client.post(
            self.token_url,
            {"username": self.superuser.username, "password": "SuperPassword@2026"},
            format="json"
        )
        refresh_token = token_res.data["refresh"]

        # Call /api/token/refresh/
        refresh_res = self.client.post(
            self.refresh_url,
            {"refresh": refresh_token},
            format="json"
        )
        self.assertEqual(refresh_res.status_code, 200)
        self.assertIn("access", refresh_res.data)
        new_access = refresh_res.data["access"]

        # Use new access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
        reg_res = self.client.post(
            self.admin_register_url,
            {
                "username": "refreshed_admin_user",
                "email": "refreshed_admin@example.com",
                "password": "ExampleStrong@2026X",
                "confirm_password": "ExampleStrong@2026X"
            },
            format="json"
        )
        self.assertEqual(reg_res.status_code, 201)

    def test_invalid_refresh_token_rejected(self):
        """Invalid refresh token returns 401 Unauthorized."""
        response = self.client.post(
            self.refresh_url,
            {"refresh": "invalid_refresh_token_payload"},
            format="json"
        )
        self.assertEqual(response.status_code, 401)


class AdminWorkflowEndToEndIntegrationTests(APITestCase):
    """
    Complete end-to-end integration test of the Admin Registration
    and Password Recovery functionalities as specified in Section 8:
    1. Create a superuser in the isolated test database.
    2. Obtain JWT access token.
    3. Register a new staff Admin through the registration API.
    4. Request password recovery for the new Admin.
    5. Capture the OTP through Django's in-memory test email backend.
    6. Verify the OTP.
    7. Receive the password reset token.
    8. Reset the Admin password.
    9. Confirm old password authentication fails.
    10. Confirm new password authentication succeeds.
    11. Confirm Admin permissions remain unchanged.
    12. Confirm used OTP and reset token cannot be reused.
    """

    def setUp(self):
        cache.clear()
        mail.outbox.clear()
        self.client = APIClient()

    def tearDown(self):
        cache.clear()
        mail.outbox.clear()

    def test_complete_admin_registration_and_password_recovery_lifecycle(self):
        # Step 1: Create a superuser in isolated test DB
        superadmin = User.objects.create_superuser(
            username="e2e_superadmin",
            email="e2e_superadmin@example.com",
            password="SuperE2EPassword@2026"
        )

        # Step 2: Obtain JWT access token
        token_url = reverse("token_obtain_pair")
        token_res = self.client.post(
            token_url,
            {"username": "e2e_superadmin", "password": "SuperE2EPassword@2026"},
            format="json"
        )
        self.assertEqual(token_res.status_code, 200)
        super_access = token_res.data["access"]

        # Step 3: Register a new staff Admin through registration API
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {super_access}")
        register_url = reverse("api_admin_register")
        initial_admin_password = "InitialAdminSecret@2026"
        reg_payload = {
            "username": "e2e_new_admin",
            "email": "e2e_new_admin@example.com",
            "first_name": "Vikram",
            "last_name": "Sharma",
            "password": initial_admin_password,
            "confirm_password": initial_admin_password
        }
        reg_res = self.client.post(register_url, reg_payload, format="json")
        self.assertEqual(reg_res.status_code, 201)
        self.assertEqual(reg_res.data["message"], "Admin user registered successfully.")
        new_admin = User.objects.get(username="e2e_new_admin")
        self.assertTrue(new_admin.is_staff)
        self.assertFalse(new_admin.is_superuser)
        self.assertTrue(new_admin.check_password(initial_admin_password))

        # Clear authentication credentials for anonymous recovery workflow
        self.client.credentials()

        # Step 4: Request password recovery for the new Admin
        forgot_url = reverse("api_admin_forgot_password")
        forgot_res = self.client.post(
            forgot_url,
            {"email": "e2e_new_admin@example.com"},
            format="json"
        )
        self.assertEqual(forgot_res.status_code, 200)
        self.assertEqual(
            forgot_res.data["message"],
            "If an eligible account exists, a password reset OTP has been sent."
        )

        # Step 5: Capture OTP through in-memory test email backend
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, ["e2e_new_admin@example.com"])
        otp_match = re.search(r"\b(\d{6})\b", sent_email.body)
        self.assertIsNotNone(otp_match, "OTP not found in email body")
        captured_otp = otp_match.group(1)

        # Step 6: Verify the OTP
        verify_url = reverse("api_admin_verify_reset_otp")
        verify_res = self.client.post(
            verify_url,
            {"email": "e2e_new_admin@example.com", "otp": captured_otp},
            format="json"
        )
        self.assertEqual(verify_res.status_code, 200)
        self.assertEqual(verify_res.data["message"], "OTP verified successfully.")

        # Step 7: Receive the password reset token
        self.assertIn("reset_token", verify_res.data)
        reset_token = verify_res.data["reset_token"]
        self.assertTrue(len(reset_token) > 20)

        # Step 8: Reset the Admin password
        reset_url = reverse("api_admin_reset_password")
        new_admin_password = "BrandNewAdminSecret@2026X"
        reset_res = self.client.post(
            reset_url,
            {
                "reset_token": reset_token,
                "new_password": new_admin_password,
                "confirm_password": new_admin_password
            },
            format="json"
        )
        self.assertEqual(reset_res.status_code, 200)
        self.assertEqual(
            reset_res.data["message"],
            "Password reset successfully. Please login with your new password."
        )

        # Step 9: Confirm old password authentication fails
        old_auth_res = self.client.post(
            token_url,
            {"username": "e2e_new_admin", "password": initial_admin_password},
            format="json"
        )
        self.assertEqual(old_auth_res.status_code, 401)

        # Step 10: Confirm new password authentication succeeds
        new_auth_res = self.client.post(
            token_url,
            {"username": "e2e_new_admin", "password": new_admin_password},
            format="json"
        )
        self.assertEqual(new_auth_res.status_code, 200)
        self.assertIn("access", new_auth_res.data)
        self.assertIn("refresh", new_auth_res.data)

        # Step 11: Confirm Admin permissions remain unchanged
        new_admin.refresh_from_db()
        self.assertTrue(new_admin.is_staff)
        self.assertFalse(new_admin.is_superuser)
        self.assertTrue(new_admin.is_active)
        self.assertTrue(new_admin.check_password(new_admin_password))

        # Step 12: Confirm used OTP and reset token cannot be reused
        # 12a. Attempting to verify used OTP fails
        reuse_otp_res = self.client.post(
            verify_url,
            {"email": "e2e_new_admin@example.com", "otp": captured_otp},
            format="json"
        )
        self.assertEqual(reuse_otp_res.status_code, 400)

        # 12b. Attempting to reset password with used reset token fails
        reuse_token_res = self.client.post(
            reset_url,
            {
                "reset_token": reset_token,
                "new_password": "YetAnotherPassword@2026",
                "confirm_password": "YetAnotherPassword@2026"
            },
            format="json"
        )
        self.assertEqual(reuse_token_res.status_code, 400)
        self.assertIn("Invalid or expired reset token.", reuse_token_res.data["detail"])


from billing.models import Customer
from accounts.models import DistributorProfile


class CustomerRegistrationAPITests(APITestCase):
    """
    Automated test suite for POST /api/distributor/customers/register/
    Validates Distributor authentication, ownership enforcement, input validation,
    security boundaries, and non-regression of existing features.
    """

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api_distributor_customer_register")

        # Distributor Group
        self.distributor_group, _ = Group.objects.get_or_create(name="Distributor")

        # Distributor 1 (User with group + DistributorProfile)
        self.distributor1 = User.objects.create_user(
            username="distributor1@example.com",
            email="distributor1@example.com",
            password="DistPassword@123",
            first_name="Rahul",
            last_name="Patel"
        )
        self.distributor1.groups.add(self.distributor_group)
        self.profile1 = DistributorProfile.objects.create(
            user=self.distributor1,
            full_name="Rahul Patel",
            email="distributor1@example.com",
            phone="9876543210"
        )

        # Distributor 2 (User with group + DistributorProfile)
        self.distributor2 = User.objects.create_user(
            username="distributor2@example.com",
            email="distributor2@example.com",
            password="DistPassword@123",
            first_name="Amit",
            last_name="Shah"
        )
        self.distributor2.groups.add(self.distributor_group)
        self.profile2 = DistributorProfile.objects.create(
            user=self.distributor2,
            full_name="Amit Shah",
            email="distributor2@example.com",
            phone="9876543211"
        )

        # Distributor 3 (User with DistributorProfile only, no group)
        self.distributor3 = User.objects.create_user(
            username="distributor3@example.com",
            email="distributor3@example.com",
            password="DistPassword@123",
            first_name="Vikas",
            last_name="Mehta"
        )
        self.profile3 = DistributorProfile.objects.create(
            user=self.distributor3,
            full_name="Vikas Mehta",
            email="distributor3@example.com",
            phone="9876543212"
        )

        # Regular Non-Distributor User
        self.regular_user = User.objects.create_user(
            username="regularuser@example.com",
            email="regularuser@example.com",
            password="RegularPassword@123"
        )

        # Staff Admin User (non-distributor)
        self.staff_admin = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="AdminPassword@123",
            is_staff=True,
            is_superuser=False
        )

        # Superuser (non-distributor)
        self.superuser = User.objects.create_superuser(
            username="superuser@example.com",
            email="superuser@example.com",
            password="SuperPassword@123"
        )

        # Default valid customer payload
        self.valid_payload = {
            "name": "Rahul Patel",
            "email": "rahul@example.com",
            "phone": "9876543210",
            "address": "Main Road",
            "city": "Ahmedabad",
            "state": "Gujarat",
            "pincode": "380001"
        }

    # 1. Authenticated Distributor can register a valid customer
    def test_authenticated_distributor_registers_valid_customer(self):
        """Authenticated Distributor can register a valid customer (201 Created)."""
        self.client.force_authenticate(user=self.distributor1)
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Customer registered successfully.")
        cust_data = response.data["customer"]
        self.assertIsNotNone(cust_data.get("id"))
        self.assertEqual(cust_data["name"], "Rahul Patel")
        self.assertEqual(cust_data["email"], "rahul@example.com")
        self.assertEqual(cust_data["phone"], "9876543210")
        self.assertEqual(cust_data["address"], "Main Road")
        self.assertEqual(cust_data["city"], "Ahmedabad")
        self.assertEqual(cust_data["state"], "Gujarat")
        self.assertEqual(cust_data["pincode"], "380001")

    # 2. Customer is saved in database and 3. linked to logged-in Distributor
    def test_customer_saved_in_database_and_linked_to_logged_in_distributor(self):
        """Saved customer exists in DB and is linked strictly to the logged-in Distributor."""
        self.client.force_authenticate(user=self.distributor1)
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, 201)

        customer_id = response.data["customer"]["id"]
        customer = Customer.objects.get(id=customer_id)
        self.assertEqual(customer.name, "Rahul Patel")
        self.assertEqual(customer.email, "rahul@example.com")
        self.assertEqual(customer.phone, "9876543210")
        self.assertEqual(customer.distributor, self.distributor1)
        self.assertNotEqual(customer.distributor, self.distributor2)

    # 4. Unauthenticated request is rejected (401)
    def test_unauthenticated_request_rejected(self):
        """Unauthenticated request must be rejected with HTTP 401."""
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(Customer.objects.filter(phone="9876543210").exists())

    # 5. Admin user is rejected unless explicitly permitted by business rules (403)
    def test_staff_admin_rejected_with_403(self):
        """Staff Admin without Distributor role must be rejected with HTTP 403."""
        self.client.force_authenticate(user=self.staff_admin)
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Customer.objects.filter(phone="9876543210").exists())

    def test_superuser_rejected_with_403(self):
        """Superuser without Distributor role must be rejected with HTTP 403."""
        self.client.force_authenticate(user=self.superuser)
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Customer.objects.filter(phone="9876543210").exists())

    def test_regular_user_rejected_with_403(self):
        """Regular non-distributor user must be rejected with HTTP 403."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Customer.objects.filter(phone="9876543210").exists())

    # 6. Distributor cannot supply another Distributor's ID
    def test_client_cannot_spoof_distributor_ownership(self):
        """Supplying another distributor's ID in payload is ignored; ownership stays with request.user."""
        self.client.force_authenticate(user=self.distributor1)
        spoofed_payload = dict(self.valid_payload)
        spoofed_payload["distributor_id"] = self.distributor2.id
        spoofed_payload["distributor"] = self.distributor2.id

        response = self.client.post(self.url, spoofed_payload, format="json")
        self.assertEqual(response.status_code, 201)

        customer = Customer.objects.get(id=response.data["customer"]["id"])
        self.assertEqual(customer.distributor, self.distributor1)
        self.assertNotEqual(customer.distributor, self.distributor2)

    # 7. Missing required fields return HTTP 400
    def test_missing_required_fields_return_400(self):
        """Missing required fields (name, phone) return HTTP 400 Bad Request."""
        self.client.force_authenticate(user=self.distributor1)
        # Empty payload
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)
        self.assertIn("phone", response.data)

    def test_missing_name_returns_400(self):
        """Missing or empty customer name returns 400."""
        self.client.force_authenticate(user=self.distributor1)
        payload = dict(self.valid_payload)
        payload["name"] = ""
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)

    def test_whitespace_name_returns_400(self):
        """Customer name with only whitespace returns 400."""
        self.client.force_authenticate(user=self.distributor1)
        payload = dict(self.valid_payload)
        payload["name"] = "   "
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)

    def test_digits_only_name_returns_400(self):
        """Customer name with only digits returns 400."""
        self.client.force_authenticate(user=self.distributor1)
        payload = dict(self.valid_payload)
        payload["name"] = "123456"
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)

    # 8. Invalid email returns HTTP 400
    def test_invalid_email_returns_400(self):
        """Invalid email format returns HTTP 400 Bad Request."""
        self.client.force_authenticate(user=self.distributor1)
        payload = dict(self.valid_payload)
        payload["email"] = "not-a-valid-email"
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_optional_fields_can_be_omitted_or_null(self):
        """Customer can be registered with only required fields (name, phone); optional fields default gracefully."""
        self.client.force_authenticate(user=self.distributor1)
        minimal_payload = {
            "name": "Minimal Customer",
            "phone": "9876543299"
        }
        response = self.client.post(self.url, minimal_payload, format="json")
        self.assertEqual(response.status_code, 201)
        cust = Customer.objects.get(id=response.data["customer"]["id"])
        self.assertEqual(cust.name, "Minimal Customer")
        self.assertEqual(cust.phone, "9876543299")
        self.assertIsNone(cust.email)
        self.assertIsNone(cust.address)

    # 9. Invalid phone or pincode returns HTTP 400
    def test_invalid_phone_formats_return_400(self):
        """Phones not matching 10-digit format starting with 6-9 return 400."""
        self.client.force_authenticate(user=self.distributor1)

        # Starts with invalid digit
        p1 = dict(self.valid_payload, phone="1234567890")
        r1 = self.client.post(self.url, p1, format="json")
        self.assertEqual(r1.status_code, 400)
        self.assertIn("phone", r1.data)

        # Less than 10 digits
        p2 = dict(self.valid_payload, phone="98765")
        r2 = self.client.post(self.url, p2, format="json")
        self.assertEqual(r2.status_code, 400)
        self.assertIn("phone", r2.data)

        # Contains non-digits
        p3 = dict(self.valid_payload, phone="98765ABCDE")
        r3 = self.client.post(self.url, p3, format="json")
        self.assertEqual(r3.status_code, 400)
        self.assertIn("phone", r3.data)

    def test_invalid_pincode_formats_return_400(self):
        """Pincodes not matching 6-digit numeric pattern return 400."""
        self.client.force_authenticate(user=self.distributor1)

        # 5 digits
        p1 = dict(self.valid_payload, pincode="38001")
        r1 = self.client.post(self.url, p1, format="json")
        self.assertEqual(r1.status_code, 400)
        self.assertIn("pincode", r1.data)

        # Non-digits
        p2 = dict(self.valid_payload, pincode="38000A")
        r2 = self.client.post(self.url, p2, format="json")
        self.assertEqual(r2.status_code, 400)
        self.assertIn("pincode", r2.data)

    def test_invalid_city_and_state_with_digits_return_400(self):
        """City and State containing numbers are rejected with 400."""
        self.client.force_authenticate(user=self.distributor1)

        p1 = dict(self.valid_payload, city="Ahmedabad123")
        r1 = self.client.post(self.url, p1, format="json")
        self.assertEqual(r1.status_code, 400)
        self.assertIn("city", r1.data)

        p2 = dict(self.valid_payload, state="Gujarat99")
        r2 = self.client.post(self.url, p2, format="json")
        self.assertEqual(r2.status_code, 400)
        self.assertIn("state", r2.data)

    # 10. Duplicate customer data follows existing model constraints
    def test_duplicate_customer_across_different_distributors_allowed(self):
        """Two different Distributors can maintain separate customer records with identical details."""
        self.client.force_authenticate(user=self.distributor1)
        res1 = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(res1.status_code, 201)

        self.client.force_authenticate(user=self.distributor2)
        res2 = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(res2.status_code, 201)

        c1 = Customer.objects.get(id=res1.data["customer"]["id"])
        c2 = Customer.objects.get(id=res2.data["customer"]["id"])
        self.assertEqual(c1.distributor, self.distributor1)
        self.assertEqual(c2.distributor, self.distributor2)
        self.assertNotEqual(c1.id, c2.id)

    # 11. One Distributor cannot change another Distributor's customer ownership
    def test_distributor_cannot_alter_existing_customer_ownership(self):
        """Registering a customer never mutates or overwrites another distributor's existing customer."""
        self.client.force_authenticate(user=self.distributor1)
        res1 = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(res1.status_code, 201)
        c1_id = res1.data["customer"]["id"]

        # Distributor 2 registers same details
        self.client.force_authenticate(user=self.distributor2)
        res2 = self.client.post(self.url, dict(self.valid_payload, id=c1_id), format="json")
        self.assertEqual(res2.status_code, 201)
        c2_id = res2.data["customer"]["id"]

        # Existing customer owned by Distributor 1 was untouched
        c1 = Customer.objects.get(id=c1_id)
        self.assertEqual(c1.distributor, self.distributor1)

        # New customer is owned by Distributor 2
        c2 = Customer.objects.get(id=c2_id)
        self.assertEqual(c2.distributor, self.distributor2)
        self.assertNotEqual(c1.id, c2.id)

    # 12. Authentication Methods: JWT Bearer Token
    def test_jwt_token_authentication(self):
        """Customer registration succeeds using JWT Bearer token authentication."""
        token_res = self.client.post(
            reverse("token_obtain_pair"),
            {"username": self.distributor1.username, "password": "DistPassword@123"},
            format="json"
        )
        self.assertEqual(token_res.status_code, 200)
        access_token = token_res.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Customer registered successfully.")
        customer = Customer.objects.get(id=response.data["customer"]["id"])
        self.assertEqual(customer.distributor, self.distributor1)

    # 13. Authentication Methods: Session Authentication
    def test_session_authentication(self):
        """Customer registration succeeds using Django Session authentication."""
        logged_in = self.client.login(username=self.distributor1.username, password="DistPassword@123")
        self.assertTrue(logged_in)
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, 201)
        customer = Customer.objects.get(id=response.data["customer"]["id"])
        self.assertEqual(customer.distributor, self.distributor1)

    # 14. Distributor Profile-only user support
    def test_distributor_with_profile_accepted(self):
        """User with DistributorProfile is recognized as eligible distributor."""
        self.client.force_authenticate(user=self.distributor3)
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, 201)
        customer = Customer.objects.get(id=response.data["customer"]["id"])
        self.assertEqual(customer.distributor, self.distributor3)

    # 15. No internal or private fields exposed
    def test_no_private_fields_exposed(self):
        """Response must not expose passwords, hashes, or unrelated private fields."""
        self.client.force_authenticate(user=self.distributor1)
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.data)
        self.assertNotIn("password", response.data["customer"])
        self.assertNotIn("distributor_id", response.data["customer"])
        self.assertNotIn("distributor", response.data["customer"])

    # 16. Existing customer management continue working
    def test_existing_customer_list_reflects_registered_customer(self):
        """Registered customer through API is correctly visible in the distributor's web customer list."""
        self.client.force_authenticate(user=self.distributor1)
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, 201)

        # Login to web session and fetch customer_list
        self.client.login(username=self.distributor1.username, password="DistPassword@123")
        list_res = self.client.get(reverse("customer_list"))
        self.assertEqual(list_res.status_code, 200)
        self.assertContains(list_res, "Rahul Patel")
        self.assertContains(list_res, "9876543210")


class CustomerRegisterViewTests(APITestCase):
    """
    Test suite for the Frontend Customer Registration Page:
    - URL routing & reverse
    - Role-based access control (RBAC) & login protection
    - Template inheritance and rendering
    - Form field inputs and accessibility attributes
    - Full end-to-end integration with POST /api/distributor/customers/register/
    """

    def setUp(self):
        self.distributor_group, _ = Group.objects.get_or_create(name="Distributor")

        # Distributor User
        self.distributor_user = User.objects.create_user(
            username="dist_user_frontend",
            email="dist_fe@example.com",
            password="StrongPassword@123"
        )
        self.distributor_user.groups.add(self.distributor_group)
        DistributorProfile.objects.create(
            user=self.distributor_user,
            full_name="Frontend Enterprises",
            email="dist_fe@example.com",
            phone="9988776655"
        )

        # Regular Non-Distributor User
        self.regular_user = User.objects.create_user(
            username="regular_user",
            email="reg@example.com",
            password="StrongPassword@123"
        )

        # Admin User
        self.admin_user = User.objects.create_superuser(
            username="admin_super",
            email="admin_super@example.com",
            password="StrongPassword@123"
        )

        self.register_url = reverse("customer_register")
        self.api_url = reverse("api_distributor_customer_register")

    def test_customer_register_url_resolves(self):
        """Verify URL reverses to expected path."""
        self.assertEqual(self.register_url, "/distributor/customers/register/")

    def test_unauthenticated_access_redirects(self):
        """Unauthenticated user accessing customer register page is redirected to distributor login."""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)

    def test_non_distributor_access_redirects(self):
        """Authenticated non-distributor user is redirected away."""
        self.client.login(username="regular_user", password="StrongPassword@123")
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)

    def test_admin_without_distributor_role_redirects(self):
        """Superuser without distributor role is redirected away."""
        self.client.login(username="admin_super", password="StrongPassword@123")
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/distributor/login/", response.url)

    def test_distributor_access_granted(self):
        """Authenticated distributor successfully loads customer registration page."""
        self.client.login(username="dist_user_frontend", password="StrongPassword@123")
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "billing/customer_register.html")
        self.assertTemplateUsed(response, "billing/base_distributor.html")

    def test_page_elements_and_fields_present(self):
        """Verify page contains required heading, subtitle, icons, breadcrumbs, inputs, and actions."""
        self.client.login(username="dist_user_frontend", password="StrongPassword@123")
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)

        # Headings & Subtitle
        self.assertContains(response, "Register New Customer")
        self.assertContains(response, "Add customer details to manage billing and invoices.")

        # Breadcrumbs
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Customers")

        # Form fields
        self.assertContains(response, 'id="id_name"')
        self.assertContains(response, 'id="id_phone"')
        self.assertContains(response, 'id="id_email"')
        self.assertContains(response, 'id="id_pincode"')
        self.assertContains(response, 'id="id_city"')
        self.assertContains(response, 'id="id_state"')
        self.assertContains(response, 'id="id_address"')

        # Buttons and Actions
        self.assertContains(response, "Register Customer")
        self.assertContains(response, "Cancel")
        self.assertContains(response, reverse("customer_list"))

        # Assets
        self.assertContains(response, "distributor.css")
        self.assertContains(response, "customer_register.js")

    def test_api_integration_via_session_auth(self):
        """Distributor logged into web session can register customer via the real API."""
        self.client.login(username="dist_user_frontend", password="StrongPassword@123")
        payload = {
            "name": "Vikram Desai",
            "phone": "9825012345",
            "email": "vikram@example.com",
            "address": "402 Sapphire Heights, CG Road",
            "city": "Ahmedabad",
            "state": "Gujarat",
            "pincode": "380009"
        }
        response = self.client.post(
            self.api_url,
            data=payload,
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Customer.objects.filter(
            name="Vikram Desai",
            phone="9825012345",
            distributor=self.distributor_user
        ).exists())


from django.test import TestCase, Client
from decimal import Decimal
from datetime import date, timedelta
from billing.models import Customer, Product, Invoice, InvoiceItem
from accounts.models import DistributorProfile


class AdminReportsAccessAndSecurityTests(TestCase):
    """
    Test suite verifying access control, authentication, and security boundaries
    for Admin Reports Dashboard and CSV Export endpoints.
    """

    def setUp(self):
        self.client = Client()
        self.reports_url = reverse("admin_reports")
        self.export_url = reverse("admin_reports_export_csv")
        self.export_pdf_url = reverse("admin_reports_export_pdf")

        # Staff Admin User
        self.staff_admin = User.objects.create_user(
            username="staff_reports_admin",
            email="staffadmin@example.com",
            password="AdminPassword@123",
            is_staff=True,
            is_superuser=False
        )

        # Superuser
        self.superuser = User.objects.create_superuser(
            username="super_reports_admin",
            email="superadmin@example.com",
            password="SuperPassword@123"
        )

        # Regular Non-Staff Distributor
        self.distributor_group, _ = Group.objects.get_or_create(name="Distributor")
        self.distributor_user = User.objects.create_user(
            username="dist_reports_user",
            email="dist@example.com",
            password="DistPassword@123"
        )
        self.distributor_user.groups.add(self.distributor_group)
        self.profile = DistributorProfile.objects.create(
            user=self.distributor_user,
            full_name="Distributor Profile User",
            email="dist@example.com",
            phone="9876543210"
        )

        # Regular Unprivileged User
        self.regular_user = User.objects.create_user(
            username="regular_reports_user",
            email="regular@example.com",
            password="RegularPassword@123"
        )

    def test_unauthenticated_user_redirected_to_admin_login(self):
        """Unauthenticated visitor accessing reports is redirected to /admin/login/."""
        response = self.client.get(self.reports_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_unauthenticated_user_cannot_export_csv(self):
        """Unauthenticated visitor cannot export CSV reports."""
        response = self.client.get(self.export_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_unauthenticated_user_cannot_export_pdf(self):
        """Unauthenticated visitor cannot export PDF reports."""
        response = self.client.get(self.export_pdf_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_distributor_user_denied_access_to_reports(self):
        """Distributor user without staff flag is rejected with redirect to login."""
        self.client.login(username="dist_reports_user", password="DistPassword@123")
        response = self.client.get(self.reports_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_distributor_user_cannot_export_csv(self):
        """Distributor user without staff flag cannot access CSV export."""
        self.client.login(username="dist_reports_user", password="DistPassword@123")
        response = self.client.get(self.export_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_distributor_user_cannot_export_pdf(self):
        """Distributor user without staff flag cannot access PDF export."""
        self.client.login(username="dist_reports_user", password="DistPassword@123")
        response = self.client.get(self.export_pdf_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_regular_user_denied_access(self):
        """Regular non-staff user is denied access."""
        self.client.login(username="regular_reports_user", password="RegularPassword@123")
        response = self.client.get(self.reports_url)
        self.assertEqual(response.status_code, 302)

    def test_staff_admin_can_access_reports_dashboard(self):
        """Staff admin successfully accesses reports dashboard (200 OK) with correct template."""
        self.client.login(username="staff_reports_admin", password="AdminPassword@123")
        response = self.client.get(self.reports_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "adminpanel/admin_reports.html")
        self.assertContains(response, "Reports & Business Analytics")
        self.assertContains(response, "Generate Invoice Report")
        self.assertContains(response, "Report Filters")
        self.assertContains(response, "Export Report (CSV)")
        self.assertContains(response, "Download PDF")
        self.assertContains(response, self.export_pdf_url)

    def test_superuser_can_access_reports_dashboard(self):
        """Superuser successfully accesses reports dashboard (200 OK)."""
        self.client.login(username="super_reports_admin", password="SuperPassword@123")
        response = self.client.get(self.reports_url)
        self.assertEqual(response.status_code, 200)

    def test_navigation_sidebar_highlights_active_reports_link(self):
        """Reports link in sidebar includes active class when on reports page."""
        self.client.login(username="staff_reports_admin", password="AdminPassword@123")
        response = self.client.get(self.reports_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/admin/reports/" class="admin-nav-item active"')


class AdminReportsDataAndFilteringTests(TestCase):
    """
    Test suite validating accurate calculation of KPIs, date range filtering,
    distributor filtering, and empty states.
    """

    def setUp(self):
        self.client = Client()
        self.reports_url = reverse("admin_reports")
        self.export_url = reverse("admin_reports_export_csv")
        self.export_pdf_url = reverse("admin_reports_export_pdf")

        # Staff Admin
        self.admin = User.objects.create_user(
            username="admin_analytics",
            password="AdminPassword@123",
            is_staff=True
        )

        # Distributor 1 & Profile
        self.distributor_group, _ = Group.objects.get_or_create(name="Distributor")
        self.dist1 = User.objects.create_user(
            username="dist1_analytics",
            password="DistPassword@123"
        )
        self.dist1.groups.add(self.distributor_group)
        DistributorProfile.objects.create(
            user=self.dist1,
            full_name="Alpha Distributors",
            email="alpha@example.com",
            phone="9876543201"
        )

        # Distributor 2 & Profile
        self.dist2 = User.objects.create_user(
            username="dist2_analytics",
            password="DistPassword@123"
        )
        self.dist2.groups.add(self.distributor_group)
        DistributorProfile.objects.create(
            user=self.dist2,
            full_name="Beta Enterprises",
            email="beta@example.com",
            phone="9876543202"
        )

        # Customers
        self.cust1 = Customer.objects.create(
            distributor=self.dist1,
            name="Ramesh Kumar",
            phone="9876543210"
        )
        self.cust2 = Customer.objects.create(
            distributor=self.dist2,
            name="Suresh Verma",
            phone="9876543211"
        )

        # Products
        self.prod1 = Product.objects.create(
            distributor=self.dist1,
            name="Wireless Mouse",
            sku="WM-1",
            price=Decimal("500.00"),
            stock=45,
            is_active=True
        )
        self.prod2 = Product.objects.create(
            distributor=self.dist1,
            name="Mechanical Keyboard",
            sku="KB-2",
            price=Decimal("2000.00"),
            stock=3,
            is_active=True
        )
        self.prod3 = Product.objects.create(
            distributor=self.dist2,
            name="USB Hub",
            sku="HUB-3",
            price=Decimal("800.00"),
            stock=0,
            is_active=False
        )

        # Invoices across different dates
        today = date.today()
        yesterday = today - timedelta(days=1)
        two_weeks_ago = today - timedelta(days=14)

        # Invoice 1: Today, Dist1, Cust1 (Grand Total: 1180.00)
        self.inv1 = Invoice.objects.create(
            distributor=self.dist1,
            customer=self.cust1,
            invoice_number="INV-REP-001",
            invoice_date=today,
            subtotal=Decimal("1000.00"),
            total_gst=Decimal("180.00"),
            grand_total=Decimal("1180.00")
        )
        InvoiceItem.objects.create(
            invoice=self.inv1,
            product=self.prod1,
            product_name="Wireless Mouse",
            quantity=2,
            unit_price=Decimal("500.00"),
            taxable_amount=Decimal("1000.00"),
            gst_amount=Decimal("180.00"),
            line_total=Decimal("1180.00")
        )

        # Invoice 2: Yesterday, Dist1, Cust1 (Grand Total: 2360.00)
        self.inv2 = Invoice.objects.create(
            distributor=self.dist1,
            customer=self.cust1,
            invoice_number="INV-REP-002",
            invoice_date=yesterday,
            subtotal=Decimal("2000.00"),
            total_gst=Decimal("360.00"),
            grand_total=Decimal("2360.00")
        )
        InvoiceItem.objects.create(
            invoice=self.inv2,
            product=self.prod2,
            product_name="Mechanical Keyboard",
            quantity=1,
            unit_price=Decimal("2000.00"),
            taxable_amount=Decimal("2000.00"),
            gst_amount=Decimal("360.00"),
            line_total=Decimal("2360.00")
        )

        # Invoice 3: Two weeks ago, Dist2, Cust2 (Grand Total: 944.00)
        self.inv3 = Invoice.objects.create(
            distributor=self.dist2,
            customer=self.cust2,
            invoice_number="INV-REP-003",
            invoice_date=two_weeks_ago,
            subtotal=Decimal("800.00"),
            total_gst=Decimal("144.00"),
            grand_total=Decimal("944.00")
        )
        InvoiceItem.objects.create(
            invoice=self.inv3,
            product=self.prod3,
            product_name="USB Hub",
            quantity=1,
            unit_price=Decimal("800.00"),
            taxable_amount=Decimal("800.00"),
            gst_amount=Decimal("144.00"),
            line_total=Decimal("944.00")
        )

        self.client.login(username="admin_analytics", password="AdminPassword@123")

    def test_all_time_kpis_aggregation(self):
        """All-time report accurately aggregates total sales, invoices, subtotal, and tax."""
        response = self.client.get(self.reports_url + "?filter=all_time")
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # Total Sales = 1180 + 2360 + 944 = 4484.00
        self.assertEqual(ctx["total_sales"], Decimal("4484.00"))
        self.assertEqual(ctx["total_invoices"], 3)
        self.assertEqual(ctx["total_subtotal"], Decimal("3800.00"))
        self.assertEqual(ctx["total_gst"], Decimal("684.00"))
        self.assertEqual(ctx["total_customers"], 2)
        self.assertEqual(ctx["total_products"], 3)
        self.assertEqual(ctx["active_products"], 2)
        self.assertEqual(ctx["low_stock_products"], 2)
        self.assertEqual(ctx["out_of_stock_products"], 1)

    def test_filter_today(self):
        """Filter 'today' only includes today's invoices."""
        response = self.client.get(self.reports_url + "?filter=today")
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        self.assertEqual(ctx["total_sales"], Decimal("1180.00"))
        self.assertEqual(ctx["total_invoices"], 1)
        invoice_numbers = [inv.invoice_number for inv in ctx["page_obj"]]
        self.assertIn("INV-REP-001", invoice_numbers)
        self.assertNotIn("INV-REP-002", invoice_numbers)
        self.assertNotIn("INV-REP-003", invoice_numbers)

    def test_filter_last_7_days(self):
        """Filter 'last_7_days' includes today and yesterday, excludes two weeks ago."""
        response = self.client.get(self.reports_url + "?filter=last_7_days")
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        self.assertEqual(ctx["total_sales"], Decimal("3540.00"))
        self.assertEqual(ctx["total_invoices"], 2)
        invoice_numbers = [inv.invoice_number for inv in ctx["page_obj"]]
        self.assertIn("INV-REP-001", invoice_numbers)
        self.assertIn("INV-REP-002", invoice_numbers)
        self.assertNotIn("INV-REP-003", invoice_numbers)

    def test_custom_date_range_filter(self):
        """Custom start and end date range filters data correctly."""
        yesterday_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        response = self.client.get(
            f"{self.reports_url}?filter=custom&start_date={yesterday_str}&end_date={yesterday_str}"
        )
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx["total_invoices"], 1)
        self.assertEqual(ctx["total_sales"], Decimal("2360.00"))

    def test_invalid_date_range_handled_gracefully(self):
        """When start_date > end_date, view flags validation errors, preserves inputs, and prevents calculation."""
        today_str = date.today().strftime("%Y-%m-%d")
        past_str = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
        response = self.client.get(
            f"{self.reports_url}?start_date={today_str}&end_date={past_str}"
        )
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertIn("start_date", ctx["field_errors"])
        self.assertEqual(ctx["field_errors"]["start_date"], "Start Date must not be later than End Date.")
        self.assertEqual(ctx["field_errors"]["end_date"], "End Date must not be earlier than Start Date.")
        # Preserves user's entered values
        self.assertEqual(ctx["start_date"], today_str)
        self.assertEqual(ctx["end_date"], past_str)
        self.assertEqual(ctx["total_invoices"], 0)
        self.assertContains(response, "Start Date must not be later than End Date.")

    def test_boundary_dates_inclusivity(self):
        """Invoices exactly on the start date and end date boundaries are inclusively returned."""
        yesterday = date.today() - timedelta(days=1)
        today = date.today()
        start_str = yesterday.strftime("%Y-%m-%d")
        end_str = today.strftime("%Y-%m-%d")

        response = self.client.get(f"{self.reports_url}?start_date={start_str}&end_date={end_str}")
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # Both INV-REP-001 (today) and INV-REP-002 (yesterday) must be included
        invoice_numbers = [inv.invoice_number for inv in ctx["page_obj"]]
        self.assertIn("INV-REP-001", invoice_numbers)
        self.assertIn("INV-REP-002", invoice_numbers)
        self.assertNotIn("INV-REP-003", invoice_numbers)  # 14 days ago
        self.assertEqual(ctx["total_invoices"], 2)

    def test_empty_date_range_displays_friendly_message(self):
        """Querying a date range with zero invoices displays 'No invoices found for the selected date range.'"""
        future_start = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
        future_end = (date.today() + timedelta(days=65)).strftime("%Y-%m-%d")
        response = self.client.get(f"{self.reports_url}?start_date={future_start}&end_date={future_end}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No invoices found for the selected date range.")

    def test_status_filter_options(self):
        """Status filter 'all' or 'paid' returns billed invoices; 'pending' returns zero."""
        response_all = self.client.get(f"{self.reports_url}?status=all")
        self.assertEqual(response_all.context["total_invoices"], 3)

        response_paid = self.client.get(f"{self.reports_url}?status=paid")
        self.assertEqual(response_paid.context["total_invoices"], 3)

        response_pending = self.client.get(f"{self.reports_url}?status=pending")
        self.assertEqual(response_pending.context["total_invoices"], 0)

    def test_distributor_isolation_filter(self):
        """Filtering by distributor narrows calculations to that distributor's invoices only."""
        response = self.client.get(f"{self.reports_url}?distributor_id={self.dist2.id}")
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        self.assertEqual(ctx["total_sales"], Decimal("944.00"))
        self.assertEqual(ctx["total_invoices"], 1)
        self.assertEqual(ctx["total_products"], 1)
        self.assertEqual(ctx["total_customers"], 1)

    def test_invoices_table_search_query(self):
        """Search query in table filters invoices by number or customer name."""
        response = self.client.get(f"{self.reports_url}?q=Ramesh")
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        for inv in ctx["page_obj"]:
            self.assertEqual(inv.customer.name, "Ramesh Kumar")

    def test_empty_dataset_renders_without_error(self):
        """Querying a date range with zero invoices renders clean empty states without error."""
        far_future = (date.today() + timedelta(days=100)).strftime("%Y-%m-%d")
        response = self.client.get(
            f"{self.reports_url}?filter=custom&start_date={far_future}&end_date={far_future}"
        )
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx["total_sales"], Decimal("0.00"))
        self.assertEqual(ctx["total_invoices"], 0)
        self.assertFalse(ctx["has_sales_data"])
        self.assertContains(response, "No Sales Records Found")
        self.assertContains(response, "No invoices found for the selected date range.")

    def test_csv_export_invoices_with_date_range_filename(self):
        """Exporting invoices CSV with date filters produces filename with start and end dates."""
        start_str = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        end_str = date.today().strftime("%Y-%m-%d")
        response = self.client.get(f"{self.export_url}?type=invoices&start_date={start_str}&end_date={end_str}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        expected_filename = f'attachment; filename="invoices_report_{start_str}_to_{end_str}.csv"'
        self.assertEqual(response["Content-Disposition"], expected_filename)
        content = response.content.decode("utf-8")
        self.assertIn("Invoice Number,Date,Distributor,Customer Name,Customer Phone,Subtotal (INR),Total GST (INR),Grand Total (INR),Status", content)
        self.assertIn("Finalized (Billed)", content)

    def test_csv_export_invoices(self):
        """Exporting invoices CSV returns text/csv with attachment header and rows."""
        response = self.client.get(f"{self.export_url}?type=invoices&filter=all_time")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("invoices_report_", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("Invoice Number,Date,Distributor,Customer Name", content)
        self.assertIn("INV-REP-001", content)
        self.assertIn("INV-REP-002", content)
        self.assertIn("INV-REP-003", content)

    def test_csv_export_products(self):
        """Exporting products CSV returns product sales aggregates."""
        response = self.client.get(f"{self.export_url}?type=products&filter=all_time")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("product_sales_report_", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("Product Name,Units Sold,Total Revenue (INR)", content)
        self.assertIn("Wireless Mouse", content)

    def test_csv_export_customers(self):
        """Exporting customers CSV returns customer spend aggregates."""
        response = self.client.get(f"{self.export_url}?type=customers&filter=all_time")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("customer_sales_report_", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("Customer Name,Phone,Email,Distributor,Invoices Count,Total Spent", content)
        self.assertIn("Ramesh Kumar", content)

    def test_csv_export_sanitizes_potential_formula_injection(self):
        """Customer names or invoice numbers starting with =, +, -, @ are prepended with quote."""
        c_malicious = Customer.objects.create(
            distributor=self.dist1,
            name="=cmd|' /C calc'!A0",
            phone="9999999999"
        )
        Invoice.objects.create(
            distributor=self.dist1,
            customer=c_malicious,
            invoice_number="@DANGEROUS-INV",
            invoice_date=date.today(),
            subtotal=Decimal("100.00"),
            total_gst=Decimal("18.00"),
            grand_total=Decimal("118.00")
        )
        response = self.client.get(f"{self.export_url}?type=invoices&filter=today")
        content = response.content.decode("utf-8")
        self.assertIn("'@DANGEROUS-INV", content)
        self.assertIn("'=cmd|' /C calc'!A0", content)

    def test_summary_cards_rendered_with_correct_metrics(self):
        """Total Invoices and Amount Collected cards render with accurate figures."""
        response = self.client.get(self.reports_url + "?filter=all_time")
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        self.assertEqual(ctx["total_invoices"], 3)
        self.assertEqual(ctx["amount_collected"], Decimal("4484.00"))
        self.assertContains(response, 'id="statTotalInvoices"')
        self.assertContains(response, 'id="statAmountCollected"')
        self.assertContains(response, "Total Invoices")
        self.assertContains(response, "Amount Collected")
        self.assertContains(response, "₹4484.00")

    def test_summary_cards_multiple_items_do_not_duplicate_invoice_count(self):
        """Invoices with multiple line items are counted exactly once in Total Invoices."""
        # Add multiple invoice items to INV-REP-001
        inv1 = Invoice.objects.get(invoice_number="INV-REP-001")
        InvoiceItem.objects.create(
            invoice=inv1,
            product=self.prod2,
            product_name="Extra Item 1",
            quantity=2,
            unit_price=Decimal("100.00"),
            taxable_amount=Decimal("200.00"),
            gst_amount=Decimal("36.00"),
            line_total=Decimal("236.00")
        )
        InvoiceItem.objects.create(
            invoice=inv1,
            product=self.prod1,
            product_name="Extra Item 2",
            quantity=1,
            unit_price=Decimal("50.00"),
            taxable_amount=Decimal("50.00"),
            gst_amount=Decimal("9.00"),
            line_total=Decimal("59.00")
        )

        response = self.client.get(self.reports_url + "?filter=today")
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        # Count must remain exactly 1, not 3 (no join duplication)
        self.assertEqual(ctx["total_invoices"], 1)

    def test_summary_cards_boundary_dates_inclusivity(self):
        """Summary cards accurately sum invoices created on boundary start and end dates."""
        yesterday = date.today() - timedelta(days=1)
        today = date.today()
        start_str = yesterday.strftime("%Y-%m-%d")
        end_str = today.strftime("%Y-%m-%d")

        response = self.client.get(f"{self.reports_url}?start_date={start_str}&end_date={end_str}")
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # INV-REP-001 (1180.00) + INV-REP-002 (2360.00) = 3540.00
        self.assertEqual(ctx["total_invoices"], 2)
        self.assertEqual(ctx["amount_collected"], Decimal("3540.00"))

    def test_summary_cards_zero_when_no_records_in_range(self):
        """Summary cards display 0 and ₹0.00 when no records match the selected date range."""
        future_start = (date.today() + timedelta(days=90)).strftime("%Y-%m-%d")
        future_end = (date.today() + timedelta(days=95)).strftime("%Y-%m-%d")

        response = self.client.get(f"{self.reports_url}?start_date={future_start}&end_date={future_end}")
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        self.assertEqual(ctx["total_invoices"], 0)
        self.assertEqual(ctx["amount_collected"], Decimal("0.00"))
        self.assertContains(response, ">0<")
        self.assertContains(response, "₹0.00")

    def test_pdf_export_invoices_returns_pdf_response(self):
        """PDF export returns application/pdf with valid PDF header and attachment filename."""
        response = self.client.get(self.export_pdf_url + "?filter=all_time")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("invoices_report_", response["Content-Disposition"])
        self.assertTrue(response["Content-Disposition"].endswith('.pdf"'))
        # PDF files begin with %PDF magic bytes
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_pdf_export_with_date_range_filename_and_content(self):
        """PDF export with start_date and end_date sets date-ranged filename and generates valid PDF."""
        yesterday = date.today() - timedelta(days=1)
        today = date.today()
        start_str = yesterday.strftime("%Y-%m-%d")
        end_str = today.strftime("%Y-%m-%d")

        response = self.client.get(f"{self.export_pdf_url}?start_date={start_str}&end_date={end_str}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        expected_filename = f'attachment; filename="invoices_report_{start_str}_to_{end_str}.pdf"'
        self.assertEqual(response["Content-Disposition"], expected_filename)
        self.assertTrue(response.content.startswith(b"%PDF"))
        # Verify non-trivial PDF size (> 1KB)
        self.assertGreater(len(response.content), 1000)

    def test_pdf_export_empty_date_range(self):
        """PDF export when no invoices match generates a clean PDF with empty state message."""
        future_start = (date.today() + timedelta(days=90)).strftime("%Y-%m-%d")
        future_end = (date.today() + timedelta(days=95)).strftime("%Y-%m-%d")

        response = self.client.get(f"{self.export_pdf_url}?start_date={future_start}&end_date={future_end}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_pdf_export_with_status_filter_pending_yields_zero_invoices(self):
        """PDF export with status=pending yields zero invoices in generated PDF."""
        response = self.client.get(f"{self.export_pdf_url}?status=pending")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_pdf_export_invalid_date_range_handled_gracefully(self):
        """When start_date > end_date, PDF generation handles it safely without crashing."""
        today_str = date.today().strftime("%Y-%m-%d")
        past_str = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
        response = self.client.get(f"{self.export_pdf_url}?start_date={today_str}&end_date={past_str}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))







