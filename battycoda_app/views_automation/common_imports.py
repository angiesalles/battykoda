"""Common imports for automation views."""

import logging
import traceback

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

# Import models using absolute imports to avoid circular references
from battycoda_app.models import (
    Call,
    CallProbability,
    Classifier,
    DetectionResult,
    DetectionRun,
    Segment,
    Segmentation,
    Task,
    TaskBatch,
)

# Set up logging
logger = logging.getLogger("battycoda.views_automation")

# Export all common imports
__all__ = [
    # Python standard library
    "logging",
    "traceback",
    # Django imports
    "messages",
    "login_required",
    "models",
    "transaction",
    "JsonResponse",
    "get_object_or_404",
    "redirect",
    "render",
    "timezone",
    # Models
    "Call",
    "CallProbability",
    "Classifier",
    "DetectionResult",
    "DetectionRun",
    "Segment",
    "Segmentation",
    "Task",
    "TaskBatch",
    # Logging
    "logger",
]
