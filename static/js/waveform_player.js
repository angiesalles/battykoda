/**
 * Initializes a waveform player for a recording
 * @param {string} containerId - ID of the container element
 * @param {number} recordingId - ID of the recording
 * @param {boolean} allowSelection - Whether to allow selecting regions
 * @param {boolean} showZoom - Whether to show zoom controls
 * @param {Array} [segmentsData] - Optional array of segments to display in the waveform
 */
function initWaveformPlayer(containerId, recordingId, allowSelection, showZoom, segmentsData) {
    // DOM elements
    const container = document.getElementById(containerId);
    if (!container) return;

    const audioPlayer = document.getElementById(`${containerId}-audio`);
    const playBtn = document.getElementById(`${containerId}-play-btn`);
    const pauseBtn = document.getElementById(`${containerId}-pause-btn`);
    const stopBtn = document.getElementById(`${containerId}-stop-btn`);
    const progressBar = document.getElementById(`${containerId}-progress-bar`);
    const progressContainer = document.getElementById(`${containerId}-progress-container`);
    const currentTimeEl = document.getElementById(`${containerId}-current-time`);
    const totalTimeEl = document.getElementById(`${containerId}-total-time`);
    const waveformContainer = document.getElementById(containerId);
    const timelineContainer = document.getElementById(`${containerId}-timeline`);
    const loadingEl = document.getElementById(`${containerId}-loading`);
    const statusEl = document.getElementById(`${containerId}-status`);

    // Optional elements
    const zoomInBtn = showZoom ? document.getElementById(`${containerId}-zoom-in-btn`) : null;
    const zoomOutBtn = showZoom ? document.getElementById(`${containerId}-zoom-out-btn`) : null;
    const resetZoomBtn = showZoom ? document.getElementById(`${containerId}-reset-zoom-btn`) : null;
    const setStartBtn = allowSelection ? document.getElementById(`${containerId}-set-start-btn`) : null;
    const setEndBtn = allowSelection ? document.getElementById(`${containerId}-set-end-btn`) : null;
    const selectionRangeEl = allowSelection ? document.getElementById(`${containerId}-selection-range`) : null;

    // State
    let currentTime = 0;
    let duration = parseFloat(totalTimeEl.textContent) || 0;
    let isPlaying = false;
    let waveformData = null;
    let segments = segmentsData || [];
    let zoomLevel = 1;
    let zoomOffset = 0;
    let selectionStart = null;
    let selectionEnd = null;
    
    // Make segments accessible from outside
    if (window.waveformPlayers === undefined) {
        window.waveformPlayers = {};
    }
    window.waveformPlayers[containerId] = {
        getSelection: function() {
            return { start: selectionStart, end: selectionEnd };
        },
        setSegments: function(newSegments) {
            segments = newSegments || [];
            drawWaveform(); // Redraw the waveform with updated segments
            drawTimeline(); // Redraw the timeline with updated segments
        }
    };

    // Load waveform data
    async function loadWaveformData() {
        try {
            // Update status
            if (statusEl) statusEl.textContent = 'Loading...';
            
            const response = await fetch(`/recordings/${recordingId}/waveform-data/`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            // Always update duration if available, even on error
            if (data.duration !== undefined && data.duration !== null) {
                duration = data.duration || 0;
                if (totalTimeEl) totalTimeEl.textContent = duration.toFixed(2) + 's';
            }
            
            if (data.success) {
                waveformData = data.waveform;
                
                // Hide loading indicator
                if (loadingEl) loadingEl.style.display = 'none';
                
                // Update status
                if (statusEl) {
                    statusEl.textContent = 'Complete';
                    statusEl.classList.remove('bg-info');
                    statusEl.classList.add('bg-success');
                }
                
                // Draw waveform
                drawWaveform();
                drawTimeline();
            } else {
                throw new Error(data.error || 'Failed to load waveform data');
            }
        } catch (error) {
            console.error('Error loading waveform data:', error);
            
            // Hide loading indicator
            if (loadingEl) loadingEl.style.display = 'none';
            
            // Update status
            if (statusEl) {
                statusEl.textContent = 'Error';
                statusEl.classList.remove('bg-info');
                statusEl.classList.add('bg-danger');
            }
            
            // Show error message
            if (waveformContainer) {
                waveformContainer.innerHTML = `
                    <div class="alert alert-danger m-3">
                        <i class="fas fa-exclamation-triangle"></i> 
                        Error loading waveform: ${error.message}
                    </div>
                `;
            }
            
            // Still attempt to draw the timeline with empty data
            drawTimeline();
        }
    }
    
    // Draw waveform
    function drawWaveform() {
        if (!waveformData || !waveformContainer) return;
        
        // Calculate visible duration for consistency
        const visibleDuration = duration / zoomLevel;
        const visibleStartTime = zoomOffset * duration;
        const visibleEndTime = Math.min(visibleStartTime + visibleDuration, duration);
        
        // Create canvas
        waveformContainer.innerHTML = '';
        const canvas = document.createElement('canvas');
        canvas.width = waveformContainer.clientWidth;
        canvas.height = waveformContainer.clientHeight;
        waveformContainer.appendChild(canvas);
        
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        
        // Clear canvas
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, width, height);
        
        // Calculate visible range based on zoom
        const visibleDataPoints = waveformData.length / zoomLevel;
        const startIdx = Math.floor(zoomOffset * waveformData.length);
        const endIdx = Math.min(startIdx + visibleDataPoints, waveformData.length);
        
        // Draw waveform with enhanced visuals
        
        // Calculate how many data points per pixel
        const pointsPerPixel = (endIdx - startIdx) / width;
        
        // Create a single blue gradient for the entire waveform
        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, '#1976D2');    // Top (furthest from center)
        gradient.addColorStop(0.5, '#42A5F5');  // Center
        gradient.addColorStop(1, '#1976D2');    // Bottom (furthest from center)
        
        // Draw the positive part of the waveform (top half)
        ctx.beginPath();
        ctx.lineWidth = 1.5;  // Slightly thicker line
        
        // Start at the center line
        ctx.moveTo(0, height/2);
        
        for (let i = 0; i < width; i++) {
            const dataIdx = startIdx + Math.floor(i * (endIdx - startIdx) / width);
            if (dataIdx < waveformData.length) {
                // Find the value, ensure it's not below zero for the positive part
                const value = Math.max(0, waveformData[dataIdx]);
                // Map from -1...1 to height...0
                const y = height/2 - (value * height/2);
                ctx.lineTo(i, y);
            }
        }
        
        // Back to center line
        ctx.lineTo(width, height/2);
        
        // Close and fill the positive half
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();
        
        // Now draw the negative part of the waveform (bottom half)
        ctx.beginPath();
        ctx.lineWidth = 1.5;  // Slightly thicker line
        
        // Start at the center line
        ctx.moveTo(0, height/2);
        
        for (let i = 0; i < width; i++) {
            const dataIdx = startIdx + Math.floor(i * (endIdx - startIdx) / width);
            if (dataIdx < waveformData.length) {
                // Find the value, ensure it's not above zero for the negative part
                const value = Math.min(0, waveformData[dataIdx]);
                // Map from -1...1 to height/2...height
                const y = height/2 + (Math.abs(value) * height/2);
                ctx.lineTo(i, y);
            }
        }
        
        // Back to center line
        ctx.lineTo(width, height/2);
        
        // Close and fill the negative half
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();
        
        // Add a line for the waveform outline
        ctx.beginPath();
        ctx.lineWidth = 1.0;  // Slightly thinner outline
        
        // Go through all points to draw a continuous outline
        let firstPoint = true;
        
        for (let i = 0; i < width; i++) {
            const dataIdx = startIdx + Math.floor(i * (endIdx - startIdx) / width);
            if (dataIdx < waveformData.length) {
                const value = waveformData[dataIdx];
                // Map from -1...1 to height...0
                const y = height/2 - (value * height/2);
                
                if (firstPoint) {
                    ctx.moveTo(i, y);
                    firstPoint = false;
                } else {
                    ctx.lineTo(i, y);
                }
            }
        }
        
        // Draw the outline in a slightly darker blue
        ctx.strokeStyle = 'rgba(21, 101, 192, 0.7)';
        ctx.stroke();
        
        // Draw centerline
        ctx.beginPath();
        ctx.strokeStyle = '#6c757d';
        ctx.lineWidth = 0.5;
        ctx.moveTo(0, height / 2);
        ctx.lineTo(width, height / 2);
        ctx.stroke();
        
        // Draw selection if allowed
        if (allowSelection) {
            // Calculate visible range based on zoom
            const visibleDuration = duration / zoomLevel;
            const visibleStartTime = zoomOffset * duration;
            const visibleEndTime = visibleStartTime + visibleDuration;
            
            // Handle case where both start and end are set
            if (selectionStart !== null && selectionEnd !== null) {
                // Convert selection times to x coordinates relative to visible window
                const startX = ((selectionStart - visibleStartTime) / visibleDuration) * width;
                const endX = ((selectionEnd - visibleStartTime) / visibleDuration) * width;
                
                // Check if any part of the selection is visible
                if ((startX >= 0 && startX <= width) || 
                    (endX >= 0 && endX <= width) || 
                    (startX < 0 && endX > width)) {
                    
                    // Calculate visible portion of selection
                    const visibleStartX = Math.max(0, startX);
                    const visibleEndX = Math.min(width, endX);
                    
                    // Only draw if there's a visible portion
                    if (visibleEndX > visibleStartX) {
                        // Fill selection area
                        ctx.fillStyle = 'rgba(255, 193, 7, 0.3)';
                        ctx.fillRect(visibleStartX, 0, visibleEndX - visibleStartX, height);
                        
                        // Draw selection boundaries if visible
                        ctx.beginPath();
                        ctx.strokeStyle = '#ffc107';
                        ctx.lineWidth = 2;
                        
                        // Start boundary
                        if (startX >= 0 && startX <= width) {
                            ctx.moveTo(startX, 0);
                            ctx.lineTo(startX, height);
                        }
                        
                        // End boundary
                        if (endX >= 0 && endX <= width) {
                            ctx.moveTo(endX, 0);
                            ctx.lineTo(endX, height);
                        }
                        
                        ctx.stroke();
                    }
                }
            } 
            // Handle case where only start is set
            else if (selectionStart !== null) {
                const startX = ((selectionStart - visibleStartTime) / visibleDuration) * width;
                
                // Check if the start point is visible
                if (startX >= 0 && startX <= width) {
                    // Draw only the start boundary
                    ctx.beginPath();
                    ctx.strokeStyle = '#ffc107';
                    ctx.lineWidth = 2;
                    ctx.moveTo(startX, 0);
                    ctx.lineTo(startX, height);
                    ctx.stroke();
                }
            }
            // Handle case where only end is set
            else if (selectionEnd !== null) {
                const endX = ((selectionEnd - visibleStartTime) / visibleDuration) * width;
                
                // Check if the end point is visible
                if (endX >= 0 && endX <= width) {
                    // Draw only the end boundary
                    ctx.beginPath();
                    ctx.strokeStyle = '#ffc107';
                    ctx.lineWidth = 2;
                    ctx.moveTo(endX, 0);
                    ctx.lineTo(endX, height);
                    ctx.stroke();
                }
            }
        }
        
        // Draw cursor at current time
        // Calculate cursor position relative to visible window
        const cursorX = ((currentTime - visibleStartTime) / visibleDuration) * width;

        // Draw cursor
        ctx.beginPath();
        ctx.strokeStyle = '#fd7e14';
        ctx.lineWidth = 2;
        ctx.moveTo(cursorX, 0);
        ctx.lineTo(cursorX, height);
        ctx.stroke();
        
        // Add click event listener to canvas for seeking
        canvas.addEventListener('click', function(e) {
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            
            // Calculate time position considering zoom:
            // First, convert x position to proportion of visible width
            const visibleProportion = x / width;
            
            // Calculate visible duration and start time
            const visibleDuration = duration / zoomLevel;
            const visibleStartTime = zoomOffset * duration;
            
            // Calculate the actual time position
            const timePos = visibleStartTime + (visibleProportion * visibleDuration);
            
            // Set current time
            currentTime = Math.max(0, Math.min(duration, timePos));
            audioPlayer.currentTime = currentTime;
            updateTimeDisplay();
            drawWaveform();
        });
    }
    
    // Draw timeline
    function drawTimeline() {
        if (!timelineContainer) return;
        
        // Clear timeline
        timelineContainer.innerHTML = '';
        
        // If no duration, draw a simple timeline
        if (!duration) {
            // Draw a simple timeline with 0 and duration markers
            const simpleDuration = 60; // Default 60 seconds if no duration available
            const width = timelineContainer.clientWidth;
            
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
            
            timelineContainer.appendChild(startMarker);
            timelineContainer.appendChild(startLabel);
            timelineContainer.appendChild(endMarker);
            timelineContainer.appendChild(endLabel);
            
            return;
        }
        
        // Calculate visible range based on zoom
        const visibleDuration = duration / zoomLevel;
        const startTime = zoomOffset * duration;
        const endTime = Math.min(startTime + visibleDuration, duration);
        
        // Calculate number of markers based on visible duration
        const width = timelineContainer.clientWidth;
        
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
            if (time > duration) break;
            
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
                
                timelineContainer.appendChild(marker);
                timelineContainer.appendChild(label);
            }
        }
        
        // Draw segments if available
        segments.forEach(segment => {
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
                
                timelineContainer.appendChild(segmentMarker);
            }
        });
    }
    
    // Update time display
    function updateTimeDisplay() {
        // Ensure currentTime is a valid number
        const time = Number.isFinite(currentTime) ? currentTime : 0;
        if (currentTimeEl) currentTimeEl.textContent = time.toFixed(2) + 's';
        
        // Avoid division by zero if duration is not set
        const percentage = duration ? ((time / duration) * 100) : 0;
        if (progressBar) progressBar.style.width = percentage + '%';
        
        // If zoomed in, add a visual indicator of the current view in the progress bar
        if (zoomLevel > 1 && progressContainer) {
            // Remove any existing view indicator
            const existingIndicator = progressContainer.querySelector('.zoom-view-indicator');
            if (existingIndicator) {
                existingIndicator.remove();
            }
            
            // Calculate visible range as percentage of total duration
            const visibleDuration = duration / zoomLevel;
            const startPercent = (zoomOffset * duration / duration) * 100;
            const widthPercent = (visibleDuration / duration) * 100;
            
            // Create indicator element
            const indicator = document.createElement('div');
            indicator.className = 'zoom-view-indicator position-absolute';
            indicator.style.position = 'absolute';
            indicator.style.left = startPercent + '%';
            indicator.style.width = widthPercent + '%';
            indicator.style.height = '5px';
            indicator.style.bottom = '0';
            indicator.style.backgroundColor = 'rgba(255, 255, 255, 0.5)';
            indicator.style.borderRadius = '2px';
            indicator.style.pointerEvents = 'none'; // Don't interfere with clicks
            
            progressContainer.appendChild(indicator);
        } else if (progressContainer) {
            // Remove indicator if not zoomed
            const existingIndicator = progressContainer.querySelector('.zoom-view-indicator');
            if (existingIndicator) {
                existingIndicator.remove();
            }
        }
    }
    
    // Update selection display (if selection is enabled)
    function updateSelectionDisplay() {
        if (!allowSelection || !selectionRangeEl) return;
        
        if (selectionStart !== null && selectionEnd !== null) {
            // Both start and end points are set
            const start = Number.isFinite(selectionStart) ? selectionStart : 0;
            const end = Number.isFinite(selectionEnd) ? selectionEnd : 0;
            const selectionDuration = end - start;
            selectionRangeEl.textContent = `Selection: ${start.toFixed(2)}s - ${end.toFixed(2)}s (${selectionDuration.toFixed(2)}s)`;
        } else if (selectionStart !== null) {
            // Only start point is set
            const start = Number.isFinite(selectionStart) ? selectionStart : 0;
            selectionRangeEl.textContent = `Start: ${start.toFixed(2)}s (End not set)`;
        } else if (selectionEnd !== null) {
            // Only end point is set
            const end = Number.isFinite(selectionEnd) ? selectionEnd : 0;
            selectionRangeEl.textContent = `End: ${end.toFixed(2)}s (Start not set)`;
        } else {
            selectionRangeEl.textContent = 'No Selection';
        }
    }
    
    // Update play/pause buttons state
    function updatePlayButtons() {
        if (isPlaying) {
            if (playBtn) playBtn.disabled = true;
            if (pauseBtn) pauseBtn.disabled = false;
            if (stopBtn) stopBtn.disabled = false;
        } else {
            if (playBtn) playBtn.disabled = false;
            if (pauseBtn) pauseBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = true;
        }
    }
    
    // Event Listeners
    
    // Audio player time update
    if (audioPlayer) {
        let lastScrollUpdateTime = 0;
        
        audioPlayer.addEventListener('timeupdate', function() {
            currentTime = audioPlayer.currentTime;
            updateTimeDisplay();
            
            // If zoomed in, continuously update the view to keep the cursor in the center
            if (zoomLevel > 1 && isPlaying) {
                const visibleDuration = duration / zoomLevel;
                
                // Center the view on current time, with bounds checking
                const targetCenter = currentTime / duration;
                const halfVisibleDuration = visibleDuration / 2 / duration;
                
                // Calculate new offset (start of visible window)
                // This centers the playhead in the visible area
                targetZoomOffset = Math.max(0, Math.min(
                    targetCenter - halfVisibleDuration,
                    1 - visibleDuration / duration
                ));
                
                // Only update if significant change or enough time has passed
                const now = performance.now();
                if (Math.abs(targetZoomOffset - zoomOffset) > 0.01 || (now - lastScrollUpdateTime > 250)) {
                    // Handle animation or immediate update
                    if (!animationFrameId) {
                        // Don't animate during continuous playback, just set position directly
                        zoomOffset = targetZoomOffset;
                        drawWaveform();
                        drawTimeline();
                    }
                    lastScrollUpdateTime = now;
                    return; // Skip the drawWaveform below to avoid double draws
                }
            }
            
            // Just update waveform (for cursor) if we didn't do a full redraw above
            drawWaveform();
        });
        
        audioPlayer.addEventListener('play', function() {
            isPlaying = true;
            updatePlayButtons();
        });
        
        audioPlayer.addEventListener('pause', function() {
            isPlaying = false;
            updatePlayButtons();
        });
        
        audioPlayer.addEventListener('ended', function() {
            isPlaying = false;
            updatePlayButtons();
        });
    }
    
    // Play button
    if (playBtn) {
        playBtn.addEventListener('click', function() {
            audioPlayer.play();
        });
    }
    
    // Pause button
    if (pauseBtn) {
        pauseBtn.addEventListener('click', function() {
            audioPlayer.pause();
        });
    }
    
    // Stop button
    if (stopBtn) {
        stopBtn.addEventListener('click', function() {
            audioPlayer.pause();
            audioPlayer.currentTime = 0;
            currentTime = 0;
            updateTimeDisplay();
            drawWaveform();
        });
    }
    
    // Progress container click
    if (progressContainer) {
        progressContainer.addEventListener('click', function(e) {
            const rect = this.getBoundingClientRect();
            const offsetX = e.clientX - rect.left;
            const clickPosition = offsetX / rect.width;
            
            // Set current time based on click position (progress bar always shows full duration)
            currentTime = clickPosition * duration;
            audioPlayer.currentTime = currentTime;
            
            // If zoomed in, adjust view to center on clicked position
            if (zoomLevel > 1) {
                const visibleDuration = duration / zoomLevel;
                targetZoomOffset = Math.max(0, Math.min(
                    currentTime / duration - (visibleDuration / duration) * 0.5,
                    1 - visibleDuration / duration
                ));
                
                // Use animation for click navigation
                if (Math.abs(targetZoomOffset - zoomOffset) > 0.01) {
                    animateScroll();
                    return; // Animation will handle update
                }
            }
            
            updateTimeDisplay();
            drawWaveform();
        });
    }
    
    // Selection buttons (if enabled)
    if (allowSelection) {
        if (setStartBtn) {
            setStartBtn.addEventListener('click', function() {
                // Start a new selection - clear any existing selection
                selectionStart = currentTime;
                selectionEnd = null;
                updateSelectionDisplay();
                drawWaveform();
                
                // Update button states
                setStartBtn.disabled = false;  // Allow changing start point
                
                // End button state will be updated by the timeupdate listener
            });
        }
        
        if (setEndBtn) {
            // Disable end button initially until start is set
            setEndBtn.disabled = true;
            
            setEndBtn.addEventListener('click', function() {
                // Only set end if there's a start point and current time is after it
                if (selectionStart !== null && currentTime > selectionStart) {
                    selectionEnd = currentTime;
                    updateSelectionDisplay();
                    drawWaveform();
                    
                    // Reset button states after completing a selection
                    setStartBtn.disabled = false;
                    setEndBtn.disabled = true;
                }
            });
            
            // We need to regularly update end button state based on playhead position
            audioPlayer.addEventListener('timeupdate', function() {
                if (selectionStart !== null && selectionEnd === null) {
                    // Only enable end button if we're to the right of start point
                    setEndBtn.disabled = currentTime <= selectionStart;
                } else {
                    // Disable end button if no start point or already have end point
                    setEndBtn.disabled = true;
                }
            });
        }
    }
    
    // Zoom buttons (if enabled)
    if (showZoom) {
        if (zoomInBtn) {
            zoomInBtn.addEventListener('click', function() {
                // Store the current position relative to the visible portion
                const oldZoomLevel = zoomLevel;
                const oldVisibleDuration = duration / oldZoomLevel;
                const oldCenterTime = currentTime;
                
                // Calculate where the current position is as a fraction of the visible area
                const relativePosition = (oldCenterTime - (zoomOffset * duration)) / oldVisibleDuration;
                
                // Update zoom level
                zoomLevel = Math.min(zoomLevel * 1.5, 10);
                
                // Calculate new visible duration
                const newVisibleDuration = duration / zoomLevel;
                
                // Calculate new offset to keep position centered
                // zoomOffset represents the start of the visible window as a fraction of total duration
                zoomOffset = Math.max(0, Math.min(
                    oldCenterTime / duration - (newVisibleDuration / duration) * 0.5, 
                    1 - newVisibleDuration / duration
                ));
                
                // Update all displays
                drawWaveform();
                drawTimeline();
                updateTimeDisplay(); // Also update time display to show zoom indicator
            });
        }
        
        if (zoomOutBtn) {
            zoomOutBtn.addEventListener('click', function() {
                // Store the current center position
                const oldCenterTime = currentTime;
                
                // Update zoom level
                zoomLevel = Math.max(zoomLevel / 1.5, 1);
                
                // If we're back to zoom level 1, reset offset
                if (zoomLevel === 1) {
                    zoomOffset = 0;
                } else {
                    // Otherwise recalculate offset to keep current position visible
                    const newVisibleDuration = duration / zoomLevel;
                    zoomOffset = Math.max(0, Math.min(
                        oldCenterTime / duration - (newVisibleDuration / duration) * 0.5,
                        1 - newVisibleDuration / duration
                    ));
                }
                
                // Update all displays
                drawWaveform();
                drawTimeline();
                updateTimeDisplay(); // Also update time display to show zoom indicator
            });
        }
        
        if (resetZoomBtn) {
            resetZoomBtn.addEventListener('click', function() {
                zoomLevel = 1;
                zoomOffset = 0;
                
                // Update all displays
                drawWaveform();
                drawTimeline();
                updateTimeDisplay(); // Also update time display to show zoom indicator
            });
        }
    }
    
    // Window resize event
    window.addEventListener('resize', function() {
        drawWaveform();
        drawTimeline();
    });
    
    // Animation frame management for smooth scrolling
    let animationFrameId = null;
    let targetZoomOffset = zoomOffset;
    
    // Function to smoothly animate the waveform scrolling
    function animateScroll() {
        // Cancel any existing animation
        if (animationFrameId) {
            cancelAnimationFrame(animationFrameId);
            animationFrameId = null;
        }
        
        const startTime = performance.now();
        const startOffset = zoomOffset;
        const offsetDiff = targetZoomOffset - startOffset;
        const duration = 300; // animation duration in ms
        
        function step(timestamp) {
            const elapsed = timestamp - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease function (ease-out cubic)
            const eased = 1 - Math.pow(1 - progress, 3);
            
            // Update zoom offset
            zoomOffset = startOffset + (offsetDiff * eased);
            
            // Redraw
            drawWaveform();
            drawTimeline();
            updateTimeDisplay();
            
            // Continue animation if not complete
            if (progress < 1) {
                animationFrameId = requestAnimationFrame(step);
            } else {
                animationFrameId = null;
            }
        }
        
        // Start animation
        animationFrameId = requestAnimationFrame(step);
    }
    
    // Initialize
    loadWaveformData();
    updateTimeDisplay();
    if (allowSelection) updateSelectionDisplay();
    updatePlayButtons();
}