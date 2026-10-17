#!/usr/bin/env bash
set -e

# Give the application user access to writable storage
echo "Preparing application storage..."
chown -R appuser:appuser /app/storage

echo "Starting server as appuser..."
exec gosu appuser gunicorn -b 0.0.0.0:5000 server:app
