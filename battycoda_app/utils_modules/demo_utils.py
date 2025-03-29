"""
Utility functions for creating demo data.
"""

import logging
import os
import traceback

from django.core.files import File
from django.db import transaction
from django.utils import timezone

# Set up logging
logger = logging.getLogger("battycoda.utils")


def create_demo_task_batch(user):
    """Create a demo task batch for a new user using sample files.

    Args:
        user: The User object to create the task batch for

    Returns:
        TaskBatch or None: The created TaskBatch object, or None if creation failed
    """
    from battycoda_app.audio.tasks import run_dummy_classifier
    from battycoda_app.audio.utils import process_pickle_file
    from battycoda_app.models import (
        CallProbability,
        Classifier,
        DetectionResult,
        DetectionRun,
        Project,
        Recording,
        Segment,
        Segmentation,
        Species,
        Task,
        TaskBatch,
    )

    logger.info(f"Creating demo task batch for user {user.username}")

    # Get the user's group and profile
    profile = user.profile
    group = profile.group
    if not group:
        logger.warning(f"User {user.username} has no group, skipping task batch creation")
        return None

    # Prerequisites: check for required resources
    try:
        # Find the user's demo project
        project, species, sample_files = _check_demo_prerequisites(user, group)
        if not project or not species or not sample_files:
            return None

        # Extract sample file paths
        wav_path, pickle_path = sample_files

        # Step 1: Create a demo recording
        recording = _create_demo_recording(user, group, project, species, wav_path)
        if not recording:
            return None

        # Step 2: Create segmentation and segments
        segmentation = _create_demo_segmentation(user, recording, pickle_path)
        if not segmentation:
            return None

        # Step 3: Run classification
        detection_run = _run_demo_classification(user, group, segmentation)
        if not detection_run:
            return None

        # Step 4: Create a task batch from the detection run
        batch = _create_task_batch_from_detection(user, group, project, species, recording, detection_run)

        if batch:
            logger.info(f"Successfully created demo task batch '{batch.name}' for user {user.username}")
            return batch

    except Exception as e:
        logger.error(f"Error creating demo task batch: {str(e)}")
        logger.error(traceback.format_exc())
        return None


def _check_demo_prerequisites(user, group):
    """Check prerequisites for creating a demo task batch

    Args:
        user: The User object
        group: The Group object

    Returns:
        tuple: (project, species, sample_files) or (None, None, None) if prerequisites not met
    """
    from battycoda_app.models import Project, Species

    # Find the user's demo project
    project = Project.objects.filter(group=group, name__contains="Demo Project").first()
    if not project:
        logger.warning(f"No demo project found for {user.username}, skipping task batch creation")
        return None, None, None

    # Find the Carollia species
    species = Species.objects.filter(group=group, name="Carollia").first()
    if not species:
        logger.warning(f"No Carollia species found for {user.username}, skipping task batch creation")
        return None, None, None

    # Define the paths to the sample files
    sample_paths = {
        "wav": ["/app/data/sample_audio/bat1_angie_19.wav"],
        "pickle": [
            "/app/data/sample_audio/bat1_angie_19.wav.pickle",
        ],
    }

    # Find the sample WAV file
    wav_path = None
    for path in sample_paths["wav"]:
        if os.path.exists(path):
            wav_path = path
            break

    if not wav_path:
        logger.warning("Sample WAV file not found, skipping task batch creation")
        return None, None, None

    # Find the sample pickle file
    pickle_path = None
    for path in sample_paths["pickle"]:
        if os.path.exists(path):
            pickle_path = path
            break

    if not pickle_path:
        logger.warning("Sample pickle file not found, skipping task batch creation")
        return None, None, None

    return project, species, (wav_path, pickle_path)


def _create_demo_recording(user, group, project, species, wav_path):
    """Create a demo recording for a user

    Args:
        user: The User object
        group: The Group object
        project: The Project object
        species: The Species object
        wav_path: Path to the WAV file

    Returns:
        Recording: The created Recording object or None if creation failed
    """
    from battycoda_app.models import Recording

    try:
        # Create the recording
        recording = Recording(
            name="Demo Bat Recording",
            description="Sample bat calls for demonstration and practice",
            created_by=user,
            species=species,
            project=project,
            group=group,
        )
        recording.save()

        # Attach the WAV file
        with open(wav_path, "rb") as wav_file:
            recording.wav_file.save("bat1_angie_19.wav", File(wav_file), save=True)

        logger.info(f"Created demo recording for user {user.username}")
        return recording
    except Exception as e:
        logger.error(f"Error creating demo recording: {str(e)}")
        return None


def _create_demo_segmentation(user, recording, pickle_path):
    """Create demo segmentation for a recording

    Args:
        user: The User object
        recording: The Recording object
        pickle_path: Path to the pickle file with segment data

    Returns:
        Segmentation: The created Segmentation object or None if creation failed
    """
    from battycoda_app.audio.utils import process_pickle_file
    from battycoda_app.models import Segment, Segmentation

    try:
        # Open and process the pickle file
        with open(pickle_path, "rb") as f:
            onsets, offsets = process_pickle_file(f)

        # Create segments from the onset/offset pairs
        segments_created = 0

        # Create the segmentation object
        segmentation = Segmentation(
            recording=recording,
            status="completed",  # Already completed
            progress=100,
            created_by=user,
            manually_edited=False,
        )
        segmentation.save()

        with transaction.atomic():
            # Only use the first 10 entries to keep the demo manageable
            max_entries = min(10, len(onsets))

            # Create segments
            for i in range(max_entries):
                # Convert numpy types to Python native types if needed
                onset_value = float(onsets[i])
                offset_value = float(offsets[i])

                # Create and save the segment
                segment = Segment(
                    recording=recording,
                    name=f"Segment {i+1}",
                    onset=onset_value,
                    offset=offset_value,
                    created_by=user,
                )
                segment.save()
                segments_created += 1

        logger.info(f"Created segmentation with {segments_created} segments for demo recording")
        return segmentation
    except Exception as e:
        logger.error(f"Error creating demo segmentation: {str(e)}")
        logger.error(traceback.format_exc())
        return None


def _run_demo_classification(user, group, segmentation):
    """Run the dummy classifier on demo segments

    Args:
        user: The User object
        group: The Group object
        segmentation: The Segmentation object

    Returns:
        DetectionRun: The created DetectionRun object or None if creation failed
    """
    from battycoda_app.audio.tasks import run_dummy_classifier
    from battycoda_app.models import Classifier, DetectionRun

    try:
        # Find the dummy classifier
        dummy_classifier = Classifier.objects.get(name="Dummy Classifier")

        # Create a detection run
        detection_run = DetectionRun.objects.create(
            name="Demo Classification Run",
            segmentation=segmentation,
            created_by=user,
            group=group,
            classifier=dummy_classifier,
            algorithm_type="full_probability",
            status="pending",
            progress=0,
        )

        # Run the dummy classifier directly (not through Celery)
        run_dummy_classifier(detection_run.id)

        # Make sure the run is marked as completed
        detection_run.refresh_from_db()
        if detection_run.status != "completed":
            detection_run.status = "completed"
            detection_run.progress = 100
            detection_run.save()

        logger.info(f"Completed dummy classification for demo recording")
        return detection_run
    except Classifier.DoesNotExist:
        logger.error("Dummy classifier not found. Make sure the Dummy Classifier exists in the database.")
        return None
    except Exception as e:
        logger.error(f"Error running demo classification: {str(e)}")
        return None


def _create_task_batch_from_detection(user, group, project, species, recording, detection_run):
    """Create a task batch from a detection run

    Args:
        user: The User object
        group: The Group object
        project: The Project object
        species: The Species object
        recording: The Recording object
        detection_run: The DetectionRun object

    Returns:
        TaskBatch: The created TaskBatch object or None if creation failed
    """
    from battycoda_app.models import CallProbability, DetectionResult, Task, TaskBatch

    try:
        # Create a unique batch name with timestamp
        batch_name = f"Demo Bat Calls ({timezone.now().strftime('%Y%m%d-%H%M%S')})"

        # Create the task batch
        batch = TaskBatch.objects.create(
            name=batch_name,
            description="Sample bat calls for demonstration and practice",
            created_by=user,
            wav_file_name=recording.wav_file.name,
            wav_file=recording.wav_file,
            species=species,
            project=project,
            group=group,
            detection_run=detection_run,  # Link to the detection run
        )

        # Create tasks for each detection result's segment
        tasks_created = 0
        with transaction.atomic():
            # Get all detection results from this run
            results = DetectionResult.objects.filter(detection_run=detection_run)

            for result in results:
                segment = result.segment

                # Get the highest probability call type
                top_probability = (
                    CallProbability.objects.filter(detection_result=result).order_by("-probability").first()
                )

                # Create a task for this segment
                task = Task.objects.create(
                    wav_file_name=recording.wav_file.name,
                    onset=segment.onset,
                    offset=segment.offset,
                    species=species,
                    project=project,
                    batch=batch,
                    created_by=user,
                    group=group,
                    # Use the highest probability call type as the initial label
                    label=top_probability.call.short_name if top_probability else None,
                    status="pending",
                )

                # Link the task back to the segment
                segment.task = task
                segment.save()

                tasks_created += 1

        logger.info(f"Created {tasks_created} tasks for demo batch {batch.name}")
        return batch
    except Exception as e:
        logger.error(f"Error creating task batch from detection run: {str(e)}")
        logger.error(traceback.format_exc())
        return None
