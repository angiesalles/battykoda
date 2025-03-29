/**
 * Waveform Viewer JavaScript
 * 
 * This file contains all the JavaScript functionality for the waveform viewer interface,
 * including spectrogram loading, audio playback, and UI interactions.
 */

document.addEventListener('DOMContentLoaded', function() {
    // File information
    const wavPath = wavViewerConfig.wavPath;
    const fileHash = wavViewerConfig.fileHash;
    const totalCalls = wavViewerConfig.totalCalls; // Loaded from the pickle file
    
    console.log("Loading WAV file:", wavPath);
    console.log("File hash:", fileHash);
    console.log("Total calls found:", totalCalls);
    
    // Current state
    let currentCall = 0;
    let currentChannel = 0;
    let contrastValue = 4.0;
    let loudnessValue = 1.0;
    let overviewMode = false;
    
    // UI elements
    const spectrogramImg = document.getElementById('spectrogram');
    const channelSelector = document.getElementById('channel-selector');
    const contrastInput = document.getElementById('contrast');
    const loudnessInput = document.getElementById('loudness');
    const playAudioBtn = document.getElementById('play-audio-btn');
    const overviewBtn = document.getElementById('overview-btn');
    const detailBtn = document.getElementById('detail-btn');
    const prevCallBtn = document.getElementById('prev-call-btn');
    const nextCallBtn = document.getElementById('next-call-btn');
    const updateBtn = document.getElementById('update-btn');
    const audioPlayer = document.getElementById('audio-player');
    const audioPlayerLong = document.getElementById('audio-player-long');
    const currentCallText = document.getElementById('current-call-text');
    const totalCallsText = document.getElementById('total-calls-text');
    const otherChannelsContainer = document.getElementById('other-channels-container');
    
    // Update UI to show current call
    function updateCallDisplay() {
        currentCallText.textContent = (currentCall + 1);
        totalCallsText.textContent = totalCalls;
    }

    // Load spectrogram
    function loadSpectrogram() {
        // Build URL for spectrogram
        const spectrogramUrl = `${wavViewerConfig.spectrogramUrl}?wav_path=${encodeURIComponent(wavPath)}&call=${currentCall}&channel=${currentChannel}&numcalls=${totalCalls}&hash=${fileHash}&overview=${overviewMode ? '1' : '0'}&contrast=${contrastValue}`;
        
        console.log("Loading spectrogram from:", spectrogramUrl);
        
        // Load spectrogram
        const img = new Image();
        img.onload = function() {
            console.log("Spectrogram loaded successfully");
            spectrogramImg.src = this.src;
        };
        img.onerror = function(e) {
            console.error("Failed to load spectrogram:", e);
            // Show error message on the page
            const container = document.querySelector('.spectrogram-section');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger';
            errorDiv.textContent = 'Failed to load spectrogram. Check console for details.';
            container.appendChild(errorDiv);
        };
        img.src = spectrogramUrl;
        
        // Load other channels
        loadOtherChannels();
    }
    
    // Load audio
    function loadAudio() {
        // Build URL for short audio snippet
        const audioUrl = `${wavViewerConfig.audioUrl}?wav_path=${encodeURIComponent(wavPath)}&call=${currentCall}&channel=${currentChannel}&hash=${fileHash}&overview=False&loudness=${loudnessValue}`;
        
        // Build URL for long audio snippet
        const audioLongUrl = `${wavViewerConfig.audioUrl}?wav_path=${encodeURIComponent(wavPath)}&call=${currentCall}&channel=${currentChannel}&hash=${fileHash}&overview=True&loudness=${loudnessValue}`;
        
        console.log("Loading short audio from:", audioUrl);
        console.log("Loading long audio from:", audioLongUrl);
        
        // Clear any previous error messages
        const existingErrors = document.querySelectorAll('.audio-error-message');
        existingErrors.forEach(el => el.remove());
        
        // Set audio sources with error handling
        audioPlayer.addEventListener('error', function(e) {
            console.error("Error loading short audio:", e);
            console.error("Error details:", audioPlayer.error);
            const container = document.querySelector('.audio-section');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger mt-2 audio-error-message';
            errorDiv.textContent = 'Failed to load audio snippet. Error: ' + 
                (audioPlayer.error ? 'Code: ' + audioPlayer.error.code + ', Message: ' + getErrorMessage(audioPlayer.error.code) : 'Unknown error');
            container.appendChild(errorDiv);
        });
        
        audioPlayerLong.addEventListener('error', function(e) {
            console.error("Error loading long audio:", e);
            console.error("Error details:", audioPlayerLong.error);
            const container = document.querySelector('.audio-section');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger mt-2 audio-error-message';
            errorDiv.textContent = 'Failed to load long audio snippet. Error: ' + 
                (audioPlayerLong.error ? 'Code: ' + audioPlayerLong.error.code + ', Message: ' + getErrorMessage(audioPlayerLong.error.code) : 'Unknown error');
            container.appendChild(errorDiv);
        });
        
        // Helper function to get media error messages
        function getErrorMessage(code) {
            switch(code) {
                case 1: return 'MEDIA_ERR_ABORTED - The fetching process was aborted by the user.';
                case 2: return 'MEDIA_ERR_NETWORK - A network error occurred while fetching the media.';
                case 3: return 'MEDIA_ERR_DECODE - A decoding error occurred.';
                case 4: return 'MEDIA_ERR_SRC_NOT_SUPPORTED - The audio format is not supported.';
                default: return 'Unknown error code.';
            }
        }
        
        // Set a cache-busting parameter to prevent browser caching issues
        const cacheBuster = new Date().getTime();
        
        // Set sources
        audioPlayer.src = audioUrl + "&t=" + cacheBuster;
        audioPlayer.load();
        
        audioPlayerLong.src = audioLongUrl + "&t=" + cacheBuster;
        audioPlayerLong.load();
    }
    
    // Load other channels
    function loadOtherChannels() {
        otherChannelsContainer.innerHTML = '';
        
        // Get all channels except the main one
        const maxChannels = 2; // This should be determined from the WAV file
        for (let i = 0; i < maxChannels; i++) {
            if (i != currentChannel) {
                const channelUrl = `${wavViewerConfig.spectrogramUrl}?wav_path=${encodeURIComponent(wavPath)}&call=${currentCall}&channel=${i}&numcalls=${totalCalls}&hash=${fileHash}&overview=0&contrast=${contrastValue}`;
                
                const container = document.createElement('div');
                container.className = 'mb-3';
                
                const title = document.createElement('p');
                title.textContent = `Channel ${i+1}:`;
                container.appendChild(title);
                
                const imgContainer = document.createElement('div');
                imgContainer.className = 'spectrogram-container';
                container.appendChild(imgContainer);
                
                const img = document.createElement('img');
                img.alt = `Channel ${i+1} Spectrogram`;
                img.src = channelUrl;
                imgContainer.appendChild(img);
                
                otherChannelsContainer.appendChild(container);
            }
        }
    }
    
    // Event handlers
    channelSelector.addEventListener('change', function() {
        currentChannel = parseInt(this.value);
        loadSpectrogram();
        loadAudio();
    });
    
    updateBtn.addEventListener('click', function(e) {
        e.preventDefault();
        contrastValue = parseFloat(contrastInput.value);
        loudnessValue = parseFloat(loudnessInput.value);
        loadSpectrogram();
        loadAudio();
    });
    
    overviewBtn.addEventListener('click', function() {
        overviewMode = true;
        overviewBtn.classList.add('active');
        detailBtn.classList.remove('active');
        loadSpectrogram();
        loadAudio();
    });
    
    detailBtn.addEventListener('click', function() {
        overviewMode = false;
        detailBtn.classList.add('active');
        overviewBtn.classList.remove('active');
        loadSpectrogram();
        loadAudio();
    });
    
    prevCallBtn.addEventListener('click', function(e) {
        e.preventDefault();
        if (currentCall > 0) {
            currentCall--;
            updateCallDisplay();
            loadSpectrogram();
            loadAudio();
        }
    });
    
    nextCallBtn.addEventListener('click', function(e) {
        e.preventDefault();
        if (currentCall < totalCalls - 1) {
            currentCall++;
            updateCallDisplay();
            loadSpectrogram();
            loadAudio();
        }
    });
    
    document.getElementById('save-changes-btn').addEventListener('click', function() {
        alert('Changes saved!'); // Placeholder - actual save functionality to be implemented
    });
    
    document.getElementById('export-csv-btn').addEventListener('click', function() {
        alert('Exporting to CSV...'); // Placeholder - actual export functionality to be implemented
    });
    
    // Initialize the page
    updateCallDisplay();
    loadSpectrogram();
    loadAudio();
});