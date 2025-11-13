#!/bin/bash
# Test script to run SCLib Background Service locally (without Docker)
# This allows you to test the service without rebuilding containers

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}SCLib Background Service - Local Test${NC}"
echo -e "${BLUE}========================================${NC}"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SCLIB_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${YELLOW}Script directory: $SCRIPT_DIR${NC}"
echo -e "${YELLOW}SCLib root: $SCLIB_ROOT${NC}"

# Check if MONGO_URL is set
if [ -z "$MONGO_URL" ]; then
    echo -e "${YELLOW}MONGO_URL not set. Checking for env file...${NC}"
    
    # Try to find and load env file
    ENV_FILE=""
    if [ -n "$SCLIB_ENV_FILE" ] && [ -f "$SCLIB_ENV_FILE" ]; then
        ENV_FILE="$SCLIB_ENV_FILE"
    elif [ -f "$SCLIB_ROOT/../SCLib_TryTest/env.local" ]; then
        ENV_FILE="$SCLIB_ROOT/../SCLib_TryTest/env.local"
    elif [ -f "$SCLIB_ROOT/../env.local" ]; then
        ENV_FILE="$SCLIB_ROOT/../env.local"
    elif [ -f "./env.local" ]; then
        ENV_FILE="./env.local"
    fi
    
    if [ -n "$ENV_FILE" ]; then
        echo -e "${GREEN}Loading environment from: $ENV_FILE${NC}"
        set -a  # automatically export all variables
        source "$ENV_FILE"
        set +a
    else
        echo -e "${YELLOW}No env file found. Please set MONGO_URL and DB_NAME manually.${NC}"
        echo -e "${YELLOW}Example: export MONGO_URL='mongodb://localhost:27017'${NC}"
        echo -e "${YELLOW}Example: export DB_NAME='scientistcloud'${NC}"
    fi
fi

# Check required environment variables
if [ -z "$MONGO_URL" ]; then
    echo -e "${YELLOW}ERROR: MONGO_URL is required${NC}"
    echo -e "${YELLOW}Set it with: export MONGO_URL='mongodb://localhost:27017'${NC}"
    echo -e "${YELLOW}Or: export MONGO_URL='mongodb+srv://user:pass@cluster.mongodb.net/dbname'${NC}"
    exit 1
fi

# Set defaults
DB_NAME="${DB_NAME:-scientistcloud}"
VISUS_DATASETS="${VISUS_DATASETS:-/tmp/visus_datasets}"

echo -e "${GREEN}Configuration:${NC}"
echo -e "  MONGO_URL: ${MONGO_URL}"
echo -e "  DB_NAME: ${DB_NAME}"
echo -e "  VISUS_DATASETS: ${VISUS_DATASETS}"

# Create necessary directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p "$VISUS_DATASETS/upload"
mkdir -p "$VISUS_DATASETS/converted"
mkdir -p "$VISUS_DATASETS/sync"
mkdir -p "$VISUS_DATASETS/tmp"
mkdir -p "$SCRIPT_DIR/../config"

# Create settings file
SETTINGS_FILE="$SCRIPT_DIR/../config/bg_service_settings.json"
cat > "$SETTINGS_FILE" <<EOF
{
  "db_name": "${DB_NAME}",
  "in_data_dir": "${VISUS_DATASETS}/upload",
  "out_data_dir": "${VISUS_DATASETS}/converted",
  "sync_data_dir": "${VISUS_DATASETS}/sync",
  "auth_dir": "${VISUS_DATASETS}/auth"
}
EOF

echo -e "${GREEN}Settings file created: $SETTINGS_FILE${NC}"

# Set Python path
export PYTHONPATH="$SCLIB_ROOT:$PYTHONPATH"
echo -e "${GREEN}PYTHONPATH: $PYTHONPATH${NC}"

# Change to the SCLib_JobProcessing directory
cd "$SCRIPT_DIR"

# Check if Python dependencies are installed
echo -e "${YELLOW}Checking Python dependencies...${NC}"
if ! python3 -c "import pymongo" 2>/dev/null; then
    echo -e "${YELLOW}WARNING: pymongo not found. Installing basic dependencies...${NC}"
    pip3 install pymongo psutil || echo -e "${YELLOW}Failed to install dependencies. You may need to install them manually.${NC}"
fi

# Check if VisoarAgExplorer is available (for slampy)
if [ -z "$PYTHONPATH" ] || ! python3 -c "import sys; sys.path.insert(0, '/home/ViSOAR/VisoarAgExplorer'); import slampy" 2>/dev/null; then
    echo -e "${YELLOW}WARNING: slampy (VisoarAgExplorer) may not be available.${NC}"
    echo -e "${YELLOW}RGB DRONE and MapIR DRONE conversions may fail.${NC}"
    echo -e "${YELLOW}To fix: Clone VisoarAgExplorer and add to PYTHONPATH${NC}"
    echo -e "${YELLOW}  export PYTHONPATH=\$PYTHONPATH:/path/to/VisoarAgExplorer${NC}"
fi

# Check if OpenVisus is available
if ! python3 -c "import OpenVisus" 2>/dev/null; then
    echo -e "${YELLOW}WARNING: OpenVisus not found. TIFF conversions may fail.${NC}"
    echo -e "${YELLOW}To fix: pip install OpenVisus==2.2.135${NC}"
fi

echo -e "${GREEN}Starting background service...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""
echo -e "${BLUE}Tip: In another terminal, run this to check the queue:${NC}"
echo -e "${BLUE}  cd $SCRIPT_DIR && python3 check_conversion_queue.py${NC}"
echo ""

# Run the background service
python3 SCLib_BackgroundService.py "$SETTINGS_FILE"

