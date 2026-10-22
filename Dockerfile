# Warehouse Demand API - the model is scored from JSON with numpy, so no LightGBM needed here
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code, trained model, and the small data files the API reads
COPY api/ api/
COPY src/features.py src/forecast.py src/tree_model.py src/
COPY models/model_info.json models/lgbm_pick_lines.json models/
COPY data/raw/uk_bank_holidays.csv data/raw/staffing_parameters.csv data/raw/
COPY data/processed/daily_workload.csv data/processed/
COPY outputs/03_test_predictions.csv outputs/03_model_comparison.csv outputs/04_staffing_policies.csv outputs/

ENV PORT=8000
EXPOSE 8000
CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
