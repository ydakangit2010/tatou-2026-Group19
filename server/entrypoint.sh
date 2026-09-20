#!/usr/bin/env bash
set -e

if [[ -z "${FLAG_2:-}" ]]; then
    echo "WARNING: FLAG_2 is not set"
fi

# Prepare Flag 2 while still running as root
if [[ -f "/app/flag" ]]; then
    if grep -q "REPLACE_THIS_STRING_WITH_SERVER_FLAG" "/app/flag"; then
        echo "Replacing placeholder in flag"
        sed -i "s/REPLACE_THIS_STRING_WITH_SERVER_FLAG/${FLAG_2}/g" /app/flag
    fi

    chown root:root /app/flag
    chmod 600 /app/flag
else
    echo "WARNING: /app/flag not found, skipping"
fi

# Give the application user access to writable storage
echo "Preparing application storage..."
chown -R appuser:appuser /app/storage

echo "Starting server as appuser..."
exec gosu appuser gunicorn -b 0.0.0.0:5000 server:app
