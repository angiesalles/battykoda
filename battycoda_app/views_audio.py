import logging

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

# Set up logging
logger = logging.getLogger("battycoda.views_audio")


@login_required
def spectrogram_view(request):
    """Handle spectrogram generation and serving"""
    from .audio.views import handle_spectrogram

    return handle_spectrogram(request)


@login_required
def audio_snippet_view(request):
    """Handle audio snippet generation and serving"""
    from .audio.views import handle_audio_snippet

    return handle_audio_snippet(request)


@login_required
def test_static_view(request, filename):
    """Test static file serving"""
    import os

    from django.conf import settings

    # Handle empty filename case
    if not filename:
        return HttpResponse("No filename provided", status=400)

    file_path = os.path.join(settings.STATIC_ROOT, filename)
    if os.path.exists(file_path):
        return FileResponse(open(file_path, "rb"))
    else:
        return HttpResponse(f"File not found: {filename}", status=404)
