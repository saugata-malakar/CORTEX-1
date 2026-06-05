#!/bin/bash
set -e

# If the reports directory or database is empty, seed it from the docker image backup
if [ ! -f /app/data/reports/defects.db ]; then
  echo "Persistent disk at /app/data is empty. Restoring default mock data..."
  mkdir -p /app/data/reports
  cp -r /app/data_backup/* /app/data/ || true
  echo "Default mock data restored."
fi

# Run the CMD
exec "$@"
