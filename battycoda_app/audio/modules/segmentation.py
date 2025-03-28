"""
Functions for audio segmentation and event detection in BattyCoda.
"""
import logging
import traceback

# Configure logging
logger = logging.getLogger("battycoda.audio.segmentation")


def auto_segment_audio(audio_path, min_duration_ms=10, smooth_window=3, threshold_factor=0.5, debug_visualization=False):
    """
    Automatically segment audio using the following steps:
    1. Take absolute value of the signal
    2. Smooth the signal using a moving average filter
    3. Apply a threshold to detect segments
    4. Reject markings shorter than the minimum duration
    
    Args:
        audio_path: Path to the audio file
        min_duration_ms: Minimum segment duration in milliseconds
        smooth_window: Window size for smoothing filter
        threshold_factor: Threshold factor (between 0-1) to apply
        debug_visualization: If True, generates a visualization of the segmentation process
        
    Returns:
        tuple: (onsets, offsets, [debug_path]) as lists of floats in seconds and optional debug image path
    """
    try:
        import numpy as np
        import soundfile as sf
        import os
        import tempfile

        # Import visualization libraries if debug_visualization is enabled
        if debug_visualization:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt

        # Load the audio file
        audio_data, sample_rate = sf.read(audio_path)
        logger.info(f"Loaded audio file for automated segmentation: {audio_path}")
        logger.info(f"Audio shape: {audio_data.shape}, sample rate: {sample_rate}")
        
        # For stereo files, use the first channel for detection
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            audio_data = audio_data[:, 0]
            logger.info(f"Using first channel from stereo recording for detection")
        
        # Step 1: Take absolute value of the signal
        abs_signal = np.abs(audio_data)
        
        # Step 2: Smooth the signal with a moving average filter
        if smooth_window > 1:
            kernel = np.ones(smooth_window) / smooth_window
            smoothed_signal = np.convolve(abs_signal, kernel, mode='same')
        else:
            smoothed_signal = abs_signal
        
        # Step 3: Apply threshold
        # Calculate adaptive threshold based on the signal statistics
        signal_mean = np.mean(smoothed_signal)
        signal_std = np.std(smoothed_signal)
        threshold = signal_mean + (threshold_factor * signal_std)
        
        logger.info(f"Auto-segmentation thresholds - Mean: {signal_mean:.6f}, Std: {signal_std:.6f}, Threshold: {threshold:.6f}")
        
        # Create binary mask where signal exceeds threshold
        binary_mask = smoothed_signal > threshold
        
        # Find transitions in the binary mask (0->1 and 1->0)
        # Transitions from 0->1 indicate segment onsets
        # Transitions from 1->0 indicate segment offsets
        transitions = np.diff(binary_mask.astype(int))
        onset_samples = np.where(transitions == 1)[0] + 1  # +1 because diff reduces length by 1
        offset_samples = np.where(transitions == -1)[0] + 1
        
        # Handle edge cases
        if binary_mask[0]:
            # Signal starts above threshold, insert onset at sample 0
            onset_samples = np.insert(onset_samples, 0, 0)
            
        if binary_mask[-1]:
            # Signal ends above threshold, append offset at the last sample
            offset_samples = np.append(offset_samples, len(binary_mask) - 1)
        
        # Ensure we have the same number of onsets and offsets
        if len(onset_samples) > len(offset_samples):
            # More onsets than offsets - trim extra onsets
            onset_samples = onset_samples[:len(offset_samples)]
        elif len(offset_samples) > len(onset_samples):
            # More offsets than onsets - trim extra offsets
            offset_samples = offset_samples[:len(onset_samples)]
            
        # Convert sample indices to time in seconds
        onsets = onset_samples / sample_rate
        offsets = offset_samples / sample_rate
        
        # Step 4: Reject segments shorter than the minimum duration
        min_samples = int((min_duration_ms / 1000) * sample_rate)
        valid_segments = []
        
        for i in range(len(onsets)):
            duration_samples = offset_samples[i] - onset_samples[i]
            if duration_samples >= min_samples:
                valid_segments.append(i)
        
        # Filter onsets and offsets to only include valid segments
        filtered_onsets = [onsets[i] for i in valid_segments]
        filtered_offsets = [offsets[i] for i in valid_segments]
        
        logger.info(f"Automated segmentation found {len(onsets)} potential segments")
        logger.info(f"After minimum duration filtering: {len(filtered_onsets)} segments")
        
        # Generate debug visualization if requested
        if debug_visualization:
            debug_path = None
            try:
                # Create a figure with multiple subplots
                fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
                
                # Time axis in seconds
                time_axis = np.arange(len(audio_data)) / sample_rate
                
                # 1. Plot the original signal
                axes[0].plot(time_axis, audio_data)
                axes[0].set_title('Original Signal')
                axes[0].set_ylabel('Amplitude')
                
                # 2. Plot the absolute signal
                axes[1].plot(time_axis, abs_signal)
                axes[1].set_title('Absolute Signal')
                axes[1].set_ylabel('Amplitude')
                
                # 3. Plot the smoothed signal with threshold
                axes[2].plot(time_axis, smoothed_signal)
                axes[2].axhline(y=threshold, color='r', linestyle='--', label=f'Threshold: {threshold:.6f}')
                axes[2].set_title(f'Smoothed Signal (window={smooth_window}) with Threshold (factor={threshold_factor})')
                axes[2].set_ylabel('Amplitude')
                axes[2].legend()
                
                # 4. Plot the binary mask with detected segments
                # Make sure binary_mask and time_axis have the same length for plotting
                if len(binary_mask) != len(time_axis):
                    logger.info(f"Fixing binary mask length for threshold plot: {len(binary_mask)} vs {len(time_axis)}")
                    if len(binary_mask) < len(time_axis):
                        # Pad binary mask if it's too short
                        padding = np.zeros(len(time_axis) - len(binary_mask))
                        binary_mask_plot = np.concatenate([binary_mask, padding])
                    else:
                        # Truncate binary mask if it's too long
                        binary_mask_plot = binary_mask[:len(time_axis)]
                else:
                    binary_mask_plot = binary_mask
                    
                axes[3].plot(time_axis, binary_mask_plot, label='Binary mask')
                
                # Add vertical lines for onsets (green) and offsets (red)
                for onset in filtered_onsets:
                    axes[3].axvline(x=onset, color='g', linestyle='--')
                    
                for offset in filtered_offsets:
                    axes[3].axvline(x=offset, color='r', linestyle='-.')
                    
                # Marking segments that were filtered out (too short)
                for i in range(len(onsets)):
                    if i not in valid_segments:
                        # Draw a light red box over rejected segments
                        axes[3].axvspan(onsets[i], offsets[i], alpha=0.2, color='red')
                
                axes[3].set_title(f'Binary Mask with Detected Segments (min duration={min_duration_ms}ms)')
                axes[3].set_xlabel('Time (s)')
                axes[3].set_ylabel('State (0/1)')
                
                # Adjust layout
                plt.tight_layout()
                
                # Save to a temporary file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    debug_path = tmp_file.name
                    plt.savefig(debug_path, dpi=100)
                    plt.close()
                
                # Log the debug file location
                logger.info(f"Created segmentation debug visualization at {debug_path}")
                
            except Exception as viz_error:
                logger.error(f"Error creating debug visualization: {str(viz_error)}")
                logger.error(traceback.format_exc())
                # If there's an error with visualization, still return the segments
            
            return filtered_onsets, filtered_offsets, debug_path
        
        # Return without visualization path if debug_visualization is False
        return filtered_onsets, filtered_offsets
        
    except Exception as e:
        logger.error(f"Error in auto_segment_audio: {str(e)}")
        logger.error(traceback.format_exc())
        raise


def energy_based_segment_audio(audio_path, min_duration_ms=10, smooth_window=3, threshold_factor=0.5, debug_visualization=False):
    """
    Segment audio based on energy levels using the following steps:
    1. Calculate the short-time energy of the signal
    2. Smooth the energy curve
    3. Apply an adaptive threshold based on the energy statistics
    4. Reject markings shorter than the minimum duration
    
    Args:
        audio_path: Path to the audio file
        min_duration_ms: Minimum segment duration in milliseconds
        smooth_window: Window size for smoothing filter
        threshold_factor: Threshold factor (between 0-1) to apply to energy detection
        debug_visualization: If True, generates a visualization of the segmentation process
        
    Returns:
        tuple: (onsets, offsets, [debug_path]) as lists of floats in seconds and optional debug image path
    """
    try:
        import numpy as np
        import soundfile as sf
        import os
        import tempfile

        # Import visualization libraries if debug_visualization is enabled
        if debug_visualization:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt

        # Load the audio file
        audio_data, sample_rate = sf.read(audio_path)
        logger.info(f"Loaded audio file for energy-based segmentation: {audio_path}")
        logger.info(f"Audio shape: {audio_data.shape}, sample rate: {sample_rate}")
        
        # For stereo files, use the first channel for detection
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            audio_data = audio_data[:, 0]
            logger.info(f"Using first channel from stereo recording for detection")
        
        # Step 1: Calculate short-time energy
        # Set the frame size for energy calculation (adjust based on expected call frequency)
        frame_size = int(0.01 * sample_rate)  # 10ms frames
        energy = np.zeros(len(audio_data) // frame_size)
        
        for i in range(len(energy)):
            # Calculate energy for each frame
            start = i * frame_size
            end = min(start + frame_size, len(audio_data))
            frame = audio_data[start:end]
            # Energy is sum of squared amplitudes
            energy[i] = np.sum(frame ** 2) / len(frame)
        
        # Interpolate energy back to signal length for easier visualization
        energy_full = np.interp(
            np.linspace(0, len(energy), len(audio_data)), 
            np.arange(len(energy)), 
            energy
        )
        
        # Step 2: Smooth the energy curve with a moving average filter
        if smooth_window > 1:
            kernel = np.ones(smooth_window) / smooth_window
            smoothed_energy = np.convolve(energy_full, kernel, mode='same')
        else:
            smoothed_energy = energy_full
        
        # Step 3: Apply threshold 
        # Calculate adaptive threshold based on the energy statistics
        energy_mean = np.mean(smoothed_energy)
        energy_std = np.std(smoothed_energy)
        threshold = energy_mean + (threshold_factor * energy_std)
        
        logger.info(f"Energy segmentation thresholds - Mean: {energy_mean:.6f}, Std: {energy_std:.6f}, Threshold: {threshold:.6f}")
        
        # Create binary mask where energy exceeds threshold
        binary_mask = smoothed_energy > threshold
        
        # Find transitions in the binary mask (0->1 and 1->0)
        transitions = np.diff(binary_mask.astype(int))
        onset_samples = np.where(transitions == 1)[0] + 1  # +1 because diff reduces length by 1
        offset_samples = np.where(transitions == -1)[0] + 1
        
        # Handle edge cases
        if binary_mask[0]:
            # Signal starts above threshold, insert onset at sample 0
            onset_samples = np.insert(onset_samples, 0, 0)
            
        if binary_mask[-1]:
            # Signal ends above threshold, append offset at the last sample
            offset_samples = np.append(offset_samples, len(binary_mask) - 1)
        
        # Ensure we have the same number of onsets and offsets
        if len(onset_samples) > len(offset_samples):
            # More onsets than offsets - trim extra onsets
            onset_samples = onset_samples[:len(offset_samples)]
        elif len(offset_samples) > len(onset_samples):
            # More offsets than onsets - trim extra offsets
            offset_samples = offset_samples[:len(onset_samples)]
            
        # Convert sample indices to time in seconds
        onsets = onset_samples / sample_rate
        offsets = offset_samples / sample_rate
        
        # Step 4: Reject segments shorter than the minimum duration
        min_samples = int((min_duration_ms / 1000) * sample_rate)
        valid_segments = []
        
        for i in range(len(onsets)):
            duration_samples = offset_samples[i] - onset_samples[i]
            if duration_samples >= min_samples:
                valid_segments.append(i)
        
        # Filter onsets and offsets to only include valid segments
        filtered_onsets = [onsets[i] for i in valid_segments]
        filtered_offsets = [offsets[i] for i in valid_segments]
        
        logger.info(f"Energy-based segmentation found {len(onsets)} potential segments")
        logger.info(f"After minimum duration filtering: {len(filtered_onsets)} segments")
        
        # Generate debug visualization if requested
        if debug_visualization:
            debug_path = None
            try:
                # Create a figure with multiple subplots
                fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
                
                # Time axis in seconds
                time_axis = np.arange(len(audio_data)) / sample_rate
                
                # 1. Plot the original signal
                axes[0].plot(time_axis, audio_data)
                axes[0].set_title('Original Signal')
                axes[0].set_ylabel('Amplitude')
                
                # 2. Plot the energy curve
                axes[1].plot(time_axis, energy_full)
                axes[1].set_title('Energy')
                axes[1].set_ylabel('Energy')
                
                # 3. Plot the smoothed energy with threshold
                axes[2].plot(time_axis, smoothed_energy)
                axes[2].axhline(y=threshold, color='r', linestyle='--', label=f'Threshold: {threshold:.6f}')
                axes[2].set_title(f'Smoothed Energy (window={smooth_window}) with Threshold (factor={threshold_factor})')
                axes[2].set_ylabel('Energy')
                axes[2].legend()
                
                # 4. Plot the binary mask with detected segments
                # Make sure binary_mask and time_axis have the same length for plotting
                if len(binary_mask) != len(time_axis):
                    logger.info(f"Fixing binary mask length for energy plot: {len(binary_mask)} vs {len(time_axis)}")
                    if len(binary_mask) < len(time_axis):
                        # Pad binary mask if it's too short
                        padding = np.zeros(len(time_axis) - len(binary_mask))
                        binary_mask_plot = np.concatenate([binary_mask, padding])
                    else:
                        # Truncate binary mask if it's too long
                        binary_mask_plot = binary_mask[:len(time_axis)]
                else:
                    binary_mask_plot = binary_mask
                    
                axes[3].plot(time_axis, binary_mask_plot, label='Binary mask')
                
                # Add vertical lines for onsets (green) and offsets (red)
                for onset in filtered_onsets:
                    axes[3].axvline(x=onset, color='g', linestyle='--')
                    
                for offset in filtered_offsets:
                    axes[3].axvline(x=offset, color='r', linestyle='-.')
                    
                # Marking segments that were filtered out (too short)
                for i in range(len(onsets)):
                    if i not in valid_segments:
                        # Draw a light red box over rejected segments
                        axes[3].axvspan(onsets[i], offsets[i], alpha=0.2, color='red')
                
                axes[3].set_title(f'Binary Mask with Detected Segments (min duration={min_duration_ms}ms)')
                axes[3].set_xlabel('Time (s)')
                axes[3].set_ylabel('State (0/1)')
                
                # Adjust layout
                plt.tight_layout()
                
                # Save to a temporary file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    debug_path = tmp_file.name
                    plt.savefig(debug_path, dpi=100)
                    plt.close()
                
                # Log the debug file location
                logger.info(f"Created energy segmentation debug visualization at {debug_path}")
                
            except Exception as viz_error:
                logger.error(f"Error creating debug visualization: {str(viz_error)}")
                logger.error(traceback.format_exc())
                # If there's an error with visualization, still return the segments
            
            return filtered_onsets, filtered_offsets, debug_path
        
        # Return without visualization path if debug_visualization is False
        return filtered_onsets, filtered_offsets
        
    except Exception as e:
        logger.error(f"Error in energy_based_segment_audio: {str(e)}")
        logger.error(traceback.format_exc())
        raise