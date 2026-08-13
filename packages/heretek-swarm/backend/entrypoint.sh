#!/bin/bash
# Entrypoint script for the Heretek Swarm API container.
# Runs database migrations before starting the main process.

set -e

echo "========================================="
echo " Heretek Swarm — Container Entrypoint"
echo "========================================="

# Run migrations if DATABASE_URL is set
if [[ -n "$DATABASE_URL" ]]; then
    echo ""
    echo "Running database migrations..."
    python /app/scripts/run_migrations.py --database-url "$DATABASE_URL" || {
        echo "⚠ Migration runner failed (exit code $?). Continuing anyway..."
        echo "  The API may fail if required tables are missing."
    }
    echo ""
else
    echo ""
    echo "⚠ DATABASE_URL not set — skipping migrations."
    echo ""
fi

# Execute the main command (default: heretek-swarm serve)
echo "Starting: $@"
exec "$@"
