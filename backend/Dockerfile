FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and install precompiled wheels directly without apt-get
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and scripts
COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY ml/ ./ml/
COPY models/ ./models/
COPY contracts/openapi-v1.yaml ./contracts/openapi-v1.yaml
COPY contracts/fixtures/g4/ ./contracts/fixtures/g4/
COPY research/g0-g1/DATASET_MANIFEST.json research/g0-g1/SIGNAL_MAP_V1.yaml research/g0-g1/G3_INCIDENT_INDEX.json research/g0-g1/G3_INCIDENT_INDEX.sha256 ./research/g0-g1/

ENV PYTHONPATH=/app

EXPOSE 8050

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8050"]
