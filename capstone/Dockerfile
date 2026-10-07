# The capstone API and its React page in one image.
#
#     docker build -t payrag-api capstone
#     docker run --rm -p 8000:8000 --env-file .env payrag-api
#
# Three stages, so the final image holds no Node, no npm cache, no compiler and no test code:
#   web   builds the React page (frontend/dist);
#   deps  installs the pinned run-time requirements (deploy/requirements.txt) into a virtualenv;
#   app   copies the virtualenv, the package source and the built page onto a slim Python image.
# Azure access stays keyless: in Azure the managed identity, locally `az login` is not available inside
# the container, so pass the identity's settings (or run the API outside Docker) for real answers.

FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS deps
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH
COPY deploy/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

FROM python:3.11-slim AS app
ENV PATH=/venv/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=deps /venv /venv
COPY src/payments_rag/ payments_rag/
# Where `find_web_root` looks first, the same place the App Service zip puts it.
COPY --from=web /web/dist/ payments_rag/web/
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
CMD ["python", "-m", "uvicorn", "payments_rag.api:app", "--host", "0.0.0.0", "--port", "8000"]
