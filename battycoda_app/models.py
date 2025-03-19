from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Team model for user grouping and permissions
class Team(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

# Create your models here.
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members', null=True)
    is_admin = models.BooleanField(default=False, help_text="Designates whether this user is an administrator of their team")
    # Cloudflare fields
    cloudflare_id = models.CharField(max_length=255, blank=True, null=True)
    is_cloudflare_user = models.BooleanField(default=False)
    cloudflare_email = models.EmailField(blank=True, null=True)
    last_cloudflare_login = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return self.user.username

# Create user profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

# Species model for bat species
class Species(models.Model):
    name = models.CharField(max_length=100, unique=True)
    scientific_name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='species_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='species')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='species', null=True)
    
    class Meta:
        verbose_name_plural = "Species"
        ordering = ['name']
    
    def __str__(self):
        return self.name

# Call types for species
class Call(models.Model):
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name='calls')
    short_name = models.CharField(max_length=50)
    long_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['short_name']
        unique_together = ['species', 'short_name']
    
    def __str__(self):
        return f"{self.species.name} - {self.short_name}"

# Project model for research projects
class Project(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='projects', null=True)
    
    def __str__(self):
        return self.name

# Task Batch for grouping tasks that were created together
class TaskBatch(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_batches')
    wav_file_name = models.CharField(max_length=255)
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name='task_batches')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='task_batches')
    wav_file = models.FileField(upload_to='task_batches/', null=True, blank=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='task_batches', null=True)
    
    def __str__(self):
        return self.name

# Task model for storing bat vocalization analysis tasks
class Task(models.Model):
    # File information
    wav_file_name = models.CharField(max_length=255)
    
    # Segment information
    onset = models.FloatField(help_text="Start time of the segment in seconds")
    offset = models.FloatField(help_text="End time of the segment in seconds")
    
    # Classification information
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name='tasks')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    
    # Link to batch
    batch = models.ForeignKey(TaskBatch, on_delete=models.CASCADE, related_name='tasks', null=True, blank=True)
    
    # Task metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='tasks', null=True)
    
    # Task status and completion
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('done', 'Done'),  # Special status for fully labeled tasks
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_done = models.BooleanField(default=False, help_text="Indicates that the task has been fully reviewed and labeled")
    
    # Classification and labeling
    classification_result = models.CharField(max_length=100, blank=True, null=True)
    confidence = models.FloatField(blank=True, null=True)
    label = models.CharField(max_length=255, blank=True, null=True, help_text="Final expert label assigned to this task")
    
    # Notes and comments
    notes = models.TextField(blank=True, null=True, help_text="Additional notes or observations about this task")
    
    class Meta:
        ordering = ['created_at']
        
    def __str__(self):
        return f"{self.wav_file_name} ({self.onset:.2f}s - {self.offset:.2f}s)"
        
    def save(self, *args, **kwargs):
        # Automatically set is_done flag when status is 'done'
        if self.status == 'done':
            self.is_done = True
        
        # If is_done is True but status isn't 'done', set status to 'done'
        if self.is_done and self.status != 'done':
            self.status = 'done'
            
        super().save(*args, **kwargs)
