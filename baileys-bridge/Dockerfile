# syntax=docker/dockerfile:1
FROM node:20-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git python3 make g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json ./
RUN git config --global url."https://github.com/".insteadOf "ssh://git@github.com/" && \
    npm install --omit=dev
COPY index.js ./
CMD ["node", "index.js"]
