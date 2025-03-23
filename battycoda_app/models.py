from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


# Team model for user grouping and permissions
class Team(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TeamInvitation(models.Model):
    """Team invitation model for inviting users via email"""

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_invitations")
    token = models.CharField(max_length=255, unique=True, help_text="Unique token for invitation link")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted = models.BooleanField(default=False)

    def __str__(self):
        return f"Invitation to {self.team.name} for {self.email}"

    @property
    def is_expired(self):
        from django.utils import timezone

        return self.expires_at < timezone.now()


# New model for team membership
class TeamMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="team_memberships")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team_memberships")
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "team")

    def __str__(self):
        return f"{self.user.username} in {self.team.name} ({'Admin' if self.is_admin else 'Member'})"


# Create your models here.
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members", null=True)
    is_admin = models.BooleanField(
        default=False, help_text="Designates whether this user is an administrator of their team"
    )
    # Authentication fields (previously Cloudflare fields, kept for data compatibility)
    cloudflare_id = models.CharField(
        max_length=255, blank=True, null=True, help_text="Deprecated - kept for data compatibility"
    )
    is_cloudflare_user = models.BooleanField(default=False, help_text="Deprecated - kept for data compatibility")
    cloudflare_email = models.EmailField(blank=True, null=True, help_text="Deprecated - kept for data compatibility")
    last_cloudflare_login = models.DateTimeField(
        blank=True, null=True, help_text="Deprecated - kept for data compatibility"
    )

    def __str__(self):
        return self.user.username

    @property
    def available_teams(self):
        """Get all teams the user is a member of through TeamMembership"""
        # Get teams from memberships
        membership_teams = Team.objects.filter(team_memberships__user=self.user).order_by("name")

        # Move current team to the front if it exists
        if self.team:
            result = list(membership_teams)
            if self.team in result:
                result.remove(self.team)
            return [self.team] + result

        return membership_teams

    @property
    def is_admin_of_team(self, team_id):
        """Check if user is admin of the specified team"""
        return TeamMembership.objects.filter(user=self.user, team_id=team_id, is_admin=True).exists()


# Create user profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        import logging

        logger = logging.getLogger("battycoda.models")

        # First create the profile
        profile = UserProfile.objects.create(user=instance)

        # Create a new team for this user
        team_name = f"{instance.username}'s Team"
        team = Team.objects.create(name=team_name, description=f"Personal team for {instance.username}")

        # Assign the user to their own team and make them an admin
        profile.team = team
        profile.is_admin = True
        profile.save()

        # Create team membership record
        TeamMembership.objects.create(user=instance, team=team, is_admin=True)

        # Create a demo project for the user
        try:
            # Import here to avoid circular imports
            Project = sender.objects.model._meta.apps.get_model("battycoda_app", "Project")

            # Generate a unique project name
            project_name = f"Demo Project - {instance.username}"

            Project.objects.create(
                name=project_name,
                description=f"Demo project created automatically for {instance.username}",
                created_by=instance,
                team=team,
            )
            logger.info(f"Created demo project '{project_name}' for user {instance.username}")
        except Exception as e:
            logger.error(f"Error creating demo project for user {instance.username}: {str(e)}")

        # Import default species in a separate try block
        try:
            from .utils import import_default_species

            created_species = import_default_species(instance)
            logger.info(f"Created {len(created_species)} default species for user {instance.username}")
        except Exception as e:
            logger.error(f"Error importing default species for user {instance.username}: {str(e)}")

        # Create a demo task batch with sample bat calls
        try:
            from .utils import create_demo_task_batch

            batch = create_demo_task_batch(instance)
            if batch:
                logger.info(f"Created demo task batch '{batch.name}' for user {instance.username}")
            else:
                logger.warning(f"Failed to create demo task batch for user {instance.username}")
        except Exception as e:
            logger.error(f"Error creating demo task batch for user {instance.username}: {str(e)}")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


# Species model for bat species
class Species(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # scientific_name field removed
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="species_images/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="species")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="species", null=True)

    class Meta:
        verbose_name_plural = "Species"
        ordering = ["name"]

    def __str__(self):
        return self.name


# Call types for species
class Call(models.Model):
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name="calls")
    short_name = models.CharField(max_length=50)
    long_name = models.CharField(max_length=255, blank=True, null=True)
    # description field removed
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["short_name"]
        unique_together = ["species", "short_name"]

    def __str__(self):
        return f"{self.species.name} - {self.short_name}"


# Project model for research projects
class Project(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="projects", null=True)

    def __str__(self):
        return self.name


# Task Batch for grouping tasks that were created together
class TaskBatch(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="task_batches")
    wav_file_name = models.CharField(max_length=255)
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name="task_batches")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="task_batches")
    wav_file = models.FileField(upload_to="task_batches/", null=True, blank=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="task_batches", null=True)

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
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name="tasks")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")

    # Link to batch
    batch = models.ForeignKey(TaskBatch, on_delete=models.CASCADE, related_name="tasks", null=True, blank=True)

    # Task metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="tasks", null=True)

    # Task status and completion
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("done", "Done"),  # Special status for fully labeled tasks
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    is_done = models.BooleanField(
        default=False, help_text="Indicates that the task has been fully reviewed and labeled"
    )

    # Classification and labeling
    classification_result = models.CharField(max_length=100, blank=True, null=True)
    confidence = models.FloatField(blank=True, null=True)
    label = models.CharField(
        max_length=255, blank=True, null=True, help_text="Final expert label assigned to this task"
    )

    # Notes and comments
    notes = models.TextField(blank=True, null=True, help_text="Additional notes or observations about this task")

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.wav_file_name} ({self.onset:.2f}s - {self.offset:.2f}s)"

    def save(self, *args, **kwargs):
        # Automatically set is_done flag when status is 'done'
        if self.status == "done":
            self.is_done = True

        # If is_done is True but status isn't 'done', set status to 'done'
        if self.is_done and self.status != "done":
            self.status = "done"

        super().save(*args, **kwargs)

        # After saving, pre-generate spectrograms
        self.generate_spectrograms()

    def generate_spectrograms(self):
        """Pre-generate spectrograms for this task to avoid frontend requests"""
        import hashlib
        import os

        from django.conf import settings

        from .audio.tasks import generate_spectrogram, normal_hwin, overview_hwin
        from .utils import convert_path_to_os_specific

        # Skip if this is called during migration
        if not os.path.exists(settings.MEDIA_ROOT):
            return

        try:
            # Prepare the WAV file path
            if self.batch and self.batch.wav_file:
                # Get the path from the uploaded file in the batch
                wav_path = self.batch.wav_file.path
            else:
                # Assume the path is based on the project structure
                wav_path = os.path.join(
                    "home", self.created_by.username, self.species.name, self.project.name, self.wav_file_name
                )
                wav_path = convert_path_to_os_specific(wav_path)

            # Create hash
            file_hash = hashlib.md5(wav_path.encode()).hexdigest()

            # Generate spectrograms for all channels (0, 1) and types (normal, overview)
            for channel in [0, 1]:  # Assuming 2 channels
                for overview in [False, True]:
                    # Prepare args for spectrogram generation
                    args = {
                        "call": "0",  # Always the first call for a task
                        "channel": str(channel),
                        "numcalls": "1",
                        "hash": file_hash,
                        "overview": "1" if overview else "0",
                        "contrast": "4.0",  # Default contrast value
                    }

                    # Add the onset and offset to the args
                    args["onset"] = str(self.onset)
                    args["offset"] = str(self.offset)

                    # Generate the spectrogram asynchronously
                    from celery import current_app

                    task = current_app.send_task(
                        "battycoda_app.audio.tasks.generate_spectrogram_task", args=[wav_path, args, None]
                    )

        except Exception as e:
            import logging

            logger = logging.getLogger("battycoda.models")
            logger.error(f"Error pre-generating spectrograms: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())
