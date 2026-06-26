FROM python:3.11-slim

# System deps: tesseract (rus+kaz langs), poppler for pdf utils, libreoffice for legacy .xls fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-rus \
        tesseract-ocr-kaz \
        poppler-utils \
        libreoffice-calc \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
# Install runtime deps (embeddings extra is optional and heavy; install via build arg if desired)
ARG INSTALL_EMBEDDINGS=false
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . \
    && if [ "$INSTALL_EMBEDDINGS" = "true" ]; then pip install --no-cache-dir ".[embeddings]"; fi

COPY . .
RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
