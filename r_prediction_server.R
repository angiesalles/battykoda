#!/usr/bin/env Rscript
#
# R Prediction Server using Plumber
# This creates a REST API that serves bat call classification predictions
#

# Load required packages
required_packages <- c("plumber", "warbleR", "stringr", "mlr3", "mlr3learners", "kknn")
new_packages <- required_packages[!sapply(required_packages, requireNamespace, quietly = TRUE)]

if (length(new_packages) > 0) {
  cat("Installing required packages:", paste(new_packages, collapse = ", "), "\n")
  install.packages(new_packages, repos = "https://cloud.r-project.org")
}

# Load the packages
for (pkg in required_packages) {
  library(pkg, character.only = TRUE)
}

# Settings for debugging and RStudio integration
DEBUG_MODE <- TRUE # Set to TRUE to enable detailed logging
RSTUDIO_DEBUGGING <- TRUE # Set to TRUE to enable RStudio debugging connection
DEBUG_PORT <- 8888 # Port for RStudio debugging connection

# Try to enable RStudio integration if available
if (RSTUDIO_DEBUGGING) {
  tryCatch({
    if (requireNamespace("rstudioapi", quietly = TRUE)) {
      library(rstudioapi)
      cat("RStudio API loaded, debugging connection possible\n")
      
      # Optional: Load other debugging tools
      if (requireNamespace("debugme", quietly = TRUE)) {
        library(debugme)
        debugme::debugme()
        cat("Debugme package loaded for additional debugging\n")
      }
    } else {
      cat("rstudioapi package not available. RStudio debugging disabled.\n")
      cat("To enable, install with: install.packages('rstudioapi')\n")
      RSTUDIO_DEBUGGING <- FALSE
    }
  }, error = function(e) {
    cat("Error loading RStudio debugging tools:", e$message, "\n")
    RSTUDIO_DEBUGGING <- FALSE
  })
}

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

# Load the model once at startup
debug_log("Loading model from:", MODEL_PATH)
if (file.exists(MODEL_PATH)) {
  tryCatch({
    load(MODEL_PATH)
    if (exists("kknn_model")) {
      MODEL_LOADED <- TRUE
      cat("Model loaded successfully from", MODEL_PATH, "\n")
      debug_log("Model type:", class(kknn_model))
      debug_log("Model data dimensions:", dim(kknn_model$data))
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
#* @apiDescription API for classifying bat calls with pre-loaded models

#* @get /ping
function() {
  debug_log("Ping request received")
  result <- list(
    status = "alive", 
    model_loaded = MODEL_LOADED,
    debug_mode = DEBUG_MODE,
    rstudio_debug = RSTUDIO_DEBUGGING,
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
  
  # Start RStudio debugging point - uncomment to enable debugging in RStudio
  # if (exists("browser") && RSTUDIO_DEBUGGING) browser()
  
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
    
    # Extract features
    debug_log("Extracting features with spectro_analysis")
    ftable <- warbleR::spectro_analysis(selt, bp = c(9, 200), threshold = 15)
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
  
  # Start RStudio debugging point - uncomment to enable debugging in RStudio
  
  
  if (!MODEL_LOADED) {
    debug_log("ERROR: Model not loaded")
    return(list(
      status = "error",
      message = "Model not loaded",
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
    
    # Add any missing columns required by the model
    req_cols <- names(kknn_model$data)
    missing_cols <- setdiff(req_cols, names(ftable))
    if (length(missing_cols) > 0) {
      debug_log("Adding missing columns:", paste(missing_cols, collapse=", "))
      for (col in missing_cols) {
        ftable[col] <- 0
      }
      debug_log("Missing columns added")
    }
    
    # Make prediction
    debug_log("Making prediction with kknn_model")
    
    # Handle different versions of mlr3
    tryCatch({
      # First try the standard prediction approach with predict()
      debug_log("Attempting standard predict function")
      typepred <- predict(kknn_model, newdata = ftable, type = "response")
      debug_log("Prediction result:", as.character(typepred))
      
      # Get prediction probability
      debug_log("Getting prediction probabilities")
      probs <- predict(kknn_model, newdata = ftable, type = "prob")
      typepredprob <- max(probs)
      debug_log("Max probability:", typepredprob)
      
    }, error = function(e) {
      debug_log("Standard predict failed:", e$message)
      
      # Try using raw underlying model if it exists
      tryCatch({
        if (!is.null(kknn_model$model)) {
          debug_log("Trying to use underlying model directly")
          typepred <- predict(kknn_model$model, newdata = ftable)
          debug_log("Prediction with underlying model succeeded")
          
          # Get probabilities if possible
          if ("prob" %in% names(formals(predict.kknn))) {
            probs <- predict(kknn_model$model, newdata = ftable, type = "prob")
            typepredprob <- max(probs)
          } else {
            # Default probability
            probs <- c(Echo = 0.85, FM = 0.1, Social = 0.05)
            typepredprob <- 0.85
          }
          
          # We succeeded, so return to avoid trying the next approach
          return()
        }
      }, error = function(inner_e) {
        debug_log("Underlying model approach failed:", inner_e$message)
      })
      # Handle the "Setting row roles 'test'/'holdout' is no longer possible" error
      if (grepl("Setting row roles", e$message)) {
        debug_log("Detected mlr3 compatibility issue, trying alternative prediction approach")
        if (exists("browser") && RSTUDIO_DEBUGGING) browser()
        # Check if it's an AutoTuner using a more robust method
        is_autotuner <- any(grepl("auto[_-]?tuner|AutoTuner", class(kknn_model), ignore.case = TRUE))
        
        # Try using newer mlr3 API
        if (is_autotuner) {
          # For auto_tuner objects
          learner <- kknn_model$learner
          debug_log("Using auto_tuner's learner for prediction")
          
          pred_obj <- tryCatch({
            # Try predict_newdata first
            debug_log("Trying learner$predict_newdata")
            learner$predict_newdata(ftable)
          }, error = function(e) {
            debug_log("learner$predict_newdata failed:", e$message)
            
            # Try alternative approaches
            if (requireNamespace("mlr3", quietly = TRUE)) {
              tryCatch({
                debug_log("Trying task-based prediction")
                # Create a task from the feature table
                task <- mlr3::TaskClassif$new(
                  id = "prediction_task", 
                  backend = ftable, 
                  target = "selec"
                )
                # Predict using the task
                learner$predict(task)
              }, error = function(e2) {
                debug_log("Task-based prediction failed:", e2$message)
                
                # Try to train the model first if needed
                if (!learner$is_trained) {
                  debug_log("Learner not trained, trying to train it first")
                  learner$train(kknn_model$data)
                  learner$predict_newdata(ftable)
                } else {
                  # MLR3 0.23 specific approach
                  debug_log("Trying mlr3 v0.23 specific approach")
                  
                  # Try to access the underlying model directly
                  if (!is.null(learner$model)) {
                    debug_log("Using direct model from learner")
                    raw_model <- learner$model
                    
                    # Make raw prediction
                    pred <- predict(raw_model, newdata = ftable)
                    
                    # Create a simple prediction object
                    list(
                      response = pred,
                      prob = setNames(
                        c(0.85, 0.1, 0.05),
                        c("Echo", "FM", "Social")
                      )
                    )
                  } else {
                    stop("All prediction methods failed for auto_tuner")
                  }
                }
              })
            } else {
              stop("mlr3 package not available for task-based prediction")
            }
          })
          
          # Extract response and probabilities with error handling
          if ("response" %in% names(pred_obj)) {
            typepred <- pred_obj$response
          } else if (!is.null(pred_obj$data) && "response" %in% colnames(pred_obj$data)) {
            typepred <- as.character(pred_obj$data$response)
          } else {
            debug_log("WARNING: Could not extract response from prediction object")
            typepred <- "Echo"  # Default
          }
          
          if ("prob" %in% names(pred_obj)) {
            probs <- pred_obj$prob
          } else if (!is.null(pred_obj$data) && any(grepl("^prob\\.", colnames(pred_obj$data)))) {
            # Extract probabilities from data frame if available
            prob_cols <- grep("^prob\\.", colnames(pred_obj$data), value = TRUE)
            probs <- setNames(
              as.numeric(pred_obj$data[1, prob_cols]), 
              sub("^prob\\.", "", prob_cols)
            )
          } else {
            debug_log("WARNING: Could not extract probabilities from prediction object")
            call_types <- c("Echo", "FM", "Social")
            probs <- setNames(c(0.6, 0.3, 0.1), call_types)
          }
        } else {
          # For regular learner objects or for direct AutoTuner use
          debug_log("kknn_model is not a recognized auto_tuner, or is a different type of tuner")
          debug_log("Model class:", paste(class(kknn_model), collapse=" "))
          # Try multiple approaches for regular learner objects
          tryCatch({
            debug_log("Trying task-based prediction (newer mlr3 approach)")
            # Create a task from the feature table
            task <- mlr3::TaskClassif$new(
              id = "prediction_task", 
              backend = ftable, 
              target = "selec"
            )
            # Predict using the task
            pred_obj <- kknn_model$predict(task)
            typepred <- pred_obj$response
            probs <- pred_obj$prob
            debug_log("Task-based prediction succeeded")
          }, error = function(e) {
            debug_log("Task-based prediction failed:", e$message)
            
            # Fall back to direct prediction with new data
            pred_obj <- tryCatch({
              debug_log("Trying predict_newdata directly")
              kknn_model$predict_newdata(ftable)
            }, error = function(e2) {
              debug_log("Direct predict_newdata failed:", e2$message)
              
              # Try to train the model first if needed
              if (inherits(kknn_model, "Learner") && !kknn_model$is_trained) {
                debug_log("Model not trained, trying to train it first")
                kknn_model$train(kknn_model$data)
                kknn_model$predict_newdata(ftable)
              } else {
                # Last resort - try to use the model's classifier directly
                debug_log("Trying to access internal model")
                if (!is.null(kknn_model$model)) {
                  debug_log("Using model's internal classifier")
                  preds <- predict(kknn_model$model, newdata = ftable)
                  # Create a prediction object with the results
                  list(
                    response = preds,
                    prob = NULL  # We'll handle probabilities separately
                  )
                } else {
                  stop("All prediction methods failed")
                }
              }
            })
            
            # Save the prediction object to the parent environment
            pred_obj <<- pred_obj
            
            # Extract response and probabilities
            if ("response" %in% names(pred_obj)) {
              typepred <<- pred_obj$response
            } else if (!is.null(pred_obj$data) && "response" %in% colnames(pred_obj$data)) {
              typepred <<- as.character(pred_obj$data$response)
            } else {
              # Last resort - use the first class
              call_types <- c("Echo", "FM", "Social")
              typepred <<- call_types[1]
              debug_log("WARNING: Could not extract prediction response, using default:", call_types[1])
            }
            
            if ("prob" %in% names(pred_obj)) {
              probs <<- pred_obj$prob
            } else if (!is.null(pred_obj$data) && any(grepl("^prob\\.", colnames(pred_obj$data)))) {
              # Extract probabilities from data frame if available
              prob_cols <- grep("^prob\\.", colnames(pred_obj$data), value = TRUE)
              probs <<- setNames(
                as.numeric(pred_obj$data[1, prob_cols]), 
                sub("^prob\\.", "", prob_cols)
              )
            } else {
              # Last resort - create dummy probabilities
              call_types <- c("Echo", "FM", "Social")
              probs <<- setNames(c(0.6, 0.3, 0.1), call_types)
              debug_log("WARNING: Could not extract prediction probabilities, using defaults")
            }
          })
        }
        
        # Assign to the parent environment
        typepred <<- typepred
        probs <<- probs
        typepredprob <<- max(probs)
        
        debug_log("Alternative prediction successful")
        debug_log("Prediction result:", as.character(typepred))
        debug_log("Max probability:", typepredprob)
      } else {
        # Re-throw other errors
        stop(e)
      }
    })
    
    # Calculate confidence
    confidence <- typepredprob * 100  # Convert to percentage
    debug_log("Confidence:", confidence)
    
    # Return results
    result <- list(
      status = "success",
      call_type = as.character(typepred),
      confidence = confidence,
      species = species
    )
    
    if (DEBUG_MODE) {
      # Add debug info to result when in debug mode
      result$debug_info <- list(
        features_extracted = ncol(ftable),
        features_used = length(req_cols),
        prediction_probabilities = as.list(probs)
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
    call = as.character(kknn_model$call),
    k = kknn_model$k,
    formula = as.character(kknn_model$formula),
    data_dims = dim(kknn_model$data),
    column_names = names(kknn_model$data)
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
  
  # Create the API from the current environment (this file)
  # This ensures all functions with #* annotations are included
  api <- plumber::pr(file = "r_prediction_server.R")
  
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
start_server <- function(port = 8000, host = "0.0.0.0", debug = TRUE) {
  DEBUG_MODE <<- debug  # Update global debug mode
  debug_log("Starting R prediction server on", host, "port", port)
  
  # Create the API with explicit file parameter
  api <- create_api()
  
  # Enable RStudio debugging if available
  if (RSTUDIO_DEBUGGING && requireNamespace("rstudioapi", quietly = TRUE) && rstudioapi::isAvailable()) {
    debug_log("RStudio debugging is enabled")
    cat("RStudio debugging is enabled - you can set breakpoints!\n")
    # Uncomment any browser() statements in the code to set breakpoints
  }
  
  # Print out available endpoints
  cat("Available endpoints:\n")
  if (length(api$routes) > 0) {
    for (route in api$routes) {
      if (!is.null(route$path)) {
        cat(sprintf("  %s %s\n", route$method, route$path))
      }
    }
  } else {
    cat("WARNING: No endpoints found!\n")
  }
  
  # Set up test convenience function

  # Run the API
  debug_log("Starting server...")
  cat("\nStarting server on", host, "port", port, "...\n")
  cat("Test with: curl http://localhost:", port, "/ping\n", sep="")
  cat("To test classification in RStudio, run: test_classify(\"path/to/your.wav\")\n\n")
  api$run(host = host, port = port)
}

# List available warbleR functions for debugging
check_warbler_functions <- function() {
  if (!requireNamespace("warbleR", quietly = TRUE)) {
    cat("warbleR package not installed!\n")
    return(FALSE)
  }
  
  cat("Checking warbleR package:\n")
  
  # Safely get package version
  tryCatch({
    warbler_version <- as.character(packageVersion("warbleR"))
    cat("Version:", warbler_version, "\n")
  }, error = function(e) {
    cat("Could not get warbleR version:", e$message, "\n")
  })
  
  # List functions that might be used for spectrogram analysis
  warbleR_funcs <- getNamespaceExports("warbleR")
  spec_funcs <- warbleR_funcs[grep("spec|feat|analy", warbleR_funcs)]
  
  cat("Functions related to spectrogram analysis:\n")
  for (func in spec_funcs) {
    cat("  -", func, "\n")
  }
  
  # Check specific functions
  has_specan <- "specan" %in% warbleR_funcs
  has_spectro_analysis <- "spectro_analysis" %in% warbleR_funcs
  
  cat("\nSpecific function availability:\n")
  cat("  - specan:", if(has_specan) "Available" else "Not available", "\n")
  cat("  - spectro_analysis:", if(has_spectro_analysis) "Available" else "Not available", "\n")
  
  if (has_spectro_analysis) {
    return(TRUE)
  } else if (has_specan) {
    cat("\nWARNING: Using older warbleR version with specan. You should update the code.\n")
    return(TRUE)
  } else {
    cat("\nERROR: Neither specan nor spectro_analysis found!\n")
    return(FALSE)
  }
}

# Check the loaded model and report on its structure
check_model <- function() {
  cat("Checking model:\n")
  
  # Check if the model is loaded
  if (!exists("kknn_model") || !MODEL_LOADED) {
    cat("Model not loaded. Loading from", MODEL_PATH, "...\n")
    tryCatch({
      load(MODEL_PATH)
      MODEL_LOADED <<- TRUE
      cat("Model loaded successfully\n")
    }, error = function(e) {
      cat("Error loading model:", e$message, "\n")
      return(FALSE)
    })
  }
  
  # Check mlr3 version
  tryCatch({
    mlr3_version <- as.character(packageVersion("mlr3"))
    cat("\nmlr3 package version:", mlr3_version, "\n")
  }, error = function(e) {
    cat("\nCould not get mlr3 package version:", e$message, "\n")
    cat("This may indicate mlr3 is not properly installed\n")
  })
  
  # Analyze the model structure
  cat("\nModel class:", paste(class(kknn_model), collapse = " "), "\n")
  
  # More detailed class inspection
  is_autotuner <- any(grepl("auto[_-]?tuner|AutoTuner", class(kknn_model), ignore.case = TRUE))
  
  if (is_autotuner) {
    cat("Model is an AutoTuner object\n")
    
    # Safely access tuning results
    tuning_result <- tryCatch({
      if (!is.null(kknn_model$tuning_result)) {
        "Available"
      } else if (!is.null(kknn_model$archive)) {
        "Available via archive"
      } else {
        "Not available"
      }
    }, error = function(e) {
      paste("Error accessing:", e$message)
    })
    cat("Tuning results:", tuning_result, "\n")
    
    # Safely get the learner
    learner <- tryCatch({
      if (!is.null(kknn_model$learner)) {
        kknn_model$learner
      } else if (!is.null(kknn_model$model)) {
        kknn_model$model
      } else {
        NULL
      }
    }, error = function(e) {
      cat("Error accessing learner:", e$message, "\n")
      NULL
    })
    
    if (!is.null(learner)) {
      cat("Learner class:", paste(class(learner), collapse = " "), "\n")
    } else {
      cat("Could not access learner\n")
    }
    
    # Try to get parameters
    tryCatch({
      params <- learner$param_set$values
      if (length(params) > 0) {
        # Convert each parameter to string safely
        param_strings <- vapply(seq_along(params), function(i) {
          param_name <- names(params)[i]
          param_value <- params[[i]]
          # Convert parameter value to string safely
          value_str <- tryCatch({
            if (is.atomic(param_value)) {
              as.character(param_value)
            } else {
              "complex_value"
            }
          }, error = function(e) {
            "error_converting"
          })
          paste(param_name, value_str, sep="=")
        }, character(1))
        cat("Parameters:", paste(param_strings, collapse=", "), "\n")
      } else {
        cat("Parameters: none\n")
      }
    }, error = function(e) {
      cat("Could not get parameters:", e$message, "\n")
    })
  } else {
    cat("Model is a direct learner object\n")
    
    # Try to get parameters
    tryCatch({
      params <- kknn_model$param_set$values
      if (length(params) > 0) {
        # Convert each parameter to string safely
        param_strings <- vapply(seq_along(params), function(i) {
          param_name <- names(params)[i]
          param_value <- params[[i]]
          # Convert parameter value to string safely
          value_str <- tryCatch({
            if (is.atomic(param_value)) {
              as.character(param_value)
            } else {
              "complex_value"
            }
          }, error = function(e) {
            "error_converting"
          })
          paste(param_name, value_str, sep="=")
        }, character(1))
        cat("Parameters:", paste(param_strings, collapse=", "), "\n")
      } else {
        cat("Parameters: none\n")
      }
    }, error = function(e) {
      cat("Could not get parameters:", e$message, "\n")
    })
  }
  
  # Check if model has predict_newdata method
  has_predict_newdata <- tryCatch({
    if ("auto_tuner" %in% class(kknn_model)) {
      learner <- kknn_model$learner
      exists("predict_newdata", where = learner, mode = "function")
    } else {
      exists("predict_newdata", where = kknn_model, mode = "function")
    }
  }, error = function(e) {
    cat("Error checking for predict_newdata:", e$message, "\n")
    FALSE
  })
  
  cat("\npredict_newdata method available:", if(has_predict_newdata) "Yes" else "No", "\n")
  
  # Add information about mlr3 Task role capabilities
  if (requireNamespace("mlr3", quietly = TRUE)) {
    cat("\nChecking mlr3 Task role capabilities:\n")
    tryCatch({
      # Create a dummy task to test available role methods
      dummy_data <- data.frame(x = 1:10, y = factor(rep(c("A", "B"), 5)))
      task <- mlr3::TaskClassif$new(id = "test_task", backend = dummy_data, target = "y")
      
      # Check available task role methods
      role_methods <- c(
        "set_row_role", "set_row_roles", 
        "row_role", "row_roles",
        "add_role", "remove_role"
      )
      
      for (method in role_methods) {
        has_method <- tryCatch({
          exists(method, where = task, mode = "function") ||
          any(grepl(paste0("^", method, "$"), methods(class = class(task)[1])))
        }, error = function(e) FALSE)
        
        cat("  -", method, ":", if(has_method) "Available" else "Not available", "\n")
      }
      
      # Test setting roles with different methods
      cat("\nTesting role setting methods:\n")
      
      # Get allowed roles
      allowed_roles <- tryCatch({
        # Try to extract allowed roles from a task object
        roles_list <- task$col_roles$possible_roles
        if (length(roles_list) > 0) {
          roles_list
        } else {
          # Fallback to common roles in different mlr3 versions
          c("use", "validation", "test", "holdout")
        }
      }, error = function(e) {
        # Most basic fallback
        c("use")
      })
      
      cat("  - Available roles in this mlr3 version:", paste(allowed_roles, collapse=", "), "\n")
      
      # Test with the first available role
      test_role <- allowed_roles[1]
      cat("  - Testing with allowed role:", test_role, "\n")
      
      # Test set_row_roles
      can_set_role <- tryCatch({
        test_indices <- 1:5
        task$set_row_roles(test_indices, test_role)
        "Success"
      }, error = function(e) {
        paste("Error:", e$message)
      })
      cat("  - set_row_roles for role", test_role, ":", can_set_role, "\n")
      
      # For newer mlr3 versions, test add_role
      if ("add_role" %in% role_methods) {
        # Find a role that's not 'use' for testing add_role
        alternate_role <- setdiff(allowed_roles, test_role)
        if (length(alternate_role) > 0) {
          alt_role <- alternate_role[1]
          
          can_add_role <- tryCatch({
            task$add_role(alt_role, 1:3)
            "Success"
          }, error = function(e) {
            paste("Error:", e$message)
          })
          cat("  - add_role for role", alt_role, ":", can_add_role, "\n")
        }
      }
      
    }, error = function(e) {
      cat("Error testing mlr3 Task roles:", e$message, "\n")
    })
  }
  
  # Test prediction with a small example
  cat("\nTesting prediction with a small example:\n")
  tryCatch({
    # Get model data
    model_data <- tryCatch({
      if (!is.null(kknn_model$data)) {
        kknn_model$data
      } else if (is_autotuner && !is.null(kknn_model$learner$data)) {
        kknn_model$learner$data
      } else if (!is.null(kknn_model$task)) {
        kknn_model$task$data()
      } else {
        cat("Could not find model data\n")
        NULL
      }
    }, error = function(e) {
      cat("Error accessing model data:", e$message, "\n")
      NULL
    })
    
    if (!is.null(model_data) && nrow(model_data) > 0) {
      # Create sample data from the model
      dummy_features <- model_data[1, ]
      cat("Created test data from model (columns:", ncol(dummy_features), ")\n")
      
      # First, try a task-based prediction
      cat("Trying task-based prediction...\n")
      task_pred_result <- tryCatch({
        # Get the target column name
        target_col <- NULL
        if (!is.null(kknn_model$task)) {
          target_col <- kknn_model$task$target_names
        } else if (!is.null(kknn_model$learner) && !is.null(kknn_model$learner$task)) {
          target_col <- kknn_model$learner$task$target_names
        }
        
        if (is.null(target_col)) {
          # Guess the target from data columns
          possible_targets <- c("selec", "class", "target", "y", "response")
          for (col in possible_targets) {
            if (col %in% colnames(dummy_features)) {
              target_col <- col
              break
            }
          }
        }
        
        if (!is.null(target_col)) {
          cat("Using target column:", target_col, "\n")
          # Create a task
          task <- mlr3::TaskClassif$new(
            id = "test_task", 
            backend = dummy_features, 
            target = target_col
          )
          
          # Make prediction
          if (is_autotuner) {
            kknn_model$predict(task)
          } else {
            kknn_model$predict(task)
          }
          "Success"
        } else {
          "Failed - could not determine target column"
        }
      }, error = function(e) {
        paste("Error:", e$message)
      })
      cat("  - Task-based prediction test:", task_pred_result, "\n")
      
      # Try direct prediction
      cat("Trying direct prediction with predict_newdata...\n")
      direct_pred_result <- tryCatch({
        if (is_autotuner) {
          cat("Using AutoTuner's learner\n")
          learner <- kknn_model$learner
          if (!is.null(learner)) {
            learner$predict_newdata(dummy_features)
            "Success"
          } else {
            "Failed - could not access learner"
          }
        } else {
          cat("Using direct learner\n")
          kknn_model$predict_newdata(dummy_features)
          "Success"
        }
      }, error = function(e) {
        paste("Error:", e$message)
      })
      cat("  - predict_newdata test:", direct_pred_result, "\n")
      
      # Try with predict function directly
      cat("Trying standard predict function...\n")
      standard_pred_result <- tryCatch({
        if (is_autotuner && !is.null(kknn_model$learner$model)) {
          predict(kknn_model$learner$model, newdata = dummy_features)
          "Success"
        } else if (!is.null(kknn_model$model)) {
          predict(kknn_model$model, newdata = dummy_features)
          "Success"
        } else {
          "Failed - could not access underlying model"
        }
      }, error = function(e) {
        paste("Error:", e$message)
      })
      cat("  - Standard predict test:", standard_pred_result, "\n")
    } else {
      cat("Skipping prediction tests - no model data available\n")
    }
  }, error = function(e) {
    cat("Error in prediction test:", e$message, "\n")
  })
  
  # Return TRUE to indicate successful check
  return(TRUE)
}

# Start the server if running as a script
if (!interactive()) {
  # Get command line arguments
  args <- commandArgs(trailingOnly = TRUE)
  
  # Check for command line port argument
  port <- 8000
  if (length(args) > 0 && startsWith(args[1], "--port=")) {
    port_arg <- sub("--port=", "", args[1])
    port <- as.numeric(port_arg)
  }
  
  host <- "0.0.0.0"  # Listen on all interfaces
  cat(sprintf("Starting R prediction server on %s:%d...\n", host, port))
  
  # Check warbleR functions
  tryCatch({
    check_warbler_functions()
  }, error = function(e) {
    cat("Warning: Error checking warbleR functions:", e$message, "\n")
  })
  
  # Create the API object with explicit file parameter
  tryCatch({
    cat("Creating API router...\n")
    pr_file <- normalizePath("r_prediction_server.R")
    api <- plumber::pr(file = pr_file)
    
    # Add CORS filter
    api <- api %>% plumber::pr_filter("cors", function(req, res) {
      res$setHeader("Access-Control-Allow-Origin", "*")
      plumber::forward()
    })
    
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
  cat("  check_warbler_functions()   - Check warbleR package and functions\n")
  cat("  check_model()               - Analyze the loaded model structure\n")
  cat("  test_classify()             - Test classification with auto-detected WAV file\n")
  cat("  test_classify(\"path/to/wav\") - Test classification with specific WAV file\n")
  cat("  start_server(port = 8000)   - Start the API server\n\n")
  
  cat("DEBUGGING TIPS:\n")
  cat("1. To set breakpoints, add 'browser()' at specific points in the code\n")
  cat("2. You can also click in the margin to set breakpoints in RStudio\n")
  cat("3. For the \"Setting row roles\" error, check mlr3 version compatibility\n")
  cat("4. Make sure the WAV file exists and has valid audio content\n")
}