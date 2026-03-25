#!/bin/sh
set -e

# Seed memory volume from local Mac on first run (volume empty)
MEMORY_DIR="/root/.claude/projects"
SEED_DIR="/initial-memory"

if [ -d "$SEED_DIR" ] && [ -z "$(ls -A $MEMORY_DIR 2>/dev/null)" ]; then
    echo "Seeding memory from local snapshot..."
    mkdir -p "$MEMORY_DIR"
    cp -r "$SEED_DIR/." "$MEMORY_DIR/"
    echo "Memory seeded."
fi

# Sync settings.json only if not already bind-mounted (read-only bind mount takes priority)
mkdir -p /root/.claude
if [ -w /root/.claude/settings.json ] || [ ! -f /root/.claude/settings.json ]; then
    cp /app/.claude/settings.json /root/.claude/settings.json
    echo "Settings synced from image."
else
    echo "Settings bind-mounted, skipping copy."
fi

# Restore .claude.json from backup if missing (created by claude login)
if [ ! -f "/root/.claude.json" ]; then
    BACKUP=$(ls -t /root/.claude/backups/.claude.json.backup.* 2>/dev/null | head -1)
    if [ -n "$BACKUP" ]; then
        echo "Restoring .claude.json from backup..."
        cp "$BACKUP" /root/.claude.json
    fi
fi

exec "$@"
