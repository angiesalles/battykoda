#!/usr/bin/env Rscript

# Script to install warbleR and its dependencies for BattyCoda on Replit
# This script is designed to be run at Replit startup

# Set CRAN mirror and package installation directory
r_libs_user <- Sys.getenv("R_LIBS_USER", ".r_libs")
if (!dir.exists(r_libs_user)) {
  dir.create(r_libs_user, recursive = TRUE)
}
.libPaths(c(r_libs_user, .libPaths()))
options(repos = c(CRAN = "https://cloud.r-project.org/"))

cat("Setting up warbleR for BattyCoda...\n")

# Function to install a package with detailed error handling
install_package <- function(pkg_name, from_source = FALSE) {
  cat(sprintf("Attempting to install %s...\n", pkg_name))
  
  if (requireNamespace(pkg_name, quietly = TRUE)) {
    cat(sprintf("%s is already installed\n", pkg_name))
    return(TRUE)
  }
  
  success <- tryCatch({
    if (from_source) {
      install.packages(pkg_name, type = "source")
    } else {
      install.packages(pkg_name)
    }
    
    # Verify installation
    if (requireNamespace(pkg_name, quietly = TRUE)) {
      cat(sprintf("Successfully installed %s\n", pkg_name))
      TRUE
    } else {
      cat(sprintf("Failed to install %s (package not available after installation)\n", pkg_name))
      FALSE
    }
  }, error = function(e) {
    cat(sprintf("Error installing %s: %s\n", pkg_name, e$message))
    FALSE
  }, warning = function(w) {
    cat(sprintf("Warning during installation of %s: %s\n", pkg_name, w$message))
    # Continue despite warning
    requireNamespace(pkg_name, quietly = TRUE)
  })
  
  return(success)
}

# First, install core system dependencies
core_packages <- c(
  "stringr",
  "devtools",
  "remotes",
  "jsonlite"
)

for (pkg in core_packages) {
  install_package(pkg)
}

# Install audio processing dependencies
audio_dependencies <- c(
  "audio",
  "tuneR",
  "seewave"
)

for (pkg in audio_dependencies) {
  install_package(pkg)
}

# Install ML dependencies
ml_dependencies <- c(
  "kknn",
  "mlr3",
  "mlr3learners",
  "mlr3tuning"
)

for (pkg in ml_dependencies) {
  install_package(pkg)
}

# BiocManager for Bioconductor packages
if (!requireNamespace("BiocManager", quietly = TRUE)) {
  install_package("BiocManager")
}

if (requireNamespace("BiocManager", quietly = TRUE)) {
  cat("Installing Bioconductor dependencies...\n")
  BiocManager::install(update = FALSE, ask = FALSE)
}

# Now install warbleR - multiple approaches
cat("Installing warbleR...\n")
warbler_installed <- FALSE

# Approach 1: Try CRAN first
if (!warbler_installed) {
  cat("Trying warbleR from CRAN...\n")
  if (install_package("warbleR")) {
    warbler_installed <- TRUE
  }
}

# Approach 2: Try from GitHub using devtools
if (!warbler_installed && requireNamespace("devtools", quietly = TRUE)) {
  cat("Trying warbleR from GitHub via devtools...\n")
  tryCatch({
    devtools::install_github("maRce10/warbleR", dependencies = TRUE)
    if (requireNamespace("warbleR", quietly = TRUE)) {
      cat("Successfully installed warbleR from GitHub\n")
      warbler_installed <- TRUE
    }
  }, error = function(e) {
    cat(sprintf("Error installing warbleR from GitHub: %s\n", e$message))
  })
}

# Approach 3: Try from GitHub using remotes
if (!warbler_installed && requireNamespace("remotes", quietly = TRUE)) {
  cat("Trying warbleR from GitHub via remotes...\n")
  tryCatch({
    remotes::install_github("maRce10/warbleR", dependencies = TRUE)
    if (requireNamespace("warbleR", quietly = TRUE)) {
      cat("Successfully installed warbleR via remotes\n")
      warbler_installed <- TRUE
    }
  }, error = function(e) {
    cat(sprintf("Error installing warbleR via remotes: %s\n", e$message))
  })
}

# Check installation status
if (warbler_installed) {
  cat("warbleR installation complete!\n")
  
  # Test loading warbleR
  tryCatch({
    library(warbleR)
    cat("warbleR loaded successfully\n")
  }, error = function(e) {
    cat(sprintf("Error loading warbleR: %s\n", e$message))
  })
} else {
  cat("Failed to install warbleR after multiple attempts\n")
}

# Print installed package versions for reference
cat("\nInstalled packages for BattyCoda R components:\n")
packages_needed <- c("warbleR", "tuneR", "seewave", "audio", "kknn", "mlr3", "mlr3learners", "stringr")
inst_pkgs <- installed.packages()

for (pkg in packages_needed) {
  if (pkg %in% rownames(inst_pkgs)) {
    version <- inst_pkgs[pkg, "Version"]
    cat(sprintf("%s: %s\n", pkg, version))
  } else {
    cat(sprintf("%s: NOT INSTALLED\n", pkg))
  }
}

cat("\nR setup complete\n")