"""
Views for audio streaming and data retrieval in BattyCoda.
"""
import fnmatch
import hashlib
import logging
import mimetypes
import os
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404

from .models import Recording, UserProfile

# Set up logging
logger = logging.getLogger("battycoda.views_audio_streaming")

# Default chunk size for streaming (1MB)
CHUNK_SIZE = 1024 * 1024


@login_required
def get_audio_waveform_data(request, recording_id):
    """Get waveform data for a recording in JSON format"""
    recording = get_object_or_404(Recording, id=recording_id)
    
    # Check permission
    profile = request.user.profile
    if not profile.group or recording.group != profile.group:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Try to get cached waveform data first
    if recording.waveform_data:
        return JsonResponse(recording.waveform_data)
    
    # Get wav file path
    wav_path = recording.wav_file.path if recording.wav_file else None
    
    if not wav_path or not os.path.exists(wav_path):
        return JsonResponse({'error': 'WAV file not found'}, status=404)
    
    try:
        # Load the wav file and compute waveform data
        import numpy as np
        import soundfile as sf
        
        # Load the audio file
        audio_data, sample_rate = sf.read(wav_path)
        
        # For stereo files, use the first channel for visualization
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            audio_data = audio_data[:, 0]
        
        # Compute waveform data (downsample for visualization)
        duration = len(audio_data) / sample_rate
        
        # Determine the downsampling factor based on duration
        # Use more points for longer recordings
        if duration > 60:  # More than 1 minute
            # Aim for about 10,000 points for long recordings
            downsample_factor = max(1, int(len(audio_data) / 10000))
        else:
            # For shorter recordings, aim for about 5,000 points
            downsample_factor = max(1, int(len(audio_data) / 5000))
        
        # Downsample the audio data
        downsampled = audio_data[::downsample_factor]
        
        # Compute time points
        time_points = np.linspace(0, duration, len(downsampled))
        
        # Format the data for JSON response
        waveform_data = {
            'duration': duration,
            'sample_rate': sample_rate,
            'time_points': time_points.tolist(),
            'amplitude': downsampled.tolist()
        }
        
        # Cache the waveform data
        recording.waveform_data = waveform_data
        recording.save()
        
        return JsonResponse(waveform_data)
    except Exception as e:
        logger.error(f"Error computing waveform data: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def stream_audio_view(request, recording_id):
    """
    Stream an audio file with support for HTTP range requests (for seeking in the browser)
    """
    # Get the recording
    recording = get_object_or_404(Recording, id=recording_id)
    
    # Check permission
    profile = request.user.profile
    if not profile.group or recording.group != profile.group:
        raise Http404("Recording not found")
    
    # Get the file path
    file_path = recording.wav_file.path if recording.wav_file else None
    
    if not file_path or not os.path.exists(file_path):
        raise Http404("Audio file not found")
    
    # Get file info
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    content_type = "audio/wav"  # Fixed for WAV files
    
    # Parse the range header from the request
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
    
    # Parse the etag header (if present)
    etag = request.META.get('HTTP_IF_NONE_MATCH', '')
    
    # Generate a simple hash of the file path and modification time as the etag
    file_mtime = os.path.getmtime(file_path)
    generated_etag = f'"{hashlib.md5(f"{file_path}:{file_mtime}".encode()).hexdigest()}"'
    
    # If the client has a matching etag, return 304 Not Modified
    if etag and etag == generated_etag:
        return HttpResponse(status=304)
    
    # If no range is specified, return the entire file
    if not range_match:
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=content_type,
            filename=file_name,
            as_attachment=False
        )
        response['Accept-Ranges'] = 'bytes'
        response['Content-Length'] = file_size
        response['ETag'] = generated_etag
        return response
    
    # Parse the range header
    start_byte = int(range_match.group(1))
    end_byte_str = range_match.group(2)
    end_byte = int(end_byte_str) if end_byte_str else file_size - 1
    
    # Clamp the end byte to the file size
    end_byte = min(end_byte, file_size - 1)
    
    # Calculate the content length
    content_length = end_byte - start_byte + 1
    
    # Return a streaming response
    response = StreamingHttpResponse(
        streaming_file_iterator(file_path, start_byte, end_byte),
        status=206,
        content_type=content_type
    )
    
    # Set the appropriate headers
    response['Content-Length'] = content_length
    response['Content-Range'] = f'bytes {start_byte}-{end_byte}/{file_size}'
    response['Accept-Ranges'] = 'bytes'
    response['ETag'] = generated_etag
    response['Cache-Control'] = 'max-age=86400'  # Cache for 24 hours
    
    return response


def streaming_file_iterator(file_path, start_byte, end_byte):
    """
    Generator function to stream a file in chunks
    """
    with open(file_path, 'rb') as f:
        f.seek(start_byte)
        remaining = end_byte - start_byte + 1
        while remaining > 0:
            chunk_size = min(CHUNK_SIZE, remaining)
            data = f.read(chunk_size)
            if not data:
                break
            remaining -= len(data)
            yield data