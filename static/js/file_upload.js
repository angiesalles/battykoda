document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form[enctype="multipart/form-data"]');
    const progressBar = document.getElementById('upload-progress-bar');
    const progressContainer = document.getElementById('upload-progress-container');
    const statusText = document.getElementById('upload-status');
    const fileInput = document.querySelector('input[type="file"][name="wav_file"]');
    const cancelButton = document.getElementById('cancel-upload');
    let xhr;
    
    if (!form || !progressBar || !fileInput) return;
    
    // Show progress bar when file is selected
    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            const fileName = this.files[0].name;
            const fileSize = (this.files[0].size / (1024 * 1024)).toFixed(2);
            statusText.textContent = `File: ${fileName} (${fileSize} MB)`;
            progressContainer.classList.remove('d-none');
        } else {
            progressContainer.classList.add('d-none');
        }
    });
    
    // Cancel button functionality
    if (cancelButton) {
        cancelButton.addEventListener('click', function() {
            if (xhr && xhr.readyState !== 4) {
                xhr.abort();
                statusText.textContent = 'Upload cancelled';
                progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
                progressBar.classList.add('bg-warning');
            }
        });
    }
    
    form.addEventListener('submit', function(e) {
        // Only handle if there's a file to upload
        if (fileInput.files.length === 0) return;
        
        e.preventDefault();
        
        xhr = new XMLHttpRequest();
        const formData = new FormData(form);
        
        // Setup progress tracking
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = percentComplete + '%';
                progressBar.textContent = percentComplete + '%';
                progressBar.setAttribute('aria-valuenow', percentComplete);
                
                if (percentComplete === 100) {
                    statusText.textContent = 'Processing file...';
                    progressBar.classList.remove('progress-bar-animated');
                }
            }
        });
        
        // Handle response
        xhr.addEventListener('load', function(e) {
            if (xhr.status === 200) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.success) {
                        statusText.textContent = 'Upload complete!';
                        progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
                        progressBar.classList.add('bg-success');
                        
                        // Redirect to the batch detail page or show success message
                        if (response.redirect_url) {
                            window.location.href = response.redirect_url;
                        }
                    } else {
                        handleError(response.error || 'Upload failed');
                    }
                } catch (err) {
                    // Handle non-JSON response (likely HTML from a successful form submission)
                    window.location.href = xhr.responseURL;
                }
            } else {
                handleError('Upload failed');
            }
        });
        
        xhr.addEventListener('error', function() {
            handleError('Network error occurred');
        });
        
        xhr.addEventListener('abort', function() {
            handleError('Upload aborted');
        });
        
        function handleError(message) {
            statusText.textContent = message;
            progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
            progressBar.classList.add('bg-danger');
        }
        
        // Send the form data
        xhr.open('POST', form.action, true);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        
        // Include CSRF token
        const csrfToken = document.querySelector('[name="csrfmiddlewaretoken"]').value;
        xhr.setRequestHeader('X-CSRFToken', csrfToken);
        
        // Start upload
        statusText.textContent = 'Starting upload...';
        xhr.send(formData);
    });
});