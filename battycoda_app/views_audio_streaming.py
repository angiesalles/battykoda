"""
Views for streaming audio files and generating waveform data.
"""
from .views_common import *

# Set up logging
logger = logging.getLogger("battycoda.views_audio_streaming")


@login_required
def get_audio_waveform_data(request, recording_id):
    """Get waveform data for a recording in JSON format"""
    recording = get_object_or_404(Recording, id=recording_id)

    # Check permission
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)

    try:
        import numpy as np
        import soundfile as sf
        from scipy import signal

        # Load the audio file
        audio_data, sample_rate = sf.read(recording.wav_file.path)

        # For stereo, convert to mono by averaging channels
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            audio_data = np.mean(audio_data, axis=1)

        # Get the actual length of audio data
        original_length = len(audio_data)
        logger.info(f"Original audio length: {original_length} samples")

        # Resample to get adequate detail for visualization (increased for better detail)
        target_points = 8000  # Increased from 2000 for more detail

        # Make sure we're processing the entire file
        if original_length > target_points:
            # For each pixel in the waveform, find min and max to capture the waveform envelope
            min_max_data = []
            samples_per_point = original_length // (target_points // 2)  # We need 2 points (min & max) per pixel

            for i in range(0, original_length, samples_per_point):
                chunk = audio_data[i : min(i + samples_per_point, original_length)]
                if len(chunk) > 0:
                    # Find min and max to preserve the waveform shape
                    chunk_min = np.min(chunk)
                    chunk_max = np.max(chunk)
                    # Add both min and max to represent the waveform envelope
                    min_max_data.append(chunk_min)
                    min_max_data.append(chunk_max)

            # Ensure we have exactly target_points
            if len(min_max_data) > target_points:
                min_max_data = min_max_data[:target_points]
            elif len(min_max_data) < target_points:
                # Pad with zeros if needed
                min_max_data.extend([0] * (target_points - len(min_max_data)))

            resampled_data = np.array(min_max_data)
        else:
            # For shorter files, use the original data
            resampled_data = audio_data

            # For very short files, interpolate to have enough points
            if len(resampled_data) < 1000:
                resampled_data = signal.resample(resampled_data, max(1000, len(resampled_data) * 2))

        # Normalize between -1 and 1 for waveform visualization
        max_val = np.max(np.abs(resampled_data))
        if max_val > 0:
            normalized_data = resampled_data / max_val
        else:
            normalized_data = resampled_data

        # Convert to list of floats
        waveform_data = normalized_data.tolist()

        return JsonResponse(
            {"success": True, "waveform": waveform_data, "duration": recording.duration, "sample_rate": sample_rate}
        )

    except Exception as e:
        logger.error(f"Error generating waveform data: {str(e)}")
        # Make sure we always return duration even on error
        return JsonResponse(
            {
                "success": False,
                "error": str(e),
                "duration": recording.duration or 0,  # Ensure duration is never null
                "waveform": [],  # Empty waveform data
            }
        )


@login_required
def stream_audio_view(request, recording_id):
    """
    Stream an audio file with support for HTTP Range requests.
    This allows seeking in the audio player without downloading the entire file.
    """
    recording = get_object_or_404(Recording, id=recording_id)

    # Check if the user has permission to access this recording
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
        raise Http404("You don't have permission to access this recording")

    # Get the file path and validate it exists
    file_path = recording.wav_file.path
    if not os.path.exists(file_path):
        logger.error(f"Audio file not found: {file_path}")
        raise Http404("Audio file not found")

    # Get file info
    file_size = os.path.getsize(file_path)
    content_type = mimetypes.guess_type(file_path)[0] or "audio/wav"

    # Parse Range header if present
    range_header = request.META.get("HTTP_RANGE", "").strip()
    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)

    # Initialize start_byte and end_byte
    start_byte = 0
    end_byte = file_size - 1

    # Handle range request
    if range_match:
        start_byte = int(range_match.group(1))
        end_group = range_match.group(2)

        if end_group:
            end_byte = min(int(end_group), file_size - 1)

        # Calculate bytes to read
        bytes_to_read = end_byte - start_byte + 1

        # Create partial response
        response = StreamingHttpResponse(
            streaming_file_iterator(file_path, start_byte, end_byte), status=206, content_type=content_type
        )

        # Add Content-Range header
        response["Content-Range"] = f"bytes {start_byte}-{end_byte}/{file_size}"
        response["Content-Length"] = str(bytes_to_read)
    else:
        # If no range is requested, serve the entire file
        response = StreamingHttpResponse(
            streaming_file_iterator(file_path, 0, file_size - 1), content_type=content_type
        )
        response["Content-Length"] = str(file_size)

    # Add common headers
    response["Accept-Ranges"] = "bytes"
    response["Content-Disposition"] = f'inline; filename="{os.path.basename(file_path)}"'

    # Return the response
    return response


def streaming_file_iterator(file_path, start_byte, end_byte):
    """Iterator function to stream a file in chunks, respecting byte range requests"""
    # Calculate bytes to read
    bytes_to_read = end_byte - start_byte + 1
    chunk_size = min(CHUNK_SIZE, bytes_to_read)

    # Open the file and seek to the start position
    with open(file_path, "rb") as f:
        f.seek(start_byte)

        # Stream the file in chunks
        remaining = bytes_to_read
        while remaining > 0:
            chunk_size = min(chunk_size, remaining)
            data = f.read(chunk_size)
            if not data:
                break
            yield data
            remaining -= len(data)
