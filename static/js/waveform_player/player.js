/**
 * BattyCoda Waveform Player - Core Player Class
 * 
 * Main player class that orchestrates all waveform player functionality
 */

import { WaveformRenderer } from './renderer.js';
import { TimelineRenderer } from './timeline.js';

/**
 * WaveformPlayer class - encapsulates waveform player functionality
 */
export class WaveformPlayer {
    /**
     * Create a new WaveformPlayer instance
     * @param {string} containerId - ID of the container element
     * @param {number} recordingId - ID of the recording
     * @param {boolean} allowSelection - Whether to allow selecting regions
     * @param {boolean} showZoom - Whether to show zoom controls
     * @param {Array} [segmentsData] - Optional array of segments to display
     */
    constructor(containerId, recordingId, allowSelection, showZoom, segmentsData) {
        // Configuration
        this.containerId = containerId;
        this.recordingId = recordingId;
        this.allowSelection = allowSelection;
        this.showZoom = showZoom;
        
        // DOM elements
        this.initDomElements();
        
        // State
        this.currentTime = 0;
        this.duration = parseFloat(this.totalTimeEl?.textContent) || 0;
        this.isPlaying = false;
        this.waveformData = null;
        this.segments = segmentsData || [];
        this.zoomLevel = 1;
        this.zoomOffset = 0;
        this.selectionStart = null;
        this.selectionEnd = null;
        this.animationFrameId = null;
        this.targetZoomOffset = this.zoomOffset;

        // Renderers
        this.waveformRenderer = new WaveformRenderer(this);
        this.timelineRenderer = new TimelineRenderer(this);
    }
    
    /**
     * Initialize DOM element references
     */
    initDomElements() {
        const id = this.containerId;
        
        // Core elements
        this.container = document.getElementById(id);
        if (!this.container) return;
        
        this.audioPlayer = document.getElementById(`${id}-audio`);
        this.playBtn = document.getElementById(`${id}-play-btn`);
        this.pauseBtn = document.getElementById(`${id}-pause-btn`);
        this.stopBtn = document.getElementById(`${id}-stop-btn`);
        this.progressBar = document.getElementById(`${id}-progress-bar`);
        this.progressContainer = document.getElementById(`${id}-progress-container`);
        this.currentTimeEl = document.getElementById(`${id}-current-time`);
        this.totalTimeEl = document.getElementById(`${id}-total-time`);
        this.waveformContainer = document.getElementById(id);
        this.timelineContainer = document.getElementById(`${id}-timeline`);
        this.loadingEl = document.getElementById(`${id}-loading`);
        this.statusEl = document.getElementById(`${id}-status`);
        
        // Optional elements based on configuration
        if (this.showZoom) {
            this.zoomInBtn = document.getElementById(`${id}-zoom-in-btn`);
            this.zoomOutBtn = document.getElementById(`${id}-zoom-out-btn`);
            this.resetZoomBtn = document.getElementById(`${id}-reset-zoom-btn`);
        }
        
        if (this.allowSelection) {
            this.setStartBtn = document.getElementById(`${id}-set-start-btn`);
            this.setEndBtn = document.getElementById(`${id}-set-end-btn`);
            this.selectionRangeEl = document.getElementById(`${id}-selection-range`);
        }
    }
    
    /**
     * Initialize the waveform player
     */
    initialize() {
        this.setupEventListeners();
        this.loadWaveformData();
        this.updateTimeDisplay();
        if (this.allowSelection) this.updateSelectionDisplay();
        this.updatePlayButtons();
    }
    
    /**
     * Load waveform data from the server
     */
    async loadWaveformData() {
        try {
            // Update status
            if (this.statusEl) this.statusEl.textContent = 'Loading...';
            
            const response = await fetch(`/recordings/${this.recordingId}/waveform-data/`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            // Always update duration if available, even on error
            if (data.duration !== undefined && data.duration !== null) {
                this.duration = data.duration || 0;
                if (this.totalTimeEl) this.totalTimeEl.textContent = this.duration.toFixed(2) + 's';
            }
            
            if (data.success) {
                this.waveformData = data.waveform;
                
                // Hide loading indicator
                if (this.loadingEl) this.loadingEl.style.display = 'none';
                
                // Update status
                if (this.statusEl) {
                    this.statusEl.textContent = 'Complete';
                    this.statusEl.classList.remove('bg-info');
                    this.statusEl.classList.add('bg-success');
                }
                
                // Draw waveform and timeline
                this.drawWaveform();
                this.drawTimeline();
            } else {
                throw new Error(data.error || 'Failed to load waveform data');
            }
        } catch (error) {
            console.error('Error loading waveform data:', error);
            
            // Hide loading indicator
            if (this.loadingEl) this.loadingEl.style.display = 'none';
            
            // Update status
            if (this.statusEl) {
                this.statusEl.textContent = 'Error';
                this.statusEl.classList.remove('bg-info');
                this.statusEl.classList.add('bg-danger');
            }
            
            // Show error message
            if (this.waveformContainer) {
                this.waveformContainer.innerHTML = `
                    <div class="alert alert-danger m-3">
                        <i class="fas fa-exclamation-triangle"></i> 
                        Error loading waveform: ${error.message}
                    </div>
                `;
            }
            
            // Still attempt to draw the timeline with empty data
            this.drawTimeline();
        }
    }
    
    /**
     * Draw the waveform visualization
     */
    drawWaveform() {
        this.waveformRenderer.draw();
    }
    
    /**
     * Draw the timeline below the waveform
     */
    drawTimeline() {
        this.timelineRenderer.draw();
    }
    
    /**
     * Update the time display
     */
    updateTimeDisplay() {
        // Ensure currentTime is a valid number
        const time = Number.isFinite(this.currentTime) ? this.currentTime : 0;
        if (this.currentTimeEl) this.currentTimeEl.textContent = time.toFixed(2) + 's';
        
        // Avoid division by zero if duration is not set
        const percentage = this.duration ? ((time / this.duration) * 100) : 0;
        if (this.progressBar) this.progressBar.style.width = percentage + '%';
        
        // If zoomed in, add a visual indicator of the current view in the progress bar
        if (this.zoomLevel > 1 && this.progressContainer) {
            // Remove any existing view indicator
            const existingIndicator = this.progressContainer.querySelector('.zoom-view-indicator');
            if (existingIndicator) {
                existingIndicator.remove();
            }
            
            // Calculate visible range as percentage of total duration
            const visibleDuration = this.duration / this.zoomLevel;
            const startPercent = (this.zoomOffset * this.duration / this.duration) * 100;
            const widthPercent = (visibleDuration / this.duration) * 100;
            
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
            
            this.progressContainer.appendChild(indicator);
        } else if (this.progressContainer) {
            // Remove indicator if not zoomed
            const existingIndicator = this.progressContainer.querySelector('.zoom-view-indicator');
            if (existingIndicator) {
                existingIndicator.remove();
            }
        }
    }
    
    /**
     * Update the selection display
     */
    updateSelectionDisplay() {
        if (!this.allowSelection || !this.selectionRangeEl) return;
        
        if (this.selectionStart !== null && this.selectionEnd !== null) {
            // Both start and end points are set
            const start = Number.isFinite(this.selectionStart) ? this.selectionStart : 0;
            const end = Number.isFinite(this.selectionEnd) ? this.selectionEnd : 0;
            const selectionDuration = end - start;
            this.selectionRangeEl.textContent = `Selection: ${start.toFixed(2)}s - ${end.toFixed(2)}s (${selectionDuration.toFixed(2)}s)`;
        } else if (this.selectionStart !== null) {
            // Only start point is set
            const start = Number.isFinite(this.selectionStart) ? this.selectionStart : 0;
            this.selectionRangeEl.textContent = `Start: ${start.toFixed(2)}s (End not set)`;
        } else if (this.selectionEnd !== null) {
            // Only end point is set
            const end = Number.isFinite(this.selectionEnd) ? this.selectionEnd : 0;
            this.selectionRangeEl.textContent = `End: ${end.toFixed(2)}s (Start not set)`;
        } else {
            this.selectionRangeEl.textContent = 'No Selection';
        }
    }
    
    /**
     * Update play/pause buttons state
     */
    updatePlayButtons() {
        if (this.isPlaying) {
            if (this.playBtn) this.playBtn.disabled = true;
            if (this.pauseBtn) this.pauseBtn.disabled = false;
            if (this.stopBtn) this.stopBtn.disabled = false;
        } else {
            if (this.playBtn) this.playBtn.disabled = false;
            if (this.pauseBtn) this.pauseBtn.disabled = true;
            if (this.stopBtn) this.stopBtn.disabled = true;
        }
    }
    
    /**
     * Get the current selection range
     * @returns {Object} The selection range with start and end times
     */
    getSelection() {
        return { start: this.selectionStart, end: this.selectionEnd };
    }
    
    /**
     * Set segments for the waveform
     * @param {Array} newSegments - Array of segment objects
     */
    setSegments(newSegments) {
        this.segments = newSegments || [];
        this.drawWaveform();
        this.drawTimeline();
    }
    
    /**
     * Set up all event listeners
     */
    setupEventListeners() {
        this.setupAudioEventListeners();
        this.setupControlEventListeners();
        this.setupZoomEventListeners();
        this.setupSelectionEventListeners();
        this.setupWindowEventListeners();
    }
    
    /**
     * Set up audio player event listeners
     */
    setupAudioEventListeners() {
        if (!this.audioPlayer) return;
        
        let lastScrollUpdateTime = 0;
        
        this.audioPlayer.addEventListener('timeupdate', () => {
            this.currentTime = this.audioPlayer.currentTime;
            this.updateTimeDisplay();
            
            // If zoomed in, continuously update the view to keep the cursor in the center
            if (this.zoomLevel > 1 && this.isPlaying) {
                const visibleDuration = this.duration / this.zoomLevel;
                
                // Center the view on current time, with bounds checking
                const targetCenter = this.currentTime / this.duration;
                const halfVisibleDuration = visibleDuration / 2 / this.duration;
                
                // Calculate new offset (start of visible window)
                // This centers the playhead in the visible area
                this.targetZoomOffset = Math.max(0, Math.min(
                    targetCenter - halfVisibleDuration,
                    1 - visibleDuration / this.duration
                ));
                
                // Only update if significant change or enough time has passed
                const now = performance.now();
                if (Math.abs(this.targetZoomOffset - this.zoomOffset) > 0.01 || (now - lastScrollUpdateTime > 250)) {
                    // Handle animation or immediate update
                    if (!this.animationFrameId) {
                        // Don't animate during continuous playback, just set position directly
                        this.zoomOffset = this.targetZoomOffset;
                        this.drawWaveform();
                        this.drawTimeline();
                    }
                    lastScrollUpdateTime = now;
                    return; // Skip the drawWaveform below to avoid double draws
                }
            }
            
            // Just update waveform (for cursor) if we didn't do a full redraw above
            this.drawWaveform();
        });
        
        this.audioPlayer.addEventListener('play', () => {
            this.isPlaying = true;
            this.updatePlayButtons();
        });
        
        this.audioPlayer.addEventListener('pause', () => {
            this.isPlaying = false;
            this.updatePlayButtons();
        });
        
        this.audioPlayer.addEventListener('ended', () => {
            this.isPlaying = false;
            this.updatePlayButtons();
        });
    }
    
    /**
     * Set up control button event listeners
     */
    setupControlEventListeners() {
        // Play button
        if (this.playBtn) {
            this.playBtn.addEventListener('click', () => {
                this.audioPlayer.play();
            });
        }
        
        // Pause button
        if (this.pauseBtn) {
            this.pauseBtn.addEventListener('click', () => {
                this.audioPlayer.pause();
            });
        }
        
        // Stop button
        if (this.stopBtn) {
            this.stopBtn.addEventListener('click', () => {
                this.audioPlayer.pause();
                this.audioPlayer.currentTime = 0;
                this.currentTime = 0;
                this.updateTimeDisplay();
                this.drawWaveform();
            });
        }
        
        // Progress container click
        if (this.progressContainer) {
            this.progressContainer.addEventListener('click', (e) => {
                const rect = this.progressContainer.getBoundingClientRect();
                const offsetX = e.clientX - rect.left;
                const clickPosition = offsetX / rect.width;
                
                // Set current time based on click position (progress bar always shows full duration)
                this.currentTime = clickPosition * this.duration;
                this.audioPlayer.currentTime = this.currentTime;
                
                // If zoomed in, adjust view to center on clicked position
                if (this.zoomLevel > 1) {
                    const visibleDuration = this.duration / this.zoomLevel;
                    this.targetZoomOffset = Math.max(0, Math.min(
                        this.currentTime / this.duration - (visibleDuration / this.duration) * 0.5,
                        1 - visibleDuration / this.duration
                    ));
                    
                    // Use animation for click navigation
                    if (Math.abs(this.targetZoomOffset - this.zoomOffset) > 0.01) {
                        this.animateScroll();
                        return; // Animation will handle update
                    }
                }
                
                this.updateTimeDisplay();
                this.drawWaveform();
            });
        }
    }
    
    /**
     * Set up zoom button event listeners
     */
    setupZoomEventListeners() {
        if (!this.showZoom) return;
        
        // Zoom in button
        if (this.zoomInBtn) {
            this.zoomInBtn.addEventListener('click', () => {
                // Store the current center position
                const oldZoomLevel = this.zoomLevel;
                const oldVisibleDuration = this.duration / oldZoomLevel;
                const oldCenterTime = this.currentTime;
                
                // Calculate where the current position is as a fraction of the visible area
                const relativePosition = (oldCenterTime - (this.zoomOffset * this.duration)) / oldVisibleDuration;
                
                // Update zoom level
                this.zoomLevel = Math.min(this.zoomLevel * 1.5, 10);
                
                // Calculate new visible duration
                const newVisibleDuration = this.duration / this.zoomLevel;
                
                // Calculate new offset to keep position centered
                this.zoomOffset = Math.max(0, Math.min(
                    oldCenterTime / this.duration - (newVisibleDuration / this.duration) * 0.5, 
                    1 - newVisibleDuration / this.duration
                ));
                
                // Update all displays
                this.drawWaveform();
                this.drawTimeline();
                this.updateTimeDisplay();
            });
        }
        
        // Zoom out button
        if (this.zoomOutBtn) {
            this.zoomOutBtn.addEventListener('click', () => {
                // Store the current center position
                const oldCenterTime = this.currentTime;
                
                // Update zoom level
                this.zoomLevel = Math.max(this.zoomLevel / 1.5, 1);
                
                // If we're back to zoom level 1, reset offset
                if (this.zoomLevel === 1) {
                    this.zoomOffset = 0;
                } else {
                    // Otherwise recalculate offset to keep current position visible
                    const newVisibleDuration = this.duration / this.zoomLevel;
                    this.zoomOffset = Math.max(0, Math.min(
                        oldCenterTime / this.duration - (newVisibleDuration / this.duration) * 0.5,
                        1 - newVisibleDuration / this.duration
                    ));
                }
                
                // Update all displays
                this.drawWaveform();
                this.drawTimeline();
                this.updateTimeDisplay();
            });
        }
        
        // Reset zoom button
        if (this.resetZoomBtn) {
            this.resetZoomBtn.addEventListener('click', () => {
                this.zoomLevel = 1;
                this.zoomOffset = 0;
                
                // Update all displays
                this.drawWaveform();
                this.drawTimeline();
                this.updateTimeDisplay();
            });
        }
    }
    
    /**
     * Set up selection button event listeners
     */
    setupSelectionEventListeners() {
        if (!this.allowSelection) return;
        
        // Set start button
        if (this.setStartBtn) {
            this.setStartBtn.addEventListener('click', () => {
                // Start a new selection - clear any existing selection
                this.selectionStart = this.currentTime;
                this.selectionEnd = null;
                this.updateSelectionDisplay();
                this.drawWaveform();
                
                // Update button states
                this.setStartBtn.disabled = false;  // Allow changing start point
            });
        }
        
        // Set end button
        if (this.setEndBtn) {
            // Disable end button initially until start is set
            this.setEndBtn.disabled = true;
            
            this.setEndBtn.addEventListener('click', () => {
                // Only set end if there's a start point and current time is after it
                if (this.selectionStart !== null && this.currentTime > this.selectionStart) {
                    this.selectionEnd = this.currentTime;
                    this.updateSelectionDisplay();
                    this.drawWaveform();
                    
                    // Reset button states after completing a selection
                    this.setStartBtn.disabled = false;
                    this.setEndBtn.disabled = true;
                }
            });
            
            // We need to regularly update end button state based on playhead position
            this.audioPlayer.addEventListener('timeupdate', () => {
                if (this.selectionStart !== null && this.selectionEnd === null) {
                    // Only enable end button if we're to the right of start point
                    this.setEndBtn.disabled = this.currentTime <= this.selectionStart;
                } else {
                    // Disable end button if no start point or already have end point
                    this.setEndBtn.disabled = true;
                }
            });
        }
    }
    
    /**
     * Set up window event listeners
     */
    setupWindowEventListeners() {
        // Window resize event
        window.addEventListener('resize', () => {
            this.drawWaveform();
            this.drawTimeline();
        });
    }
    
    /**
     * Animate scrolling the waveform smoothly
     */
    animateScroll() {
        // Cancel any existing animation
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
        
        const startTime = performance.now();
        const startOffset = this.zoomOffset;
        const offsetDiff = this.targetZoomOffset - startOffset;
        const duration = 300; // animation duration in ms
        
        const step = (timestamp) => {
            const elapsed = timestamp - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease function (ease-out cubic)
            const eased = 1 - Math.pow(1 - progress, 3);
            
            // Update zoom offset
            this.zoomOffset = startOffset + (offsetDiff * eased);
            
            // Redraw
            this.drawWaveform();
            this.drawTimeline();
            this.updateTimeDisplay();
            
            // Continue animation if not complete
            if (progress < 1) {
                this.animationFrameId = requestAnimationFrame(step);
            } else {
                this.animationFrameId = null;
            }
        };
        
        // Start animation
        this.animationFrameId = requestAnimationFrame(step);
    }
}
