# Define defaults that can be overridden with --build-arg
ARG AIRFLOW_VERSION=3.0.0
ARG PY_MM=3.12           # use major.minor only (e.g., 3.12)

# Use them in FROM (this works for ARGs defined before FROM)
FROM apache/airflow:${AIRFLOW_VERSION}-python${PY_MM}

# IMPORTANT: re-declare ARGs inside the stage to use them later
ARG AIRFLOW_VERSION
ARG PY_MM

# (Optional) expose them as ENV (so they're available at runtime too)
ENV AIRFLOW_VERSION=${AIRFLOW_VERSION}
ENV PY_MM=${PY_MM}

# (Optional) install system packages
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim-tiny curl \
 && rm -rf /var/lib/apt/lists/*
USER airflow

# Add Python dependencies
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PY_MM}.txt"
