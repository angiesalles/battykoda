# R Integration Requirements for BattyKoda

BattyKoda uses R for advanced bat call analysis and classification. The following R packages need to be installed for the R integration to function correctly.

## Required R Packages

- **warbleR** - Main package for acoustic analysis of wildlife sound recordings
- **stringr** - String manipulation utilities
- **mlr3** - Machine learning framework
- **mlr3learners** - Machine learning algorithms for mlr3
- **kknn** - k-Nearest Neighbor classification

## Installation Instructions

You can install these packages in R using the following commands:

```r
# Install packages
install.packages(c("stringr", "mlr3", "kknn", "mlr3learners"))

# Install warbleR from GitHub (for latest version)
if (!requireNamespace("remotes", quietly = TRUE))
    install.packages("remotes")
remotes::install_github("maRce10/warbleR")

# Or from CRAN (more stable)
install.packages("warbleR")
```

## Verifying Installation

To verify that all required packages are installed, run this command in R:

```r
required_pkgs <- c("warbleR", "stringr", "mlr3", "mlr3learners", "kknn")
installed <- rownames(installed.packages())
missing <- required_pkgs[!(required_pkgs %in% installed)]
if(length(missing) > 0) {
  cat("Missing packages:", paste(missing, collapse=", "), "\n")
} else {
  cat("All required packages are installed.\n")
}
```

## Testing the R Integration

To test if the R script is working correctly, run:

```bash
# Replace with a path to a WAV file in your system
Rscript classify_call.R /path/to/your/file.wav 0.1 0.2 Efuscus
```

You should see output that includes:
```
type: 'Echo'
confidence: 75.5
```

## Troubleshooting

If you encounter issues with the R integration:

1. Check that R is properly installed and available in your system PATH
2. Verify all required packages are installed
3. Make sure R script permissions are set correctly (executable)
4. Check the server.log file for specific R-related errors

## Notes for Mac Users

On macOS, you may need to install additional dependencies for some R packages:

```bash
# Install XQuartz for image rendering
brew install --cask xquartz

# Install libraries required by warbleR
brew install fftw
```

## System Requirements

- R version 4.0.0 or higher
- Python 3.6 or higher
- Sufficient disk space for audio analysis (at least 500MB free)