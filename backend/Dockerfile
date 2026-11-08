FROM python:3.11-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY pyproject.toml ./
# CPU-only torch keeps the image small; embeddings model is not an LLM.
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu torch \
 && pip install ".[ml]" 2>/dev/null || pip install .
COPY . .
# Pre-download embedding weights at build time (best effort; see docs/KNOWN_ISSUES.md).
RUN python -c "from sentence_transformers import SentenceTransformer as S; S('intfloat/multilingual-e5-small')" || true
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
