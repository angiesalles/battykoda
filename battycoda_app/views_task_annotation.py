import hashlib
import logging
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Species, Task
from .utils import convert_path_to_os_specific

# Set up logging
logger = logging.getLogger("battycoda.views_task_annotation")


@login_required
def task_annotation_view(request, task_id):
    """Show the annotation interface for a specific task"""
    # Get the task - allow team members to access tasks from the same team
    task = get_object_or_404(Task, id=task_id)

    # Check if user has permission to view this task
    if task.created_by != request.user and (not request.user.profile.team or task.team != request.user.profile.team):
        messages.error(request, "You don't have permission to view this task.")
        return redirect("battycoda_app:task_list")

    # Handle task update if form submitted
    if request.method == "POST":
        # Check if the "mark as done" button was clicked
        if "mark_done" in request.POST:
            label = request.POST.get("type_call", "")
            # Handle custom "other" label
            if not label and "other_call" in request.POST:
                label = request.POST.get("other_call", "")

            # Update the task
            task.label = label
            task.is_done = True
            task.status = "done"
            task.save()

            messages.success(request, "Task marked as done with label: " + label)

            # Redirect to the next task
            return redirect("battycoda_app:get_next_task")

    # Get hash of the wav file for validation
    # Extract the wav file information from the task
    wav_file_name = task.wav_file_name
    species = task.species

    # Path to the WAV file - check if it's in the media directory (uploaded file)
    if task.batch and task.batch.wav_file:
        # Get the path from the uploaded file in the batch
        wav_url = task.batch.wav_file.url
        full_path = task.batch.wav_file.path
        os_path = full_path
    else:
        # Assume the path is based on the project structure (old way)
        full_path = os.path.join("home", request.user.username, species, task.project, wav_file_name)
        os_path = convert_path_to_os_specific(full_path)
        wav_url = f"/{full_path}"

    # Create hash
    file_hash = hashlib.md5(os_path.encode()).hexdigest()
    logger.info(f"Generated hash {file_hash} for path {os_path}")

    # Set up onset and offset as a "call"
    # In our case, we'll treat each task as one "call"
    total_calls = 1

    # Get call types from the database (preferred) or fall back to text file
    call_types = []
    call_descriptions = {}  # To store full descriptions for tooltips

    # Try to get call types from the database first
    species_obj = None
    try:
        # First try exact match (for backward compatibility)
        try:
            species_obj = Species.objects.get(name=species)
        except Species.DoesNotExist:
            # If not found, try with team-based naming format
            # Look for a species that starts with the species name followed by " - "
            species_obj = Species.objects.filter(name__startswith=f"{species} - ").first()

            # If still not found, try looking up by team
            if not species_obj and hasattr(request.user, "profile") and request.user.profile.team:
                species_obj = Species.objects.filter(
                    name__startswith=f"{species} - ", team=request.user.profile.team
                ).first()

            if not species_obj:
                # Last resort, just use the first matching species name
                species_obj = Species.objects.filter(name__startswith=f"{species}").first()

            if not species_obj:
                raise Species.DoesNotExist(f"No species found matching '{species}'")

        # Get calls from the database
        calls = species_obj.calls.all()
        if calls.exists():
            for call in calls:
                call_types.append(call.short_name)
                # Use long_name as the description if available
                description = call.long_name if call.long_name else ""
                call_descriptions[call.short_name] = description

            logger.info(f"Loaded {len(call_types)} call types from database for species {species_obj.name}")
    except Species.DoesNotExist:
        logger.warning(f"Species {species} not found in database")
    except Exception as e:
        logger.error(f"Error loading call types from database: {str(e)}")

    # If no call types were loaded from the database, log a warning
    if not call_types:
        logger.warning(f"No call types found in database for species {species}")
        # Add a default "Unknown" call type to ensure the interface has at least one option
        call_types.append("Unknown")
        call_descriptions["Unknown"] = "Unspecified call type"

    # Get pre-generated spectrogram URLs
    from .audio.utils import appropriate_file

    # Create cache paths for spectrograms
    spectrogram_urls = {}
    for channel in [0, 1]:
        for is_overview in [True, False]:
            # Create args for the spectrogram
            spectrogram_args = {
                "call": "0",
                "channel": str(channel),
                "numcalls": "1",
                "hash": file_hash,
                "overview": "1" if is_overview else "0",
                "contrast": "4.0",
            }

            # Add onset/offset to args
            spectrogram_args["onset"] = str(task.onset)
            spectrogram_args["offset"] = str(task.offset)

            # Generate the file path
            cache_path = appropriate_file(full_path, spectrogram_args)

            # Check if the file exists, if not, trigger generation
            if not os.path.exists(cache_path):
                # Trigger spectrogram generation
                logger.info(f"Pre-generating spectrogram: channel={channel}, overview={is_overview}")
                task.generate_spectrograms()

            # Create a URL for the spectrogram (that will be handled by spectrogram_view)
            spectrogram_url = f"/spectrogram/?wav_path={full_path}&call=0&channel={channel}&numcalls=1&hash={file_hash}&overview={'1' if is_overview else '0'}&contrast=4.0&onset={task.onset}&offset={task.offset}"

            # Store in the dictionary with a descriptive key
            key = f"channel_{channel}_{'overview' if is_overview else 'detail'}"
            spectrogram_urls[key] = spectrogram_url

    # Calculate midpoint time for axis
    midpoint_time = (task.onset + task.offset) / 2

    # Get window size for the spectrogram
    from .audio.utils import normal_hwin

    normal_window_size = normal_hwin()

    # Create context for the template
    context = {
        "task": task,
        "username": request.user.username,
        "species": species,
        "species_obj": species_obj,  # Add the species object to the context
        "wav_path": wav_file_name,
        "full_path": full_path,
        "wav_url": wav_url,
        "file_hash": file_hash,
        "total_calls": total_calls,
        "call_types": call_types,
        "call_descriptions": call_descriptions,
        "onset": task.onset,
        "offset": task.offset,
        "midpoint_time": midpoint_time,  # Add midpoint time for x-axis
        "spectrogram_urls": spectrogram_urls,  # Add pre-generated spectrogram URLs
        "normal_hwin": normal_window_size,  # Add window size for time axis in milliseconds
    }

    # Return the annotation interface
    return render(request, "tasks/annotate_task.html", context)
