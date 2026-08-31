FROM python:3.12-slim

# Install system dependencies for Tesseract OCR, PDF rendering, and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    poppler-utils \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and install wheel tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Leverage Docker layer caching: Copy setup/dependency files first
COPY pyproject.toml setup.py* requirements.txt* /app/
RUN pip install --no-cache-dir -e . || pip install --no-cache-dir -r requirements.txt

# Copy source code after dependencies are installed
COPY . /app

EXPOSE 8000 8501

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]