from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from battycoda_app.models import Team, UserProfile, Species, Project, TaskBatch, Task
from battycoda_app.tests.test_base import BattycodaTestCase


class TaskViewsTest(BattycodaTestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.profile = UserProfile.objects.get(user=self.user)
        
        # Create another test user
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='password123'
        )
        self.profile2 = UserProfile.objects.get(user=self.user2)
    
        # Create a test team
        self.team = Team.objects.create(
            name="Test Team",
            description="A test team"
        )
        
        # Set as active team for user1
        self.profile.team = self.team
        self.profile.is_admin = True
        self.profile.save()
        
        # Create test species
        self.species = Species.objects.create(
            name="Test Species",
            description="A test species",
            created_by=self.user,
            team=self.team
        )
        
        # Create test project
        self.project = Project.objects.create(
            name="Test Project",
            description="A test project",
            created_by=self.user,
            team=self.team
        )
        
        # Create test batch
        self.batch = TaskBatch.objects.create(
            name="Test Batch",
            description="A test batch",
            created_by=self.user,
            wav_file_name="test.wav",
            species=self.species,
            project=self.project,
            team=self.team
        )
        
        # Create test tasks
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
        
        self.task2 = Task.objects.create(
            wav_file_name="test.wav",
            onset=3.0,
            offset=4.0,
            species=self.species,
            project=self.project,
            batch=self.batch,
            created_by=self.user,
            team=self.team,
            status='in_progress'
        )
    
        # URL paths
        self.task_list_url = reverse('battycoda_app:task_list')
        self.task_detail_url = reverse('battycoda_app:task_detail', args=[self.task.id])
        # Note: Individual task creation was removed - tasks are now created through batches
        self.create_batch_url = reverse('battycoda_app:create_task_batch')
        self.batch_list_url = reverse('battycoda_app:task_batch_list')
        self.batch_detail_url = reverse('battycoda_app:task_batch_detail', args=[self.batch.id])
    
    def test_task_list_view_authenticated(self):
        # Login
        self.client.login(username='testuser', password='password123')
        
        response = self.client.get(self.task_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/task_list.html')
        
        # Admin should see both tasks
        self.assertEqual(len(response.context['tasks']), 2)
    
    def test_task_list_view_non_admin(self):
        # Make user not an admin
        self.profile.is_admin = False
        self.profile.save()
        
        # Create a task for user2
        Task.objects.create(
            wav_file_name="user2.wav",
            onset=5.0,
            offset=6.0,
            species=self.species,
            project=self.project,
            created_by=self.user2,
            team=self.team,
            status='pending'
        )
    
        # Login as non-admin
        self.client.login(username='testuser', password='password123')
        
        response = self.client.get(self.task_list_url)
        self.assertEqual(response.status_code, 200)
        
        # Non-admin should only see their own tasks
        self.assertEqual(len(response.context['tasks']), 2)
    
    def test_task_detail_view_own_task(self):
        # Login
        self.client.login(username='testuser', password='password123')
        
        response = self.client.get(self.task_detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/task_detail.html')
        
        # Check context
        self.assertEqual(response.context['task'], self.task)
        self.assertTrue(response.context['can_edit'])
    
    def test_task_detail_view_update(self):
        # Login
        self.client.login(username='testuser', password='password123')
        
        # Update task
        update_data = {
            'status': 'completed',
            'is_done': True,
            'label': 'Test Label',
            'notes': 'Test notes'
        }
        
        response = self.client.post(self.task_detail_url, update_data)
        self.assertEqual(response.status_code, 302)  # Redirects to task detail
        self.assertRedirects(response, self.task_detail_url)
        
        # Check that task was updated
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'done')  # should be set to 'done' when is_done is True
        self.assertTrue(self.task.is_done)
        self.assertEqual(self.task.label, 'Test Label')
        self.assertEqual(self.task.notes, 'Test notes')
    
    # Note: Individual task creation was removed; tasks are now created through batches
    # Adding test for batch creation instead
    def test_create_batch_view_get(self):
        # Login
        self.client.login(username='testuser', password='password123')
        
        response = self.client.get(self.create_batch_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/create_batch.html')
    
    def test_batch_list_view(self):
        # Login
        self.client.login(username='testuser', password='password123')
        
        response = self.client.get(self.batch_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/batch_list.html')
        
        # Check that batch is in context
        self.assertIn(self.batch, response.context['batches'])
    
    def test_batch_detail_view(self):
        # Login
        self.client.login(username='testuser', password='password123')
        
        response = self.client.get(self.batch_detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/batch_detail.html')
        
        # Check context
        self.assertEqual(response.context['batch'], self.batch)
        self.assertEqual(len(response.context['tasks']), 2)