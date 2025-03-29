/**
 * Task Annotation JavaScript
 * 
 * This file contains all the JavaScript functionality for the task annotation interface,
 * including spectrogram switching, channel toggling, and form handling.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize spectrogram viewer functionality
    initSpectrogramViewer();
    
    // Initialize form behavior
    initFormBehavior();
});

/**
 * Initialize the spectrogram viewer with channel and view switching
 */
function initSpectrogramViewer() {
    const mainSpectrogram = document.getElementById('main-spectrogram');
    const detailViewBtn = document.getElementById('detail-view-btn');
    const overviewBtn = document.getElementById('overview-btn');
    const channelToggle = document.getElementById('channel-toggle');
    const channelLabel = document.getElementById('channel-label');
    const detailTicks = document.getElementById('detail-ticks');
    const overviewTicks = document.getElementById('overview-ticks');
    
    // If any of these elements don't exist, return early
    if (!mainSpectrogram || !detailViewBtn || !overviewBtn || !channelToggle || 
        !channelLabel || !detailTicks || !overviewTicks) {
        console.error("Some required elements are missing from the page.");
        return;
    }
    
    let currentChannel = 0;
    let isOverview = false;
    
    // Function to update spectrogram based on current settings
    function updateSpectrogram() {
        const key = `channel_${currentChannel}_${isOverview ? 'overview' : 'detail'}`;
        
        if (taskConfig.spectrogramUrls[key]) {
            // Update the image source
            mainSpectrogram.src = taskConfig.spectrogramUrls[key];
            
            // Update audio player
            updateAudioPlayer();
            
            // Update x-axis ticks
            if (isOverview) {
                detailTicks.classList.remove('active');
                overviewTicks.classList.add('active');
            } else {
                detailTicks.classList.add('active');
                overviewTicks.classList.remove('active');
            }
        } else {
            console.error("Spectrogram URL not found for key:", key);
        }
    }
    
    // Function to update audio player URL
    function updateAudioPlayer() {
        const audioPlayer = document.getElementById('audio-player');
        if (audioPlayer) {
            const overviewParam = isOverview ? 'True' : 'False';
            const cacheBuster = new Date().getTime();
            
            // Build audio URL with configuration variables
            audioPlayer.src = `${taskConfig.audioSnippetUrl}?wav_path=${encodeURIComponent(taskConfig.wavPath)}&call=0&channel=${currentChannel}&hash=${taskConfig.fileHash}&overview=${overviewParam}&onset=${taskConfig.onset}&offset=${taskConfig.offset}&loudness=1.0&t=${cacheBuster}`;
        }
    }
    
    // Set up event listeners
    detailViewBtn.addEventListener('click', function() {
        isOverview = false;
        // Update button styles
        detailViewBtn.classList.add('active');
        detailViewBtn.classList.remove('btn-outline-primary');
        detailViewBtn.classList.add('btn-primary');
        overviewBtn.classList.remove('active');
        overviewBtn.classList.remove('btn-primary');
        overviewBtn.classList.add('btn-outline-secondary');
        updateSpectrogram();
    });
    
    overviewBtn.addEventListener('click', function() {
        isOverview = true;
        // Update button styles
        overviewBtn.classList.add('active');
        overviewBtn.classList.remove('btn-outline-secondary');
        overviewBtn.classList.add('btn-primary');
        detailViewBtn.classList.remove('active');
        detailViewBtn.classList.remove('btn-primary');
        detailViewBtn.classList.add('btn-outline-secondary');
        updateSpectrogram();
    });
    
    channelToggle.addEventListener('change', function() {
        currentChannel = this.checked ? 1 : 0;
        channelLabel.textContent = `Channel ${currentChannel + 1}`;
        updateSpectrogram();
    });
    
    // Initialize on page load
    updateSpectrogram();
}

/**
 * Initialize form behavior for the task annotation
 */
function initFormBehavior() {
    // When the "Other" input receives focus, also select the "Other" radio button
    const otherRadio = document.getElementById('Other');
    const otherInput = document.getElementById('other-input');
    
    if (otherInput && otherRadio) {
        otherInput.addEventListener('focus', function() {
            otherRadio.checked = true;
        });
    }
    
    // Add any other form-related behavior here
}