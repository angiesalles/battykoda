from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone

from battycoda_app.models import (
    Call,
    Group,
    GroupInvitation,
    GroupMembership,
    Project,
    Species,
    Task,
    TaskBatch,
    UserProfile,
)
from battycoda_app.tests.test_base import BattycodaTestCase


class GroupModelTest(BattycodaTestCase):
    def setUp(self):
        self.group = Group.objects.create(name="Test Group", description="A test group")

    def test_group_str_method(self):
        self.assertEqual(str(self.group), "Test Group")


class UserProfileModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")
        # User profile is created by signal
        self.profile = UserProfile.objects.get(user=self.user)

        # Create additional group
        self.group2 = Group.objects.create(name="Second Group", description="Second group for testing")
        GroupMembership.objects.create(user=self.user, group=self.group2, is_admin=False)

    def test_profile_str_method(self):
        self.assertEqual(str(self.profile), "testuser")

    def test_available_groups(self):
        # User should have access to their personal group and the second group
        self.assertEqual(len(self.profile.available_groups), 2)
        # Personal group should be first
        self.assertEqual(self.profile.available_groups[0], self.profile.group)
        self.assertTrue(self.group2 in self.profile.available_groups)

    def test_user_profile_creation_signal(self):
        # Test that UserProfile is created for new user
        new_user = User.objects.create_user(username="newuser", email="new@example.com", password="password123")

        # Verify profile was created
        self.assertTrue(UserProfile.objects.filter(user=new_user).exists())

        # Verify personal group was created
        user_profile = UserProfile.objects.get(user=new_user)
        self.assertIsNotNone(user_profile.group)
        self.assertEqual(user_profile.group.name, "newuser's Group")

        # Verify user is admin of personal group
        self.assertTrue(user_profile.is_admin)

        # Verify group membership was created
        self.assertTrue(GroupMembership.objects.filter(user=new_user, group=user_profile.group).exists())

        # Verify demo project was created
        self.assertTrue(Project.objects.filter(created_by=new_user).exists())


class GroupInvitationModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")
        self.group = Group.objects.create(name="Test Group", description="Test group")

        # Create an invitation
        self.invitation = GroupInvitation.objects.create(
            group=self.group,
            email="invited@example.com",
            invited_by=self.user,
            token="testtoken123",
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Create an expired invitation
        self.expired_invitation = GroupInvitation.objects.create(
            group=self.group,
            email="expired@example.com",
            invited_by=self.user,
            token="expiredtoken",
            expires_at=timezone.now() - timedelta(days=1),
        )

    def test_invitation_str_method(self):
        self.assertEqual(str(self.invitation), f"Invitation to {self.group.name} for invited@example.com")

    def test_is_expired_property(self):
        self.assertFalse(self.invitation.is_expired)
        self.assertTrue(self.expired_invitation.is_expired)


class SpeciesModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")
        self.group = Group.objects.create(name="Test Group", description="Test group")

        self.species = Species.objects.create(
            name="Test Species", description="A test species", created_by=self.user, group=self.group
        )

    def test_species_str_method(self):
        self.assertEqual(str(self.species), "Test Species")

    def test_species_meta_options(self):
        self.assertEqual(Species._meta.verbose_name_plural, "Species")
        self.assertEqual(Species._meta.ordering, ["name"])
        
    def test_species_unique_together_constraint(self):
        """Test that species names must be unique within a group but can be duplicated across groups"""
        # Create a second group
        group2 = Group.objects.create(name="Second Group", description="Another test group")
        
        # Create a species with the same name in a different group (should work)
        species2 = Species.objects.create(
            name="Test Species", description="Same name, different group", created_by=self.user, group=group2
        )
        self.assertEqual(species2.name, self.species.name)
        
        # Try to create a species with the same name in the same group (should fail)
        with self.assertRaises(IntegrityError):
            Species.objects.create(
                name="Test Species", description="Duplicate in same group", created_by=self.user, group=self.group
            )


class CallModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")
        self.group = Group.objects.create(name="Test Group", description="Test group")

        self.species = Species.objects.create(
            name="Test Species", description="A test species", created_by=self.user, group=self.group
        )

        self.call = Call.objects.create(species=self.species, short_name="TC", long_name="Test Call")

    def test_call_str_method(self):
        self.assertEqual(str(self.call), "Test Species - TC")

    def test_call_meta_options(self):
        self.assertEqual(Call._meta.ordering, ["short_name"])


class ProjectModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")
        self.group = Group.objects.create(name="Test Group", description="Test group")

        self.project = Project.objects.create(
            name="Test Project", description="A test project", created_by=self.user, group=self.group
        )

    def test_project_str_method(self):
        self.assertEqual(str(self.project), "Test Project")


class TaskBatchModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")
        self.group = Group.objects.create(name="Test Group", description="Test group")

        self.species = Species.objects.create(
            name="Test Species", description="A test species", created_by=self.user, group=self.group
        )

        self.project = Project.objects.create(
            name="Test Project", description="A test project", created_by=self.user, group=self.group
        )

        self.batch = TaskBatch.objects.create(
            name="Test Batch",
            description="A test batch",
            created_by=self.user,
            wav_file_name="test.wav",
            species=self.species,
            project=self.project,
            group=self.group,
        )

    def test_batch_str_method(self):
        self.assertEqual(str(self.batch), "Test Batch")


class TaskModelTest(BattycodaTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")
        self.group = Group.objects.create(name="Test Group", description="Test group")

        self.species = Species.objects.create(
            name="Test Species", description="A test species", created_by=self.user, group=self.group
        )

        self.project = Project.objects.create(
            name="Test Project", description="A test project", created_by=self.user, group=self.group
        )

        self.batch = TaskBatch.objects.create(
            name="Test Batch",
            description="A test batch",
            created_by=self.user,
            wav_file_name="test.wav",
            species=self.species,
            project=self.project,
            group=self.group,
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
            group=self.group,
            status="pending",
        )

    def test_task_str_method(self):
        self.assertEqual(str(self.task), "test.wav (1.00s - 2.00s)")

    def test_task_status_done_sets_is_done(self):
        self.task.status = "done"
        self.task.save()
        self.assertTrue(self.task.is_done)

    def test_is_done_sets_status_done(self):
        self.task.is_done = True
        self.task.save()
        self.assertEqual(self.task.status, "done")
