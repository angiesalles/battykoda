from django.urls import path

from . import views, views_automation, views_batch_upload, views_debug, views_project, views_recordings, views_species, views_task_batch

app_name = "battycoda_app"

urlpatterns = [
    path("", views.index, name="index"),
    # Authentication URLs
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/register/", views.register_view, name="register"),
    path("accounts/logout/", views.logout_view, name="logout"),
    path("accounts/profile/", views.profile_view, name="profile"),
    path("accounts/profile/edit/", views.edit_profile_view, name="edit_profile"),
    path("accounts/password-reset/", views.password_reset_request, name="password_reset_request"),
    path("accounts/reset-password/<str:token>/", views.password_reset, name="password_reset"),
    path("accounts/request-login-code/", views.request_login_code, name="request_login_code"),
    # Routes for task functionality only
    # Directory and file browsing functionality removed
    # Spectrogram routes
    path("spectrogram/", views.spectrogram_view, name="spectrogram"),
    path("status/task/<str:task_id>/", views.task_status_view, name="task_status"),
    path("audio/snippet/", views.audio_snippet_view, name="audio_snippet"),
    # Test static file serving (disabled - using built-in Django static file handling)
    # path('test-static/<path:filename>', views.test_static_view, name='test_static'),
    # Task management routes
    path("tasks/<int:task_id>/", views.task_detail_view, name="task_detail"),
    # Individual task creation removed - tasks are now only created through batches
    path("tasks/batches/", views.task_batch_list_view, name="task_batch_list"),
    path("tasks/batches/<int:batch_id>/", views.task_batch_detail_view, name="task_batch_detail"),
    path("tasks/batches/<int:batch_id>/export/", views_task_batch.export_task_batch_view, name="export_task_batch"),
    path("tasks/batches/create/", views.create_task_batch_view, name="create_task_batch"),
    path("tasks/next/", views.get_next_task_view, name="get_next_task"),
    path("tasks/last/", views.get_last_task_view, name="get_last_task"),
    path("tasks/batch/<int:batch_id>/annotate/", views.get_next_task_from_batch_view, name="annotate_batch"),
    path("tasks/annotate/<int:task_id>/", views.task_annotation_view, name="annotate_task"),
    # Automation routes
    path("automation/", views_automation.automation_home_view, name="automation_home"),
    path("automation/runs/<int:run_id>/", views_automation.detection_run_detail_view, name="detection_run_detail"),
    path("automation/runs/create/", views_automation.create_detection_run_view, name="create_detection_run"),
    path("automation/runs/create/<int:segmentation_id>/", views_automation.create_detection_run_view, name="create_detection_run_for_segmentation"),
    path("automation/runs/<int:run_id>/status/", views_automation.detection_run_status_view, name="detection_run_status"),
    path("automation/runs/<int:run_id>/apply/", views_automation.apply_detection_results_view, name="apply_detection_results"),
    path("automation/runs/<int:run_id>/apply/<int:segment_id>/", views_automation.apply_detection_results_view, name="apply_detection_result_for_segment"),
    path("automation/runs/<int:run_id>/create-tasks/", views_automation.create_task_batch_from_detection_run, name="create_task_batch_from_detection_run"),
    path("automation/runs/<int:run_id>/delete/", views_automation.delete_detection_run_view, name="delete_detection_run"),
    # Species management routes
    path("species/", views_species.species_list_view, name="species_list"),
    path("species/<int:species_id>/", views_species.species_detail_view, name="species_detail"),
    path("species/create/", views_species.create_species_view, name="create_species"),
    path("species/<int:species_id>/edit/", views_species.edit_species_view, name="edit_species"),
    path("species/<int:species_id>/delete/", views_species.delete_species_view, name="delete_species"),
    path("species/parse-calls-file/", views_species.parse_calls_file_view, name="parse_calls_file"),
    path("species/<int:species_id>/calls/add/", views_species.add_call_view, name="add_call"),
    path("species/<int:species_id>/calls/<int:call_id>/delete/", views_species.delete_call_view, name="delete_call"),
    # Project management routes
    path("projects/", views_project.project_list_view, name="project_list"),
    path("projects/<int:project_id>/", views_project.project_detail_view, name="project_detail"),
    path("projects/create/", views_project.create_project_view, name="create_project"),
    path("projects/<int:project_id>/edit/", views_project.edit_project_view, name="edit_project"),
    path("projects/<int:project_id>/delete/", views_project.delete_project_view, name="delete_project"),
    # Group management routes
    path("groups/", views.group_list_view, name="group_list"),
    path("groups/<int:group_id>/", views.group_detail_view, name="group_detail"),
    path("groups/create/", views.create_group_view, name="create_group"),
    path("groups/<int:group_id>/edit/", views.edit_group_view, name="edit_group"),
    path("groups/<int:group_id>/members/", views.manage_group_members_view, name="manage_group_members"),
    path("groups/switch/<int:group_id>/", views.switch_group_view, name="switch_group"),
    # Group users and invitations
    path("users/", views.group_users_view, name="group_users"),
    path("users/invite/", views.invite_user_view, name="invite_user"),
    path("invitation/<str:token>/", views.accept_invitation_view, name="accept_invitation"),
    # Debug routes
    path("debug/env/", views_debug.debug_env_view, name="debug_env"),
    
    # Recordings management
    path("recordings/", views_recordings.recording_list_view, name="recording_list"),
    path("recordings/<int:recording_id>/", views_recordings.recording_detail_view, name="recording_detail"),
    path("recordings/create/", views_recordings.create_recording_view, name="create_recording"),
    path("recordings/batch-upload/", views_batch_upload.batch_upload_recordings_view, name="batch_upload_recordings"),
    path("recordings/<int:recording_id>/edit/", views_recordings.edit_recording_view, name="edit_recording"),
    path("recordings/<int:recording_id>/delete/", views_recordings.delete_recording_view, name="delete_recording"),
    path("recordings/<int:recording_id>/segment/", views_recordings.segment_recording_view, name="segment_recording"),
    path("recordings/<int:recording_id>/auto-segment/", views_recordings.auto_segment_recording_view, name="auto_segment_recording"),
    path("recordings/<int:recording_id>/auto-segment/<int:algorithm_id>/", views_recordings.auto_segment_recording_view, name="auto_segment_recording_with_algorithm"),
    path("recordings/<int:recording_id>/auto-segment/status/", views_recordings.auto_segment_status_view, name="auto_segment_status"),
    path("recordings/<int:recording_id>/upload-pickle/", views_recordings.upload_pickle_segments_view, name="upload_pickle_segments"),
    path("recordings/<int:recording_id>/spectrogram-status/", views_recordings.recording_spectrogram_status_view, name="recording_spectrogram_status"),
    path("recordings/<int:recording_id>/waveform-data/", views_recordings.get_audio_waveform_data, name="recording_waveform_data"),
    path("recordings/<int:recording_id>/create-tasks/", views_recordings.create_tasks_from_segments_view, name="create_tasks_from_segments"),
    path("recordings/<int:recording_id>/stream/", views_recordings.stream_audio_view, name="stream_recording_audio"),
    
    # Segmentation management
    path("segmentation/", views_recordings.batch_segmentation_view, name="batch_segmentation"),
    path("segmentation/jobs/status/", views_recordings.segmentation_jobs_status_view, name="segmentation_jobs_status"),
    path("segmentation/<int:segmentation_id>/activate/", views_recordings.activate_segmentation_view, name="activate_segmentation"),
    
    # Segment management
    path("segments/<int:recording_id>/add/", views_recordings.add_segment_view, name="add_segment"),
    path("segments/<int:segment_id>/edit/", views_recordings.edit_segment_view, name="edit_segment"),
    path("segments/<int:segment_id>/delete/", views_recordings.delete_segment_view, name="delete_segment"),
]
