FROM python:3.12-slim

# Install Node.js and system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Install Google Workspace CLI and Claude Code CLI
RUN npm install -g @googleworkspace/cli @anthropic-ai/claude-code

WORKDIR /app

# Create venv and install dependencies
COPY requirements.txt ./
RUN python -m venv .venv && .venv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["/app/.venv/bin/python", "-m", "src.main"]
