document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form[enctype="multipart/form-data"]');
    const progressBar = document.getElementById('upload-progress-bar');
    const progressContainer = document.getElementById('upload-progress-container');
    const statusText = document.getElementById('upload-status');
    const wavFileInput = document.querySelector('input[type="file"][name="wav_file"]');
    const pickleFileInput = document.querySelector('input[type="file"][name="pickle_file"]');
    const cancelButton = document.getElementById('cancel-upload');
    let xhr;
    
    if (!form || !progressBar || !wavFileInput || !pickleFileInput) return;
    
    // Track total file size for both files
    let totalFileSize = 0;
    let fileCount = 0;
    let filenames = [];
    
    // Initialize dropzone styling for file inputs
    setupDropzone(wavFileInput);
    setupDropzone(pickleFileInput);
    
    // Handle file selection for either file input
    wavFileInput.addEventListener('change', updateFilesInfo);
    pickleFileInput.addEventListener('change', updateFilesInfo);
    
    function setupDropzone(fileInput) {
        const container = fileInput.parentElement;
        const dropArea = document.createElement('div');
        dropArea.className = 'file-dropzone p-4 mb-3 text-center border border-secondary rounded';
        dropArea.innerHTML = `
            <div class="file-icon mb-2"><i class="fas fa-file-upload fa-2x"></i></div>
            <p>Drag & drop your file here or click to browse</p>
            <small class="text-muted">Selected file: <span class="selected-filename">None</span></small>
        `;
        
        // Insert dropzone before fileInput
        fileInput.parentNode.insertBefore(dropArea, fileInput);
        
        // Hide the original input
        fileInput.style.display = 'none';
        
        // Click on dropzone should trigger file input
        dropArea.addEventListener('click', function() {
            fileInput.click();
        });
        
        // Update dropzone when file is selected
        fileInput.addEventListener('change', function() {
            const filenameSpan = dropArea.querySelector('.selected-filename');
            if (this.files.length > 0) {
                const fileName = this.files[0].name;
                const fileSize = (this.files[0].size / (1024 * 1024)).toFixed(2);
                filenameSpan.textContent = `${fileName} (${fileSize} MB)`;
                dropArea.classList.add('border-success');
                dropArea.classList.remove('border-secondary');
            } else {
                filenameSpan.textContent = 'None';
                dropArea.classList.remove('border-success');
                dropArea.classList.add('border-secondary');
            }
        });
        
        // Handle drag and drop
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        // Handle visual feedback during drag
        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight() {
            dropArea.classList.add('border-primary');
            dropArea.classList.add('bg-dark');
        }
        
        function unhighlight() {
            dropArea.classList.remove('border-primary');
            dropArea.classList.remove('bg-dark');
        }
        
        // Handle the actual drop
        dropArea.addEventListener('drop', function(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (files.length > 0) {
                fileInput.files = files;
                // Trigger change event manually
                const event = new Event('change');
                fileInput.dispatchEvent(event);
            }
        });
    }
    
    function updateFilesInfo() {
        // Reset counts
        totalFileSize = 0;
        fileCount = 0;
        filenames = [];
        
        // Check WAV file
        if (wavFileInput.files.length > 0) {
            totalFileSize += wavFileInput.files[0].size;
            fileCount++;
            filenames.push(wavFileInput.files[0].name);
        }
        
        // Check pickle file
        if (pickleFileInput.files.length > 0) {
            totalFileSize += pickleFileInput.files[0].size;
            fileCount++;
            filenames.push(pickleFileInput.files[0].name);
        }
        
        // Only show progress if at least one file is selected
        if (fileCount > 0) {
            const totalSizeMB = (totalFileSize / (1024 * 1024)).toFixed(2);
            statusText.innerHTML = `
                <div class="mb-2">Selected ${fileCount} file${fileCount > 1 ? 's' : ''} (${totalSizeMB} MB total)</div>
                <div>${filenames.map(name => `<span class="badge bg-info me-2">${name}</span>`).join('')}</div>
            `;
            progressContainer.classList.remove('d-none');
        } else {
            progressContainer.classList.add('d-none');
        }
    }
    
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
        // Check if we have the required files
        if (wavFileInput.files.length === 0 || pickleFileInput.files.length === 0) {
            // Let the normal form submission handle validation errors
            return;
        }
        
        e.preventDefault();
        
        // Update UI to show we're starting
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        progressBar.setAttribute('aria-valuenow', 0);
        progressBar.classList.remove('bg-success', 'bg-danger', 'bg-warning');
        progressBar.classList.add('progress-bar-striped', 'progress-bar-animated', 'bg-primary');
        statusText.textContent = 'Preparing files for upload...';
        
        xhr = new XMLHttpRequest();
        const formData = new FormData(form);
        
        // Setup progress tracking
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = percentComplete + '%';
                progressBar.textContent = percentComplete + '%';
                progressBar.setAttribute('aria-valuenow', percentComplete);
                
                if (percentComplete < 100) {
                    statusText.textContent = `Uploading files: ${percentComplete}% (${Math.round(e.loaded / 1048576)}MB / ${Math.round(e.total / 1048576)}MB)`;
                } else {
                    statusText.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Processing files and creating tasks...';
                    progressBar.classList.remove('progress-bar-animated');
                }
            }
        });
        
        // Handle response
        xhr.addEventListener('load', function() {
            if (xhr.status === 200) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.success) {
                        statusText.innerHTML = `
                            <div class="alert alert-success">
                                <i class="fas fa-check-circle me-2"></i>
                                Upload complete! Successfully created batch with ${response.tasks_created || 'multiple'} tasks.
                            </div>
                        `;
                        progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
                        progressBar.classList.add('bg-success');
                        
                        // Show success animation before redirect
                        setTimeout(() => {
                            // Redirect to the batch detail page or show success message
                            if (response.redirect_url) {
                                window.location.href = response.redirect_url;
                            }
                        }, 1500);
                    } else {
                        handleError(response.error || 'Upload failed');
                    }
                } catch (err) {
                    console.error("JSON parse error:", err);
                    // Handle non-JSON response (likely HTML from a successful form submission)
                    if (xhr.responseURL) {
                        window.location.href = xhr.responseURL;
                    } else {
                        handleError('Unknown response from server');
                    }
                }
            } else {
                handleError(`Upload failed (${xhr.status}: ${xhr.statusText})`);
            }
        });
        
        xhr.addEventListener('error', function() {
            handleError('Network error occurred');
        });
        
        xhr.addEventListener('abort', function() {
            handleError('Upload aborted');
        });
        
        function handleError(message) {
            statusText.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    ${message}
                </div>
            `;
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