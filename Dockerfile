# Contenedor OCI opcional para la interfaz Streamlit.
# No sustituye el build Windows/Flet ni modifica la lógica del motor.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TESSDATA_DIR=/usr/share/tesseract-ocr/5/tessdata \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata \
    HOME=/tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY app ./app
COPY assets ./assets

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir ".[streamlit]"

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3).read()" || exit 1

CMD ["python", "-m", "streamlit", "run", "app/main_streamlit.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
