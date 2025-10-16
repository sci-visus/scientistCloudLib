#!/bin/bash

# ScientistCloud Docker Startup Script
# This script allows you to specify different environment files for different deployments

set -e

# Default values
ENV_FILE=""
COMPOSE_FILE="docker-compose.yml"
SERVICES=""

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
    echo "  --env-file FILE     Use specific environment file (required)"
    echo "  --services SERVICE  Start only specific services (comma-separated)"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 up --env-file env.local"
    echo "  $0 up --env-file env.production"
    echo "  $0 up --env-file ../../SCLib_TryTest/env.local"
    echo "  $0 up --services mongodb,fastapi"
    echo "  $0 logs --env-file env.local"
    echo ""
    echo "Environment files:"
    echo "  - You must provide a valid environment file using --env-file"
    echo "  - Common names: env.local, env.production, env.development"
    echo "  - The file must exist and be accessible from the current directory"
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

# Check if environment file is provided
if [ -z "$ENV_FILE" ]; then
    print_error "No environment file provided"
    print_info "You must specify an environment file using --env-file"
    show_usage
    exit 1
fi

# Check if environment file exists
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
    print_info "Using existing .env file"
fi

# Keep the original MongoDB URL (cloud or local)
print_info "Using MongoDB URL as provided in environment file"

# Build docker-compose command (Docker Compose will automatically use .env file)
COMPOSE_CMD="docker-compose -f $COMPOSE_FILE"

# Add services if specified
if [ -n "$SERVICES" ]; then
    COMPOSE_CMD="$COMPOSE_CMD $SERVICES"
fi

# Execute commands
case $COMMAND in
    up)
        print_info "Starting ScientistCloud services..."
        print_info "Environment: $ENV_FILE"
        print_info "Services: ${SERVICES:-all}"
        
        # Build the services first
        print_info "Building services..."
        $COMPOSE_CMD build --no-cache auth fastapi
        
        # Start services
        $COMPOSE_CMD up -d
        
        print_success "Services started successfully!"
        print_info "Authentication API: http://localhost:8001"
        print_info "Auth API Documentation: http://localhost:8001/docs"
        print_info "FastAPI API: http://localhost:5001"
        print_info "API Documentation: http://localhost:5001/docs"
        print_info "MongoDB: localhost:27017"
        print_info "Redis: localhost:6379"
        print_info "Nginx: http://localhost (if enabled)"
        ;;
        
    down)
        print_info "Stopping ScientistCloud services..."
        $COMPOSE_CMD down
        # Clean up the .env file
        if [ -f ".env" ]; then
            rm -f .env
            print_info "Cleaned up .env file"
        fi
        print_success "Services stopped successfully!"
        ;;
        
    restart)
        print_info "Restarting ScientistCloud services..."
        $COMPOSE_CMD restart
        print_success "Services restarted successfully!"
        ;;
        
    logs)
        print_info "Showing logs for ScientistCloud services..."
        $COMPOSE_CMD logs -f
        ;;
        
    status)
        print_info "Status of ScientistCloud services:"
        $COMPOSE_CMD ps
        ;;
        
    build)
        print_info "Building services..."
        $COMPOSE_CMD build --no-cache auth fastapi
        print_success "Build completed!"
        ;;
        
    clean)
        print_warning "This will remove all containers and volumes. Are you sure? (y/N)"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            print_info "Cleaning up Docker resources..."
            $COMPOSE_CMD down -v --remove-orphans
            docker system prune -f
            print_success "Cleanup completed!"
        else
            print_info "Cleanup cancelled."
        fi
        ;;
        
    *)
        print_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac
