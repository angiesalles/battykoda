"""
Utility functions for the battycoda application.
"""
import logging
import os
import platform
import shutil
import subprocess

from django.conf import settings

# Set up logging
logger = logging.getLogger("battycoda.utils")


def get_home_directory():
    """
    Get the system home directory based on platform

    Returns:
        str: Path to the home directory
    """
    if platform.system() == "Windows":
        return "Users"
    else:
        return "home"


def get_template_directory():
    """
    Find the template directory for user directory creation and species templates

    Returns:
        str: Path to the template directory, or None if not found
    """
    # List of possible template directory locations
    template_dirs = [
        "/template",  # Docker mount (primary)
        "/app/template",  # Project directory in Docker
        os.path.join(settings.BASE_DIR, "template"),  # Django project base
        "/home/ubuntu/template",  # Host system location
    ]

    # Try each location
    for template_dir in template_dirs:
        if os.path.exists(template_dir):
            logger.info(f"Found template directory at: {template_dir}")
            return template_dir

    # No template directory found
    logger.warning("No template directory found in any location")
    return None


def convert_path_to_os_specific(path):
    """
    Convert a web path to an OS-specific path

    Args:
        path (str): Web path (like "home/username/folder")

    Returns:
        str: OS-specific path to the location in media directory
    """
    # Normalize directory separators
    path = path.replace("\\", "/")

    # Remove leading slash if present
    if path.startswith("/"):
        path = path[1:]

    # All user paths now go to media folder
    return os.path.join(settings.MEDIA_ROOT, path)


def ensure_user_directory_exists(username):
    """
    Ensure that a user's home directory exists, create it if it doesn't

    Args:
        username (str): Username to check/create directory for

    Returns:
        bool: True if directory exists or was created
    """
    # Get template directory
    template_dir = "/template"

    # Store user directories in media folder (shared between containers)
    user_home_path = os.path.join(settings.MEDIA_ROOT, "home", username)

    # Return if directory already exists
    if os.path.exists(user_home_path):
        return True

    # Create the directory
    logger.info(f"Creating user home directory: {user_home_path}")
    os.makedirs(user_home_path, exist_ok=True)

    # Copy template content
    for item in os.listdir(template_dir):
        source = os.path.join(template_dir, item)
        destination = os.path.join(user_home_path, item)

        if os.path.isdir(source):
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)

    # Set permissions to make directories writable by everyone
    subprocess.run(["chmod", "-R", "777", user_home_path])
    logger.info(f"Set permissions for {user_home_path}")

    return True


def available_species():
    """
    Get a list of available species templates

    Returns:
        list: List of species template names
    """
    try:
        # Get template directory
        template_dir = get_template_directory()
        if not template_dir:
            logger.warning("Cannot list available species: No template directory found")
            return []

        # Get list of directories in template
        species_list = [
            item
            for item in os.listdir(template_dir)
            if os.path.isdir(os.path.join(template_dir, item)) and not item.startswith(".")
        ]

        return sorted(species_list)

    except Exception as e:
        logger.error(f"Error getting available species: {str(e)}")
        return []


def import_default_species(user):
    """Import default species (Carollia and Efuscus) for a new user's team

    Args:
        user: The User object to import species for

    Returns:
        list: List of created Species objects
    """
    import time
    import traceback

    from django.core.files import File

    from .models import Call, Species

    # Add a delay to ensure user creation transaction is complete
    time.sleep(1)

    logger.info(f"Importing default species for user {user.username}")

    # Get the user's team
    team = user.profile.team
    if not team:
        logger.warning(f"User {user.username} has no team, skipping species import")
        return []

    created_species = []

    # Define the default species to import
    default_species = [
        {
            "name": "Carollia",
            "image_file": "Carollia.png",
            "call_file": "Carollia.txt",
            "description": "Carollia is a genus of short-tailed leaf-nosed bats. Their calls include various types such as aggressive warbles, distress calls, and echolocation.",
        },
        {
            "name": "Efuscus",
            "image_file": "Efuscus.jpg",
            "call_file": "Efuscus.txt",
            "description": "Eptesicus fuscus (big brown bat) is a species found across North America. Their calls range from frequency-modulated sweeps to quasi-constant frequency calls.",
        },
    ]

    # Import each species
    for species_data in default_species:
        # Create a unique name for this team
        unique_name = f"{species_data['name']} - {team.name}"

        # Skip if species already exists for this team
        if Species.objects.filter(name=unique_name).exists():
            logger.info(f"Species {unique_name} already exists")
            continue

        try:
            # Create the species with a unique name
            species = Species.objects.create(
                name=unique_name, description=species_data["description"], created_by=user, team=team
            )
            logger.info(f"Created species {species.name} for team {team.name}")

            # Add the image if it exists
            # Use explicit paths for Docker container
            image_paths = [
                f"/app/static/{species_data['image_file']}",
                f"/home/ubuntu/battycoda/static/{species_data['image_file']}",
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
                f"/app/static/{species_data['call_file']}",
                f"/home/ubuntu/battycoda/static/{species_data['call_file']}",
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


def create_demo_task_batch(user):
    """Create a demo task batch for a new user using sample files

    Args:
        user: The User object to create the task batch for

    Returns:
        TaskBatch or None: The created TaskBatch object, or None if creation failed
    """
    import pickle
    import traceback

    from django.core.files import File
    from django.db import transaction

    import numpy as np

    from .models import Project, Species, Task, TaskBatch

    logger.info(f"Creating demo task batch for user {user.username}")

    # Get the user's team and profile
    profile = user.profile
    team = profile.team
    if not team:
        logger.warning(f"User {user.username} has no team, skipping task batch creation")
        return None

    # Find the user's demo project
    try:
        project = Project.objects.filter(team=team, name__contains="Demo Project").first()

        if not project:
            logger.warning(f"No demo project found for {user.username}, skipping task batch creation")
            return None

        # Find the Carollia species
        species = Species.objects.filter(team=team, name__contains="Carollia").first()

        if not species:
            logger.warning(f"No Carollia species found for {user.username}, skipping task batch creation")
            return None

        # Define the paths to the sample files
        sample_paths = {
            "wav": ["/app/static/bat1_angie_19.wav", "/home/ubuntu/battycoda/static/bat1_angie_19.wav"],
            "pickle": [
                "/app/static/bat1_angie_19.wav.pickle",
                "/home/ubuntu/battycoda/static/bat1_angie_19.wav.pickle",
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
        batch_name = f"Demo Bat Calls - {user.username}"

        # Create and save the TaskBatch
        batch = TaskBatch(
            name=batch_name,
            description="Sample bat calls for demonstration and practice",
            created_by=user,
            wav_file_name="bat1_angie_19.wav",
            species=species,
            project=project,
            team=team,
        )

        # Save the batch to get an ID
        batch.save()

        # Attach the WAV file
        with open(wav_path, "rb") as wav_file:
            batch.wav_file.save("bat1_angie_19.wav", File(wav_file), save=True)

        logger.info(f"Created task batch {batch.name} for user {user.username}")

        # Load the pickle file
        try:
            with open(pickle_path, "rb") as f:
                pickle_data = pickle.load(f)

            # Extract onsets and offsets
            if isinstance(pickle_data, dict):
                onsets = pickle_data.get("onsets", [])
                offsets = pickle_data.get("offsets", [])
            elif isinstance(pickle_data, (list, tuple)) and len(pickle_data) >= 2:
                onsets = pickle_data[0]
                offsets = pickle_data[1]
            else:
                logger.error(f"Pickle file format not recognized")
                return batch

            # Convert to lists if they're NumPy arrays
            if isinstance(onsets, np.ndarray):
                onsets = onsets.tolist()
            if isinstance(offsets, np.ndarray):
                offsets = offsets.tolist()

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
                            team=team,
                            status="pending",
                        )
                        task.save()
                        tasks_created += 1
                    except Exception as e:
                        logger.error(f"Error creating task {i}: {str(e)}")
                        logger.error(traceback.format_exc())
                        raise  # Re-raise to trigger transaction rollback

            logger.info(f"Created {tasks_created} tasks for batch {batch.name}")
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
