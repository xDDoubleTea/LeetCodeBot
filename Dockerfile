FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN groupadd --system --gid 1000 nonroot \
    && useradd --system --gid 1000 --uid 1000 --create-home nonroot

WORKDIR /app
RUN chown nonroot:nonroot /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pandoc \
    && rm -rf /var/lib/apt/lists/*

USER nonroot

# Set environment variables for uv
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PATH="/app/.venv/bin:$PATH"

COPY --chown=nonroot:nonroot pyproject.toml uv.lock* ./

RUN --mount=type=cache,target=/home/nonroot/.cache/uv,uid=1000,gid=1000 \
    uv sync --no-install-project

COPY --chown=nonroot:nonroot . .

RUN --mount=type=cache,target=/home/nonroot/.cache/uv,uid=1000,gid=1000 \
    uv sync

CMD ["uv", "run", "main.py"]
