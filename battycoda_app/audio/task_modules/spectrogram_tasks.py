"""
Spectrogram generation tasks for BattyCoda.
"""
import os
import tempfile
import time

from django.conf import settings

import numpy as np
from celery import shared_task
from PIL import Image

from ...utils import convert_path_to_os_specific
from ..utils import appropriate_file, get_audio_bit, normal_hwin, overview_hwin
from .base import log_performance, logger

# Import soundfile in the functions where needed


@shared_task(bind=True, name="battycoda_app.audio.tasks.generate_spectrogram_task", max_retries=3, retry_backoff=True)
def generate_spectrogram_task(self, path, args, output_path=None):
    """
    Task to generate a spectrogram image.

    Args:
        path: Path to the audio file
        args: Dict of parameters (call, channel, etc.)
        output_path: Optional explicit output path

    Returns:
        dict: Result information
    """
    start_time = time.time()

    # Create minimal task identifier for logging
    call = args.get("call", "?")
    channel = args.get("channel", "?")
    task_id = f"Call {call} Ch {channel}"

    try:
        # Skip state updates to reduce logs

        # Get file paths
        if output_path is None:
            output_path = appropriate_file(path, args)

        # Convert URL path to OS path (if not already converted)
        if path.startswith("home/"):
            os_path = convert_path_to_os_specific(path)
        else:
            os_path = path

        # Generate the spectrogram
        success, output_file, error = generate_spectrogram(os_path, args, output_path)

        # Only log results for failures
        if not success:
            logger.error(f"{task_id} FAILED: {error}")

        if success:
            return {"status": "success", "file_path": output_file, "original_path": path, "args": args}
        else:
            return {
                "status": "error",
                "error": error if error else "Failed to generate spectrogram",
                "file_path": output_file,
            }

    except Exception as e:
        # Only log full errors for catastrophic failures
        logger.error(f"{task_id} CATASTROPHIC ERROR: {str(e)}")

        # Retry the task if appropriate
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2**self.request.retries)

        return {"status": "error", "error": str(e), "path": path, "args": args}


@shared_task(bind=True, name="audio.prefetch_spectrograms")
def prefetch_spectrograms(self, path, base_args, call_range):
    """
    Prefetch multiple spectrograms for a range of calls.
    DISABLED - This function now does nothing to reduce server load

    Args:
        path: Path to the audio file
        base_args: Base arguments dict
        call_range: Tuple of (start_call, end_call)

    Returns:
        dict: Status indicating the function is disabled
    """
    logger.info("Prefetching is disabled for performance reasons")

    # Return a summary indicating prefetch is disabled
    return {"status": "disabled", "message": "Prefetching is disabled for performance reasons"}


@shared_task(bind=True, name="battycoda_app.audio.tasks.generate_recording_spectrogram")
def generate_recording_spectrogram(self, recording_id):
    """
    Generate a full spectrogram for a recording.

    Args:
        recording_id: ID of the Recording model

    Returns:
        dict: Result with the spectrogram file path
    """
    import hashlib
    import os
    import tempfile

    from django.conf import settings

    import matplotlib

    matplotlib.use("Agg")  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import numpy as np
    import soundfile as sf
    from PIL import Image

    from ...models import Recording

    logger.info(f"Generating full spectrogram for recording {recording_id}")

    try:
        # Get the recording
        recording = Recording.objects.get(id=recording_id)

        # Get the WAV file path
        wav_path = recording.wav_file.path

        # Create a hash of the file path for caching
        file_hash = hashlib.md5(wav_path.encode()).hexdigest()

        # Create the output directory and filename
        output_dir = os.path.join(settings.MEDIA_ROOT, "spectrograms", "recordings")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{file_hash}.png")

        # Check if file already exists
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Spectrogram already exists at {output_path}")
            return {"status": "success", "file_path": output_path, "recording_id": recording_id, "cached": True}

        # Load the audio file
        audio_data, sample_rate = sf.read(wav_path)

        # For very long recordings, downsample to improve performance
        max_duration_samples = 10 * 60 * sample_rate  # 10 minutes maximum
        if len(audio_data) > max_duration_samples:
            # Downsample by taking every nth sample
            downsample_factor = int(len(audio_data) / max_duration_samples) + 1
            audio_data = audio_data[::downsample_factor]
            effective_sample_rate = sample_rate / downsample_factor
            logger.info(f"Downsampled recording from {len(audio_data)*downsample_factor} to {len(audio_data)} samples")
        else:
            effective_sample_rate = sample_rate

        # If stereo, convert to mono by averaging channels
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            audio_data = np.mean(audio_data, axis=1)

        # Generate spectrogram
        plt.figure(figsize=(20, 10))
        plt.specgram(audio_data, Fs=effective_sample_rate, cmap="viridis")
        plt.title(f"Spectrogram: {recording.name}")
        plt.xlabel("Time (s)")
        plt.ylabel("Frequency (Hz)")
        plt.colorbar(label="Intensity")

        # Save the figure to a temporary file first
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            temp_path = tmp_file.name
            plt.savefig(temp_path, dpi=100, bbox_inches="tight")
            plt.close()

        # Convert with PIL for final processing and compression
        with Image.open(temp_path) as img:
            # Apply any image processing here if needed
            img.save(output_path, format="PNG", optimize=True)

        # Clean up temporary file
        os.unlink(temp_path)

        logger.info(f"Generated spectrogram at {output_path}")
        return {"status": "success", "file_path": output_path, "recording_id": recording_id, "cached": False}

    except Exception as e:
        logger.error(f"Error generating recording spectrogram: {str(e)}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e), "recording_id": recording_id}


def generate_spectrogram(path, args, output_path=None):
    """
    Pure function to generate a spectrogram.

    Args:
        path: Path to the audio file
        args: Dict of parameters (call, channel, etc.)
        output_path: Optional output path, will be generated if not provided

    Returns:
        tuple: (success, output_path, error_message)
    """
    # Start performance timer
    start_time = time.time()

    if output_path is None:
        output_path = appropriate_file(path, args)

    # Extract basic parameters for minimal task ID
    call = args.get("call", "0")
    channel = args.get("channel", "0")
    task_id = f"Call {call} Ch {channel}"

    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Parse parameters
        call_to_do = int(args.get("call", 0))
        overview = args.get("overview") == "1" or args.get("overview") == "True"
        channel = int(args.get("channel", 0))
        contrast = float(args.get("contrast", 4))

        # Select window size
        hwin = overview_hwin() if overview else normal_hwin()

        # Get audio data with direct segment loading if possible
        extra_params = None
        if "onset" in args and "offset" in args:
            extra_params = {"onset": args["onset"], "offset": args["offset"]}

        thr_x1, fs, hashof = get_audio_bit(path, call_to_do, hwin, extra_params)

        # Validate audio data
        if thr_x1 is None or thr_x1.size == 0:
            return False, output_path, "Audio data is empty"

        # Check channel is valid
        if channel >= thr_x1.shape[1]:
            return False, output_path, f"Channel index {channel} is out of bounds"

        # Extract channel
        thr_x1 = thr_x1[:, channel]

        # OPTIMIZATION: Skip hash validation to reduce overhead
        # This is safe because we're using file paths that are already validated

        # Use high-quality spectrogram parameters for better visual detail
        # - Higher nperseg for better frequency resolution
        # - Higher overlap for smoother time transitions
        # - Larger nfft for better frequency bins
        if overview:
            # For overview, use very high detail since we're showing more
            nperseg = 2**9  # 512
            noverlap = int(nperseg * 0.99)  # 99% overlap for highest quality
            nfft = 2**10  # 1024 for excellent frequency resolution
        else:
            # For call detail view, use high quality parameters
            nperseg = 2**8  # 256
            noverlap = 254
            nfft = 2**8

        # Generate spectrogram with optimized parameters
        import scipy.signal

        f, t, sxx = scipy.signal.spectrogram(thr_x1, fs, nperseg=nperseg, noverlap=noverlap, nfft=nfft)

        # Process data for image creation - measure time
        process_start = time.time()

        # Apply contrast enhancement
        temocontrast = 10**contrast
        processed_data = np.arctan(temocontrast * sxx)

        # Normalize the data to 0-255 range for image
        processed_data = (processed_data - processed_data.min()) / (processed_data.max() - processed_data.min()) * 255

        # Flip the spectrogram vertically (low frequencies at bottom)
        processed_data = np.flipud(processed_data)

        # Convert to 8-bit unsigned integer
        img_data = processed_data.astype(np.uint8)

        # For a more colorful image, you can create an RGB version:
        # Here we're using a purple-blue colormap similar to the original
        height, width = img_data.shape
        rgb_data = np.zeros((height, width, 3), dtype=np.uint8)

        # Check if this spectrogram is generated on-the-fly - if so, use inverted colors
        if args.get("generated_on_fly") == "1":
            logger.info("Generating on-the-fly spectrogram with inverted colors")
            # Inverted colormap (yellow-green instead of purple-blue)
            # R channel - more for brighter areas
            rgb_data[:, :, 0] = np.clip(img_data * 0.9, 0, 255).astype(np.uint8)
            # G channel - more overall
            rgb_data[:, :, 1] = np.clip(img_data * 0.8, 0, 255).astype(np.uint8)
            # B channel - less in all areas
            rgb_data[:, :, 2] = np.clip(img_data * 0.3, 0, 255).astype(np.uint8)
        else:
            # Standard colormap: convert grayscale to indigo-purple
            # R channel - more for brighter areas
            rgb_data[:, :, 0] = np.clip(img_data * 0.7, 0, 255).astype(np.uint8)
            # G channel - less overall
            rgb_data[:, :, 1] = np.clip(img_data * 0.2, 0, 255).astype(np.uint8)
            # B channel - more in all areas for blue/indigo base
            rgb_data[:, :, 2] = np.clip(img_data * 0.9, 0, 255).astype(np.uint8)

        log_performance(process_start, f"{task_id}: Process spectrogram data")

        # Create and save image - measure time
        img_start = time.time()

        # Create PIL Image and save
        img = Image.fromarray(rgb_data)

        # Resize to standard dimensions (800x600)
        img = img.resize((800, 600), Image.Resampling.LANCZOS)

        # Save with minimal compression for speed
        img.save(output_path, format="PNG", compress_level=1)

        log_performance(img_start, f"{task_id}: Create and save image")

        # Verify the file was created and log performance
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            log_performance(start_time, f"{task_id}: TOTAL SPECTROGRAM GENERATION")
            return True, output_path, None
        else:
            logger.error(f"ERROR: Output file not created properly: {output_path}")
            return False, output_path, "Failed to create output file"

    except Exception as e:
        logger.error(f"Error generating spectrogram: {str(e)}")
        # Simply return the error, no attempt to create error image
        return False, output_path, str(e)
