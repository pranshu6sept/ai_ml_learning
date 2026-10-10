# The API and its React page as one image. Build from the capstone folder:
#
#   docker build -t payrag-api capstone
#   docker run --rm -p 8000:8000 payrag-api            # http://localhost:8000
#
# Three stages, so the final image holds no Node, no compiler, no pip cache and no source of the page:
#   web      builds the React app (npm ci + tsc + vite)
#   deps     installs the compiled requirements (capstone/deploy/requirements.txt) into a virtualenv
#   runtime  the Python base plus that virtualenv, the package and the built page
#
# Nothing secret is built in: the image has no .env and no key. Azure access at run time is by
# identity (the platform's managed identity, or `az login` credentials mounted by you); the API key
# comes from PAYRAG_API_KEY in the environment.

FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /venv
COPY deploy/requirements.txt /tmp/requirements.txt
RUN /venv/bin/pip install -r /tmp/requirements.txt

FROM python:3.11-slim AS runtime
ENV PATH=/venv/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN useradd --system --uid 10001 --no-create-home app
COPY --from=deps /venv /venv
COPY src/payments_rag /app/payments_rag
COPY --from=web /web/dist /app/payments_rag/web
USER app
WORKDIR /app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "payments_rag.api:app", "--host", "0.0.0.0", "--port", "8000"]
