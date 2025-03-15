#!/usr/bin/env Rscript

# Script to install R packages required for BattyCoda
# This script should be run manually on Replit if R package errors occur

# Function to install a package if it's not already installed
install_if_missing <- function(package) {
  if (!require(package, character.only = TRUE, quietly = TRUE)) {
    message(paste("Installing package:", package))
    install.packages(package, repos = "https://cloud.r-project.org/")
  } else {
    message(paste("Package already installed:", package))
  }
}

# Main packages required for audio processing
required_packages <- c(
  "tuneR",
  "randomForest"
)

# Optional additional packages for more advanced audio processing
# Uncomment to install
optional_packages <- c(
  # "signal",
  # "seewave",
  # "audio",
  # "soundgen"
)

# Install required packages
for (pkg in required_packages) {
  install_if_missing(pkg)
}

# Install optional packages if uncommented
for (pkg in optional_packages) {
  install_if_missing(pkg)
}

message("R package installation complete!")

# Check what was installed
installed <- installed.packages()[,"Package"]
missing <- setdiff(required_packages, installed)

if (length(missing) > 0) {
  warning("The following required packages could not be installed: ", 
          paste(missing, collapse = ", "))
} else {
  message("All required packages were successfully installed.")
}