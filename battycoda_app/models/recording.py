"""Recording models for BattyCoda application."""

import logging

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .organization import Project, Species
from .user import Group

logger = logging.getLogger("battycoda.models")


class Recording(models.Model):
    """Recording model for storing full audio recordings."""

    # Recording file
    name = models.CharField(max_length=255, help_text="Name of the recording")
    description = models.TextField(blank=True, null=True, help_text="Description of the recording")
    wav_file = models.FileField(upload_to="recordings/", help_text="WAV file for the recording")
    duration = models.FloatField(blank=True, null=True, help_text="Duration of the recording in seconds")
    sample_rate = models.IntegerField(blank=True, null=True, help_text="Sample rate of the recording in Hz")

    # Recording metadata
    recorded_date = models.DateField(blank=True, null=True, help_text="Date when the recording was made")
    location = models.CharField(
        max_length=255, blank=True, null=True, help_text="Location where the recording was made"
    )
    equipment = models.CharField(max_length=255, blank=True, null=True, help_text="Equipment used for recording")
    environmental_conditions = models.TextField(
        blank=True, null=True, help_text="Environmental conditions during recording"
    )

    # Organization and permissions
    species = models.ForeignKey(
        Species, on_delete=models.CASCADE, related_name="recordings", help_text="Species associated with this recording"
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="recordings", help_text="Project this recording belongs to"
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="recordings",
        null=True,
        help_text="Group that owns this recording",
    )

    # Creation metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recordings")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Recording"
        verbose_name_plural = "Recordings"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Standard save method - duration is calculated via post-save signal"""
        super().save(*args, **kwargs)

    def get_segments(self):
        """Get all segments for this recording, sorted by onset time"""
        return Segment.objects.filter(recording=self).order_by("onset")


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
        max_length=20, choices=ALGORITHM_TYPE_CHOICES, default="threshold", help_text="Type of segmentation algorithm"
    )

    # Celery task to call
    celery_task = models.CharField(
        max_length=255,
        help_text="Fully qualified Celery task name to execute this algorithm",
        default="battycoda_app.audio.task_modules.segmentation_tasks.auto_segment_recording_task",
    )

    # External service parameters (for external algorithms)
    service_url = models.CharField(
        max_length=255, blank=True, null=True, help_text="URL of the external service, if applicable"
    )
    endpoint = models.CharField(max_length=255, blank=True, null=True, help_text="Endpoint path for the service")

    # Default parameters
    default_min_duration_ms = models.IntegerField(default=10, help_text="Default minimum duration in milliseconds")
    default_smooth_window = models.IntegerField(default=3, help_text="Default smoothing window size")
    default_threshold_factor = models.FloatField(default=0.5, help_text="Default threshold factor (0-10)")

    # Admin only flag
    is_active = models.BooleanField(default=True, help_text="Whether this algorithm is currently active")
    created_at = models.DateTimeField(auto_now_add=True)
    group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        related_name="segmentation_algorithms",
        null=True,
        blank=True,
        help_text="Group that owns this algorithm. If null, it's available to all groups",
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class Segmentation(models.Model):
    """Track segmentation for a recording. Each recording can have multiple segmentations."""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    recording = models.ForeignKey(
        Recording,
        on_delete=models.CASCADE,
        related_name="segmentations",
        help_text="The recording this segmentation belongs to",
    )
    name = models.CharField(
        max_length=255, default="Default Segmentation", help_text="Descriptive name for this segmentation run"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this is the currently active segmentation for the recording"
    )
    algorithm = models.ForeignKey(
        SegmentationAlgorithm,
        on_delete=models.SET_NULL,
        related_name="segmentations",
        null=True,
        blank=True,
        help_text="The algorithm used for this segmentation, if any",
    )
    task_id = models.CharField(
        max_length=100, blank=True, null=True, help_text="Celery task ID for automated segmentation"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="completed")
    progress = models.FloatField(default=100, help_text="Progress percentage (0-100)")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True, null=True)

    # Store segmentation parameters
    min_duration_ms = models.IntegerField(default=10)
    smooth_window = models.IntegerField(default=3)
    threshold_factor = models.FloatField(default=0.5)

    # Store results
    segments_created = models.IntegerField(default=0)

    # Track if this segmentation has been manually edited
    manually_edited = models.BooleanField(
        default=False, help_text="Indicates if this segmentation was manually edited after initial creation"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        """Return string representation."""
        return f"Segmentation job {self.id} - {self.recording.name} ({self.status})"

    @property
    def is_processing(self):
        """Return True if the segmentation is currently being processed."""
        return self.status in ("pending", "in_progress")


class Segment(models.Model):
    """Segment model for marking regions in recordings."""

    # Link to recording
    recording = models.ForeignKey(
        Recording, on_delete=models.CASCADE, related_name="segments", help_text="Recording this segment belongs to"
    )

    # Link to the segmentation that created or manages this segment
    segmentation = models.ForeignKey(
        Segmentation,
        on_delete=models.CASCADE,
        related_name="segments",
        help_text="Segmentation that manages this segment",
    )

    # Segment information
    name = models.CharField(max_length=255, blank=True, null=True, help_text="Optional name for this segment")
    onset = models.FloatField(help_text="Start time of the segment in seconds")
    offset = models.FloatField(help_text="End time of the segment in seconds")

    # Task created from this segment (if any) - using string reference to avoid circular import
    task = models.OneToOneField(
        "battycoda_app.Task",
        on_delete=models.SET_NULL,
        related_name="source_segment",
        null=True,
        blank=True,
        help_text="Task created from this segment, if any",
    )

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

    def save(self, *args, **kwargs):
        """Override save to handle segmentation relationship"""
        # Check if this is an automated save or manual edit
        # If manual_edit is explicitly set to False, don't mark as manually edited
        manual_edit = kwargs.pop("manual_edit", True)

        # Check if we need a segmentation for this segment
        if not hasattr(self, "segmentation") or self.segmentation is None:
            # Find active segmentation for this recording or create a new one
            try:
                # Get the Segmentation model through the apps registry to avoid circular imports
                Segmentation = self.__class__._meta.apps.get_model("battycoda_app", "Segmentation")

                # Look for an active segmentation
                try:
                    segmentation = Segmentation.objects.get(recording=self.recording, is_active=True)
                except Segmentation.DoesNotExist:
                    # No active segmentation, create a new one
                    segmentation = Segmentation.objects.create(
                        recording=self.recording,
                        name=f"Manual Segmentation {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        created_by=self.created_by,
                        status="completed",
                        progress=100,
                        is_active=True,
                        manually_edited=manual_edit,  # Only mark as manually edited if it's a manual save
                    )

                # Assign this segmentation to the segment
                self.segmentation = segmentation
            except Exception as e:
                logger.error(f"Error handling segmentation for segment: {str(e)}")

        # Call the original save method
        super().save(*args, **kwargs)

        # Mark the segment's segmentation as manually edited ONLY if this is a manual edit
        if manual_edit and hasattr(self, "segmentation") and self.segmentation:
            try:
                self.segmentation.manually_edited = True
                self.segmentation.save()
            except Exception as e:
                logger.error(f"Error marking segmentation as manually edited: {str(e)}")

    def delete(self, *args, **kwargs):
        """Override delete to mark segmentation as manually edited before deletion"""
        # Mark the segmentation as manually edited if it exists
        if hasattr(self, "segmentation") and self.segmentation:
            try:
                self.segmentation.manually_edited = True
                self.segmentation.save()
            except Exception as e:
                logger.error(f"Error marking segmentation as manually edited: {str(e)}")

        # Call the original delete method
        super().delete(*args, **kwargs)

    def create_task(self):
        """Create a Task from this segment"""
        from .task import Task, TaskBatch

        if self.task:
            return self.task

        # Create a new batch if needed or use the existing one
        batch_name = f"Batch from {self.recording.name} - {timezone.now().strftime('%Y%m%d-%H%M%S')}"

        batch = TaskBatch.objects.create(
            name=batch_name,
            description=f"Automatically created from recording segments at {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
            created_by=self.created_by,
            wav_file_name=self.recording.wav_file.name,
            wav_file=self.recording.wav_file,
            species=self.recording.species,
            project=self.recording.project,
            group=self.recording.group,
        )

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
            label=None,  # Call type is no longer on segment
            notes=self.notes,
        )

        # Link the task back to this segment
        self.task = task
        self.save()

        return task
