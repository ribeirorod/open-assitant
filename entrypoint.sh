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

# Always sync project settings.json into the user-level volume so permissions
# are applied correctly (volume may have a stale or blank settings.json)
mkdir -p /root/.claude
cp /app/.claude/settings.json /root/.claude/settings.json
echo "Settings synced."

# Restore .claude.json from backup if missing (created by claude login)
if [ ! -f "/root/.claude.json" ]; then
    BACKUP=$(ls -t /root/.claude/backups/.claude.json.backup.* 2>/dev/null | head -1)
    if [ -n "$BACKUP" ]; then
        echo "Restoring .claude.json from backup..."
        cp "$BACKUP" /root/.claude.json
    fi
fi

exec "$@"
