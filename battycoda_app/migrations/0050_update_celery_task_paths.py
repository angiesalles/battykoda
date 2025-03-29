"""
Migration to update Celery task paths from legacy battycoda_app.audio.tasks to specialized module paths.
"""

from django.db import migrations


def update_classifier_task_paths(apps, schema_editor):
    """Update task paths for Classifier model."""
    Classifier = apps.get_model("battycoda_app", "Classifier")

    # Define mapping for path updates
    path_mapping = {
        "battycoda_app.audio.tasks.run_call_detection": "battycoda_app.audio.task_modules.detection_tasks.run_call_detection",
        "battycoda_app.audio.tasks.run_dummy_classifier": "battycoda_app.audio.task_modules.detection_tasks.run_dummy_classifier",
    }

    # Update each classifier
    for classifier in Classifier.objects.all():
        if classifier.celery_task in path_mapping:
            print(f"Updating Classifier task path: {classifier.celery_task} -> {path_mapping[classifier.celery_task]}")
            classifier.celery_task = path_mapping[classifier.celery_task]
            classifier.save()


def update_segmentation_algorithm_task_paths(apps, schema_editor):
    """Update task paths for SegmentationAlgorithm model."""
    SegmentationAlgorithm = apps.get_model("battycoda_app", "SegmentationAlgorithm")

    # Define mapping for path updates
    path_mapping = {
        "battycoda_app.audio.tasks.auto_segment_recording": 
        "battycoda_app.audio.task_modules.segmentation_tasks.auto_segment_recording_task",
    }

    # Update each algorithm
    for algorithm in SegmentationAlgorithm.objects.all():
        if algorithm.celery_task in path_mapping:
            print(f"Updating SegmentationAlgorithm task path: {algorithm.celery_task} -> {path_mapping[algorithm.celery_task]}")
            algorithm.celery_task = path_mapping[algorithm.celery_task]
            algorithm.save()


def reverse_update_classifier_task_paths(apps, schema_editor):
    """Reverse task path updates for Classifier model."""
    Classifier = apps.get_model("battycoda_app", "Classifier")

    # Define mapping for path updates
    reverse_mapping = {
        "battycoda_app.audio.task_modules.detection_tasks.run_call_detection": "battycoda_app.audio.tasks.run_call_detection",
        "battycoda_app.audio.task_modules.detection_tasks.run_dummy_classifier": "battycoda_app.audio.tasks.run_dummy_classifier",
    }

    # Revert each classifier
    for classifier in Classifier.objects.all():
        if classifier.celery_task in reverse_mapping:
            classifier.celery_task = reverse_mapping[classifier.celery_task]
            classifier.save()


def reverse_update_segmentation_algorithm_task_paths(apps, schema_editor):
    """Reverse task path updates for SegmentationAlgorithm model."""
    SegmentationAlgorithm = apps.get_model("battycoda_app", "SegmentationAlgorithm")

    # Define mapping for path updates
    reverse_mapping = {
        "battycoda_app.audio.task_modules.segmentation_tasks.auto_segment_recording_task": 
        "battycoda_app.audio.tasks.auto_segment_recording",
    }

    # Revert each algorithm
    for algorithm in SegmentationAlgorithm.objects.all():
        if algorithm.celery_task in reverse_mapping:
            algorithm.celery_task = reverse_mapping[algorithm.celery_task]
            algorithm.save()


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0049_merge_20250329_0405'),
    ]

    operations = [
        migrations.RunPython(
            update_classifier_task_paths,
            reverse_code=reverse_update_classifier_task_paths
        ),
        migrations.RunPython(
            update_segmentation_algorithm_task_paths,
            reverse_code=reverse_update_segmentation_algorithm_task_paths
        ),
    ]