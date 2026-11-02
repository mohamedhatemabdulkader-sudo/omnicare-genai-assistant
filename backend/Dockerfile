FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EMBEDDING_CACHE_DIR=/app/models \
    QDRANT_LOCAL_PATH=/app/qdrant_data \
    CLAIMS_PATH=/app/claims/mock_claims.json

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into the image so startup needs no download.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/app/models')"

COPY app ./app
COPY data ./data
COPY docker_entrypoint.py /app/docker_entrypoint.py
RUN mkdir -p /app/claims /app/qdrant_data \
    && cp data/mock_claims.json /app/claims/ \
    && chmod 1777 /app/claims /app/qdrant_data \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser /app

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=3)"

ENTRYPOINT ["python", "/app/docker_entrypoint.py"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
