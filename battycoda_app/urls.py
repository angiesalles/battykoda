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
    
    # Directory routes
    path('home/', views.home_view, name='home'),
    path('home/<str:username>/', views.user_directory_view, name='user_directory'),
    path('home/<str:username>/<str:species>/', views.species_directory_view, name='species_directory'),
    path('home/<str:username>/<str:species>/<path:subpath>/', views.subdirectory_view, name='subdirectory'),
    
    # File interaction
    path('species-info/<str:species_name>/', views.species_info_view, name='species_info'),
    path('create-directory/', views.create_directory_view, name='create_directory'),
    path('upload-file/', views.upload_file_view, name='upload_file'),
    
    # WAV file handling
    path('home/<str:username>/<str:species>/<path:wav_path>', views.wav_file_view, name='wav_file'),
    
    # Spectrogram routes
    path('spectrogram/', views.spectrogram_view, name='spectrogram'),
    path('status/task/<str:task_id>/', views.task_status_view, name='task_status'),
    path('audio/snippet/', views.audio_snippet_view, name='audio_snippet'),
    
    # Test static file serving
    path('test-static/<path:filename>', views.test_static_view, name='test_static'),
]
