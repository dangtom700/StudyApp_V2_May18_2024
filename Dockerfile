FROM continuumio/miniconda3:latest

WORKDIR /app

# Install Linux equivalent of your C++ dependencies (g++, sqlite3, openssl)
RUN apt-get update && apt-get install -y \
    g++ \
    libsqlite3-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Setup Conda Environment
COPY src/env.yml /app/environment.yml
# We use Python dotenv to support your .env configuration seamlessly
RUN conda env create -f /app/environment.yml && /opt/conda/bin/conda install -n StudyAssistant -c conda-forge python-dotenv -y

# Copy source code and orchestrator
COPY src/ /app/src/
COPY config/main.sh /app/config/main.sh
RUN chmod +x /app/config/main.sh

# Ensure the conda environment activates for the shell script
ENV PATH="/opt/conda/envs/StudyAssistant/bin:${PATH}"

# Execute the newly minted shell script orchestrator!
ENTRYPOINT ["/bin/bash", "config/main.sh"]
