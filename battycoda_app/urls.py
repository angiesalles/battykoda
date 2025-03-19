from django.urls import path, re_path
from . import views

app_name = 'battycoda_app'

urlpatterns = [
    path('', views.index, name='index'),
    
    # Authentication URLs
    path('accounts/login/', views.login_view, name='login'),
    path('accounts/register/', views.register_view, name='register'),
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/profile/', views.profile_view, name='profile'),
    path('accounts/profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('accounts/password-reset/', views.password_reset_request, name='password_reset_request'),
    path('accounts/reset-password/<str:token>/', views.password_reset, name='password_reset'),
    path('accounts/request-login-code/', views.request_login_code, name='request_login_code'),
    
    # Routes for task functionality only
    # Directory and file browsing functionality removed
    
    # Spectrogram routes
    path('spectrogram/', views.spectrogram_view, name='spectrogram'),
    path('status/task/<str:task_id>/', views.task_status_view, name='task_status'),
    path('audio/snippet/', views.audio_snippet_view, name='audio_snippet'),
    
    # Test static file serving (disabled - using built-in Django static file handling)
    # path('test-static/<path:filename>', views.test_static_view, name='test_static'),
    
    # Task management routes
    path('tasks/', views.task_list_view, name='task_list'),
    path('tasks/<int:task_id>/', views.task_detail_view, name='task_detail'),
    # Individual task creation removed - tasks are now only created through batches
    path('tasks/batches/', views.task_batch_list_view, name='task_batch_list'),
    path('tasks/batches/<int:batch_id>/', views.task_batch_detail_view, name='task_batch_detail'),
    path('tasks/batches/create/', views.create_task_batch_view, name='create_task_batch'),
    path('tasks/next/', views.get_next_task_view, name='get_next_task'),
    path('tasks/last/', views.get_last_task_view, name='get_last_task'),
    path('tasks/annotate/<int:task_id>/', views.task_annotation_view, name='annotate_task'),
    
    # Species management routes
    path('species/', views.species_list_view, name='species_list'),
    path('species/<int:species_id>/', views.species_detail_view, name='species_detail'),
    path('species/create/', views.create_species_view, name='create_species'),
    path('species/<int:species_id>/edit/', views.edit_species_view, name='edit_species'),
    
    # Project management routes
    path('projects/', views.project_list_view, name='project_list'),
    path('projects/<int:project_id>/', views.project_detail_view, name='project_detail'),
    path('projects/create/', views.create_project_view, name='create_project'),
    path('projects/<int:project_id>/edit/', views.edit_project_view, name='edit_project'),
    
    # Team management routes
    path('teams/', views.team_list_view, name='team_list'),
    path('teams/<int:team_id>/', views.team_detail_view, name='team_detail'),
    path('teams/create/', views.create_team_view, name='create_team'),
    path('teams/<int:team_id>/edit/', views.edit_team_view, name='edit_team'),
    path('teams/<int:team_id>/members/', views.manage_team_members_view, name='manage_team_members'),
]
