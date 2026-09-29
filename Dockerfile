# ==============================================================================
# Production Dockerfile for WhatsApp SACCO AI Companion
# Target: Production Container Deployment (FastAPI, Groq Inference, Twilio)
# ==============================================================================

FROM python:3.12-slim

# Set environment variables for Python and Model Caching
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/model_cache \
    PORT=8000

WORKDIR /app

# Install system dependencies required for building psycopg2 and running healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download and bake Sentence Transformer model weights into image layer
# This guarantees sub-second container startup without dynamic downloads from Hugging Face
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy application code, migrations, and static assets
COPY app/ ./app/
COPY data/ ./data/
COPY migrations/ ./migrations/
COPY scripts/ ./scripts/

# Ensure static dashboard files are present and readable
RUN chmod -R a+r /app/app/static/dashboard

# Dynamic port binding ($PORT injected at runtime, defaults to 8000)
EXPOSE 8000

# Production Uvicorn entrypoint with single worker (optimal for container horizontal scaling),
# proxy headers enabled, and dynamic port binding
CMD exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT} \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips "*"
