# Multi-stage build for filmlist backend
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic1 \
    libpq-dev \
    gcc \
    g++ \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r app && useradd -r -g app app

# Set work directory
WORKDIR /app

# Upgrade pip and install wheel
RUN pip install --upgrade pip setuptools wheel

# Install Python dependencies in stages for better caching and error handling
COPY requirements.txt .

# Install core dependencies first
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0 \
    pydantic-settings==2.1.0

# Install database dependencies
RUN pip install --no-cache-dir \
    sqlalchemy==2.0.23 \
    alembic==1.13.1 \
    psycopg2-binary==2.9.9

# Install remaining dependencies (excluding heavy ML packages for now)
RUN pip install --no-cache-dir \
    redis==5.0.1 \
    aioredis==2.0.1 \
    python-jose[cryptography]==3.3.0 \
    passlib[bcrypt]==1.7.4 \
    python-multipart==0.0.6 \
    python-docx==1.1.0 \
    Pillow==10.1.0 \
    aiofiles==23.2.0 \
    python-magic==0.4.27 \
    chardet==5.2.0 \
    "numpy<2.0" \
    opencv-python==4.8.1.78 \
    openai==1.3.7 \
    requests==2.31.0 \
    aiohttp==3.9.1 \
    pytest==7.4.3 \
    pytest-asyncio==0.21.1 \
    pytest-cov==4.1.0 \
    pytest-mock==3.12.0 \
    pytest-xdist==3.5.0 \
    httpx==0.25.2 \
    black==23.11.0 \
    isort==5.12.0 \
    flake8==6.1.0 \
    psutil==5.9.6 \
    memory-profiler==0.61.0 \
    python-dotenv==1.0.0 \
    asyncio-mqtt==0.13.0

# Install heavy ML packages separately with timeout and retries
RUN pip install --no-cache-dir --timeout 1000 \
    torch==2.1.1 \
    torchaudio==2.1.1 || echo "Warning: Failed to install torch packages"

RUN pip install --no-cache-dir --timeout 1000 \
    pyannote.audio==3.1.1 || echo "Warning: Failed to install pyannote.audio"

RUN pip install --no-cache-dir \
    scenedetect[opencv]==0.6.2 || echo "Warning: Failed to install scenedetect"

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads output logs && \
    chown -R app:app /app

# Switch to app user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]