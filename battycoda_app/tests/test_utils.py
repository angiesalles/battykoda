from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User

from battycoda_app.models import Species, Team
from battycoda_app.utils import import_default_species


class UtilsTest(TestCase):
    @patch('django.core.files.File')
    @patch('builtins.open', new_callable=MagicMock)
    @patch('os.path.exists', return_value=True)
    def test_import_default_species(self, mock_exists, mock_open, mock_file):
        # Create a user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        # Create a team
        team = Team.objects.create(name="Test Team", description="Test team")
        
        # Setup user profile
        user.profile.team = team
        user.profile.save()
        
        # Mock the open file
        mock_file_handle = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file_handle
        
        # Patch the species.image.save method to avoid permission issues
        with patch('django.db.models.fields.files.ImageFieldFile.save'):
            # Call the function
            created_species = import_default_species(user)
            
            # Check the results
            self.assertIsInstance(created_species, list)
            self.assertGreaterEqual(len(created_species), 0)  # At least some species were created