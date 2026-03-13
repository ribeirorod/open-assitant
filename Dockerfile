FROM python:3.12-slim

# Install Node.js (needed for gws CLI via npm) and system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Install Google Workspace CLI
RUN npm install -g @googleworkspace/cli

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

EXPOSE 8080

CMD ["python", "-m", "src.main"]
