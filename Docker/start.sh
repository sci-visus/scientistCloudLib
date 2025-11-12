#!/bin/bash

# ScientistCloud Docker Startup Script
# This script allows you to specify different environment files for different deployments

set -e

# Default values
ENV_FILE=""
COMPOSE_FILE="docker-compose.yml"
SERVICES=""
FORCE_CLEAN=true
REBUILD_BASE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "ScientistCloud Docker Management Script"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  up          Start all services"
    echo "  down        Stop all services"
    echo "  restart     Restart all services"
    echo "  logs        Show logs for all services"
    echo "  status      Show status of all services"
    echo "  build       Build the FastAPI service"
    echo "  clean       Remove all containers and volumes"
    echo ""
    echo "Options:"
    echo "  --env-file FILE     Use specific environment file (optional if .env exists)"
    echo "  --services SERVICE  Start only specific services (comma-separated)"
    echo "  --force             Force clean without confirmation prompt"
    echo "  --rebuild-base      Rebuild background service base image from scratch"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 up                                    # Use existing .env file"
    echo "  $0 up --env-file env.local              # Use specific env file"
    echo "  $0 up --env-file env.production         # Use production env file"
    echo "  $0 up --services mongodb,fastapi        # Start specific services"
    echo "  $0 up --rebuild-base                    # Rebuild base image from scratch"
    echo "  $0 build --rebuild-base                 # Rebuild base image and services"
    echo "  $0 logs                                 # Use existing .env file"
    echo "  $0 clean                                # No env file needed"
    echo "  $0 clean --force                        # Force clean without confirmation"
    echo "  $0 down                                 # No env file needed"
    echo "  $0 status                               # No env file needed"
    echo ""
    echo "Environment files:"
    echo "  - Commands requiring env files: up, build, restart, logs"
    echo "  - Commands NOT requiring env files: clean, down, status"
    echo "  - If .env exists, it will be used automatically"
    echo "  - Use --env-file to specify a different environment file"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --services)
            SERVICES="$2"
            shift 2
            ;;
        --force)
            FORCE_CLEAN=true
            shift
            ;;
        --rebuild-base)
            REBUILD_BASE=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        up|down|restart|logs|status|build|clean)
            COMMAND="$1"
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Check if command is provided
if [ -z "$COMMAND" ]; then
    print_error "No command provided"
    show_usage
    exit 1
fi

# Commands that don't require environment files
NO_ENV_COMMANDS=("clean" "down" "status")

# Check if this command needs an environment file
NEEDS_ENV=true
for cmd in "${NO_ENV_COMMANDS[@]}"; do
    if [ "$COMMAND" = "$cmd" ]; then
        NEEDS_ENV=false
        break
    fi
done

# Handle environment file logic
if [ "$NEEDS_ENV" = true ]; then
    # Commands that need environment files (up, build, restart, logs)
    if [ -z "$ENV_FILE" ]; then
        # No env file specified - check if .env exists
        if [ -f ".env" ]; then
            print_info "Using existing .env file"
            ENV_FILE=".env"
        else
            print_error "No environment file provided and no .env file found"
            print_info "You must either:"
            print_info "  1. Provide an environment file using --env-file"
            print_info "  2. Have a .env file in the current directory"
            show_usage
            exit 1
        fi
    else
        # Env file specified - check if it exists
        if [ ! -f "$ENV_FILE" ]; then
            print_error "Environment file not found: $ENV_FILE"
            print_info "Please specify a valid environment file using --env-file"
            print_info "Example: $0 up --env-file /path/to/your/env.file"
            exit 1
        fi
        
        print_info "Using environment file: $ENV_FILE"
        
        # Copy the environment file to .env for Docker Compose to use (only if .env doesn't exist)
        if [ ! -f ".env" ]; then
            print_info "Copying $ENV_FILE to .env for Docker Compose..."
            cp "$ENV_FILE" .env
            print_success "Environment file prepared: .env"
        else
            print_info "Using existing .env file (ignoring --env-file)"
        fi
    fi
else
    # Commands that don't need environment files
    print_info "Command '$COMMAND' does not require environment file"
fi

# Keep the original MongoDB URL (cloud or local)
print_info "Using MongoDB URL as provided in environment file"

# Build docker-compose command (Docker Compose will automatically use .env file)
COMPOSE_CMD="docker-compose -f $COMPOSE_FILE"

# Add services if specified
if [ -n "$SERVICES" ]; then
    COMPOSE_CMD="$COMPOSE_CMD $SERVICES"
fi

# Function to check if base image exists
check_base_image_exists() {
    docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^sclib_background_service_base:latest$"
}

# Function to check if base image Dockerfile is newer than the image
check_base_image_needs_rebuild() {
    local dockerfile_path="SCLib_JobProcessing/Docker/Dockerfile.background-service-base"
    local requirements_path="SCLib_JobProcessing/requirements_conversion.txt"
    
    if ! check_base_image_exists; then
        return 0  # Needs build if image doesn't exist
    fi
    
    # Get image creation time (ISO 8601 format)
    local image_time=$(docker inspect -f '{{ .Created }}' sclib_background_service_base:latest 2>/dev/null || echo "")
    if [ -z "$image_time" ]; then
        return 0  # Needs build if we can't get image time
    fi
    
    # Convert image time to Unix timestamp (handle both Linux and macOS)
    local image_timestamp
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS uses BSD date
        image_timestamp=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${image_time%.*}" +%s 2>/dev/null || echo "0")
    else
        # Linux uses GNU date
        image_timestamp=$(date -d "$image_time" +%s 2>/dev/null || echo "0")
    fi
    
    # Check if Dockerfile or requirements files are newer
    # Use stat with platform-specific flags
    if [ -f "$dockerfile_path" ]; then
        local dockerfile_timestamp
        if [[ "$OSTYPE" == "darwin"* ]]; then
            dockerfile_timestamp=$(stat -f %m "$dockerfile_path" 2>/dev/null || echo "0")
        else
            dockerfile_timestamp=$(stat -c %Y "$dockerfile_path" 2>/dev/null || echo "0")
        fi
        if [ "$dockerfile_timestamp" -gt "$image_timestamp" ]; then
            return 0  # Dockerfile is newer, needs rebuild
        fi
    fi
    
    if [ -f "$requirements_path" ]; then
        local req_timestamp
        if [[ "$OSTYPE" == "darwin"* ]]; then
            req_timestamp=$(stat -f %m "$requirements_path" 2>/dev/null || echo "0")
        else
            req_timestamp=$(stat -c %Y "$requirements_path" 2>/dev/null || echo "0")
        fi
        if [ "$req_timestamp" -gt "$image_timestamp" ]; then
            return 0  # Requirements file is newer, needs rebuild
        fi
    fi
    
    return 1  # No rebuild needed
}

# Function to build base image
build_base_image() {
    local rebuild_flag=$1
    local base_image_name="sclib_background_service_base:latest"
    
    if [ "$rebuild_flag" = true ]; then
        print_info "Rebuilding background service base image from scratch (this may take a while - OpenVisus is large)..."
        docker-compose -f $COMPOSE_FILE --profile base-images build --no-cache background-service-base
        print_success "Base image rebuilt successfully"
    elif check_base_image_needs_rebuild; then
        print_info "Base image Dockerfile or requirements have changed, rebuilding base image (this may take a while - OpenVisus is large)..."
        docker-compose -f $COMPOSE_FILE --profile base-images build --no-cache background-service-base
        print_success "Base image rebuilt successfully"
    elif check_base_image_exists; then
        print_info "Base image exists and is up to date, skipping build (use --rebuild-base to force rebuild)"
    else
        print_info "Base image not found, building it now (this may take a while - OpenVisus is large)..."
        docker-compose -f $COMPOSE_FILE --profile base-images build background-service-base
        print_success "Base image built successfully"
    fi
}

# Execute commands
case $COMMAND in
    up)
        print_info "Starting ScientistCloud services..."
        print_info "Environment: $ENV_FILE"
        print_info "Services: ${SERVICES:-all}"
        
        # Build base image if needed (automatically detects if Dockerfile changed)
        build_base_image $REBUILD_BASE
        
        # Build the services first (build individually to avoid one failure canceling others)
        print_info "Building services..."
        print_info "Building auth service..."
        $COMPOSE_CMD build --no-cache auth || print_warning "Auth build failed, continuing..."
        
        print_info "Building fastapi service..."
        $COMPOSE_CMD build --no-cache fastapi || print_warning "FastAPI build failed, continuing..."
        
        print_info "Building background-service (depends on base image)..."
        $COMPOSE_CMD build --no-cache background-service || print_warning "Background service build failed, continuing..."
        
        # Start services
        $COMPOSE_CMD up -d
        
        print_success "Services started successfully!"
        print_info "Authentication API: http://localhost:8001"
        print_info "Auth API Documentation: http://localhost:8001/docs"
        print_info "FastAPI API: http://localhost:5001"
        print_info "API Documentation: http://localhost:5001/docs"
        print_info "Background Service: Processing datasets with 'conversion queued' status"
        print_info "MongoDB: localhost:27017"
        print_info "Redis: localhost:6379"
        print_info "Nginx: http://localhost (if enabled)"
        print_info "Note: If you modified conversion dependencies, the base image was automatically rebuilt"
        ;;
        
    down)
        print_info "Stopping ScientistCloud services..."
        $COMPOSE_CMD down auth fastapi background-service redis
        # Clean up the .env file
        if [ -f ".env" ]; then
            rm -f .env
            print_info "Cleaned up .env file"
        fi
        print_success "SCLib services stopped successfully!"
        ;;
        
    restart)
        print_info "Restarting ScientistCloud services..."
        $COMPOSE_CMD restart auth fastapi background-service redis
        print_success "SCLib services restarted successfully!"
        ;;
        
    logs)
        print_info "Showing logs for ScientistCloud services..."
        $COMPOSE_CMD logs -f auth fastapi background-service redis
        ;;
        
    status)
        print_info "Status of ScientistCloud services:"
        $COMPOSE_CMD ps auth fastapi background-service redis
        ;;
        
    build)
        print_info "Building services..."
        
        # Build base image if needed (automatically detects if Dockerfile changed)
        build_base_image $REBUILD_BASE
        
        # Build main services
        # Build services individually to avoid one failure canceling others
        print_info "Building auth service..."
        $COMPOSE_CMD build --no-cache auth || print_warning "Auth build failed, continuing..."
        
        print_info "Building fastapi service..."
        $COMPOSE_CMD build --no-cache fastapi || print_warning "FastAPI build failed, continuing..."
        
        print_info "Building background-service (depends on base image)..."
        $COMPOSE_CMD build --no-cache background-service || print_warning "Background service build failed, continuing..."
        
        print_success "Build completed!"
        print_info "Note: If you modified conversion dependencies, the base image was automatically rebuilt"
        ;;
        
    clean)
        if [ "$FORCE_CLEAN" = true ]; then
            print_info "Force cleaning SCLib Docker resources..."
        else
            print_warning "This will remove SCLib containers and volumes. Are you sure? (y/N)"
            read -r response
            if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
                print_info "Cleanup cancelled."
                exit 0
            fi
        fi
        
        print_info "Cleaning up SCLib Docker resources..."
        # Stop and remove only SCLib containers
        $COMPOSE_CMD stop auth fastapi background-service redis
        $COMPOSE_CMD rm -f auth fastapi background-service redis
        # Remove only SCLib volumes (not all volumes)
        docker volume rm docker_fastapi_logs docker_auth_logs docker_bg_service_logs docker_redis_data 2>/dev/null || true
        
        # Optionally remove base image if requested
        if [ "$REBUILD_BASE" = true ]; then
            print_info "Removing base image..."
            docker rmi sclib_background_service_base:latest 2>/dev/null || print_warning "Base image not found or already removed"
        fi
        
        print_success "SCLib cleanup completed!"
        ;;
        
    *)
        print_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac
