import logging
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# Set up logging
logger = logging.getLogger("battycoda.views_directory")


@login_required
def home_view(request):
    """Home page showing user directories and templates"""
    from .directory_handlers import list_users_directory

    return list_users_directory(request)


@login_required
def user_directory_view(request, username):
    """List the species directories for a user"""
    from .directory_handlers import list_species_directory
    from .utils import ensure_user_directory_exists

    # If the directory doesn't exist, create it from template (only for the current user)
    if request.user.username == username:
        user_dir_path = os.path.join("/home", username)
        if not os.path.exists(user_dir_path):
            logger.info(f"Auto-creating directory for user {username}")
            ensure_user_directory_exists(username)

    return list_species_directory(request, f"home/{username}", username)


@login_required
def species_directory_view(request, username, species):
    """List the contents of a species directory"""
    from .directory_handlers import list_project_directory

    return list_project_directory(request, f"home/{username}/{species}", username, species)


@login_required
def subdirectory_view(request, username, species, subpath):
    """List the contents of a subdirectory within a species directory"""
    from .directory_handlers import list_project_directory

    path = f"home/{username}/{species}/{subpath}"
    return list_project_directory(request, path, username, species)


@login_required
def species_info_view(request, species_name):
    """Display information about bat species templates"""
    # TODO: Implement the species info view
    context = {
        "species_name": species_name,
        "listicle": f"<h2>Species: {species_name}</h2><p>Information about this species template.</p>",
    }

    return render(request, "listBC.html", context)


@login_required
@csrf_exempt  # Properly exempt this view from CSRF protection
@require_http_methods(["GET", "POST"])
def create_directory_view(request):
    """Create a new directory in user's space"""

    if request.method == "POST":
        path = request.POST.get("path")
        directory_name = request.POST.get("directory_name")

        if not path or not directory_name:
            messages.error(request, "Path and directory name are required.")
            return redirect("battycoda_app:index")

        try:
            # Validate directory name (prevent path traversal)
            if "/" in directory_name or "\\" in directory_name or ".." in directory_name:
                messages.error(request, "Invalid directory name.")
                return redirect(f"/{path}/")

            # Create the directory
            import os

            from .utils import convert_path_to_os_specific

            # Convert path to OS specific
            full_path = convert_path_to_os_specific(f"{path}/{directory_name}")

            # Check if directory already exists
            if os.path.exists(full_path):
                messages.error(request, f"Directory {directory_name} already exists.")
                return redirect(f"/{path}/")

            # Create the directory
            os.makedirs(full_path, exist_ok=True)

            # Set directory permissions to be writable
            try:
                import subprocess

                subprocess.run(["chmod", "-R", "777", full_path])
                logger.info(f"Set permissions for {full_path}")
            except Exception as e:
                logger.warning(f"Could not set permissions for {full_path}: {str(e)}")

            messages.success(request, f"Directory {directory_name} created successfully.")

        except Exception as e:
            logger.error(f"Error creating directory: {str(e)}")
            messages.error(request, f"Error creating directory: {str(e)}")

        # Check if AJAX request
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": True, "message": f"Directory {directory_name} created successfully."})

        return redirect(f"/{path}/")

    return redirect("battycoda_app:index")


@login_required
@csrf_exempt  # Properly exempt this view from CSRF protection
@require_http_methods(["GET", "POST"])
def upload_file_view(request):
    """Handle file uploads"""
    if request.method == "POST":
        path = request.POST.get("path")
        file = request.FILES.get("file")

        if not file:
            messages.error(request, "No file selected.")
            return redirect(f"/{path}/")

        try:
            # Validate filename (prevent path traversal)
            filename = file.name
            if "/" in filename or "\\" in filename or ".." in filename:
                messages.error(request, "Invalid filename.")
                return redirect(f"/{path}/")

            # Save the file
            import os

            from .utils import convert_path_to_os_specific

            # Convert path to OS specific
            full_path = convert_path_to_os_specific(f"{path}/{filename}")

            # Check if file already exists
            if os.path.exists(full_path):
                messages.error(request, f"File {filename} already exists.")
                return redirect(f"/{path}/")

            # Save the file
            with open(full_path, "wb+") as destination:
                for chunk in file.chunks():
                    destination.write(chunk)

            messages.success(request, f"File {filename} uploaded successfully.")

        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            error_message = f"Error uploading file: {str(e)}"
            messages.error(request, error_message)

            # If this is an AJAX request, return error in JSON
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": error_message}, status=500)

        # Check if AJAX request
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": True,
                    "message": f"File {filename} uploaded successfully.",
                    "file_name": filename,
                    "path": path,
                }
            )

        return redirect(f"/{path}/")

    return redirect("battycoda_app:index")
