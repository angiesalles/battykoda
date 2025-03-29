"""
BattyCoda Models Package

This package contains all the application models organized into logical modules:
- user.py: User profiles, groups, and authentication models
- organization.py: Projects, species, and organizational models
- recording.py: Recording, segments, and segmentation models
- task.py: Task and task batch models
- detection.py: Detection and classification models
- utils.py: Utility functions and helpers
"""

# Detection models
from .detection import CallProbability, Classifier, DetectionResult, DetectionRun

# Organization models
from .organization import Call, Project, Species

# Recording models
from .recording import Recording, Segment, Segmentation, SegmentationAlgorithm

# Task models
from .task import Task, TaskBatch

# User models
from .user import Group, GroupInvitation, GroupMembership, UserProfile
