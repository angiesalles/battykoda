/**
 * BattyCoda Waveform Player - Timeline Renderer
 * 
 * Responsible for drawing the timeline below the waveform
 */

export class TimelineRenderer {
    /**
     * Create a new TimelineRenderer
     * @param {Object} player - The parent WaveformPlayer instance
     */
    constructor(player) {
        this.player = player;
    }
    
    /**
     * Draw the timeline
     */
    draw() {
        const player = this.player;
        if (!player.timelineContainer) return;
        
        // Clear timeline
        player.timelineContainer.innerHTML = '';
        
        // If no duration, draw a simple timeline
        if (!player.duration) {
            this.drawSimpleTimeline();
            return;
        }
        
        // Calculate visible range based on zoom
        const visibleDuration = player.duration / player.zoomLevel;
        const startTime = player.zoomOffset * player.duration;
        const endTime = Math.min(startTime + visibleDuration, player.duration);
        
        // Draw time markers
        this.drawTimeMarkers(startTime, endTime, visibleDuration);
        
        // Draw segments if available
        this.drawSegments(startTime, visibleDuration);
    }
    
    /**
     * Draw a simple timeline when no duration is available
     */
    drawSimpleTimeline() {
        const player = this.player;
        
        // Draw a simple timeline with 0 and duration markers
        const simpleDuration = 60; // Default 60 seconds if no duration available
        const width = player.timelineContainer.clientWidth;
        
        // Start marker (0s)
        const startMarker = document.createElement('div');
        startMarker.className = 'position-absolute';
        startMarker.style.left = '0px';
        startMarker.style.top = '0';
        startMarker.style.bottom = '0';
        startMarker.style.width = '1px';
        startMarker.style.backgroundColor = '#6c757d';
        
        const startLabel = document.createElement('div');
        startLabel.className = 'position-absolute text-light small';
        startLabel.style.left = '0px';
        startLabel.style.bottom = '0';
        startLabel.textContent = '0.0s';
        
        // End marker
        const endMarker = document.createElement('div');
        endMarker.className = 'position-absolute';
        endMarker.style.left = (width - 1) + 'px';
        endMarker.style.top = '0';
        endMarker.style.bottom = '0';
        endMarker.style.width = '1px';
        endMarker.style.backgroundColor = '#6c757d';
        
        const endLabel = document.createElement('div');
        endLabel.className = 'position-absolute text-light small';
        endLabel.style.left = (width - 30) + 'px';
        endLabel.style.bottom = '0';
        endLabel.textContent = simpleDuration.toFixed(1) + 's';
        
        player.timelineContainer.appendChild(startMarker);
        player.timelineContainer.appendChild(startLabel);
        player.timelineContainer.appendChild(endMarker);
        player.timelineContainer.appendChild(endLabel);
    }
    
    /**
     * Draw time markers on the timeline
     */
    drawTimeMarkers(startTime, endTime, visibleDuration) {
        const player = this.player;
        const width = player.timelineContainer.clientWidth;
        
        // Determine appropriate time step based on visible duration
        let timeStep;
        if (visibleDuration <= 2) {
            timeStep = 0.1; // Show 0.1 second intervals for very zoomed view
        } else if (visibleDuration <= 5) {
            timeStep = 0.5; // Show 0.5 second intervals
        } else if (visibleDuration <= 10) {
            timeStep = 1; // Show 1 second intervals
        } else if (visibleDuration <= 30) {
            timeStep = 2; // Show 2 second intervals
        } else if (visibleDuration <= 60) {
            timeStep = 5; // Show 5 second intervals
        } else if (visibleDuration <= 300) {
            timeStep = 30; // Show 30 second intervals
        } else {
            timeStep = 60; // Show 1 minute intervals
        }
        
        // Calculate start time aligned with time step
        const firstMarkerTime = Math.ceil(startTime / timeStep) * timeStep;
        
        // Draw time markers
        for (let time = firstMarkerTime; time <= endTime; time += timeStep) {
            // Skip if we're at exactly duration (edge case)
            if (time > player.duration) break;
            
            // Calculate x position for the marker
            const markerX = ((time - startTime) / visibleDuration) * width;
            
            // Only draw if in the visible area
            if (markerX >= 0 && markerX <= width) {
                const marker = document.createElement('div');
                marker.className = 'position-absolute';
                marker.style.left = markerX + 'px';
                marker.style.top = '0';
                marker.style.bottom = '0';
                marker.style.width = '1px';
                marker.style.backgroundColor = '#6c757d';
                
                const label = document.createElement('div');
                label.className = 'position-absolute text-light small';
                label.style.left = (markerX - 12) + 'px';
                label.style.bottom = '0';
                
                // Format the label based on duration
                if (visibleDuration > 60) {
                    // Show minutes:seconds for longer durations
                    const minutes = Math.floor(time / 60);
                    const seconds = time % 60;
                    label.textContent = `${minutes}:${seconds.toFixed(0).padStart(2, '0')}`;
                } else if (visibleDuration <= 3) {
                    // Show more precision for short durations
                    label.textContent = time.toFixed(2) + 's';
                } else {
                    label.textContent = time.toFixed(1) + 's';
                }
                
                player.timelineContainer.appendChild(marker);
                player.timelineContainer.appendChild(label);
            }
        }
    }
    
    /**
     * Draw segments on the timeline
     */
    drawSegments(startTime, visibleDuration) {
        const player = this.player;
        const width = player.timelineContainer.clientWidth;
        
        player.segments.forEach(segment => {
            // Calculate segment position in the visible window
            const segmentStartTime = segment.onset;
            const segmentEndTime = segment.offset;
            
            // Convert to pixel positions
            const segmentStart = ((segmentStartTime - startTime) / visibleDuration) * width;
            const segmentEnd = ((segmentEndTime - startTime) / visibleDuration) * width;
            
            // Skip segments outside the visible range
            if (segmentEnd < 0 || segmentStart > width) {
                return;
            }
            
            // Clip to visible area
            const visibleStart = Math.max(0, segmentStart);
            const visibleEnd = Math.min(width, segmentEnd);
            const visibleWidth = visibleEnd - visibleStart;
            
            // Create segment marker
            if (visibleWidth > 0) {
                const segmentMarker = document.createElement('div');
                segmentMarker.className = 'position-absolute';
                segmentMarker.style.left = visibleStart + 'px';
                segmentMarker.style.width = visibleWidth + 'px';
                segmentMarker.style.top = '5px';
                segmentMarker.style.height = '20px';
                segmentMarker.style.backgroundColor = '#007bff';
                segmentMarker.style.opacity = '0.7';
                segmentMarker.style.borderRadius = '2px';
                segmentMarker.title = `Segment ${segment.id}: ${segment.onset.toFixed(2)}s - ${segment.offset.toFixed(2)}s`;
                
                // Add clipping indicators if segment extends beyond visible area
                if (segmentStart < 0) {
                    // Add left indicator
                    segmentMarker.style.borderLeftWidth = '3px';
                    segmentMarker.style.borderLeftStyle = 'dashed';
                    segmentMarker.style.borderLeftColor = '#ff9800';
                }
                
                if (segmentEnd > width) {
                    // Add right indicator
                    segmentMarker.style.borderRightWidth = '3px';
                    segmentMarker.style.borderRightStyle = 'dashed';
                    segmentMarker.style.borderRightColor = '#ff9800';
                }
                
                player.timelineContainer.appendChild(segmentMarker);
            }
        });
    }
}
