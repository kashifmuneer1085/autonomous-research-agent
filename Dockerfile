# ─────────────────────────────────────────────────────────────────────
# Autonomous AI Research Agent — Docker image
# Works for:
#   • HuggingFace Spaces (Docker SDK)  → uses default CMD, port 7860
#   • Local docker-compose             → overrides CMD per service
# ─────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# System libs required by Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates curl \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# HuggingFace Spaces require non-root UID 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/home/user/app/data

WORKDIR $HOME/app

# Install Python deps first for better layer caching
COPY --chown=user:user requirements.txt .
RUN pip install --user --no-cache-dir --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser (~150 MB)
RUN python -m playwright install chromium

# Copy application source
COPY --chown=user:user . .

# Create data directory
RUN mkdir -p $HOME/app/data

# Default port for HuggingFace Spaces
EXPOSE 7860
# Also expose 8000/8501 for local docker-compose
EXPOSE 8000 8501

# Default CMD = Streamlit on port 7860 (for HuggingFace Spaces)
# Local docker-compose overrides this per service.
CMD ["streamlit", "run", "frontend/streamlit_app.py", \
     "--server.port=7860", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.enableCORS=false", \
     "--server.enableXsrfProtection=false"]
