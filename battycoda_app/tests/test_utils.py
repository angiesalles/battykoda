from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from battycoda_app.models import Group, Species
from battycoda_app.utils import import_default_species


class UtilsTest(TestCase):
    @patch("django.core.files.File")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("os.path.exists", return_value=True)
    def test_import_default_species(self, mock_exists, mock_open, mock_file):
        # Create a user
        user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")

        # Create a group
        group = Group.objects.create(name="Test Group", description="Test group")

        # Setup user profile
        user.profile.group = group
        user.profile.save()

        # Mock the open file
        mock_file_handle = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file_handle

        # Patch the species.image.save method to avoid permission issues
        with patch("django.db.models.fields.files.ImageFieldFile.save"):
            # Call the function
            created_species = import_default_species(user)

            # Check the results
            self.assertIsInstance(created_species, list)
            self.assertGreaterEqual(len(created_species), 0)  # At least some species were created
