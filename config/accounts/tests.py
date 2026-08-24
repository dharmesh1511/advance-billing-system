from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from accounts.models import DistributorProfile


class DistributorProfileUpdateTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.distributor_group, _ = Group.objects.get_or_create(name="Distributor")

        # Create primary test distributor
        self.user = User.objects.create_user(
            username="distributor@example.com",
            email="distributor@example.com",
            password="Password123!",
            first_name="John",
            last_name="Patel"
        )
        self.user.groups.add(self.distributor_group)

        self.profile = DistributorProfile.objects.create(
            user=self.user,
            full_name="John Patel",
            email="distributor@example.com",
            phone="9876543210"
        )

        # Create secondary distributor to test duplicate email protection
        self.other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="Password123!",
            first_name="Other",
            last_name="User"
        )
        self.other_user.groups.add(self.distributor_group)

        self.other_profile = DistributorProfile.objects.create(
            user=self.other_user,
            full_name="Other User",
            email="other@example.com",
            phone="9123456789"
        )

        self.profile_url = reverse("distributor_profile")
        self.edit_profile_url = reverse("edit_distributor_profile")

    def test_unauthenticated_redirect(self):
        """Unauthenticated user should be redirected to distributor login page."""
        response = self.client.get(self.edit_profile_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("distributor_login"), response.url)

        post_response = self.client.post(self.edit_profile_url, {
            "full_name": "New Name",
            "email": "new@example.com",
            "phone": "9876543210"
        })
        self.assertEqual(post_response.status_code, 302)
        self.assertIn(reverse("distributor_login"), post_response.url)

    def test_authenticated_get_prefilled_form(self):
        """Authenticated distributor should see pre-filled edit form."""
        self.client.login(username="distributor@example.com", password="Password123!")
        response = self.client.get(self.edit_profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/edit_distributor_profile.html")
        self.assertContains(response, "John Patel")
        self.assertContains(response, "distributor@example.com")
        self.assertContains(response, "9876543210")

    def test_successful_profile_update(self):
        """Submitting valid profile data should update DB, add message, and redirect."""
        self.client.login(username="distributor@example.com", password="Password123!")
        response = self.client.post(self.edit_profile_url, {
            "full_name": "John Sharma",
            "email": "johnsharma@example.com",
            "phone": "9876543211"
        }, follow=True)

        self.assertRedirects(response, self.profile_url)
        self.assertContains(response, "Profile updated successfully.")

        # Reload records from DB
        self.profile.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(self.profile.full_name, "John Sharma")
        self.assertEqual(self.profile.email, "johnsharma@example.com")
        self.assertEqual(self.profile.phone, "9876543211")

        self.assertEqual(self.user.first_name, "John")
        self.assertEqual(self.user.last_name, "Sharma")
        self.assertEqual(self.user.email, "johnsharma@example.com")
        self.assertEqual(self.user.username, "johnsharma@example.com")

    def test_name_validation(self):
        """Empty, too short, or whitespace-only name should be rejected."""
        self.client.login(username="distributor@example.com", password="Password123!")

        # Invalid cases
        invalid_names = ["", "   ", "A"]
        for bad_name in invalid_names:
            response = self.client.post(self.edit_profile_url, {
                "full_name": bad_name,
                "email": "distributor@example.com",
                "phone": "9876543210"
            })
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Please enter a valid name.")

    def test_email_validation(self):
        """Invalid email formats should be rejected."""
        self.client.login(username="distributor@example.com", password="Password123!")
        invalid_emails = ["john", "john@", "@gmail.com"]

        for bad_email in invalid_emails:
            response = self.client.post(self.edit_profile_url, {
                "full_name": "John Patel",
                "email": bad_email,
                "phone": "9876543210"
            })
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Please enter a valid email address.")

    def test_duplicate_email_protection(self):
        """Using another registered user's email should be rejected."""
        self.client.login(username="distributor@example.com", password="Password123!")
        response = self.client.post(self.edit_profile_url, {
            "full_name": "John Patel",
            "email": "other@example.com",
            "phone": "9876543210"
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This email address is already registered.")

    def test_same_email_update_allowed(self):
        """User can save without changing their email."""
        self.client.login(username="distributor@example.com", password="Password123!")
        response = self.client.post(self.edit_profile_url, {
            "full_name": "John Updated",
            "email": "distributor@example.com",
            "phone": "9876543210"
        }, follow=True)
        self.assertRedirects(response, self.profile_url)
        self.assertContains(response, "Profile updated successfully.")

    def test_phone_validation(self):
        """Invalid phone numbers should be rejected."""
        self.client.login(username="distributor@example.com", password="Password123!")
        invalid_phones = ["1234567890", "98765", "98765432101", "abcdefghij"]

        for bad_phone in invalid_phones:
            response = self.client.post(self.edit_profile_url, {
                "full_name": "John Patel",
                "email": "distributor@example.com",
                "phone": bad_phone
            })
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Please enter a valid phone number.")

    def test_password_remains_unchanged(self):
        """Updating profile must not alter user password or auth mechanism."""
        self.client.login(username="distributor@example.com", password="Password123!")
        self.client.post(self.edit_profile_url, {
            "full_name": "John Changed",
            "email": "distributor@example.com",
            "phone": "9876543210"
        })
        self.client.logout()

        # Login with original password must succeed
        login_success = self.client.login(username="distributor@example.com", password="Password123!")
        self.assertTrue(login_success)
