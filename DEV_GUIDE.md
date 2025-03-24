# BattyCoda Developer Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Project Overview](#project-overview)
3. [System Architecture](#system-architecture)
4. [Development Environment Setup](#development-environment-setup)
5. [Application Structure](#application-structure)
6. [Core Components](#core-components)
7. [Data Models](#data-models)
8. [Authentication and Authorization](#authentication-and-authorization)
9. [Audio Processing System](#audio-processing-system)
10. [Task Processing Workflow](#task-processing-workflow)
11. [API Endpoints](#api-endpoints)
12. [Frontend Templates](#frontend-templates)
13. [Asynchronous Task Processing](#asynchronous-task-processing)
14. [R Integration](#r-integration)
15. [Docker Deployment](#docker-deployment)
16. [Cloudflare Integration](#cloudflare-integration)
17. [Testing](#testing)
18. [Common Development Tasks](#common-development-tasks)
19. [Troubleshooting](#troubleshooting)
20. [Contribution Guidelines](#contribution-guidelines)

## Introduction

BattyCoda is a comprehensive web application for analyzing animal vocalizations, with a particular focus on bat echolocation calls. It allows researchers to upload, analyze, classify, and annotate audio files containing animal vocalizations.

The system integrates Django for the web application, Celery for asynchronous processing, R for advanced audio analysis, and offers team-based collaboration features. This developer guide provides an in-depth overview of the BattyCoda system architecture, components, and development processes.

## Project Overview

### Purpose

BattyCoda serves as a collaborative platform for researchers studying animal vocalizations. It provides tools for:

- Uploading and organizing audio recordings
- Automatically extracting and visualizing vocalizations as spectrograms
- Classifying calls using machine learning algorithms
- Manually annotating and labeling calls
- Organizing research into projects and teams
- Tracking progress on annotation tasks

### Key Features

- **Team-based Access Control**: Researchers can work in teams with specific permissions
- **Project Management**: Organize work into distinct research projects
- **Species Database**: Maintain a database of species with associated call types
- **Task Batch Processing**: Process audio files in batches to extract call segments
- **Spectrogram Generation**: Visualize audio segments as spectrograms
- **Classification**: Automatic call classification using R-based machine learning
- **Manual Annotation**: Interface for experts to review and label calls
- **Asynchronous Processing**: Handle resource-intensive tasks in the background

## System Architecture

BattyCoda follows a modern web application architecture with several integrated components:

### High-Level Architecture

```
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│  Web Browser  │◄────────▶   Django App  │◄────────▶   Database    │
└───────────────┘         └───────┬───────┘         └───────────────┘
                                 ▲│
                                 ││
                                 │▼
                          ┌──────────────┐          ┌───────────────┐
                          │ Celery Queue │◄─────────▶ Redis Server  │
                          └──────┬───────┘          └───────────────┘
                                ▲│
                                ││
                                │▼
                          ┌───────────────┐         ┌───────────────┐
                          │ Celery Worker │◄────────▶ R API Server  │
                          └───────────────┘         └───────────────┘
                                 │                         │
                                 ▼                         ▼
                          ┌───────────────────────────────────────────┐
                          │               File System                  │
                          │ (Audio Files, Spectrograms, Media, Cache) │
                          └───────────────────────────────────────────┘
```

### Key Components

1. **Django Web Application**: Handles HTTP requests, renders templates, manages models
2. **Celery Task Queue**: Manages asynchronous and background tasks
3. **Redis**: Used as a message broker for Celery and for caching
4. **R Servers**: Specialized servers for audio analysis and machine learning
5. **SQLite Database**: Stores application data (species, projects, tasks, users)
6. **File System**: Stores audio files, generated spectrograms, and other media

## Development Environment Setup

### Prerequisites

- Python 3.8+
- R (latest version)
- Redis server
- Git

### Installation Steps

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd battycoda
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install required R packages:
   ```bash
   Rscript setup_r_packages.R
   ```

5. Apply database migrations:
   ```bash
   python manage.py migrate
   ```

6. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```

7. Initialize default data:
   ```bash
   python manage.py initialize_defaults
   ```

8. Run the development server:
   ```bash
   python manage.py runserver
   ```

### Running with Docker

For a complete development environment using Docker:

```bash
docker-compose up
```

This will start all required services:
- Django web application on port 8060
- Celery workers for task processing
- Redis server for messaging
- R server for audio analysis (port 8100)
- Flower dashboard for monitoring Celery tasks (port 5555)

## Application Structure

BattyCoda follows a typical Django project structure with additional components for Celery and R integration.

### Directory Structure

```
battycoda/
├── battycoda/                  # Original project configuration (legacy)
├── battycoda_app/              # Main Django application
│   ├── admin.py                # Admin interface configuration
│   ├── apps.py                 # App configuration
│   ├── audio/                  # Audio processing submodule
│   │   ├── apps.py
│   │   ├── tasks.py            # Celery tasks for audio processing
│   │   ├── utils.py            # Audio utility functions
│   │   └── views.py            # Views for audio processing
│   ├── directory_handlers.py   # File system operations
│   ├── forms.py                # Form definitions
│   ├── management/             # Custom management commands
│   ├── middleware/             # Custom middleware (e.g., Cloudflare)
│   ├── migrations/             # Database migrations
│   ├── models.py               # Data models
│   ├── signals.py              # Signal handlers
│   ├── tasks.py                # General Celery tasks
│   ├── templatetags/           # Custom template tags
│   ├── tests.py                # Unit tests
│   ├── urls.py                 # URL routing
│   ├── utils.py                # Utility functions
│   └── views.py                # View functions
├── config/                     # Django project settings
│   ├── asgi.py                 # ASGI configuration
│   ├── celery.py               # Celery configuration
│   ├── settings.py             # Django settings
│   ├── urls.py                 # Project URL routing
│   └── wsgi.py                 # WSGI configuration
├── data/                       # Data directory (machine learning models, etc.)
├── media/                      # User-uploaded files
│   ├── audio_cache/            # Generated audio snippets
│   └── task_batches/           # Uploaded audio files
├── static/                     # Static files (CSS, JS, images)
│   ├── css/                    # CSS files
│   ├── js/                     # JavaScript files
│   └── mymodel.RData           # R machine learning model
├── staticfiles/                # Collected static files for production
├── templates/                  # HTML templates
│   ├── audio/                  # Audio-related templates
│   ├── auth/                   # Authentication templates
│   ├── base.html               # Base template
│   ├── projects/               # Project management templates
│   ├── species/                # Species management templates
│   ├── tasks/                  # Task management templates
│   └── teams/                  # Team management templates
├── manage.py                   # Django management script
├── requirements.txt            # Python dependencies
├── r_server_direct.R           # R server for audio analysis
├── setup_r_packages.R          # R package installation script
└── docker-compose.yml          # Docker Compose configuration
```

## Core Components

### Django Project Configuration

The `config` directory contains the main Django project settings:

- **settings.py**: Core configuration, including database, middleware, installed apps
- **celery.py**: Celery task queue configuration
- **urls.py**: Main URL routing

### Main Application

The `battycoda_app` directory contains the main Django application:

- **models.py**: Data models (Team, User, Species, Project, Task, etc.)
- **views.py**: View functions for handling HTTP requests
- **urls.py**: URL routing for the application
- **admin.py**: Django admin interface configuration

### Audio Processing Module

The `battycoda_app/audio` subdirectory contains specialized code for audio processing:

- **tasks.py**: Celery tasks for generating spectrograms and processing audio
- **utils.py**: Utility functions for audio processing
- **views.py**: Views for serving spectrograms and audio snippets

### Asynchronous Task Processing

Celery is used for asynchronous task processing:

- **config/celery.py**: Celery configuration
- **battycoda_app/tasks.py**: General tasks
- **battycoda_app/audio/tasks.py**: Audio-specific tasks

### R Integration

R is used for advanced audio analysis and machine learning:

- **r_server_direct.R**: R server using Plumber for API endpoints
- **r_prediction_server.R**: R server for predictions
- **static/mymodel.RData**: Pre-trained machine learning model

## Data Models

BattyCoda uses several interconnected data models to organize research work:

### Team

Teams are groups of users collaborating on research projects.

```python
class Team(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### UserProfile

Extends the Django User model with additional fields.

```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members', null=True)
    is_admin = models.BooleanField(default=False)
    # Cloudflare fields
    cloudflare_id = models.CharField(max_length=255, blank=True, null=True)
    is_cloudflare_user = models.BooleanField(default=False)
    cloudflare_email = models.EmailField(blank=True, null=True)
    last_cloudflare_login = models.DateTimeField(blank=True, null=True)
```

### Species

Represents an animal species with associated call types.

```python
class Species(models.Model):
    name = models.CharField(max_length=100, unique=True)
    scientific_name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='species_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='species')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='species', null=True)
```

### Call

Represents a type of vocalization associated with a species.

```python
class Call(models.Model):
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name='calls')
    short_name = models.CharField(max_length=50)
    long_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Project

Research projects that contain tasks and task batches.

```python
class Project(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='projects', null=True)
```

### TaskBatch

Groups of tasks created together from a single audio file.

```python
class TaskBatch(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_batches')
    wav_file_name = models.CharField(max_length=255)
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name='task_batches')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='task_batches')
    wav_file = models.FileField(upload_to='task_batches/', null=True, blank=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='task_batches', null=True)
```

### Task

Individual annotation tasks, typically representing a single vocalization segment.

```python
class Task(models.Model):
    # File information
    wav_file_name = models.CharField(max_length=255)
    
    # Segment information
    onset = models.FloatField(help_text="Start time of the segment in seconds")
    offset = models.FloatField(help_text="End time of the segment in seconds")
    
    # Classification information
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name='tasks')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    
    # Link to batch
    batch = models.ForeignKey(TaskBatch, on_delete=models.CASCADE, related_name='tasks', null=True, blank=True)
    
    # Task metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='tasks', null=True)
    
    # Task status and completion
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('done', 'Done'),  # Special status for fully labeled tasks
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_done = models.BooleanField(default=False)
    
    # Classification and labeling
    classification_result = models.CharField(max_length=100, blank=True, null=True)
    confidence = models.FloatField(blank=True, null=True)
    label = models.CharField(max_length=255, blank=True, null=True)
    
    # Notes and comments
    notes = models.TextField(blank=True, null=True)
```

### Model Relationships

The models form a hierarchical structure:

- Teams contain Users
- Teams own Species, Projects, TaskBatches, and Tasks
- Projects contain TaskBatches and Tasks
- Species have Calls
- TaskBatches contain Tasks

## Authentication and Authorization

BattyCoda uses Django's built-in authentication system with extensions for team-based access control and Cloudflare Access integration.

### User Authentication

- Standard Django authentication (username/password)
- Cloudflare Access authentication (JWT-based)

### Team-Based Authorization

Access to resources (species, projects, tasks) is controlled by team membership:

- Users belong to a single team
- Resources belong to a team
- Users can only access resources that belong to their team
- Team administrators have additional privileges

### Cloudflare Integration

Cloudflare Access provides additional authentication and security:

- JWT token verification
- User identity mapping between Cloudflare and Django users
- CloudflareAccessMiddleware for request validation

## Audio Processing System

The audio processing system is a core component of BattyCoda, responsible for:

1. Extracting vocalization segments from audio files
2. Generating spectrograms for visualization
3. Processing audio snippets for playback
4. Interfacing with R for machine learning classification

### Key Components

- **Audio Views**: Handle HTTP requests for spectrograms and audio snippets
- **Audio Tasks**: Celery tasks for asynchronous processing
- **Audio Utils**: Utility functions for audio processing
- **R Integration**: API calls to R servers for analysis and classification

### Spectrogram Generation

Spectrograms are generated using the following process:

1. Client requests a spectrogram for a specific segment
2. Django checks if the spectrogram exists in cache
3. If not, a Celery task is created to generate it
4. The task uses scipy and matplotlib to process the audio and create the image
5. The spectrogram is cached for future requests
6. The image is served to the client

### Audio Snippet Generation

Audio snippets are processed for playback:

1. Client requests an audio snippet for a specific segment
2. Django extracts the segment from the original audio file
3. The snippet is resampled and processed (slowed down for better analysis)
4. The processed audio is cached and served to the client

## Task Processing Workflow

The task processing workflow in BattyCoda follows these steps:

1. **Task Batch Creation**:
   - User uploads an audio file
   - System analyzes the file to detect vocalizations
   - System creates a TaskBatch and individual Tasks for each detected vocalization

2. **Task Annotation**:
   - User selects a task to annotate
   - System loads the spectrogram and audio snippet
   - User reviews the vocalization and selects a call type
   - User submits the annotation
   - System updates the task status and moves to the next task

3. **Task Management**:
   - Project managers can view task progress
   - Tasks can be filtered by status, species, project, etc.
   - Tasks can be exported for further analysis

### Task States

Tasks can be in one of several states:

- **Pending**: Task created but not yet started
- **In Progress**: Task has been viewed but not completed
- **Completed**: Task has been annotated
- **Done**: Task has been fully reviewed and labeled

## API Endpoints

BattyCoda provides several API endpoints for client-side functionality:

### Spectrogram API

```
GET /spectrogram/
```

Parameters:
- `wav_path`: Path to the WAV file
- `call`: Call number 
- `channel`: Audio channel
- `numcalls`: Total number of calls
- `hash`: File hash for validation
- `overview`: Whether to generate an overview (0/1)
- `contrast`: Contrast value
- `onset`: Start time in seconds (optional)
- `offset`: End time in seconds (optional)
- `async`: Use asynchronous mode (true/false)

### Audio Snippet API

```
GET /audio/snippet/
```

Parameters:
- `wav_path`: Path to the WAV file
- `call`: Call number
- `channel`: Audio channel
- `hash`: File hash for validation
- `overview`: Generate full overview (True/False)
- `loudness`: Volume level
- `onset`: Start time in seconds (optional)
- `offset`: End time in seconds (optional)

### Task Status API

```
GET /status/task/<task_id>/
```

Returns the status of an asynchronous Celery task.

### R Server API

R servers provide additional API endpoints for audio analysis:

```
GET /ping
POST /classify
GET /call_types
GET /debug/model
```

## Frontend Templates

BattyCoda uses Django templates for server-side rendering, with JavaScript for dynamic client-side interactions.

### Main Templates

- **base.html**: Base template with common layout
- **auth/**: Authentication templates (login, register, profile)
- **tasks/**: Task management templates
- **projects/**: Project management templates
- **species/**: Species management templates
- **teams/**: Team management templates

### Task Annotation Template

The task annotation interface (`templates/tasks/annotate_task.html`) is a key component:

- Displays the spectrogram for the current task
- Provides audio playback controls
- Allows selection of call type
- Handles form submission for task annotation
- Provides navigation between tasks

## Asynchronous Task Processing

BattyCoda uses Celery for asynchronous task processing, allowing resource-intensive operations to be performed in the background.

### Celery Configuration

Celery is configured in `config/celery.py`:

- Redis is used as the message broker
- Tasks are auto-discovered from installed apps
- Workers are configured for concurrent processing

### Key Tasks

- **generate_spectrogram_task**: Generates spectrograms from audio segments
- **prefetch_spectrograms**: Prefetches multiple spectrograms for a range of calls

### Task Status Tracking

Task status is tracked using Celery's task tracking system:

- Tasks are assigned a unique ID
- Clients can poll for task status using the task ID
- Task results are stored in Redis

### Flower Dashboard

The Flower dashboard provides a web interface for monitoring Celery tasks:

- Task status and history
- Worker status
- Queue statistics
- Task details and results

Access the dashboard at `http://localhost:5555` when running with Docker.

## R Integration

BattyCoda integrates with R for advanced audio analysis and machine learning classification.

### R Server

An R server is provided:

**r_server_direct.R**: R server using Plumber for API endpoints

### R API Endpoints

The R server provides several API endpoints:

- `/ping`: Check if the server is running
- `/classify`: Classify a bat call
- `/call_types`: Get available call types for a species
- `/debug/model`: Get debug information about the model

### Machine Learning Model

A pre-trained machine learning model is provided in `static/mymodel.RData`. This model is used for classifying bat calls based on acoustic features.

## Docker Deployment

BattyCoda can be deployed using Docker Compose, which provides a complete environment with all required services.

### Docker Services

The `docker-compose.yml` file defines several services:

- **web**: Django web application
- **celery**: Celery worker for task processing
- **flower**: Flower dashboard for monitoring Celery tasks
- **redis**: Redis server for message brokering
- **r-server-direct**: R server using Plumber for API endpoints

### Docker Volumes

Several volumes are used for persistent data:

- **data-volume**: User-uploaded files
- **redis-data**: Redis data
- **r-libs**: R libraries

### Network Configuration

Services use the host network mode for simplified local development.

## Cloudflare Integration

BattyCoda integrates with Cloudflare Access for authentication and security.

### Cloudflare Access

Cloudflare Access provides:

- Identity verification
- Zero Trust access controls
- JWT-based authentication

### Cloudflare Middleware

The `CloudflareAccessMiddleware` validates Cloudflare Access JWT tokens in requests:

- Verifies token authenticity
- Maps Cloudflare identities to Django users
- Creates or updates user profiles

### Configuration

Cloudflare Access is configured in `settings.py`:

```python
# Cloudflare Access settings
CLOUDFLARE_ACCESS_ENABLED = True
CLOUDFLARE_AUDIENCE = os.environ.get('CLOUDFLARE_AUDIENCE', '92f9c8b2586479249c3bea574d492514af0593259e62280662f6a3876f00cc1b')
CLOUDFLARE_DOMAIN = os.environ.get('CLOUDFLARE_DOMAIN', 'batlab.cloudflareaccess.com')
ENFORCE_CLOUDFLARE_IN_DEV = True
```

## Testing

BattyCoda includes unit tests for key functionality.

### Running Tests

Run the tests using the Django test runner:

```bash
python manage.py test
```

### Test Coverage

Test coverage can be measured using the `coverage` tool:

```bash
coverage run --source='.' manage.py test
coverage report
```

## Common Development Tasks

### Creating a New User

```bash
python manage.py createsuperuser
```

### Creating a New Team

1. Access the admin interface at `/admin/`
2. Create a new Team object
3. Assign users to the team

### Adding a New Species

1. Log in to the application
2. Navigate to the Species section
3. Click "Create New Species"
4. Fill in the species details and upload an image
5. Add call types for the species

### Creating a New Project

1. Log in to the application
2. Navigate to the Projects section
3. Click "Create New Project"
4. Fill in the project details

### Processing a New Audio File

1. Log in to the application
2. Navigate to the Task Batches section
3. Click "Create New Batch"
4. Upload an audio file and select the species and project
5. The system will analyze the file and create individual tasks

## Troubleshooting

### Common Issues

#### Spectrogram Generation Fails

- Check that the audio file exists and is readable
- Verify that matplotlib and scipy are installed correctly
- Check the Celery logs for errors

#### R Server Connection Issues

- Verify that the R server is running
- Check that the required R packages are installed
- Check network connectivity between Django and the R server

#### Task Processing Delays

- Verify that Celery workers are running
- Check Redis connectivity
- Check for worker backlog in the Flower dashboard

### Logging

BattyCoda uses Django's logging system for debugging. Logs are configured in `settings.py`:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'battycoda.cloudflare': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'battycoda.audio': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'battycoda.tasks': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

## Contribution Guidelines

### Code Style

BattyCoda follows PEP 8 for Python code style.

### Git Workflow

1. Create a feature branch from `master`
2. Make changes and commit them
3. Submit a pull request
4. Ensure tests pass
5. Wait for code review and approval

### Documentation

- Document all functions and classes with docstrings
- Update this developer guide when adding major features
- Include examples for complex functionality

### Testing

- Write unit tests for new functionality
- Ensure existing tests pass
- Test on multiple browsers for frontend changes