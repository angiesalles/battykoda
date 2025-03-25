#!/usr/bin/env Rscript
#
# R Prediction Server using Plumber
# This creates a REST API that serves bat call classification predictions
# Using direct KNN approach that avoids mlr3 compatibility issues
#

# Load required packages - all should be pre-installed
library(plumber)
library(warbleR)
library(class)

# Settings for debugging
DEBUG_MODE <- TRUE # Set to TRUE to enable detailed logging

# Debug logging function
debug_log <- function(...) {
  if (DEBUG_MODE) {
    timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
    message <- paste(...)
    cat(sprintf("[DEBUG %s] %s\n", timestamp, message))
  }
}

# Global variables
MODEL_LOADED <- FALSE
MODEL_PATH <- "static/mymodel.RData"
TRAIN_DATA <- NULL

# Load the model once at startup
debug_log("Loading model from:", MODEL_PATH)
if (file.exists(MODEL_PATH)) {
  tryCatch({
    load(MODEL_PATH)
    if (exists("kknn_model")) {
      MODEL_LOADED <- TRUE
      cat("Model loaded successfully from", MODEL_PATH, "\n")
      
      # Extract training data
      if (!is.null(kknn_model$learner$model$data)) {
        TRAIN_DATA <- kknn_model$learner$model$data
        
        # Convert data.table to data.frame if needed
        if ("data.table" %in% class(TRAIN_DATA)) {
          TRAIN_DATA <- as.data.frame(TRAIN_DATA)
        }
        
        debug_log("Training data extracted:", nrow(TRAIN_DATA), "rows,", ncol(TRAIN_DATA), "columns")
      } else {
        cat("Error: Could not extract training data from model\n")
      }
    } else {
      cat("Error: kknn_model object not found in loaded data\n")
    }
  }, error = function(e) {
    cat("Error loading model:", e$message, "\n")
  })
} else {
  cat("Model file not found at:", MODEL_PATH, "\n")
}

#* @apiTitle BattyCoda Bat Call Classification API
#* @apiDescription API for classifying bat calls with direct KNN approach

#* @get /ping
function() {
  debug_log("Ping request received")
  result <- list(
    status = "alive", 
    model_loaded = MODEL_LOADED,
    debug_mode = DEBUG_MODE,
    timestamp = format(Sys.time(), "%Y-%m-%d %H:%M:%S"),
    r_version = R.version.string
  )
  debug_log("Ping response sent")
  return(result)
}

#* Extract acoustic features from a WAV file
#* @param wav_path Path to the WAV file
#* @param start Start time in seconds
#* @param end End time in seconds
#* @return A data frame with acoustic features
extract_features <- function(wav_path, start, end) {
  debug_log("extract_features called with path:", wav_path, "start:", start, "end:", end)
  
  tryCatch({
    # Verify file exists
    if (!file.exists(wav_path)) {
      debug_log("ERROR: WAV file not found:", wav_path)
      stop(paste("WAV file not found:", wav_path))
    }
    
    # Create selection table
    debug_log("Creating selection dataframe")
    sound.files <- basename(wav_path)
    sel_df <- data.frame(
      sound.files = sound.files,
      selec = "1",
      start = as.numeric(start),
      end = as.numeric(end)
    )
    debug_log("Selection dataframe created")
    
    # Set working directory to the location of the WAV file
    original_dir <- getwd()
    debug_log("Original directory:", original_dir)
    on.exit(setwd(original_dir))  # Ensure we return to original directory
    
    wav_dir <- dirname(wav_path)
    debug_log("Changing to WAV directory:", wav_dir)
    setwd(wav_dir)
    
    # Create a selection table
    debug_log("Creating warbleR selection table")
    selt <- warbleR::selection_table(sel_df)
    debug_log("Selection table created")
    
    # Extract features using spectro_analysis if available, fall back to specan
    has_spectro_analysis <- "spectro_analysis" %in% getNamespaceExports("warbleR")
    
    if (has_spectro_analysis) {
      debug_log("Extracting features with spectro_analysis")
      ftable <- warbleR::spectro_analysis(selt, bp = c(9, 200), threshold = 15)
    } else {
      debug_log("Extracting features with specan")
      ftable <- warbleR::specan(selt, bp = c(9, 200), threshold = 15)
    }
    debug_log("Features extracted, count:", ncol(ftable))
    
    # Scale features (same as in training)
    if (nrow(ftable) > 0) {
      debug_log("Scaling features")
      # Scale numeric columns (excluding the first column with filenames)
      numeric_cols <- sapply(ftable, is.numeric)
      numeric_cols[1] <- FALSE  # Exclude first column
      ftable[, numeric_cols] <- scale(ftable[, numeric_cols])
      debug_log("Feature scaling complete")
    }
    
    debug_log("Returning to original directory")
    setwd(original_dir)
    debug_log("Feature extraction complete")
    return(ftable)
  }, error = function(e) {
    debug_log("ERROR in extract_features:", e$message)
    debug_log("Traceback:", paste(capture.output(traceback()), collapse="\n"))
    stop(paste("Error extracting features:", e$message))
  })
}

#* Classify a bat call
#* @post /classify
#* @param wav_path:character Path to the WAV file
#* @param onset:numeric Start time in seconds
#* @param offset:numeric End time in seconds
#* @param species:character Species of bat
function(wav_path, onset, offset, species = "Efuscus") {
  debug_log("Classification request received for path:", wav_path)
  debug_log("Onset:", onset, "Offset:", offset, "Species:", species)
  
  if (!MODEL_LOADED || is.null(TRAIN_DATA)) {
    debug_log("ERROR: Model not loaded or no training data available")
    return(list(
      status = "error",
      message = "Model not loaded or no training data available",
      call_type = "Echo",  # Default
      confidence = 60.0    # Default
    ))
  }
  
  tryCatch({
    # Extract features
    debug_log("Calling extract_features function")
    ftable <- extract_features(wav_path, onset, offset)
    
    # Check if we have features
    if (nrow(ftable) == 0) {
      debug_log("ERROR: Empty feature table returned")
      return(list(
        status = "error",
        message = "Failed to extract features",
        call_type = "Echo",
        confidence = 60.0
      ))
    }
    
    debug_log("Features extracted successfully, rows:", nrow(ftable), "columns:", ncol(ftable))
    
    # Direct KNN classification approach
    debug_log("Performing direct KNN classification")
    
    # Get common columns (excluding target)
    train_cols <- setdiff(colnames(TRAIN_DATA), "selec")
    test_cols <- setdiff(colnames(ftable), "selec")
    common_cols <- intersect(train_cols, test_cols)
    
    debug_log("Using", length(common_cols), "common feature columns")
    
    # Extract features for training and testing
    train_x <- TRAIN_DATA[, common_cols, drop = FALSE]
    train_y <- TRAIN_DATA$selec
    test_x <- ftable[, common_cols, drop = FALSE]
    
    # Make sure column order matches
    test_x <- test_x[, colnames(train_x), drop = FALSE]
    
    # Ensure all columns are numeric
    non_numeric <- which(!sapply(train_x, is.numeric))
    if (length(non_numeric) > 0) {
      debug_log("Removing", length(non_numeric), "non-numeric columns")
      train_x <- train_x[, sapply(train_x, is.numeric), drop = FALSE]
      test_x <- test_x[, colnames(train_x), drop = FALSE]
    }
    
    # Check for missing values
    missing_in_train <- sapply(train_x, function(x) any(is.na(x)))
    missing_in_test <- sapply(test_x, function(x) any(is.na(x)))
    
    if (any(missing_in_train) || any(missing_in_test)) {
      debug_log("Imputing missing values with column means")
      
      # Simple imputation for missing values
      for (col in colnames(train_x)) {
        if (any(is.na(train_x[[col]]))) {
          col_mean <- mean(train_x[[col]], na.rm = TRUE)
          train_x[[col]][is.na(train_x[[col]])] <- col_mean
        }
        
        if (any(is.na(test_x[[col]]))) {
          col_mean <- mean(train_x[[col]], na.rm = TRUE)  # Use train mean for test imputation
          test_x[[col]][is.na(test_x[[col]])] <- col_mean
        }
      }
    }
    
    # Apply KNN
    debug_log("Applying KNN classifier")
    k <- 5
    prediction <- knn(train = as.matrix(train_x), 
                     test = as.matrix(test_x),
                     cl = train_y,
                     k = k,
                     prob = TRUE)
    
    # Get the prediction result
    typepred <- as.character(prediction)
    typepredprob <- attr(prediction, "prob")
    
    debug_log("KNN prediction:", typepred, "with probability:", typepredprob)
    
    # Calculate confidence
    confidence <- typepredprob * 100  # Convert to percentage
    debug_log("Confidence:", confidence)
    
    # Return results
    result <- list(
      status = "success",
      call_type = typepred,
      confidence = confidence,
      species = species
    )
    
    if (DEBUG_MODE) {
      # Add debug info to result when in debug mode
      result$debug_info <- list(
        features_extracted = ncol(ftable),
        features_used = ncol(train_x),
        k_value = k
      )
    }
    
    debug_log("Classification completed successfully")
    return(result)
  }, error = function(e) {
    debug_log("ERROR in classify function:", e$message)
    debug_log("Traceback:", paste(capture.output(traceback()), collapse="\n"))
    
    return(list(
      status = "error",
      message = paste("Error making prediction:", e$message),
      call_type = "Echo",  # Default
      confidence = 60.0,   # Default
      debug_info = if(DEBUG_MODE) list(error = e$message, traceback = capture.output(traceback())) else NULL
    ))
  })
}

# Load call types for reference
#* @get /call_types
#* @param species:character Species name
function(species = "Efuscus") {
  debug_log("Call types request for species:", species)
  
  call_types <- list(
    "Efuscus" = c("Echo", "FM", "Social"),
    "Myotis" = c("Echo", "Social"),
    "Nleps" = c("Echo", "FM", "Social", "Type A")
  )
  
  if (species %in% names(call_types)) {
    result <- list(
      status = "success",
      species = species,
      call_types = call_types[[species]]
    )
    debug_log("Call types returned:", paste(call_types[[species]], collapse=", "))
    return(result)
  } else {
    debug_log("ERROR: Unknown species:", species)
    return(list(
      status = "error",
      message = paste("Unknown species:", species),
      available_species = names(call_types)
    ))
  }
}

#* Debug endpoint for model inspection
#* @get /debug/model
function() {
  debug_log("Debug model info request received")
  
  if (!DEBUG_MODE) {
    return(list(status = "error", message = "Debug mode not enabled"))
  }
  
  if (!MODEL_LOADED) {
    return(list(status = "error", message = "Model not loaded"))
  }
  
  # Return model information
  model_info <- list(
    model_class = class(kknn_model),
    training_data_rows = nrow(TRAIN_DATA),
    training_data_cols = ncol(TRAIN_DATA),
    training_classes = levels(TRAIN_DATA$selec),
    feature_names = setdiff(names(TRAIN_DATA), "selec")
  )
  
  debug_log("Debug model info sent")
  return(list(
    status = "success",
    model_info = model_info
  ))
}

# Function to create and configure the API
create_api <- function() {
  debug_log("Creating API router")
  
  # Create the API from string definitions, not from the current environment
  # This avoids infinite recursion issues
  
  # Define ping endpoint
  ping_func <- "function() {
    result <- list(
      status = 'alive', 
      model_loaded = MODEL_LOADED,
      debug_mode = DEBUG_MODE,
      timestamp = format(Sys.time(), '%Y-%m-%d %H:%M:%S'),
      r_version = R.version.string
    )
    return(result)
  }"
  
  # Define classify endpoint
  classify_func <- "function(wav_path, onset, offset, species = 'Efuscus') {
    if (!MODEL_LOADED || is.null(TRAIN_DATA)) {
      return(list(
        status = 'error',
        message = 'Model not loaded or no training data available',
        call_type = 'Echo',
        confidence = 60.0
      ))
    }
    
    tryCatch({
      # Extract features
      ftable <- extract_features(wav_path, onset, offset)
      
      # Check if we have features
      if (nrow(ftable) == 0) {
        return(list(
          status = 'error',
          message = 'Failed to extract features',
          call_type = 'Echo',
          confidence = 60.0
        ))
      }
      
      # Direct KNN classification
      train_cols <- setdiff(colnames(TRAIN_DATA), 'selec')
      test_cols <- setdiff(colnames(ftable), 'selec')
      common_cols <- intersect(train_cols, test_cols)
      
      train_x <- TRAIN_DATA[, common_cols, drop = FALSE]
      train_y <- TRAIN_DATA$selec
      test_x <- ftable[, common_cols, drop = FALSE]
      test_x <- test_x[, colnames(train_x), drop = FALSE]
      
      # Ensure numeric columns
      non_numeric <- which(!sapply(train_x, is.numeric))
      if (length(non_numeric) > 0) {
        train_x <- train_x[, sapply(train_x, is.numeric), drop = FALSE]
        test_x <- test_x[, colnames(train_x), drop = FALSE]
      }
      
      # Check for missing values
      missing_in_train <- sapply(train_x, function(x) any(is.na(x)))
      missing_in_test <- sapply(test_x, function(x) any(is.na(x)))
      
      if (any(missing_in_train) || any(missing_in_test)) {
        for (col in colnames(train_x)) {
          if (any(is.na(train_x[[col]]))) {
            col_mean <- mean(train_x[[col]], na.rm = TRUE)
            train_x[[col]][is.na(train_x[[col]])] <- col_mean
          }
          if (any(is.na(test_x[[col]]))) {
            col_mean <- mean(train_x[[col]], na.rm = TRUE)
            test_x[[col]][is.na(test_x[[col]])] <- col_mean
          }
        }
      }
      
      # Apply KNN
      k <- 5
      prediction <- knn(train = as.matrix(train_x), test = as.matrix(test_x), 
                       cl = train_y, k = k, prob = TRUE)
      
      typepred <- as.character(prediction)
      typepredprob <- attr(prediction, 'prob')
      confidence <- typepredprob * 100
      
      result <- list(
        status = 'success',
        call_type = typepred,
        confidence = confidence,
        species = species
      )
      
      if (DEBUG_MODE) {
        result$debug_info <- list(
          features_extracted = ncol(ftable),
          features_used = ncol(train_x),
          k_value = k
        )
      }
      
      return(result)
    }, error = function(e) {
      return(list(
        status = 'error',
        message = paste('Error making prediction:', e$message),
        call_type = 'Echo',
        confidence = 60.0
      ))
    })
  }"
  
  # Define call_types endpoint
  call_types_func <- "function(species = 'Efuscus') {
    call_types <- list(
      'Efuscus' = c('Echo', 'FM', 'Social'),
      'Myotis' = c('Echo', 'Social'),
      'Nleps' = c('Echo', 'FM', 'Social', 'Type A')
    )
    
    if (species %in% names(call_types)) {
      result <- list(
        status = 'success',
        species = species,
        call_types = call_types[[species]]
      )
      return(result)
    } else {
      return(list(
        status = 'error',
        message = paste('Unknown species:', species),
        available_species = names(call_types)
      ))
    }
  }"
  
  # Define debug model endpoint
  debug_model_func <- "function() {
    if (!DEBUG_MODE) {
      return(list(status = 'error', message = 'Debug mode not enabled'))
    }
    
    if (!MODEL_LOADED) {
      return(list(status = 'error', message = 'Model not loaded'))
    }
    
    model_info <- list(
      model_class = class(kknn_model),
      training_data_rows = nrow(TRAIN_DATA),
      training_data_cols = ncol(TRAIN_DATA),
      training_classes = levels(TRAIN_DATA$selec),
      feature_names = setdiff(names(TRAIN_DATA), 'selec')
    )
    
    return(list(status = 'success', model_info = model_info))
  }"
  
  # Create a new, empty router
  api <- plumber::pr()
  
  # Add endpoints manually
  api$handle("GET", "/ping", eval(parse(text = ping_func)))
  api$handle("POST", "/classify", eval(parse(text = classify_func)))
  api$handle("GET", "/call_types", eval(parse(text = call_types_func)))
  api$handle("GET", "/debug/model", eval(parse(text = debug_model_func)))
  
  # Add CORS filter
  api <- api %>% plumber::pr_filter("cors", function(req, res) {
    res$setHeader("Access-Control-Allow-Origin", "*")
    plumber::forward()
  })
  
  # Log endpoints
  debug_log("API router created with endpoints:")
  endpoints <- api$routes
  if (length(endpoints) > 0) {
    for (route in endpoints) {
      if (!is.null(route$path)) {
        debug_log("Endpoint:", route$path, "Method:", route$method)
      }
    }
  } else {
    debug_log("WARNING: No endpoints found!")
  }
  
  return(api)
}

# Function to start the server programmatically
# This can be called from RStudio for debugging
start_server <- function(port = 8100, host = "0.0.0.0", debug = TRUE) {
  DEBUG_MODE <<- debug  # Update global debug mode
  debug_log("Starting R prediction server on", host, "port", port)
  
  # Create the API with explicit file parameter
  api <- create_api()
  
  # Run the API
  debug_log("Starting server...")
  cat("\nStarting server on", host, "port", port, "...\n")
  cat("Test with: curl http://localhost:", port, "/ping\n", sep="")
  api$run(host = host, port = port)
}

# Start the server if running as a script
if (!interactive()) {
  # Get command line arguments
  args <- commandArgs(trailingOnly = TRUE)
  
  # Check for command line port argument
  port <- 8100  # Updated default port to match Docker configuration
  if (length(args) > 0 && startsWith(args[1], "--port=")) {
    port_arg <- sub("--port=", "", args[1])
    port <- as.numeric(port_arg)
  }
  
  host <- "0.0.0.0"  # Listen on all interfaces
  cat(sprintf("Starting R prediction server on %s:%d...\n", host, port))
  
  # Create the API object using our custom create_api function
  tryCatch({
    cat("Creating API router...\n")
    api <- create_api()
    
    # Routes summary
    cat("Starting server with routes:\n")
    routes <- api$routes
    for (route in routes) {
      if (!is.null(route$path)) {
        cat(sprintf("  %s %s\n", route$method, route$path))
      }
    }
    
    # Run the server
    cat(sprintf("Binding to %s:%d...\n", host, port))
    api$run(host = host, port = port)
    
  }, error = function(e) {
    cat("ERROR starting server:", e$message, "\n")
    print(traceback())
  })
} else {
  # When running in RStudio, provide helper message
  cat("Running in RStudio interactive mode.\n")
  cat("\nDEBUGGING COMMANDS:\n")
  cat("  start_server(port = 8000)   - Start the API server\n\n")
}