FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    EVALUATION_ARTIFACT_ROOT=/app/data/evaluation/baseline-sla-v1

WORKDIR /app

# Create a non-root runtime user.
RUN groupadd --system casemesh \
    && useradd --system --gid casemesh --create-home casemesh

# Install the API from the repository-root Docker build context.
COPY apps/api/pyproject.toml ./
COPY apps/api/src ./src

# Package the committed evaluation baseline as read-only runtime data.
COPY data/evaluation/baseline-sla-v1 ./data/evaluation/baseline-sla-v1

# Fail the image build if the expected evaluation evidence is incomplete.
RUN test -f /app/data/evaluation/baseline-sla-v1/evaluation_results.json \
    && test -f /app/data/evaluation/baseline-sla-v1/evaluation_summary.json \
    && test -f /app/data/evaluation/baseline-sla-v1/evaluation_failures.json \
    && test -f /app/data/evaluation/baseline-sla-v1/evaluation_runs.csv \
    && test -f /app/data/evaluation/baseline-sla-v1/evaluation_stability.json

RUN python -m pip install --upgrade pip \
    && python -m pip install .

# Ensure the runtime user owns the application directory.
RUN chown -R casemesh:casemesh /app

USER casemesh

EXPOSE 8000

# Use the API readiness endpoint without requiring curl/wget.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)" || exit 1

CMD ["uvicorn", "casemesh.main:app", "--host", "0.0.0.0", "--port", "8000"]
