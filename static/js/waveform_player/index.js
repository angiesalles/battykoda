/**
 * BattyCoda Waveform Player - Main Entry Point
 * 
 * This is the main entry point for the waveform player that exports the public API
 * and imports all required modules.
 */

import { WaveformPlayer } from './player.js';

// Global registry to expose player instances outside this module
if (window.waveformPlayers === undefined) {
    window.waveformPlayers = {};
}

/**
 * Initializes a waveform player for a recording
 * @param {string} containerId - ID of the container element
 * @param {number} recordingId - ID of the recording
 * @param {boolean} allowSelection - Whether to allow selecting regions
 * @param {boolean} showZoom - Whether to show zoom controls
 * @param {Array} [segmentsData] - Optional array of segments to display in the waveform
 */
function initWaveformPlayer(containerId, recordingId, allowSelection, showZoom, segmentsData) {
    // Create a new WaveformPlayer instance
    const player = new WaveformPlayer(containerId, recordingId, allowSelection, showZoom, segmentsData);
    
    // Register the player instance in the global registry
    window.waveformPlayers[containerId] = {
        getSelection: function() {
            return player.getSelection();
        },
        setSegments: function(newSegments) {
            player.setSegments(newSegments || []);
        }
    };
    
    // Initialize the player
    player.initialize();
}

// Export for use in global scope
window.initWaveformPlayer = initWaveformPlayer;
