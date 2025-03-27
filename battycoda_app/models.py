from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


# Group model for user grouping and permissions
class Group(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class GroupInvitation(models.Model):
    """Group invitation model for inviting users via email"""

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_invitations")
    token = models.CharField(max_length=255, unique=True, help_text="Unique token for invitation link")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted = models.BooleanField(default=False)

    def __str__(self):
        return f"Invitation to {self.group.name} for {self.email}"

    @property
    def is_expired(self):
        from django.utils import timezone

        return self.expires_at < timezone.now()


# New model for group membership
class GroupMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="group_memberships")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="group_memberships")
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "group")

    def __str__(self):
        return f"{self.user.username} in {self.group.name} ({'Admin' if self.is_admin else 'Member'})"


# Create your models here.
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="members", null=True)
    is_admin = models.BooleanField(
        default=False, help_text="Designates whether this user is an administrator of their group"
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
    def available_groups(self):
        """Get all groups the user is a member of through GroupMembership"""
        # Get groups from memberships
        membership_groups = Group.objects.filter(group_memberships__user=self.user).order_by("name")

        # Move current group to the front if it exists
        if self.group:
            result = list(membership_groups)
            if self.group in result:
                result.remove(self.group)
            return [self.group] + result

        return membership_groups

    @property
    def is_admin_of_group(self, group_id):
        """Check if user is admin of the specified group"""
        return GroupMembership.objects.filter(user=self.user, group_id=group_id, is_admin=True).exists()


# Create user profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        import logging

        logger = logging.getLogger("battycoda.models")

        # First create the profile
        profile = UserProfile.objects.create(user=instance)

        # Create a new group for this user
        group_name = "My Group"
        group = Group.objects.create(name=group_name, description="Your personal workspace for projects and recordings")

        # Assign the user to their own group and make them an admin
        profile.group = group
        profile.is_admin = True
        profile.save()

        # Create group membership record
        GroupMembership.objects.create(user=instance, group=group, is_admin=True)

        # Create a demo project for the user
        try:
            # Import here to avoid circular imports
            Project = sender.objects.model._meta.apps.get_model("battycoda_app", "Project")

            # Create a standard demo project
            project_name = "Demo Project"

            Project.objects.create(
                name=project_name,
                description="Sample project for demonstration and practice",
                created_by=instance,
                group=group,
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


def get_species_image_path(instance, filename):
    """
    Generate a unique path for species images.
    Format: species_images/user_<user_id>/species_<species_id>/<timestamp>_<filename>
    This ensures:
    1. Separation by user
    2. Separation by species
    3. Timestamp to avoid name collisions
    4. Original filename preserved for reference
    """
    import os
    from datetime import datetime

    # Extract file extension
    ext = os.path.splitext(filename)[1].lower()
    
    # Generate a timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Use the user ID and create a timestamp-based filename
    user_id = instance.created_by.id if instance.created_by else 'unknown'
    species_id = instance.id if instance.id else 'new'
    
    # Create a clean filename (remove special characters)
    clean_filename = ''.join(c for c in os.path.splitext(filename)[0] if c.isalnum() or c in '_- ')
    clean_filename = clean_filename.replace(' ', '_')
    
    # Format: user_<id>/species_<id>/<timestamp>_<clean_filename><ext>
    return f"species_images/user_{user_id}/species_{species_id}/{timestamp}_{clean_filename}{ext}"

# Species model for bat species
class Species(models.Model):
    name = models.CharField(max_length=100)
    # scientific_name field removed
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to=get_species_image_path, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="species")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="species", null=True)

    class Meta:
        verbose_name_plural = "Species"
        ordering = ["name"]
        unique_together = [("name", "group")]

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
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="projects", null=True)
    
    class Meta:
        ordering = ["name"]
        unique_together = [("name", "group")]
    
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
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="task_batches", null=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("name", "group")]

    def __str__(self):
        return self.name


# Classifier model for storing algorithm information
class Classifier(models.Model):
    name = models.CharField(max_length=255, help_text="Name of the classification algorithm")
    description = models.TextField(blank=True, null=True, help_text="Description of how the algorithm works")
    
    # Response format choices
    RESPONSE_FORMAT_CHOICES = (
        ("full_probability", "Full Probability Distribution"),
        ("highest_only", "Highest Probability Only"),
    )
    response_format = models.CharField(
        max_length=20,
        choices=RESPONSE_FORMAT_CHOICES,
        help_text="Format of the response returned by this algorithm"
    )
    
    # Celery task to call
    celery_task = models.CharField(
        max_length=255, 
        help_text="Fully qualified Celery task name to execute this algorithm",
        default="battycoda_app.audio.tasks.run_call_detection"
    )
    
    # External service parameters
    service_url = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="URL of the external service, if applicable"
    )
    endpoint = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Endpoint path for the service"
    )
    
    # Admin only flag
    is_active = models.BooleanField(default=True, help_text="Whether this classifier is currently active")
    created_at = models.DateTimeField(auto_now_add=True)
    group = models.ForeignKey(
        Group, 
        on_delete=models.SET_NULL, 
        related_name="classifiers", 
        null=True,
        blank=True,
        help_text="Group that owns this classifier. If null, it's available to all groups"
    )
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ["name"]


class DetectionRun(models.Model):
    name = models.CharField(max_length=255)
    batch = models.ForeignKey(TaskBatch, on_delete=models.CASCADE, related_name="detection_runs")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="detection_runs")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="detection_runs", null=True)
    
    # Algorithm type choices (for backward compatibility)
    ALGORITHM_TYPE_CHOICES = (
        ("full_probability", "Full Probability Distribution"),
        ("highest_only", "Highest Probability Only"),
    )
    algorithm_type = models.CharField(
        max_length=20, 
        choices=ALGORITHM_TYPE_CHOICES, 
        default="highest_only",
        help_text="Whether the algorithm returns full probability distributions or only the highest probability"
    )
    
    # Link to the classifier used
    classifier = models.ForeignKey(
        Classifier, 
        on_delete=models.CASCADE, 
        related_name="detection_runs",
        null=True, 
        blank=True,
        help_text="The classifier algorithm used for this detection run"
    )
    
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    progress = models.FloatField(default=0.0, help_text="Progress percentage from 0-100")
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.name} - {self.batch.name}"

# Detection Result model for storing individual call detection probabilities
class DetectionResult(models.Model):
    detection_run = models.ForeignKey(DetectionRun, on_delete=models.CASCADE, related_name="results")
    task = models.ForeignKey("Task", on_delete=models.CASCADE, related_name="detection_results")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["task__onset"]
    
    def __str__(self):
        return f"Detection for {self.task}"

# Call probability model for storing probability for each call type
class CallProbability(models.Model):
    detection_result = models.ForeignKey(DetectionResult, on_delete=models.CASCADE, related_name="probabilities")
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name="probabilities")
    probability = models.FloatField(help_text="Probability value between 0-1")
    
    class Meta:
        ordering = ["-probability"]
    
    def __str__(self):
        return f"{self.call.short_name}: {self.probability:.2f}"

# Recording model for storing full audio recordings
class Recording(models.Model):
    # Recording file
    name = models.CharField(max_length=255, help_text="Name of the recording")
    description = models.TextField(blank=True, null=True, help_text="Description of the recording")
    wav_file = models.FileField(upload_to="recordings/", help_text="WAV file for the recording")
    duration = models.FloatField(blank=True, null=True, help_text="Duration of the recording in seconds")
    
    # Recording metadata
    recorded_date = models.DateField(blank=True, null=True, help_text="Date when the recording was made")
    location = models.CharField(max_length=255, blank=True, null=True, help_text="Location where the recording was made")
    equipment = models.CharField(max_length=255, blank=True, null=True, help_text="Equipment used for recording")
    environmental_conditions = models.TextField(blank=True, null=True, help_text="Environmental conditions during recording")
    
    # Organization and permissions
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name="recordings", 
                              help_text="Species associated with this recording")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="recordings",
                              help_text="Project this recording belongs to")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="recordings", null=True,
                           help_text="Group that owns this recording")
    
    # Creation metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recordings")
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Override save to extract duration if not provided"""
        if not self.duration and self.wav_file:
            try:
                import soundfile as sf
                info = sf.info(self.wav_file.path)
                self.duration = info.duration
            except Exception as e:
                import logging
                logger = logging.getLogger("battycoda.models")
                logger.error(f"Error getting audio duration: {str(e)}")
        
        super().save(*args, **kwargs)
    
    def get_segments(self):
        """Get all segments for this recording, sorted by onset time"""
        return Segment.objects.filter(recording=self).order_by('onset')


# Segment model for marking regions in recordings
class Segment(models.Model):
    # Link to recording
    recording = models.ForeignKey(Recording, on_delete=models.CASCADE, related_name="segments",
                                 help_text="Recording this segment belongs to")
    
    # Segment information
    name = models.CharField(max_length=255, blank=True, null=True, help_text="Optional name for this segment")
    onset = models.FloatField(help_text="Start time of the segment in seconds")
    offset = models.FloatField(help_text="End time of the segment in seconds")
    
    # Classification information
    call_type = models.ForeignKey(Call, on_delete=models.SET_NULL, related_name="segments", 
                                 null=True, blank=True, help_text="Call type classification")
    
    # Task created from this segment (if any) - using string reference to avoid circular import
    task = models.OneToOneField('battycoda_app.Task', on_delete=models.SET_NULL, related_name="source_segment", 
                              null=True, blank=True, help_text="Task created from this segment, if any")
    
    # Creation metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="segments")
    
    # Notes
    notes = models.TextField(blank=True, null=True, help_text="Notes about this segment")
    
    class Meta:
        ordering = ["onset"]
    
    def __str__(self):
        return f"{self.recording.name} ({self.onset:.2f}s - {self.offset:.2f}s)"
    
    def duration(self):
        """Calculate segment duration"""
        return self.offset - self.onset
    
    def create_task(self):
        """Create a Task from this segment"""
        if self.task:
            return self.task
        
        # Create a new batch if needed or use the existing one
        # Removed unused import: slugify
        batch_name = f"Batch from {self.recording.name} - {timezone.now().strftime('%Y%m%d-%H%M%S')}"
        
        batch = TaskBatch.objects.create(
            name=batch_name,
            description=f"Automatically created from recording segments at {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
            created_by=self.created_by,
            wav_file_name=self.recording.wav_file.name,
            wav_file=self.recording.wav_file,
            species=self.recording.species,
            project=self.recording.project,
            group=self.recording.group
        )
        
        # Import the Task model here to avoid circular imports
        from battycoda_app.models import Task

        # Create task
        task = Task.objects.create(
            wav_file_name=self.recording.wav_file.name,
            onset=self.onset,
            offset=self.offset,
            species=self.recording.species,
            project=self.recording.project,
            batch=batch,
            created_by=self.created_by,
            group=self.recording.group,
            label=self.call_type.short_name if self.call_type else None,
            notes=self.notes
        )
        
        # Link the task back to this segment
        self.task = task
        self.save()
        
        return task


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
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="tasks", null=True)

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
                # Assume the path is based on the recordings structure
                wav_path = os.path.join(
                    "recordings", self.wav_file_name
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


# Segmentation algorithm model
class SegmentationAlgorithm(models.Model):
    """Model for storing different segmentation algorithms."""
    
    name = models.CharField(max_length=255, help_text="Name of the segmentation algorithm")
    description = models.TextField(blank=True, null=True, help_text="Description of how the algorithm works")
    
    # Algorithm type choices
    ALGORITHM_TYPE_CHOICES = (
        ("threshold", "Threshold-based Detection"),
        ("energy", "Energy-based Detection"),
        ("ml", "Machine Learning Detection"),
        ("external", "External Service"),
    )
    algorithm_type = models.CharField(
        max_length=20,
        choices=ALGORITHM_TYPE_CHOICES,
        default="threshold",
        help_text="Type of segmentation algorithm"
    )
    
    # Celery task to call
    celery_task = models.CharField(
        max_length=255, 
        help_text="Fully qualified Celery task name to execute this algorithm",
        default="battycoda_app.audio.tasks.auto_segment_recording"
    )
    
    # External service parameters (for external algorithms)
    service_url = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="URL of the external service, if applicable"
    )
    endpoint = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Endpoint path for the service"
    )
    
    # Default parameters
    default_min_duration_ms = models.IntegerField(
        default=10, 
        help_text="Default minimum duration in milliseconds"
    )
    default_smooth_window = models.IntegerField(
        default=3, 
        help_text="Default smoothing window size"
    )
    default_threshold_factor = models.FloatField(
        default=0.5, 
        help_text="Default threshold factor (0-10)"
    )
    
    # Admin only flag
    is_active = models.BooleanField(default=True, help_text="Whether this algorithm is currently active")
    created_at = models.DateTimeField(auto_now_add=True)
    group = models.ForeignKey(
        Group, 
        on_delete=models.SET_NULL, 
        related_name="segmentation_algorithms", 
        null=True,
        blank=True,
        help_text="Group that owns this algorithm. If null, it's available to all groups"
    )
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ["name"]


# Segmentation model for a recording
class Segmentation(models.Model):
    """Track segmentation for a recording. Each recording can have only one segmentation."""

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    recording = models.OneToOneField(
        Recording, 
        on_delete=models.CASCADE, 
        related_name="segmentation",
        help_text="The recording this segmentation belongs to"
    )
    algorithm = models.ForeignKey(
        SegmentationAlgorithm, 
        on_delete=models.SET_NULL, 
        related_name="segmentations",
        null=True,
        blank=True,
        help_text="The algorithm used for this segmentation, if any"
    )
    task_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Celery task ID for automated segmentation"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    progress = models.FloatField(default=100, help_text="Progress percentage (0-100)")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    @property
    def is_processing(self):
        """Return True if the segmentation is currently being processed."""
        return self.status in ('pending', 'in_progress')
        
    def __str__(self):
        """String representation of segmentation, using recording name."""
        return f"Segmentation for {self.recording.name}"
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True, null=True)
    
    # Store segmentation parameters
    min_duration_ms = models.IntegerField(default=10)
    smooth_window = models.IntegerField(default=3)
    threshold_factor = models.FloatField(default=0.5)
    
    # Store results
    segments_created = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        """Return string representation."""
        return f"Segmentation job {self.id} - {self.recording.name} ({self.status})"
