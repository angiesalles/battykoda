from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from battycoda_app.models import (
    Team, TeamInvitation, TeamMembership, UserProfile, Species, Call, Project, TaskBatch, Task
)
from battycoda_app.tests.test_base import BattycodaTestCase


class TeamModelTest(BattycodaTestCase):
    def setUp(self):
        self.team = Team.objects.create(
            name="Test Team",
            description="A test team"
        )
    
    def test_team_str_method(self):
        self.assertEqual(str(self.team), "Test Team")


class UserProfileModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        # User profile is created by signal
        self.profile = UserProfile.objects.get(user=self.user)
        
        # Create additional team
        self.team2 = Team.objects.create(name="Second Team", description="Second team for testing")
        TeamMembership.objects.create(user=self.user, team=self.team2, is_admin=False)
    
    def test_profile_str_method(self):
        self.assertEqual(str(self.profile), "testuser")
    
    def test_available_teams(self):
        # User should have access to their personal team and the second team
        self.assertEqual(len(self.profile.available_teams), 2)
        # Personal team should be first
        self.assertEqual(self.profile.available_teams[0], self.profile.team)
        self.assertTrue(self.team2 in self.profile.available_teams)
    
    def test_user_profile_creation_signal(self):
        # Test that UserProfile is created for new user
        new_user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='password123'
        )
        
        # Verify profile was created
        self.assertTrue(UserProfile.objects.filter(user=new_user).exists())
        
        # Verify personal team was created
        user_profile = UserProfile.objects.get(user=new_user)
        self.assertIsNotNone(user_profile.team)
        self.assertEqual(user_profile.team.name, "newuser's Team")
        
        # Verify user is admin of personal team
        self.assertTrue(user_profile.is_admin)
        
        # Verify team membership was created
        self.assertTrue(TeamMembership.objects.filter(user=new_user, team=user_profile.team).exists())
        
        # Verify demo project was created
        self.assertTrue(Project.objects.filter(created_by=new_user).exists())


class TeamInvitationModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.team = Team.objects.create(name="Test Team", description="Test team")
        
        # Create an invitation
        self.invitation = TeamInvitation.objects.create(
            team=self.team,
            email='invited@example.com',
            invited_by=self.user,
            token='testtoken123',
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # Create an expired invitation
        self.expired_invitation = TeamInvitation.objects.create(
            team=self.team,
            email='expired@example.com',
            invited_by=self.user,
            token='expiredtoken',
            expires_at=timezone.now() - timedelta(days=1)
        )
    
    def test_invitation_str_method(self):
        self.assertEqual(str(self.invitation), f"Invitation to {self.team.name} for invited@example.com")
    
    def test_is_expired_property(self):
        self.assertFalse(self.invitation.is_expired)
        self.assertTrue(self.expired_invitation.is_expired)


class SpeciesModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.team = Team.objects.create(name="Test Team", description="Test team")
        
        self.species = Species.objects.create(
            name="Test Species",
            description="A test species",
            created_by=self.user,
            team=self.team
        )
    
    def test_species_str_method(self):
        self.assertEqual(str(self.species), "Test Species")
    
    def test_species_meta_options(self):
        self.assertEqual(Species._meta.verbose_name_plural, "Species")
        self.assertEqual(Species._meta.ordering, ['name'])


class CallModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.team = Team.objects.create(name="Test Team", description="Test team")
        
        self.species = Species.objects.create(
            name="Test Species",
            description="A test species",
            created_by=self.user,
            team=self.team
        )
        
        self.call = Call.objects.create(
            species=self.species,
            short_name="TC",
            long_name="Test Call"
        )
    
    def test_call_str_method(self):
        self.assertEqual(str(self.call), "Test Species - TC")
    
    def test_call_meta_options(self):
        self.assertEqual(Call._meta.ordering, ['short_name'])


class ProjectModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.team = Team.objects.create(name="Test Team", description="Test team")
        
        self.project = Project.objects.create(
            name="Test Project",
            description="A test project",
            created_by=self.user,
            team=self.team
        )
    
    def test_project_str_method(self):
        self.assertEqual(str(self.project), "Test Project")


class TaskBatchModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.team = Team.objects.create(name="Test Team", description="Test team")
        
        self.species = Species.objects.create(
            name="Test Species",
            description="A test species",
            created_by=self.user,
            team=self.team
        )
        
        self.project = Project.objects.create(
            name="Test Project",
            description="A test project",
            created_by=self.user,
            team=self.team
        )
        
        self.batch = TaskBatch.objects.create(
            name="Test Batch",
            description="A test batch",
            created_by=self.user,
            wav_file_name="test.wav",
            species=self.species,
            project=self.project,
            team=self.team
        )
    
    def test_batch_str_method(self):
        self.assertEqual(str(self.batch), "Test Batch")


class TaskModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.team = Team.objects.create(name="Test Team", description="Test team")
        
        self.species = Species.objects.create(
            name="Test Species",
            description="A test species",
            created_by=self.user,
            team=self.team
        )
        
        self.project = Project.objects.create(
            name="Test Project",
            description="A test project",
            created_by=self.user,
            team=self.team
        )
        
        self.batch = TaskBatch.objects.create(
            name="Test Batch",
            description="A test batch",
            created_by=self.user,
            wav_file_name="test.wav",
            species=self.species,
            project=self.project,
            team=self.team
        )
        
        # Create test task
        self.task = Task.objects.create(
            wav_file_name="test.wav",
            onset=1.0,
            offset=2.0,
            species=self.species,
            project=self.project,
            batch=self.batch,
            created_by=self.user,
            team=self.team,
            status='pending'
        )
    
    def test_task_str_method(self):
        self.assertEqual(str(self.task), "test.wav (1.00s - 2.00s)")
    
    def test_task_status_done_sets_is_done(self):
        self.task.status = 'done'
        self.task.save()
        self.assertTrue(self.task.is_done)
    
    def test_is_done_sets_status_done(self):
        self.task.is_done = True
        self.task.save()
        self.assertEqual(self.task.status, 'done')