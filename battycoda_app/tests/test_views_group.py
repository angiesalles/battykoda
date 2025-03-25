from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from battycoda_app.models import Project, Species, Group, GroupMembership, UserProfile
from battycoda_app.tests.test_base import BattycodaTestCase


class GroupViewsTest(BattycodaTestCase):
    def setUp(self):
        self.client = Client()

        # Create test users
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")
        self.profile = UserProfile.objects.get(user=self.user)

        self.user2 = User.objects.create_user(username="testuser2", email="test2@example.com", password="password123")
        self.profile2 = UserProfile.objects.get(user=self.user2)

        # Create a test group
        self.group = Group.objects.create(name="Test Group", description="A test group")

        # Add user1 to the group as admin
        self.membership = GroupMembership.objects.create(user=self.user, group=self.group, is_admin=True)

        # Set as active group for user1
        self.profile.group = self.group
        self.profile.is_admin = True
        self.profile.save()

        # URL paths
        self.group_list_url = reverse("battycoda_app:group_list")
        self.group_detail_url = reverse("battycoda_app:group_detail", args=[self.group.id])
        self.create_group_url = reverse("battycoda_app:create_group")
        self.edit_group_url = reverse("battycoda_app:edit_group", args=[self.group.id])
        self.manage_members_url = reverse("battycoda_app:manage_group_members", args=[self.group.id])
        self.switch_group_url = reverse("battycoda_app:switch_group", args=[self.group.id])

    def test_group_list_view_authenticated(self):
        # Login first
        self.client.login(username="testuser", password="password123")

        response = self.client.get(self.group_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "groups/group_list.html")
        # Instead of checking the response content which might be mocked
        # check that our group is in the context
        self.assertTrue(any(group.name == "Test Group" for group in response.context["groups"]))

    def test_group_list_view_unauthenticated(self):
        response = self.client.get(self.group_list_url)
        self.assertEqual(response.status_code, 302)  # Redirects to login

    def test_group_detail_view_member(self):
        # Login as group member
        self.client.login(username="testuser", password="password123")

        response = self.client.get(self.group_detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "groups/group_detail.html")
        # Check that the group is in the context rather than checking response content
        self.assertEqual(response.context["group"].name, "Test Group")

    def test_group_detail_view_non_member(self):
        # Login as non-group member
        self.client.login(username="testuser2", password="password123")

        response = self.client.get(self.group_detail_url)
        self.assertEqual(response.status_code, 302)  # Redirects to group list
        self.assertRedirects(response, self.group_list_url)

    def test_create_group_view_authenticated(self):
        # Login first
        self.client.login(username="testuser", password="password123")

        response = self.client.get(self.create_group_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "groups/create_group.html")

    def test_create_group_post(self):
        # Login first
        self.client.login(username="testuser", password="password123")

        group_data = {"name": "New Group", "description": "A new group created in tests"}

        response = self.client.post(self.create_group_url, group_data)
        self.assertEqual(response.status_code, 302)  # Redirects to group detail

        # Check that the group was created
        self.assertTrue(Group.objects.filter(name="New Group").exists())
        new_group = Group.objects.get(name="New Group")

        # Check that the user was added as member and admin
        self.assertTrue(GroupMembership.objects.filter(user=self.user, group=new_group).exists())
        membership = GroupMembership.objects.get(user=self.user, group=new_group)
        self.assertTrue(membership.is_admin)

        # Check that the group was set as active group for the user
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.group, new_group)
        self.assertTrue(self.user.profile.is_admin)

    def test_edit_group_view_admin(self):
        # Login as group admin
        self.client.login(username="testuser", password="password123")

        response = self.client.get(self.edit_group_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "groups/edit_group.html")

    def test_edit_group_post(self):
        # Login as group admin
        self.client.login(username="testuser", password="password123")

        group_data = {"name": "Updated Group Name", "description": "Updated description"}

        response = self.client.post(self.edit_group_url, group_data)
        self.assertEqual(response.status_code, 302)  # Redirects to group detail

        # Check that the group was updated
        self.group.refresh_from_db()
        self.assertEqual(self.group.name, "Updated Group Name")
        self.assertEqual(self.group.description, "Updated description")

    def test_manage_group_members_view_admin(self):
        # Login as group admin
        self.client.login(username="testuser", password="password123")

        response = self.client.get(self.manage_members_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "groups/manage_members.html")

    def test_manage_group_members_add_user(self):
        # Login as group admin
        self.client.login(username="testuser", password="password123")

        post_data = {"add_user": True, "user_id": self.user2.id}

        response = self.client.post(self.manage_members_url, post_data)
        self.assertEqual(response.status_code, 302)  # Redirects to manage members

        # Check that user2 was added to the group
        self.assertTrue(GroupMembership.objects.filter(user=self.user2, group=self.group).exists())

    def test_manage_group_members_toggle_admin(self):
        # First add user2 to the group
        GroupMembership.objects.create(user=self.user2, group=self.group, is_admin=False)

        # Login as group admin
        self.client.login(username="testuser", password="password123")

        post_data = {"toggle_admin": True, "user_id": self.user2.id}

        response = self.client.post(self.manage_members_url, post_data)
        self.assertEqual(response.status_code, 302)  # Redirects to manage members

        # Check that user2 was made admin
        membership = GroupMembership.objects.get(user=self.user2, group=self.group)
        self.assertTrue(membership.is_admin)

    def test_switch_group(self):
        # Create a second group
        group2 = Group.objects.create(name="Second Group", description="Another test group")

        # Add user1 to the second group
        GroupMembership.objects.create(user=self.user, group=group2, is_admin=False)

        # Login as user1
        self.client.login(username="testuser", password="password123")

        # Switch to group2
        response = self.client.get(reverse("battycoda_app:switch_group", args=[group2.id]))
        self.assertEqual(response.status_code, 302)  # Redirects

        # Check that the user's active group was updated
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.group, group2)
        self.assertFalse(self.user.profile.is_admin)