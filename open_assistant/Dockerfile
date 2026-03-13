FROM python:3.12-slim

# Install Node.js (needed for gws CLI via npm) and system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Install Google Workspace CLI
RUN npm install -g @googleworkspace/cli

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8080

CMD ["uv", "run", "python", "-m", "src.main"]
