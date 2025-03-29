"""
Common imports and utilities for segmentation views.
"""
import fnmatch
import hashlib
import logging
import os
import traceback

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from battycoda_app.forms import SegmentForm

# Import models directly using absolute imports
from battycoda_app.models import Recording, Segment, Segmentation

# Set up logging
logger = logging.getLogger("battycoda.views_segmentation")
