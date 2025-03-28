from django.db import migrations

def create_default_segmentation_algorithms(apps, schema_editor):
    """Create default segmentation algorithms for all users."""
    SegmentationAlgorithm = apps.get_model('battycoda_app', 'SegmentationAlgorithm')
    
    # Create standard threshold-based algorithm (built-in)
    SegmentationAlgorithm.objects.create(
        name="Standard Threshold",
        description="Default threshold-based segmentation algorithm. Takes the absolute value of the signal, "
                    "smooths it using a moving average filter, applies a threshold to detect segments, and "
                    "rejects segments shorter than the minimum duration.",
        algorithm_type="threshold",
        celery_task="battycoda_app.audio.tasks.auto_segment_recording",
        default_min_duration_ms=10,
        default_smooth_window=3,
        default_threshold_factor=0.5,
        is_active=True,
        group=None  # Available to all groups
    )
    
    # Create energy-based algorithm
    SegmentationAlgorithm.objects.create(
        name="Energy-based Detection",
        description="Segments audio based on energy levels in the signal. Effective for recordings with "
                    "clear energy differences between calls and background noise.",
        algorithm_type="energy",
        celery_task="battycoda_app.audio.tasks.auto_segment_recording",
        default_min_duration_ms=15,
        default_smooth_window=5,
        default_threshold_factor=0.6,
        is_active=True,
        group=None  # Available to all groups
    )
    
    # Create placeholder for ML-based algorithm
    SegmentationAlgorithm.objects.create(
        name="ML-based Detection (Beta)",
        description="Machine learning based detection that uses a pre-trained model to identify bat calls. "
                   "Currently in beta testing.",
        algorithm_type="ml",
        celery_task="battycoda_app.audio.tasks.auto_segment_recording",
        default_min_duration_ms=5,
        default_smooth_window=2,
        default_threshold_factor=0.4,
        is_active=False,  # Not active yet
        group=None  # Available to all groups
    )


def remove_default_segmentation_algorithms(apps, schema_editor):
    """Remove all default segmentation algorithms."""
    SegmentationAlgorithm = apps.get_model('battycoda_app', 'SegmentationAlgorithm')
    SegmentationAlgorithm.objects.filter(
        name__in=[
            "Standard Threshold", 
            "Energy-based Detection", 
            "ML-based Detection (Beta)"
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0027_segmentationalgorithm_segmentationjob_algorithm'),
    ]

    operations = [
        migrations.RunPython(
            create_default_segmentation_algorithms,
            remove_default_segmentation_algorithms
        ),
    ]