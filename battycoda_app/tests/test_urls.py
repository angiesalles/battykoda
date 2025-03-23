from django.contrib.auth.models import User
from django.urls import resolve, reverse

from battycoda_app import views, views_auth, views_task, views_team
from battycoda_app.tests.test_base import BattycodaTestCase


class UrlsTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")

    def test_index_url(self):
        url = reverse("battycoda_app:index")
        self.assertEqual(resolve(url).func, views.index)

    def test_auth_urls(self):
        # Login
        url = reverse("battycoda_app:login")
        self.assertEqual(resolve(url).func, views_auth.login_view)

        # Register
        url = reverse("battycoda_app:register")
        self.assertEqual(resolve(url).func, views_auth.register_view)

        # Logout
        url = reverse("battycoda_app:logout")
        self.assertEqual(resolve(url).func, views_auth.logout_view)

        # Profile
        url = reverse("battycoda_app:profile")
        self.assertEqual(resolve(url).func, views_auth.profile_view)

    def test_team_urls(self):
        # Team list
        url = reverse("battycoda_app:team_list")
        self.assertEqual(resolve(url).func, views_team.team_list_view)

        # Create team
        url = reverse("battycoda_app:create_team")
        self.assertEqual(resolve(url).func, views_team.create_team_view)

        # Team detail with ID parameter
        url = reverse("battycoda_app:team_detail", args=[1])
        self.assertEqual(resolve(url).func, views_team.team_detail_view)

        # Edit team with ID parameter
        url = reverse("battycoda_app:edit_team", args=[1])
        self.assertEqual(resolve(url).func, views_team.edit_team_view)

        # Manage team members with ID parameter
        url = reverse("battycoda_app:manage_team_members", args=[1])
        self.assertEqual(resolve(url).func, views_team.manage_team_members_view)

        # Switch team with ID parameter
        url = reverse("battycoda_app:switch_team", args=[1])
        self.assertEqual(resolve(url).func, views_team.switch_team_view)

    def test_task_urls(self):
        # Task list
        url = reverse("battycoda_app:task_list")
        self.assertEqual(resolve(url).func, views_task.task_list_view)

        # Task detail with ID parameter
        url = reverse("battycoda_app:task_detail", args=[1])
        self.assertEqual(resolve(url).func, views_task.task_detail_view)

        # Task batch list
        url = reverse("battycoda_app:task_batch_list")
        self.assertEqual(resolve(url).func, views_task.task_batch_list_view)

        # Task batch detail with ID parameter
        url = reverse("battycoda_app:task_batch_detail", args=[1])
        self.assertEqual(resolve(url).func, views_task.task_batch_detail_view)

        # Create task batch
        url = reverse("battycoda_app:create_task_batch")
        self.assertEqual(resolve(url).func, views_task.create_task_batch_view)

        # Task annotation with ID parameter
        url = reverse("battycoda_app:annotate_task", args=[1])
        self.assertEqual(resolve(url).func, views_task.task_annotation_view)
