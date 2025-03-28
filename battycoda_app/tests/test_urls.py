from django.contrib.auth.models import User
from django.urls import resolve, reverse

from battycoda_app import views, views_auth, views_group, views_task
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

    def test_group_urls(self):
        # Group list
        url = reverse("battycoda_app:group_list")
        self.assertEqual(resolve(url).func, views_group.group_list_view)

        # Create group
        url = reverse("battycoda_app:create_group")
        self.assertEqual(resolve(url).func, views_group.create_group_view)

        # Group detail with ID parameter
        url = reverse("battycoda_app:group_detail", args=[1])
        self.assertEqual(resolve(url).func, views_group.group_detail_view)

        # Edit group with ID parameter
        url = reverse("battycoda_app:edit_group", args=[1])
        self.assertEqual(resolve(url).func, views_group.edit_group_view)

        # Manage group members with ID parameter
        url = reverse("battycoda_app:manage_group_members", args=[1])
        self.assertEqual(resolve(url).func, views_group.manage_group_members_view)

        # Switch group with ID parameter
        url = reverse("battycoda_app:switch_group", args=[1])
        self.assertEqual(resolve(url).func, views_group.switch_group_view)

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
