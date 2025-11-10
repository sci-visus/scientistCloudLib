#!/bin/bash
# Script to run update_dataset_sizes.py inside the FastAPI Docker container
# Usage: ./run_in_container.sh [--dry-run] [--uuid UUID] [--log-level LEVEL]

# Container name (from docker-compose.yml)
CONTAINER_NAME="sclib_fastapi"

# Script path in container
SCRIPT_PATH="/app/scientistCloudLib/SCLib_Maintenance/update_dataset_sizes.py"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container '${CONTAINER_NAME}' is not running"
    echo "Start it with: cd scientistCloudLib/Docker && docker-compose up -d fastapi"
    exit 1
fi

# Build the command with all arguments passed through
docker exec -it "${CONTAINER_NAME}" python3 "${SCRIPT_PATH}" "$@"

