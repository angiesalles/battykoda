"""
Utility functions for the battycoda application.
"""
import logging
import os

from django.conf import settings

# Removed unused import: subprocess


# Set up logging
logger = logging.getLogger("battycoda.utils")


def convert_path_to_os_specific(path):
    """
    Convert a web path to an OS-specific path

    Args:
        path (str): Web path (like "recordings/audio.wav")

    Returns:
        str: OS-specific path to the location in media directory
    """
    # Normalize directory separators
    path = path.replace("\\", "/")

    # Remove leading slash if present
    if path.startswith("/"):
        path = path[1:]

    # All paths now go to media folder
    return os.path.join(settings.MEDIA_ROOT, path)


def available_species():
    """
    Get a list of available default species

    Returns:
        list: List of default species names
    """
    try:
        # Import directly from the default_species module
        from .default_species import DEFAULT_SPECIES
        return [species["name"] for species in DEFAULT_SPECIES]
    except Exception as e:
        logger.error(f"Error getting available species: {str(e)}")
        return []


def import_default_species(user):
    """Import default species for a new user's group

    Args:
        user: The User object to import species for

    Returns:
        list: List of created Species objects
    """
    import time
    import traceback

    from django.core.files import File

    from .default_species import DEFAULT_SPECIES
    from .models import Call, Species

    # Add a delay to ensure user creation transaction is complete
    time.sleep(1)

    logger.info(f"Importing default species for user {user.username}")

    # Get the user's group
    group = user.profile.group
    if not group:
        logger.warning(f"User {user.username} has no group, skipping species import")
        return []

    created_species = []

    # Use the default species defined in the separate module
    default_species = DEFAULT_SPECIES

    # Import each species
    for species_data in default_species:
        # Use the actual species name (no group suffix)
        species_name = species_data['name']

        # Skip if species already exists for this group
        if Species.objects.filter(name=species_name, group=group).exists():
            logger.info(f"Species {species_name} already exists for group {group.name}")
            continue

        try:
            # Create the species with its normal name
            species = Species.objects.create(
                name=species_name, description=species_data["description"], created_by=user, group=group
            )
            logger.info(f"Created species {species.name} for group {group.name}")

            # Add the image if it exists
            # Use explicit paths for Docker container
            image_paths = [
                f"/app/data/species_images/{species_data['image_file']}",
            ]

            image_found = False
            for image_path in image_paths:
                logger.info(f"Looking for image at {image_path}")
                if os.path.exists(image_path):
                    logger.info(f"Found image at {image_path}")
                    with open(image_path, "rb") as img_file:
                        species.image.save(species_data["image_file"], File(img_file), save=True)
                    logger.info(f"Saved image for {species.name}")
                    image_found = True
                    break

            if not image_found:
                logger.warning(f"Image file not found for {species_data['name']}")

            # Parse call types from the text file
            call_paths = [
                f"/app/data/species_images/{species_data['call_file']}",
            ]

            call_file_found = False
            for call_path in call_paths:
                logger.info(f"Looking for call file at {call_path}")
                if os.path.exists(call_path):
                    logger.info(f"Found call file at {call_path}")
                    call_count = 0

                    with open(call_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                        logger.info(f"Read {len(file_content)} bytes from {call_path}")

                        # Process each line
                        for line in file_content.splitlines():
                            line = line.strip()
                            if not line:
                                continue

                            if "," in line:
                                short_name, long_name = line.split(",", 1)
                            elif "|" in line:
                                short_name, long_name = line.split("|", 1)
                            elif "\t" in line:
                                short_name, long_name = line.split("\t", 1)
                            else:
                                # If no separator, use whole line as short_name and leave long_name empty
                                short_name = line
                                long_name = ""

                            short_name = short_name.strip()
                            long_name = long_name.strip()

                            # Create the call
                            Call.objects.create(
                                species=species, short_name=short_name, long_name=long_name if long_name else None
                            )
                            call_count += 1

                    logger.info(f"Created {call_count} calls for species {species.name}")
                    call_file_found = True
                    break

            if not call_file_found:
                logger.warning(f"Call file not found for {species_data['name']}")

            created_species.append(species)

        except Exception as e:
            logger.error(f"Error importing species {species_data['name']}: {str(e)}")
            logger.error(traceback.format_exc())

    return created_species


def create_recording_from_batch(batch, onsets=None, offsets=None, pickle_file=None):
    """Create a recording and segments from a task batch
    
    Args:
        batch: The TaskBatch object to create a recording from
        onsets: Optional list of onset times in seconds
        offsets: Optional list of offset times in seconds
        pickle_file: Optional pickle file object containing onset/offset data
        
    Returns:
        tuple: (recording, segments_created) - The Recording object and count of segments created,
               or (None, 0) if creation failed
    """
    import traceback

    from django.db import transaction

    from .audio.utils import process_pickle_file
    from .models import Recording, Segment, Segmentation
    
    logger.info(f"Creating recording from task batch {batch.name}")
    
    # Ensure we have a valid batch with a WAV file
    if not batch.wav_file:
        logger.error(f"Task batch {batch.name} has no WAV file")
        return None, 0
    
    try:
        # Create a new recording using the same WAV file
        recording = Recording(
            name=f"Recording from {batch.name}",
            description=f"Created automatically from task batch {batch.name}",
            wav_file=batch.wav_file,  # Use the same WAV file
            species=batch.species,
            project=batch.project,
            group=batch.group,
            created_by=batch.created_by
        )
        recording.save()
        
        segments_created = 0
        
        # Process the pickle file if provided
        if pickle_file:
            try:
                # Process the pickle file to get onsets and offsets
                onsets, offsets = process_pickle_file(pickle_file)
            except Exception as e:
                logger.error(f"Error processing pickle file: {str(e)}")
                logger.error(traceback.format_exc())
                return recording, segments_created
        
        # Create segments if we have onset/offset data
        if onsets and offsets and len(onsets) == len(offsets):
            try:
                with transaction.atomic():
                    # First, create the segmentation object
                    segmentation = Segmentation(
                        recording=recording,
                        status='completed',  # Already completed since we have the data
                        progress=100,
                        created_by=batch.created_by
                    )
                    segmentation.save()
                    
                    # Now create the segments
                    for i in range(len(onsets)):
                        # Create segment name
                        segment_name = f"Segment {i+1}"
                        
                        # Convert numpy types to Python native types if needed
                        onset_value = float(onsets[i])
                        offset_value = float(offsets[i])
                        
                        # Create and save the segment
                        segment = Segment(
                            recording=recording,
                            name=segment_name,
                            onset=onset_value,
                            offset=offset_value,
                            created_by=batch.created_by
                        )
                        segment.save()
                        segments_created += 1
                
                logger.info(f"Created segmentation with {segments_created} segments for recording from task batch {batch.name}")
            except Exception as e:
                logger.error(f"Error creating segments: {str(e)}")
                logger.error(traceback.format_exc())
        
        return recording, segments_created
        
    except Exception as e:
        logger.error(f"Error creating recording from task batch: {str(e)}")
        logger.error(traceback.format_exc())
        return None, 0


def create_demo_task_batch(user):
    """Create a demo task batch for a new user using sample files.

    Args:
        user: The User object to create the task batch for

    Returns:
        TaskBatch or None: The created TaskBatch object, or None if creation failed
    """
    import pickle
    import traceback

    from django.core.files import File
    from django.db import transaction

    from .models import Project, Species, Task, TaskBatch
    from .audio.utils import process_pickle_file

    logger.info(f"Creating demo task batch for user {user.username}")

    # Get the user's group and profile
    profile = user.profile
    group = profile.group
    if not group:
        logger.warning(f"User {user.username} has no group, skipping task batch creation")
        return None

    # Find the user's demo project
    try:
        project = Project.objects.filter(group=group, name__contains="Demo Project").first()

        if not project:
            logger.warning(f"No demo project found for {user.username}, skipping task batch creation")
            return None

        # Find the Carollia species
        species = Species.objects.filter(group=group, name="Carollia").first()

        if not species:
            logger.warning(f"No Carollia species found for {user.username}, skipping task batch creation")
            return None

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
            return None

        # Find the sample pickle file
        pickle_path = None
        for path in sample_paths["pickle"]:
            if os.path.exists(path):
                pickle_path = path
                break

        if not pickle_path:
            logger.warning("Sample pickle file not found, skipping task batch creation")
            return None

        # Create the task batch
        batch_name = "Demo Bat Calls"

        # Create and save the TaskBatch
        batch = TaskBatch(
            name=batch_name,
            description="Sample bat calls for demonstration and practice",
            created_by=user,
            wav_file_name="bat1_angie_19.wav",
            species=species,
            project=project,
            group=group,
        )

        # Save the batch to get an ID
        batch.save()

        # Attach the WAV file
        with open(wav_path, "rb") as wav_file:
            batch.wav_file.save("bat1_angie_19.wav", File(wav_file), save=True)

        logger.info(f"Created task batch {batch.name} for user {user.username}")

        # Load the pickle file and process it once to get onsets and offsets
        try:
            with open(pickle_path, "rb") as f:
                # Process the pickle file using our standard utility
                onsets, offsets = process_pickle_file(f)
            
            # Create tasks for each onset-offset pair inside a transaction
            tasks_created = 0
            with transaction.atomic():
                # Only use the first 10 entries to keep the demo manageable
                max_entries = min(10, len(onsets))

                for i in range(max_entries):
                    try:
                        # Convert numpy types to Python native types if needed
                        onset_value = float(onsets[i])
                        offset_value = float(offsets[i])

                        # Create and save the task
                        task = Task(
                            wav_file_name=batch.wav_file_name,
                            onset=onset_value,
                            offset=offset_value,
                            species=batch.species,
                            project=batch.project,
                            batch=batch,
                            created_by=user,
                            group=group,
                            status="pending",
                        )
                        task.save()
                        tasks_created += 1
                    except Exception as e:
                        logger.error(f"Error creating task {i}: {str(e)}")
                        logger.error(traceback.format_exc())
                        raise  # Re-raise to trigger transaction rollback

            logger.info(f"Created {tasks_created} tasks for batch {batch.name}")
            
            # Create recording and segments using the same onsets/offsets
            try:
                # Use our utility function to create the recording and segments
                recording, segments_created = create_recording_from_batch(batch, onsets=onsets, offsets=offsets)
                
                if recording:
                    logger.info(f"Created recording with {segments_created} segments for demo batch {batch.name}")
                else:
                    logger.warning(f"Failed to create recording for demo batch {batch.name}")
            except Exception as e:
                logger.error(f"Error creating recording from demo batch: {str(e)}")
                logger.error(traceback.format_exc())
                # Don't fail task batch creation if recording creation fails
            
            return batch

        except Exception as e:
            logger.error(f"Error processing pickle file: {str(e)}")
            logger.error(traceback.format_exc())

            # Delete the batch if pickle processing failed
            if batch.id:
                batch.delete()

            return None

    except Exception as e:
        logger.error(f"Error creating demo task batch: {str(e)}")
        logger.error(traceback.format_exc())
        return None
