document.addEventListener('DOMContentLoaded', function() {
    // Only apply to the batch upload form by checking URL
    if (!window.location.pathname.includes('batch-upload')) {
        return;
    }
    
    const uploadForm = document.querySelector('form[enctype="multipart/form-data"]');
    
    if (uploadForm) {
        // Create progress elements
        const progressContainer = document.createElement('div');
        progressContainer.id = 'upload-progress-container';
        progressContainer.style.display = 'none';
        progressContainer.style.marginTop = '20px';
        progressContainer.style.padding = '15px';
        progressContainer.style.border = '1px solid #dee2e6';
        progressContainer.style.borderRadius = '5px';
        progressContainer.style.backgroundColor = '#212529';
        
        const progressLabel = document.createElement('h6');
        progressLabel.textContent = 'Upload Progress';
        progressLabel.style.marginBottom = '10px';
        
        const progressBarContainer = document.createElement('div');
        progressBarContainer.style.height = '24px';
        progressBarContainer.style.backgroundColor = '#495057';
        progressBarContainer.style.borderRadius = '4px';
        progressBarContainer.style.overflow = 'hidden';
        
        const progressBar = document.createElement('div');
        progressBar.id = 'progress-bar';
        progressBar.style.width = '0%';
        progressBar.style.height = '100%';
        progressBar.style.backgroundColor = '#0d6efd';
        progressBar.style.transition = 'width 0.3s';
        
        const progressText = document.createElement('div');
        progressText.id = 'progress-text';
        progressText.className = 'text-light';
        progressText.textContent = '0%';
        progressText.style.marginTop = '8px';
        progressText.style.textAlign = 'center';
        
        const progressDetails = document.createElement('div');
        progressDetails.id = 'progress-details';
        progressDetails.className = 'text-muted small';
        progressDetails.style.marginTop = '5px';
        progressDetails.textContent = 'Preparing upload...';
        
        // Assemble progress UI
        progressBarContainer.appendChild(progressBar);
        progressContainer.appendChild(progressLabel);
        progressContainer.appendChild(progressBarContainer);
        progressContainer.appendChild(progressText);
        progressContainer.appendChild(progressDetails);
        
        // Add to the page after the form
        uploadForm.insertAdjacentElement('afterend', progressContainer);
        
        // Create a unique upload ID for this session
        const uploadId = 'upload_' + Date.now();
        
        // Store it in a hidden input
        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'upload_id';
        hiddenInput.value = uploadId;
        uploadForm.appendChild(hiddenInput);
        
        // Add submit event listener
        uploadForm.addEventListener('submit', function(e) {
            // Check if any files are selected
            const fileInputs = document.querySelectorAll('input[type="file"]');
            let hasFiles = false;
            
            fileInputs.forEach(input => {
                if (input.files.length > 0) {
                    hasFiles = true;
                }
            });
            
            if (hasFiles) {
                // Show progress container
                progressContainer.style.display = 'block';
                
                // Start polling for progress
                startProgressPolling(uploadId);
                
                // Let the form submit normally
                return true;
            }
        });
        
        // Function to poll progress
        function startProgressPolling(uploadId) {
            // Set a flag to know when to stop polling
            window.isUploading = true;
            
            // Function to fetch progress
            function checkProgress() {
                if (!window.isUploading) {
                    return; // Stop polling if upload is done
                }
                
                // Make AJAX request to get progress
                fetch(`/recordings/upload-progress/?upload_id=${uploadId}`)
                    .then(response => response.json())
                    .then(data => {
                        const progressBar = document.getElementById('progress-bar');
                        const progressText = document.getElementById('progress-text');
                        const progressDetails = document.getElementById('progress-details');
                        
                        if (progressBar && progressText) {
                            // Set progress bar width and text
                            const percent = data.percent || 0;
                            progressBar.style.width = `${percent}%`;
                            progressText.textContent = `${percent}%`;
                            
                            // Set details text
                            if (progressDetails) {
                                if (data.status === 'processing') {
                                    progressDetails.textContent = 'Processing files on server...';
                                    progressBar.style.animation = 'pulse 1.5s infinite';
                                } else if (percent === 100) {
                                    progressDetails.textContent = 'Upload complete, processing...';
                                    progressBar.style.animation = 'pulse 1.5s infinite';
                                } else {
                                    const uploaded = formatBytes(data.uploaded || 0);
                                    const total = formatBytes(data.total || 0);
                                    progressDetails.textContent = `${uploaded} of ${total} uploaded`;
                                }
                            }
                            
                            // Add pulsing effect for processing state
                            if (!document.getElementById('progress-style') && (percent === 100 || data.status === 'processing')) {
                                const style = document.createElement('style');
                                style.id = 'progress-style';
                                style.textContent = `
                                    @keyframes pulse {
                                        0% { opacity: 1; }
                                        50% { opacity: 0.6; }
                                        100% { opacity: 1; }
                                    }
                                `;
                                document.head.appendChild(style);
                            }
                            
                            // Continue polling unless we're at 100% or the status is 'complete'
                            if (percent < 100 && data.status !== 'complete') {
                                setTimeout(checkProgress, 1000);
                            } else {
                                // We'll continue for a short while even at 100% to show processing
                                setTimeout(checkProgress, 2000);
                            }
                        }
                    })
                    .catch(error => {
                        console.error('Error checking upload progress:', error);
                        // Try again after a delay
                        setTimeout(checkProgress, 3000);
                    });
            }
            
            // Format bytes to human-readable format
            function formatBytes(bytes, decimals = 2) {
                if (bytes === 0) return '0 Bytes';
                
                const k = 1024;
                const dm = decimals < 0 ? 0 : decimals;
                const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
                
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                
                return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
            }
            
            // Start the polling
            checkProgress();
            
            // Set an event listener to stop polling when page unloads
            window.addEventListener('beforeunload', function() {
                window.isUploading = false;
            });
        }
    }
});