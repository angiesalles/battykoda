from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from battycoda_app.models import Project, Species, Team, TeamMembership, UserProfile
from battycoda_app.tests.test_base import BattycodaTestCase


class TeamViewsTest(BattycodaTestCase):
    def setUp(self):
        self.client = Client()

        # Create test users
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")
        self.profile = UserProfile.objects.get(user=self.user)

        self.user2 = User.objects.create_user(username="testuser2", email="test2@example.com", password="password123")
        self.profile2 = UserProfile.objects.get(user=self.user2)

        # Create a test team
        self.team = Team.objects.create(name="Test Team", description="A test team")

        # Add user1 to the team as admin
        self.membership = TeamMembership.objects.create(user=self.user, team=self.team, is_admin=True)

        # Set as active team for user1
        self.profile.team = self.team
        self.profile.is_admin = True
        self.profile.save()

        # URL paths
        self.team_list_url = reverse("battycoda_app:team_list")
        self.team_detail_url = reverse("battycoda_app:team_detail", args=[self.team.id])
        self.create_team_url = reverse("battycoda_app:create_team")
        self.edit_team_url = reverse("battycoda_app:edit_team", args=[self.team.id])
        self.manage_members_url = reverse("battycoda_app:manage_team_members", args=[self.team.id])
        self.switch_team_url = reverse("battycoda_app:switch_team", args=[self.team.id])

    def test_team_list_view_authenticated(self):
        # Login first
        self.client.login(username="testuser", password="password123")

        response = self.client.get(self.team_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "teams/team_list.html")
        # Instead of checking the response content which might be mocked
        # check that our team is in the context
        self.assertTrue(any(team.name == "Test Team" for team in response.context["teams"]))

    def test_team_list_view_unauthenticated(self):
        response = self.client.get(self.team_list_url)
        self.assertEqual(response.status_code, 302)  # Redirects to login

    def test_team_detail_view_member(self):
        # Login as team member
        self.client.login(username="testuser", password="password123")

        response = self.client.get(self.team_detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "teams/team_detail.html")
        # Check that the team is in the context rather than checking response content
        self.assertEqual(response.context["team"].name, "Test Team")

    def test_team_detail_view_non_member(self):
        # Login as non-team member
        self.client.login(username="testuser2", password="password123")

        response = self.client.get(self.team_detail_url)
        self.assertEqual(response.status_code, 302)  # Redirects to team list
        self.assertRedirects(response, self.team_list_url)

    def test_create_team_view_authenticated(self):
        # Login first
        self.client.login(username="testuser", password="password123")

        response = self.client.get(self.create_team_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "teams/create_team.html")

    def test_create_team_post(self):
        # Login first
        self.client.login(username="testuser", password="password123")

        team_data = {"name": "New Team", "description": "A new team created in tests"}

        response = self.client.post(self.create_team_url, team_data)
        self.assertEqual(response.status_code, 302)  # Redirects to team detail

        # Check that the team was created
        self.assertTrue(Team.objects.filter(name="New Team").exists())
        new_team = Team.objects.get(name="New Team")

        # Check that the user was added as member and admin
        self.assertTrue(TeamMembership.objects.filter(user=self.user, team=new_team).exists())
        membership = TeamMembership.objects.get(user=self.user, team=new_team)
        self.assertTrue(membership.is_admin)

        # Check that the team was set as active team for the user
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.team, new_team)
        self.assertTrue(self.user.profile.is_admin)

    def test_edit_team_view_admin(self):
        # Login as team admin
        self.client.login(username="testuser", password="password123")

        response = self.client.get(self.edit_team_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "teams/edit_team.html")

    def test_edit_team_post(self):
        # Login as team admin
        self.client.login(username="testuser", password="password123")

        team_data = {"name": "Updated Team Name", "description": "Updated description"}

        response = self.client.post(self.edit_team_url, team_data)
        self.assertEqual(response.status_code, 302)  # Redirects to team detail

        # Check that the team was updated
        self.team.refresh_from_db()
        self.assertEqual(self.team.name, "Updated Team Name")
        self.assertEqual(self.team.description, "Updated description")

    def test_manage_team_members_view_admin(self):
        # Login as team admin
        self.client.login(username="testuser", password="password123")

        response = self.client.get(self.manage_members_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "teams/manage_members.html")

    def test_manage_team_members_add_user(self):
        # Login as team admin
        self.client.login(username="testuser", password="password123")

        post_data = {"add_user": True, "user_id": self.user2.id}

        response = self.client.post(self.manage_members_url, post_data)
        self.assertEqual(response.status_code, 302)  # Redirects to manage members

        # Check that user2 was added to the team
        self.assertTrue(TeamMembership.objects.filter(user=self.user2, team=self.team).exists())

    def test_manage_team_members_toggle_admin(self):
        # First add user2 to the team
        TeamMembership.objects.create(user=self.user2, team=self.team, is_admin=False)

        # Login as team admin
        self.client.login(username="testuser", password="password123")

        post_data = {"toggle_admin": True, "user_id": self.user2.id}

        response = self.client.post(self.manage_members_url, post_data)
        self.assertEqual(response.status_code, 302)  # Redirects to manage members

        # Check that user2 was made admin
        membership = TeamMembership.objects.get(user=self.user2, team=self.team)
        self.assertTrue(membership.is_admin)

    def test_switch_team(self):
        # Create a second team
        team2 = Team.objects.create(name="Second Team", description="Another test team")

        # Add user1 to the second team
        TeamMembership.objects.create(user=self.user, team=team2, is_admin=False)

        # Login as user1
        self.client.login(username="testuser", password="password123")

        # Switch to team2
        response = self.client.get(reverse("battycoda_app:switch_team", args=[team2.id]))
        self.assertEqual(response.status_code, 302)  # Redirects

        # Check that the user's active team was updated
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.team, team2)
        self.assertFalse(self.user.profile.is_admin)
