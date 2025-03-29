"""
Functions for generating tick marks for spectrograms in BattyCoda.
"""
import logging

# Configure logging
logger = logging.getLogger("battycoda.audio.tick_generation")


def get_spectrogram_ticks(task, sample_rate=None, normal_window_size=None, overview_window_size=None):
    """Generate tick mark data for spectrograms.

    Args:
        task: Task model instance containing onset and offset
        sample_rate: Sample rate of the recording in Hz (optional)
        normal_window_size: Tuple of (pre_window, post_window) in milliseconds for detail view
        overview_window_size: Tuple of (pre_window, post_window) in milliseconds for overview

    Returns:
        dict: Dictionary containing x and y tick data for both detail and overview views
    """
    # Import here to avoid circular imports
    from .audio_processing import normal_hwin, overview_hwin

    # Use default window sizes if not provided
    if normal_window_size is None:
        normal_window_size = normal_hwin()
    if overview_window_size is None:
        overview_window_size = overview_hwin()

    # Calculate call duration in milliseconds
    call_duration_ms = (task.offset - task.onset) * 1000

    # Calculate the actual time spans for detail view (in ms)
    detail_left_padding = normal_window_size[0]  # Pre-window in ms
    detail_right_padding = normal_window_size[1]  # Post-window in ms
    detail_total_duration = detail_left_padding + call_duration_ms + detail_right_padding  # Total window duration in ms

    # Calculate detail view x-axis positions (percentages) based on actual time values
    detail_left_pos = 0  # Left edge
    detail_zero_pos = (detail_left_padding / detail_total_duration) * 100  # Start of sound
    detail_call_end_pos = ((detail_left_padding + call_duration_ms) / detail_total_duration) * 100  # End of sound
    detail_right_pos = 100  # Right edge

    # Calculate the actual time spans for overview (in ms)
    overview_left_padding = overview_window_size[0]  # Pre-window in ms
    overview_right_padding = overview_window_size[1]  # Post-window in ms
    overview_total_duration = overview_left_padding + overview_right_padding  # Total window duration in ms

    # Calculate overview x-axis positions (percentages) based on actual time values
    overview_left_pos = 0  # Left edge
    overview_zero_pos = (overview_left_padding / overview_total_duration) * 100  # Start of sound
    overview_right_pos = 100  # Right edge
    overview_call_end_pos = ((overview_left_padding + call_duration_ms) / overview_total_duration) * 100
    # Generate x-axis ticks data for detail view
    # Start with the left and right edge ticks
    x_ticks_detail = [
        {
            "id": "left-tick-detail",
            "position": detail_left_pos,
            "value": f"-{normal_window_size[0]:.1f} ms",
            "type": "major",
        },
        {"id": "zero-tick-detail", "position": detail_zero_pos, "value": "0.0 ms", "type": "major"},
        {
            "id": "right-tick-detail",
            "position": detail_right_pos,
            "value": f"{call_duration_ms + normal_window_size[1]:.1f} ms",  # Include call length + padding
            "type": "major",
        },
    ]

    # Only add the call-end tick if the call duration is at least 2ms
    if call_duration_ms >= 2.0:
        x_ticks_detail.insert(
            2,
            {
                "id": "call-end-tick-detail",
                "position": detail_call_end_pos,
                "value": f"{call_duration_ms:.1f} ms",
                "type": "major",
            },
        )

    # Generate x-axis ticks data for overview
    # For overview, the total width should be just left_padding + right_padding
    x_ticks_overview = [
        {
            "id": "left-tick-overview",
            "position": overview_left_pos,
            "value": f"-{overview_window_size[0]:.1f} ms",
            "type": "major",
        },
        {"id": "zero-tick-overview", "position": overview_zero_pos, "value": "0.0 ms", "type": "major"},
        {
            "id": "right-tick-overview",
            "position": overview_right_pos,
            "value": f"{overview_window_size[1]:.1f} ms",  # padding
            "type": "major",
        },
    ]

    # Only add the call-end tick if the call duration is at least 2ms
    if call_duration_ms >= 30.0:
        x_ticks_overview.insert(
            2,
            {
                "id": "call-end-tick-overview",
                "position": overview_call_end_pos,
                "value": f"{call_duration_ms:.1f} ms",
                "type": "major",
            },
        )

    # Add minor ticks for the overview at 50ms intervals
    total_overview_ms = overview_left_padding + overview_right_padding  # Total time span in ms (including call length)

    # Start at 50ms and go up to the total overview time in 50ms steps
    for time_ms in range(50, int(total_overview_ms), 50):
        # Convert time to a percentage of the total overview width
        position_percent = (time_ms / total_overview_ms) * 100

        # Add a minor tick at this position
        x_ticks_overview.append(
            {"id": f"minor-overview-{time_ms}ms", "position": position_percent, "value": "", "type": "minor"}
        )

    # Generate y-axis ticks for frequency
    if not sample_rate:
        raise ValueError("Sample rate is required for spectrogram ticks")

    # Nyquist frequency (maximum possible frequency in the recording) is half the sample rate
    max_freq = sample_rate / 2 / 1000  # Convert to kHz

    # Increase the number of ticks for more granularity
    num_ticks = 11  # 0%, 10%, 20%, ..., 100%
    y_ticks = []

    # Generate main ticks
    for i in range(num_ticks):
        position = i * (100 / (num_ticks - 1))  # Positions from 0% to 100%
        value = max_freq - (max_freq * position / 100)  # Values from max_freq to 0 kHz

        # Add the tick with a size class for styling
        y_ticks.append(
            {
                "position": position,
                "value": int(value),  # Integer values for cleaner display
                "type": "major",  # Mark as major tick for styling
            }
        )

    # Add intermediate minor ticks between major ticks for extra precision
    if num_ticks > 2:  # Only add minor ticks if we have enough space
        for i in range(num_ticks - 1):
            # Calculate position halfway between major ticks
            position = (i * (100 / (num_ticks - 1))) + ((100 / (num_ticks - 1)) / 2)
            value = max_freq - (max_freq * position / 100)

            # Add minor tick (without displaying the value)
            y_ticks.append(
                {
                    "position": position,
                    "value": "",  # No value displayed for minor ticks
                    "type": "minor",  # Mark as minor tick for styling
                }
            )

    return {"x_ticks_detail": x_ticks_detail, "x_ticks_overview": x_ticks_overview, "y_ticks": y_ticks}
