# BattyCoda

BattyCoda is a web application for analyzing and classifying bat call recordings. It provides spectrograms, audio playback, and automated classification of bat vocalizations.

## System Architecture

BattyCoda combines several technologies to provide a robust, scalable bat call analysis platform:

### Core Components

1. **Web Application (Flask)**
   - Serves the user interface
   - Handles authentication and user management
   - Provides directory navigation and file browsing
   - Integrated with Celery for asynchronous processing

2. **Spectrogram Generation System (Celery)**
   - Processes audio files to generate spectrograms asynchronously
   - Pre-fetches and caches spectrograms for improved performance
   - Scales to handle multiple simultaneous requests
   - Task retry and error handling capabilities

3. **Classification Engine (R)**
   - Analyzes bat calls using R's specialized audio processing libraries
   - Classifies calls using machine learning algorithms
   - Provides confidence scores for classifications
   - Integrates with Python through scripted interfaces

4. **Storage and Caching**
   - SQLite database for user and session management
   - File-based caching for spectrograms and audio snippets
   - Redis for task queue management and result storage

### Data Flow

1. User navigates directories and selects an audio file
2. Flask application handles the request and triggers spectrogram generation
3. Celery workers process the audio data and create spectrograms
4. Spectrograms are cached and served back to the user
5. User can classify calls manually or verify automatic classifications
6. Classifications are stored and used to improve the classification model

## New Celery-Based Architecture

The system now uses Celery for asynchronous task processing, providing several advantages:

### Key Features

- **Asynchronous Processing**: Spectrograms are generated in the background
- **Pre-fetching**: System predicts and prepares spectrograms before they're requested
- **Parallel Processing**: Multiple workers can process different requests simultaneously
- **Monitoring**: Flower dashboard provides real-time monitoring of tasks
- **Error Handling**: Automated retry logic for failed tasks
- **Scalability**: Easy to scale by adding more worker instances

### Technology Stack

- **Flask**: Web framework
- **Celery**: Distributed task queue
- **Redis**: Message broker and result backend
- **Matplotlib/SciPy**: Spectrogram generation
- **R with warbleR**: Audio analysis and classification

## Deployment Options

### Option 1: Deploying on Replit

1. **Fork this repository on GitHub**
   
2. **Create a new Repl on Replit**
   - Go to [Replit](https://replit.com/)
   - Click "Create Repl"
   - Choose "Import from GitHub"
   - Paste your forked repository URL
   - Click "Import from GitHub"

3. **The application will automatically configure using the .replit file**
   - The necessary environment, dependencies, and run command are already configured
   - Replit will install all required packages from requirements.txt

4. **R Package Installation (Important!)**
   - BattyCoda requires R and several R packages, most importantly the `warbleR` package
   - The first time you run the application, it will automatically try to install these packages
   - This process may take 5-10 minutes, so please be patient
   - If you encounter issues with R package installation, you can manually run:
   ```
   python check_r_setup.py
   ```

5. **Run the application**
   - Click the "Run" button
   - BattyCoda should start on the Replit-provided URL
   - The first run may take longer due to R package installation

6. **Login with test credentials**
   - Username: `demo`
   - Password: `demo123`
   - Or register a new account

7. **Troubleshooting R packages on Replit**
   - If you encounter issues with R packages, check the console output for error messages
   - You can manually install R packages using the Replit Shell:
   ```
   R -e "install.packages('packageName')"
   ```
   - For warbleR specifically, try:
   ```
   R -e "install.packages('warbleR')"
   ```
   - The R packages are installed in the `.r_libs` directory

### Option 2: Local Installation with Celery (Recommended)

This guide will walk you through setting up and running BattyCoda with Celery on your local machine.

**Prerequisites:**
- Python 3.8 or higher
- R 4.0 or higher
- Redis (for Celery task queue)

**Step 1: Clone the Repository**
```
git clone https://github.com/yourusername/battykoda.git
cd battykoda
```

**Step 2: Create and Activate a Virtual Environment**  
To keep dependencies isolated, it is best to use a virtual environment.  

On macOS/Linux:  
```  
python3 -m venv .venv  
source .venv/bin/activate  
```  

On Windows:  
```  
python -m venv .venv  
.venv\Scripts\activate  
```  

**Step 3: Install Dependencies**  
After activating the virtual environment, install required packages:  
```  
pip install -r requirements.txt  
```  

**Step 4: Install Redis**
Redis is required for the Celery task queue.

On macOS:
```
brew install redis
brew services start redis
```

On Ubuntu/Debian:
```
sudo apt-get install redis-server
sudo systemctl start redis-server
```

**Step 5: Install R and Required R Packages**  
BattyCoda uses R for its bat call classification functionality.

```
# Install R (if not already installed)
# On Ubuntu/Debian
sudo apt-get install r-base

# On macOS (using Homebrew)
brew install r

# On Windows
# Download and install R from https://cran.r-project.org/bin/windows/base/
```

Install required R packages:
```
# Run this in your terminal
Rscript -e "install.packages(c('warbleR', 'stringr', 'mlr3', 'mlr3learners', 'kknn', 'tuneR', 'seewave'), repos='https://cloud.r-project.org/')"
```

**Step 6: Initialize the Database**  
```
python init_db.py
```

**Step 7: Start the System with Management Scripts**

The system includes management scripts for easy operation:

```bash
# Start all components (Redis, Celery worker, Flower, Flask)
./start_system.sh

# View logs
./view_logs.sh all    # View all logs (requires tmux)
./view_logs.sh flask  # View only Flask logs

# Check system health
./check_system.sh

# Stop the system
./stop_system.sh

# Restart after code changes
./refresh_system.sh
```

For more details on the management scripts, see [SCRIPTS_README.md](SCRIPTS_README.md).

**Step 8: Access the Application**  
Open a web browser and visit:  
```  
http://127.0.0.1:8060/  
```  

**Step 9: Login with test credentials**  
When the application starts for the first time, an admin user is created:
- Username: `admin`
- Password: `admin123`

You can also register a new account from the login page.

### Option 3: Local Installation without Celery (Basic)

For simpler deployments, you can run the application without Celery:

**Step 1-5**: Same as Option 2

**Step 6: Initialize the Database**  
```
python init_db.py
```

**Step 7: Run the Flask Server**  

Option A: Run with enhanced logging (recommended)
```  
python run_server.py  
```  

Option B: Run directly (basic logging)
```  
python main.py  
```

With either option, if correctly configured, the server will start and you will see output similar to:  
```  
* Running on http://0.0.0.0:8060/ (Press CTRL+C to quit)  
```

**Steps 8-9**: Same as Option 2

## Folder Structure

The server replicates the home folder user structure. Additionally, there should be a user called 'data'. In the home folder of that user, there should be a folder called 'battykoda', with two subfolders: 'static' and 'tempdata'.

Each species should have an ABC.jpg and ABC.txt file in the static folder. Once these files are created, subfolders of other users called ABC will be visible. Example Efuscus.txt and Efuscus.jpg files are provided in the repository.

### System Component Structure

- **Flask Routes**
  - `routes/`: Contains route handlers for different parts of the application
  - `routes/directory_routes.py`: Directory navigation
  - `routes/path_routes.py`: Path-based request handling
  - `routes/spectrogram_routes.py`: Spectrogram generation and serving
  - `routes/audio_routes.py`: Audio snippet generation and serving

- **Celery Components**
  - `celery_app.py`: Celery configuration and setup
  - `tasks.py`: Task definitions for background processing
  - `spectrogram_generator.py`: Core spectrogram generation functions

- **Authentication System**
  - `auth/`: Authentication module containing login/registration logic
  - `database.py`: Database models and initialization

- **File Management**
  - `file_management/`: File and directory handling utilities
  - `AppropriateFile.py`: File path generation for temporary files

- **R Integration**
  - `classify_call.R`: R script for call classification
  - `setup_r_packages.R`: R package installation script

## Spectrogram Generation

Spectrograms are generated using a combination of Python and Celery:

1. When a request is made for a spectrogram, the system first checks if it's already cached
2. If not cached, a Celery task is created to generate the spectrogram
3. The task processes the audio file and extracts the relevant segment
4. The spectrogram is generated using matplotlib and scipy
5. The resulting image is cached for future requests
6. The image is served back to the client

### Advanced Features

- **Asynchronous Mode**: By adding `?async=true` to spectrogram requests, the request returns immediately with a task ID
- **Prefetching**: By adding `?prefetch=true`, the system will preload future spectrograms
- **Task Status Tracking**: Check task status at `/status/task/{task_id}`
- **Monitoring**: Access the Flower dashboard at `http://localhost:5555` for real-time monitoring

For more details on the Celery implementation, see [CELERY_README.md](CELERY_README.md).

## User Interface Guide

Once you have BattyCoda set up for your species (labels and template), you can convert your files for analysis. Files need to be converted to pickle files containing metadata about the calls.

### Pickle Generation

To create pickle files, you need:
1. The WAV audio file
2. An XLSX file with acoustic parameters, including start and end times of calls
3. Run the conversion script to create the pickle file

### Classification Interface

Below is the interface you will see once you have chosen your file in BattyCoda:

1. **Login**: You will be prompted to enter your username
2. **Spectrogram View**:
   - Left: Zoomed-in spectrogram of the specific call you are labeling
   - Right: Zoomed-out version of the same call for context

3. **Controls**:
   - **Contrast**: Adjust to make quiet calls more visible or loud calls less overwhelming
   - **Channel Selection**: If your recording has multiple microphones, you can select different channels
   - **Main Channel**: Set your preferred channel for analysis
   - **Classification**: Choose the correct label and select next call
   - **Update**: Apply changes to settings
   - **Undo**: Go back to previous call

4. **Confidence Score**:
   Once enough files are analyzed, this shows how confident the classifier is at identifying each call.
   You can set a threshold to only review calls below a certain confidence level.

## Contributing

Contributions to BattyCoda are welcome! Please see [DEV_GUIDE.md](DEV_GUIDE.md) for development guidelines.

## License

[MIT License](LICENSE)