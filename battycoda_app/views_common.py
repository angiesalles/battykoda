"""
Common imports and utilities for views modules.
"""
import fnmatch
import hashlib
import logging
import mimetypes
import os
import re
import traceback
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .audio.utils import process_pickle_file
from .forms import RecordingForm, SegmentForm, SegmentFormSetFactory
from .models import Group, Recording, Segment, Segmentation, UserProfile

# Default chunk size for streaming (1MB)
CHUNK_SIZE = 1024 * 1024

# Set up logging
logger = logging.getLogger("battycoda.views_common")
