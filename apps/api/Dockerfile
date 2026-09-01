FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /app

# Create a non-root runtime user.
RUN groupadd --system casemesh \
    && useradd --system --gid casemesh --create-home casemesh

# Install the application separately so Docker can cache dependencies.
COPY pyproject.toml ./
COPY src ./src

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