#!/bin/bash
# Startup script for SCLib Background Service

set -e

echo "Starting SCLib Background Service..."

# Wait for MongoDB to be available (if using local MongoDB)
# For cloud MongoDB, this will just fail fast if connection is bad
if [ -n "$MONGO_URL" ]; then
    echo "MongoDB URL: ${MONGO_URL}"
else
    echo "WARNING: MONGO_URL not set"
fi

# Create settings file
SETTINGS_FILE="/app/config/bg_service_settings.json"
cat > "$SETTINGS_FILE" <<EOF
{
  "db_name": "${DB_NAME:-scientistcloud}"
}
EOF

echo "Settings file created at $SETTINGS_FILE"

# Set Python path to include SCLib
export PYTHONPATH=/app/scientistCloudLib:$PYTHONPATH

# Change to SCLib_JobProcessing directory
cd /app/scientistCloudLib/SCLib_JobProcessing

# Start the background service
echo "Starting background service..."
exec python3 SCLib_BackgroundService.py "$SETTINGS_FILE"

