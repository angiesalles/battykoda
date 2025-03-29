import logging
import os

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

# Set up logging
logger = logging.getLogger("battycoda.views_debug")


@login_required
def debug_env_view(request):
    """Debug view to show environment variables"""
    if not request.user.is_staff and not request.user.is_superuser:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    env_vars = {
        "SECRET_KEY": os.environ.get("SECRET_KEY", "Not found"),
        "DEBUG": os.environ.get("DEBUG", "Not found"),
        "DOMAIN_NAME": os.environ.get("DOMAIN_NAME", "Not found"),
        "DJANGO_SETTINGS_MODULE": os.environ.get("DJANGO_SETTINGS_MODULE", "Not found"),
    }

    return JsonResponse(env_vars)
