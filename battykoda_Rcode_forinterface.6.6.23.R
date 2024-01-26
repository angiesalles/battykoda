
##########################################
#                                        #
#         Project: BattyKoda             #
#   Script: Sound feature extraction     #
#                                        #
##########################################

### Required packages
library(warbleR)
library(stringr)

### Setting directory to where sound files are located
setwd("Z:\\battykoda\\for_gabby")

### Import .wav file paths and create input table (wavtable) for WarbleR

sound.files <- list.files()
c <- str_split_fixed(sound.files,"_", 2)
d <- str_split_fixed(c[,2],".wav", 2)
selec <- d[,1]
start <- rep(0,length(sound.files))
end <- seq(1,length(sound.files))
wavtable <- cbind.data.frame(sound.files,selec,start,end)

### Get length of sound file ('end' column in wavtable)

for (i in 1:nrow(wavtable)){
  audio<-readWave(wavtable[i,1], header=TRUE)
  audiolength <- (audio$samples / audio$sample.rate)
  wavtable[i,4] <- audiolength
}


### Format table for WarbleR

selt <- selection_table(wavtable)

### Extract sound features from calls in table

ftable <- specan(selt, bp = c(9,200), threshold = 15)

### Export sound features table for use in classification model

#write.csv(params,"Feature_table_test.csv")



##########################################
#                                        #
#         Project: BattyKoda             #
#  Script: Running classification model  #
#                                        #
##########################################

library(mlr3)
library(mlr3learners)
library(kknn)
library(mlr3tuning)


###### Training the K-Nearest-Neighbor Classification Model in mlr3 ######

# Feature Scaling

ftable[2:27] = scale(ftable[2:27])

# Create task 

task = as_task_classif(ftable,target='selec')

# Create learner 

learner = lrn("classif.kknn",
              k  = to_tune(1, 120,logscale=T),
              distance = to_tune(1, 100, logscale = TRUE),
              kernel = "rectangular",
              predict_type="prob"
)

# Create auto tuner for hyperparameters #best hyperparameter atm: k=2.398,distance=0

at = auto_tuner(
  tuner = tnr("grid_search", resolution = 5, batch_size = 5),
  learner = learner,
  resampling = rsmp("cv", folds = 3),
  measure = msr("classif.ce")
)

# Training the model

kknn_model = at$train(task)

####### Code for BattyKoda output ########

## Input
input = ftable[nrow(ftable),] ### the code here should be input from battykoda (right now it just extracts the last call in the table)

## Outputs
typepred = predict(kknn_model, newdata = input, "response")
typepredprob = max(predict(kknn_model, newdata = input, "prob"))
typepred ### type predicted, to be exported back to battykoda
typepredprob ### probability of type predicted, to be exported back to battykoda


