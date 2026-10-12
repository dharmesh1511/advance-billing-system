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



