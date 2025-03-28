from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from battycoda_app.models import Group, GroupInvitation, GroupMembership, UserProfile
from battycoda_app.tests.test_base import BattycodaTestCase


class AuthViewsTest(BattycodaTestCase):
    def setUp(self):
        self.client = Client()

        # Create a test user
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")

        # Create a second user for testing group functionality
        self.user2 = User.objects.create_user(username="testuser2", email="test2@example.com", password="password123")

        # Create a group for testing invitations
        self.group = Group.objects.create(name="Test Group", description="A test group for invitations")

        # Create a group invitation
        self.invitation = GroupInvitation.objects.create(
            group=self.group,
            email="new@example.com",
            invited_by=self.user,
            token="testtoken123",
            expires_at=timezone.now() + timedelta(days=7),
        )

        # URL paths
        self.login_url = reverse("battycoda_app:login")
        self.register_url = reverse("battycoda_app:register")
        self.logout_url = reverse("battycoda_app:logout")
        self.profile_url = reverse("battycoda_app:profile")

    def test_login_view_get(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/login.html")

    def test_login_view_post_success(self):
        response = self.client.post(self.login_url, {"username": "testuser", "password": "password123"})
        self.assertEqual(response.status_code, 302)  # Redirects to index
        # We only check the redirect status code and not follow the redirect
        self.assertTrue(response.url.startswith(reverse("battycoda_app:index")))

    def test_login_view_post_failure(self):
        response = self.client.post(self.login_url, {"username": "testuser", "password": "wrongpassword"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/login.html")
        # Since the exact error message might change, we'll check for a more generic
        # indicator that the login failed instead
        self.assertFalse(response.context["form"].is_valid())

    def test_register_view_get(self):
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/register.html")

    def test_register_view_post_success(self):
        response = self.client.post(
            self.register_url,
            {
                "username": "newuser",
                "email": "new@example.com",
                "password1": "Password123!",
                "password2": "Password123!",
            },
        )

        self.assertEqual(response.status_code, 302)  # Redirects to login
        self.assertRedirects(response, self.login_url)

        # Check that the user was created
        self.assertTrue(User.objects.filter(username="newuser").exists())

        # Check that profile and personal group were created
        user = User.objects.get(username="newuser")
        profile = UserProfile.objects.get(user=user)
        self.assertIsNotNone(profile)
        self.assertIsNotNone(profile.group)

        # Test that a group membership was created
        self.assertTrue(GroupMembership.objects.filter(user=user, group=profile.group).exists())

    def test_register_with_invitation(self):
        # Set up session
        session = self.client.session
        session["invitation_token"] = "testtoken123"
        session.save()

        response = self.client.post(
            self.register_url,
            {
                "username": "inviteduser",
                "email": "new@example.com",  # Must match invitation email
                "password1": "Password123!",
                "password2": "Password123!",
            },
        )

        self.assertEqual(response.status_code, 302)  # Redirects to login

        # Check that the user was created
        user = User.objects.get(username="inviteduser")

        # Check that the user was added to the invited group
        self.assertTrue(GroupMembership.objects.filter(user=user, group=self.group).exists())

        # Check that the invitation was marked as accepted
        invitation = GroupInvitation.objects.get(token="testtoken123")
        self.assertTrue(invitation.accepted)

    def test_logout_view(self):
        # Login first
        self.client.login(username="testuser", password="password123")

        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 302)  # Redirects to login
        self.assertRedirects(response, self.login_url)

    def test_profile_view_authenticated(self):
        # Login first
        self.client.login(username="testuser", password="password123")

        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/profile.html")

    def test_profile_view_unauthenticated(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 302)  # Redirects to login
        # Check that the redirect includes the next parameter
        self.assertTrue(response.url.startswith(self.login_url))
