#!/bin/bash
# Automated Upload Test Runner for ScientistCloud2.0
# ===================================================
# 
# This script runs the automated upload tests with proper environment setup.
#
# Usage:
#   ./run_upload_tests.sh                    # Run all tests
#   ./run_upload_tests.sh --local-only       # Run only local upload tests
#   ./run_upload_tests.sh --remote-only      # Run only remote upload tests
#   ./run_upload_tests.sh --verbose           # Run with verbose output
#   ./run_upload_tests.sh --help             # Show help

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LIB_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Default options
TEST_TYPE="all"
VERBOSE=false
PYTEST_ARGS=""
UPLOAD_API_URL="${UPLOAD_API_URL:-http://localhost:5000}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --local-only)
            TEST_TYPE="local"
            shift
            ;;
        --remote-only)
            TEST_TYPE="remote"
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            PYTEST_ARGS="$PYTEST_ARGS -v"
            shift
            ;;
        --api-url)
            UPLOAD_API_URL="$2"
            shift 2
            ;;
        --help|-h)
            echo "Automated Upload Test Runner for ScientistCloud2.0"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --local-only      Run only local file upload tests"
            echo "  --remote-only      Run only remote link upload tests"
            echo "  --verbose, -v     Run with verbose output"
            echo "  --api-url URL     Set upload API URL (default: http://localhost:5000)"
            echo "  --help, -h        Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  UPLOAD_API_URL    Upload API base URL (default: http://localhost:5000)"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${YELLOW}Warning: pytest not found. Installing...${NC}"
    pip install pytest
fi

# Set environment variables
export UPLOAD_API_URL="$UPLOAD_API_URL"

# Validate test configuration
echo -e "${BLUE}Validating test configuration...${NC}"
python3 "$SCRIPT_DIR/test_upload_config.py" || {
    echo -e "${YELLOW}Warning: Some test files may be missing${NC}"
    echo "Tests will skip missing files automatically"
}

# Print test information
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Automated Upload Test Suite${NC}"
echo -e "${BLUE}(ScientistCloud2.0)${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Library: ${GREEN}$LIB_DIR${NC}"
echo -e "Upload API: ${GREEN}$UPLOAD_API_URL${NC}"
echo -e "Test Type: ${GREEN}$TEST_TYPE${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Build pytest command
PYTEST_CMD="pytest $SCRIPT_DIR/test_upload_automated.py"

if [ "$TEST_TYPE" == "local" ]; then
    PYTEST_CMD="$PYTEST_CMD::TestLocalUploads"
elif [ "$TEST_TYPE" == "remote" ]; then
    PYTEST_CMD="$PYTEST_CMD::TestRemoteUploads"
fi

PYTEST_CMD="$PYTEST_CMD $PYTEST_ARGS"

# Run tests
echo -e "${BLUE}Running tests...${NC}"
echo ""

cd "$SCRIPT_DIR"
eval $PYTEST_CMD

TEST_EXIT_CODE=$?

echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}All tests passed!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}Some tests failed${NC}"
    echo -e "${RED}========================================${NC}"
fi

exit $TEST_EXIT_CODE

