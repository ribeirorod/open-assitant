# syntax=docker/dockerfile:1
FROM node:20-slim
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client python3 make g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json ./
RUN --mount=type=ssh \
    mkdir -p -m 0700 ~/.ssh && \
    ssh-keyscan github.com >> ~/.ssh/known_hosts && \
    npm install --omit=dev
COPY index.js ./
CMD ["node", "index.js"]
