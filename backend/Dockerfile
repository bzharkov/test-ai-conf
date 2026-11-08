FROM python:3.11-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY pyproject.toml ./
COPY app ./app
# CPU-only torch keeps the image small. The embedding model is NOT an LLM (TZ section 2).
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu torch \
 && pip install ".[ml]" \
 || pip install .
COPY . .
# Pre-download e5-small weights at build time; best effort, falls back to a hash embedder.
RUN python -c "from sentence_transformers import SentenceTransformer as S; S('intfloat/multilingual-e5-small')" || true
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
