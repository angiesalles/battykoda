FROM rocker/r-base:latest

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libssl-dev \
    libcurl4-openssl-dev \
    libxml2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install R packages
RUN R -e "install.packages(c('plumber', 'class', 'jsonlite', 'stringr'), repos='https://cloud.r-project.org/')"

# Copy R code
COPY *.R /app/
COPY ./static/mymodel.RData /app/static/mymodel.RData

# Default command
CMD ["Rscript", "r_server_direct.R"]