# Deploying BattyCoda on Replit

This guide explains how to deploy the BattyCoda application on Replit.

## Setup Steps

1. **Import the Repository**
   - Create a new Replit from GitHub
   - Use the repository URL: https://github.com/YOUR_USERNAME/battykoda

2. **Configure Environment**
   - Replit will automatically detect the Python application
   - The included `replit.nix` file configures Python 3.12
   - The `requirements.txt` file will automatically install dependencies

3. **Run the Application**
   - Click the "Run" button in Replit
   - The application will:
     - Automatically create the database if it doesn't exist
     - Initialize default users
     - Create necessary directories
   - The first run may take a bit longer as it sets up everything

4. **Default Login**
   - Username: `admin`
   - Password: `admin123`
   - It's recommended to change this password after first login

## Troubleshooting

If you encounter database errors:

1. Try stopping and restarting the Replit
2. If the error persists, you can manually initialize the database:
   ```bash
   python create_db.py
   ```

3. For persistent issues, try cleaning up and recreating:
   ```bash
   rm -f battycoda.db
   python create_db.py
   ```

## R Integration

The application requires R for bat call classification:

1. R packages are installed via the `setup_r_packages.R` script
2. The model file is located at `static/mymodel.RData`
3. Classification is handled by `classify_call.R`

If you encounter R-related errors, check the logs for details on missing packages.

## Directory Structure

- `data/home`: User project directories
- `static`: Static assets and model files
- `templates`: HTML templates
- `battycoda.db`: SQLite database (automatically created)

## Custom Configuration

You can customize the application by setting these environment variables:

- `PORT`: The port to listen on (default: 8060)
- `FLASK_DEBUG`: Set to "1" for debug mode (default: "0")
- `SECRET_KEY`: Flask session secret key

## Next Steps

1. Change the default admin password
2. Upload your own species templates
3. Create bat call projects
4. Start classifying bat calls!