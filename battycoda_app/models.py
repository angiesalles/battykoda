"""
BattyCoda Models Module

Re-exports all model classes from the models package for backward compatibility.
"""

from battycoda_app.models.detection import CallProbability, Classifier, DetectionResult, DetectionRun
from battycoda_app.models.organization import Call, Project, Species
from battycoda_app.models.recording import Recording, Segment, Segmentation, SegmentationAlgorithm
from battycoda_app.models.task import Task, TaskBatch

# Re-export all models from the models package
from battycoda_app.models.user import Group, GroupInvitation, GroupMembership, UserProfile

# For backwards compatibility, if any code directly imports from this file
__all__ = [
    # User models
    "Group",
    "GroupInvitation",
    "GroupMembership",
    "UserProfile",
    # Organization models
    "Project",
    "Species",
    "Call",
    # Recording models
    "Recording",
    "Segment",
    "Segmentation",
    "SegmentationAlgorithm",
    # Task models
    "Task",
    "TaskBatch",
    # Detection models
    "Classifier",
    "DetectionRun",
    "DetectionResult",
    "CallProbability",
]
