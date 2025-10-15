#!/bin/bash

# Setup environment for running maintenance scripts on host system
# This script loads the environment variables from the Docker env file

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(dirname "$SCRIPT_DIR")/Docker"

# Check if docker.env exists
if [ ! -f "$DOCKER_DIR/docker.env" ]; then
    echo "Error: docker.env not found at $DOCKER_DIR/docker.env"
    echo "Please ensure the Docker environment file exists."
    exit 1
fi

print_status "Loading environment from $DOCKER_DIR/docker.env"

# Load environment variables from docker.env
export $(grep -v '^#' "$DOCKER_DIR/docker.env" | xargs)

print_success "Environment variables loaded"

# Show current environment
echo ""
echo "Current environment:"
echo "MONGO_URL: ${MONGO_URL:0:50}..."
echo "DB_NAME: $DB_NAME"
echo "VISUS_DATASETS: $VISUS_DATASETS"
echo ""

# Run the maintenance script with the loaded environment
if [ $# -eq 0 ]; then
    echo "Usage: $0 <command> [options]"
    echo "Example: $0 stats"
    echo "Example: $0 list"
    echo "Example: $0 clean"
    exit 1
fi

# Execute the maintenance script with the loaded environment
exec "$SCRIPT_DIR/maintenance.sh" "$@"
