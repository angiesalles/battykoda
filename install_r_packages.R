#!/usr/bin/env Rscript

# Script to install R packages needed for BattyCoda on Replit
cat("Installing required R packages for BattyCoda...\n")

# Function to safely install a package
install_if_missing <- function(package_name) {
  if (!requireNamespace(package_name, quietly = TRUE)) {
    cat(sprintf("Installing package: %s\n", package_name))
    install.packages(package_name, repos = "https://cloud.r-project.org/")
    
    # Verify installation
    if (requireNamespace(package_name, quietly = TRUE)) {
      cat(sprintf("Successfully installed %s\n", package_name))
      return(TRUE)
    } else {
      cat(sprintf("Failed to install %s\n", package_name))
      return(FALSE)
    }
  } else {
    cat(sprintf("Package %s is already installed\n", package_name))
    return(TRUE)
  }
}

# Install dependencies for warbleR first
dependencies <- c(
  "seewave",
  "tuneR",
  "stringr",
  "kknn",
  "mlr3",
  "mlr3learners",
  "mlr3tuning"
)

# Install each dependency
all_deps_installed <- TRUE
for (dep in dependencies) {
  if (!install_if_missing(dep)) {
    all_deps_installed <- FALSE
  }
}

# Install warbleR if dependencies are installed
if (all_deps_installed) {
  # Try to load warbleR first in case it's already installed
  if (!requireNamespace("warbleR", quietly = TRUE)) {
    cat("Installing warbleR package...\n")
    
    # warbleR requires bioconductor packages
    if (!requireNamespace("BiocManager", quietly = TRUE)) {
      install.packages("BiocManager", repos = "https://cloud.r-project.org/")
    }
    
    # Install warbleR through CRAN
    install.packages("warbleR", repos = "https://cloud.r-project.org/")
    
    # Check if installation succeeded
    if (requireNamespace("warbleR", quietly = TRUE)) {
      cat("Successfully installed warbleR\n")
    } else {
      cat("Failed to install warbleR, will try an alternative method\n")
      
      # Try direct GitHub install as fallback
      if (!requireNamespace("devtools", quietly = TRUE)) {
        install.packages("devtools", repos = "https://cloud.r-project.org/")
      }
      
      if (requireNamespace("devtools", quietly = TRUE)) {
        devtools::install_github("maRce10/warbleR")
        
        if (requireNamespace("warbleR", quietly = TRUE)) {
          cat("Successfully installed warbleR from GitHub\n")
        } else {
          cat("Failed to install warbleR. Please check error messages and ensure Bioconductor is properly installed.\n")
        }
      } else {
        cat("Failed to install devtools. Cannot proceed with GitHub installation of warbleR.\n")
      }
    }
  } else {
    cat("warbleR is already installed\n")
  }
}

# List all installed packages with versions for debugging
cat("\nInstalled package versions:\n")
ip <- installed.packages()[, c("Package", "Version")]
ip <- ip[order(ip[,"Package"]), ]
for (i in 1:nrow(ip)) {
  cat(sprintf("%s: %s\n", ip[i, "Package"], ip[i, "Version"]))
}

cat("\nR package installation complete!\n")