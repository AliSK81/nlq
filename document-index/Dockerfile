FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV FASTEMBED_CACHE_PATH=/models/fastembed
ENV HF_HOME=/models/hf
RUN mkdir -p /models/fastembed /models/hf

COPY pyproject.toml .
COPY app/ app/
RUN pip install --no-cache-dir . \
    && python -c "from fastembed import TextEmbedding, SparseTextEmbedding; \
TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); \
SparseTextEmbedding(model_name='Qdrant/bm25')" \
    || echo "model pre-warm skipped (will download on first use)"

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
