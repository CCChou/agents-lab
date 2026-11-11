# Build from the repo root (D-039): docker build -f deploy/Dockerfile -t agents-lab .
FROM python:3.14-slim

# The container defaults to UTC; tzdata lets TZ set the time CurrentTimeTool reports.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7.9 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

# Dependencies first, so changing the code does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY agent ./agent
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 agent
USER agent

# Settings come from a mounted directory, secrets from the environment (D-038).
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    AGENT_CONFIG=/etc/agent/config.toml
EXPOSE 8000

# Python runs as PID 1, so `docker stop` reaches uvicorn and it shuts down cleanly.
CMD ["python", "-m", "agent", "serve", "--host", "0.0.0.0", "--port", "8000"]
