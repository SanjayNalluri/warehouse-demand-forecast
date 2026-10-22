# Warehouse Demand API - small image with only what the API needs
FROM python:3.12-slim

# LightGBM needs the OpenMP runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Code, trained model, and the small data files the API reads
COPY api/ api/
COPY src/features.py src/forecast.py src/
COPY models/ models/
COPY data/raw/uk_bank_holidays.csv data/raw/staffing_parameters.csv data/raw/
COPY data/processed/daily_workload.csv data/processed/
COPY outputs/03_test_predictions.csv outputs/03_model_comparison.csv outputs/04_staffing_policies.csv outputs/

# Render (and most hosts) pass the port in $PORT
ENV PORT=8000
EXPOSE 8000
CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT}