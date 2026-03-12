FROM python:3.13-slim

# Install uv (pinned for reproducible builds)
COPY --from=ghcr.io/astral-sh/uv:0.5.29 /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml .

# Install dependencies (no project install yet)
RUN uv sync --no-install-project

# Copy source code
COPY . .

# Install project itself
RUN uv sync

# Make entrypoint executable
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["sh", "entrypoint.sh"]
