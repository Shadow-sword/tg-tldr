FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ src/

# Install dependencies
RUN uv sync --no-dev --no-editable

# Create data directory
RUN mkdir -p /app/data

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["python", "-m", "tg_tldr"]
CMD ["run"]
