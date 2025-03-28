document.addEventListener('DOMContentLoaded', function() {
    // Set a flag to let other scripts know we've initialized
    window.advancedUploadInitialized = true;
    
    // Setup persistent logging
    const debugLogs = localStorage.getItem('debugLogs') || '';
    if (debugLogs) {
        console.log('PREVIOUS SESSION LOGS:');
        console.log(debugLogs);
        
        // Create debug panel if not exists
        if (!document.getElementById('debug-panel')) {
            const debugPanel = document.createElement('div');
            debugPanel.id = 'debug-panel';
            debugPanel.style.position = 'fixed';
            debugPanel.style.bottom = '10px';
            debugPanel.style.right = '10px';
            debugPanel.style.width = '300px';
            debugPanel.style.maxHeight = '200px';
            debugPanel.style.overflow = 'auto';
            debugPanel.style.backgroundColor = 'rgba(0,0,0,0.8)';
            debugPanel.style.color = '#0f0';
            debugPanel.style.padding = '10px';
            debugPanel.style.borderRadius = '5px';
            debugPanel.style.zIndex = '10000';
            debugPanel.style.fontFamily = 'monospace';
            debugPanel.style.fontSize = '10px';
            debugPanel.innerHTML = `
                <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
                    <strong>Debug Log</strong>
                    <button id="clear-logs" style="background:none;border:none;color:red;cursor:pointer;font-size:10px;">Clear</button>
                </div>
                <div id="debug-log-content">${debugLogs.replace(/\n/g, '<br>')}</div>
            `;
            document.body.appendChild(debugPanel);
            
            // Add clear logs handler
            document.getElementById('clear-logs').addEventListener('click', function() {
                localStorage.removeItem('debugLogs');
                document.getElementById('debug-log-content').innerHTML = '';
            });
        }
    }
    
    // Override console.log
    const originalLog = console.log;
    console.log = function() {
        // Call original console.log
        originalLog.apply(console, arguments);
        
        // Format the log message
        const msg = Array.from(arguments).map(arg => {
            if (typeof arg === 'object') {
                try {
                    return JSON.stringify(arg);
                } catch (e) {
                    return String(arg);
                }
            }
            return String(arg);
        }).join(' ');
        
        // Add to localStorage
        const logs = localStorage.getItem('debugLogs') || '';
        localStorage.setItem('debugLogs', logs + '\n' + msg);
        
        // Update debug panel if exists
        const logContent = document.getElementById('debug-log-content');
        if (logContent) {
            logContent.innerHTML += '<br>' + msg;
            logContent.scrollTop = logContent.scrollHeight;
        }
    };
    
    console.log('File upload script initialized');
    
    const form = document.querySelector('form[enctype="multipart/form-data"]');
    const progressBar = document.getElementById('upload-progress-bar');
    const progressContainer = document.getElementById('upload-progress-container');
    const statusText = document.getElementById('upload-status');
    
    // Support both single file and multiple files upload forms
    // For single file uploads (task batch form)
    const wavFileInput = document.querySelector('input[type="file"][name="wav_file"]');
    const pickleFileInput = document.querySelector('input[type="file"][name="pickle_file"]');
    
    // For batch uploads (recordings batch upload)
    const wavFilesInput = document.querySelector('input[type="file"][name="wav_files"]');
    const pickleFilesInput = document.querySelector('input[type="file"][name="pickle_files"]');
    
    const cancelButton = document.getElementById('cancel-upload');
    let xhr;
    
    // If we don't have the necessary elements, skip initialization
    if (!form || !progressBar) {
        console.log("File upload initialization skipped - missing elements");
        return;
    }
    
    // Determine which form we're on - batch or single
    const isBatchUpload = wavFilesInput !== null;
    
    // Track total file size for both files
    let totalFileSize = 0;
    let fileCount = 0;
    let filenames = [];
    
    // Initialize dropzone styling for file inputs based on which form we're on
    if (isBatchUpload) {
        // For batch upload form
        setupDropzone(wavFilesInput);
        setupDropzone(pickleFilesInput);
        
        // Handle file selection for either file input
        wavFilesInput.addEventListener('change', updateFilesInfo);
        pickleFilesInput.addEventListener('change', updateFilesInfo);
    } else if (wavFileInput && pickleFileInput) {
        // For single file upload form
        setupDropzone(wavFileInput);
        setupDropzone(pickleFileInput);
        
        // Handle file selection for either file input
        wavFileInput.addEventListener('change', updateFilesInfo);
        pickleFileInput.addEventListener('change', updateFilesInfo);
    }
    
    function setupDropzone(fileInput) {
        const container = fileInput.parentElement;
        const dropArea = document.createElement('div');
        dropArea.className = 'file-dropzone p-4 mb-3 text-center border border-secondary rounded';
        
        // Change wording for multiple files
        const isMultiple = fileInput.multiple;
        const uploadText = isMultiple ? 'Drag & drop your files here or click to browse' : 'Drag & drop your file here or click to browse';
        const selectedText = isMultiple ? 'Selected files:' : 'Selected file:';
        
        dropArea.innerHTML = `
            <div class="file-icon mb-2"><i class="fas fa-file-upload fa-2x"></i></div>
            <p>${uploadText}</p>
            <small class="text-muted">${selectedText} <span class="selected-filename">None</span></small>
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
                if (isMultiple && this.files.length > 1) {
                    // Show multiple file count for multiple file inputs
                    const totalSize = Array.from(this.files).reduce((sum, file) => sum + file.size, 0);
                    const totalSizeMB = (totalSize / (1024 * 1024)).toFixed(2);
                    filenameSpan.textContent = `${this.files.length} files selected (${totalSizeMB} MB)`;
                } else {
                    // Show single filename for single file input or when only one file is selected
                    const fileName = this.files[0].name;
                    const fileSize = (this.files[0].size / (1024 * 1024)).toFixed(2);
                    filenameSpan.textContent = `${fileName} (${fileSize} MB)`;
                }
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
                // Handle multiple files for multiple inputs
                if (fileInput.multiple) {
                    // Create a new DataTransfer object to build the file list
                    const dataTransfer = new DataTransfer();
                    
                    // Add each dropped file to the DataTransfer
                    for (let i = 0; i < files.length; i++) {
                        dataTransfer.items.add(files[i]);
                    }
                    
                    // Assign the files to the input
                    fileInput.files = dataTransfer.files;
                } else {
                    // For single file inputs, just use the first file
                    const singleFileTransfer = new DataTransfer();
                    singleFileTransfer.items.add(files[0]);
                    fileInput.files = singleFileTransfer.files;
                }
                
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
        
        if (isBatchUpload) {
            // Batch upload form - handle multiple files
            // Check WAV files
            if (wavFilesInput && wavFilesInput.files.length > 0) {
                for (let i = 0; i < wavFilesInput.files.length; i++) {
                    totalFileSize += wavFilesInput.files[i].size;
                    fileCount++;
                    filenames.push(wavFilesInput.files[i].name);
                }
            }
            
            // Check pickle files
            if (pickleFilesInput && pickleFilesInput.files.length > 0) {
                for (let i = 0; i < pickleFilesInput.files.length; i++) {
                    totalFileSize += pickleFilesInput.files[i].size;
                    fileCount++;
                    filenames.push(pickleFilesInput.files[i].name);
                }
            }
        } else {
            // Single file upload form
            // Check WAV file
            if (wavFileInput && wavFileInput.files.length > 0) {
                totalFileSize += wavFileInput.files[0].size;
                fileCount++;
                filenames.push(wavFileInput.files[0].name);
            }
            
            // Check pickle file
            if (pickleFileInput && pickleFileInput.files.length > 0) {
                totalFileSize += pickleFileInput.files[0].size;
                fileCount++;
                filenames.push(pickleFileInput.files[0].name);
            }
        }
        
        // Only show progress if at least one file is selected
        if (fileCount > 0) {
            const totalSizeMB = (totalFileSize / (1024 * 1024)).toFixed(2);
            
            // Show full file list for small number of files, or summary for many files
            let fileListHtml = '';
            const maxDisplayFiles = 10;
            
            if (filenames.length <= maxDisplayFiles) {
                fileListHtml = filenames.map(name => `<span class="badge bg-info me-2 mb-1">${name}</span>`).join('');
            } else {
                // Show the first few files with a count of remaining
                const displayedFiles = filenames.slice(0, maxDisplayFiles);
                const remainingCount = filenames.length - maxDisplayFiles;
                fileListHtml = displayedFiles.map(name => `<span class="badge bg-info me-2 mb-1">${name}</span>`).join('') +
                    `<span class="badge bg-secondary">+${remainingCount} more file${remainingCount > 1 ? 's' : ''}</span>`;
            }
            
            statusText.innerHTML = `
                <div class="mb-2">Selected ${fileCount} file${fileCount > 1 ? 's' : ''} (${totalSizeMB} MB total)</div>
                <div class="file-badges-container">${fileListHtml}</div>
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
        // Different validation based on form type
        if (isBatchUpload) {
            // Batch upload form - just need WAV files
            if (!wavFilesInput || wavFilesInput.files.length === 0) {
                // Let the normal form submission handle validation errors
                return;
            }
        } else {
            // Single upload form - need both WAV and pickle files
            if (!wavFileInput || !pickleFileInput || 
                wavFileInput.files.length === 0 || pickleFileInput.files.length === 0) {
                // Let the normal form submission handle validation errors
                return;
            }
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
            console.log(`XHR load event fired, status: ${xhr.status}`);
            
            // Always log the raw response for debugging
            console.log("Raw response text:", xhr.responseText.substring(0, 1000));
            
            if (xhr.status === 200) {
                try {
                    console.log("Attempting to parse JSON response");
                    const response = JSON.parse(xhr.responseText);
                    console.log("Parsed JSON response:", response);
                    
                    if (response.success) {
                        console.log("Success response detected");
                        statusText.innerHTML = `
                            <div class="alert alert-success">
                                <i class="fas fa-check-circle me-2"></i>
                                Upload complete! Successfully created batch with ${response.recordings_created || 'multiple'} recordings.
                            </div>
                        `;
                        progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
                        progressBar.classList.add('bg-success');
                        
                        // Ensure we have a redirect URL
                        if (!response.redirect_url) {
                            console.warn("Missing redirect_url in response");
                        }
                        
                        // Show success animation before redirect
                        console.log("Setting timeout for redirect");
                        setTimeout(() => {
                            // Redirect to the batch detail page or show success message
                            if (response.redirect_url) {
                                console.log("Executing redirect to:", response.redirect_url);
                                // Force a hard redirect to bypass any caching
                                window.location.assign(response.redirect_url);
                            } else {
                                console.error("No redirect URL available");
                            }
                        }, 1500);
                    } else {
                        console.warn("Response success=false:", response);
                        handleError(response.error || 'Upload failed');
                    }
                } catch (err) {
                    console.error("JSON parse error:", err);
                    console.log("Unable to parse response as JSON");
                    
                    // Handle non-JSON response (likely HTML from a successful form submission)
                    if (xhr.responseURL) {
                        console.log("Non-JSON response with responseURL available");
                        console.log("Redirecting to response URL:", xhr.responseURL);
                        window.location.assign(xhr.responseURL);
                    } else {
                        console.error("No responseURL available for non-JSON response");
                        handleError('Unknown response from server');
                    }
                }
            } else {
                console.error("HTTP error status:", xhr.status, xhr.statusText);
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
        
        // Modify form action to explicitly request JSON
        const formActionUrl = new URL(form.action, window.location.href);
        formActionUrl.searchParams.append('format', 'json');
        console.log("Adding format=json to URL:", formActionUrl.toString());
        
        // Send the form data
        xhr.open('POST', formActionUrl.toString(), true);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.setRequestHeader('Accept', 'application/json');
        console.log("Setting headers for AJAX/JSON submission");
        
        // Include CSRF token
        const csrfToken = document.querySelector('[name="csrfmiddlewaretoken"]').value;
        xhr.setRequestHeader('X-CSRFToken', csrfToken);
        
        // Add more detailed logging for the response handling
        xhr.onreadystatechange = function() {
            console.log(`XHR state change: readyState=${xhr.readyState}, status=${xhr.status}`);
            if (xhr.readyState === 4) {
                console.log(`Response complete: status=${xhr.status}`);
                if (xhr.getResponseHeader('Content-Type')) {
                    console.log(`Content-Type: ${xhr.getResponseHeader('Content-Type')}`);
                }
            }
        };
        
        // Start upload
        statusText.textContent = 'Starting upload...';
        xhr.send(formData);
    });
});