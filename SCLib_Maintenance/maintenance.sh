#!/bin/bash

# ScientistCloud Maintenance Script
# This script helps maintain the job queue and prevent old spinning jobs

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
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

# Function to check if Docker services are running
check_services() {
    print_status "Checking Docker services..."
    
    if ! docker ps | grep -q scientistcloud_fastapi; then
        print_error "FastAPI service is not running!"
        return 1
    fi
    
    print_success "Docker services are running"
    return 0
}

# Function to get the Docker directory path
get_docker_dir() {
    # Get the directory where this script is located
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    # Go up one level to scientistCloudLib, then into Docker
    echo "$(dirname "$SCRIPT_DIR")/Docker"
}

# Function to show job statistics
show_stats() {
    print_status "Getting job queue statistics..."
    docker exec scientistcloud_fastapi python /app/monitor_jobs.py stats
}

# Function to list queued jobs
list_queued() {
    local limit=${1:-10}
    print_status "Listing queued jobs (limit: $limit)..."
    docker exec scientistcloud_fastapi python /app/monitor_jobs.py list $limit
}

# Function to clean old queued jobs
clean_old_jobs() {
    local hours=${1:-1}
    print_status "Cleaning queued jobs older than $hours hour(s)..."
    docker exec scientistcloud_fastapi python /app/monitor_jobs.py clean $hours
}

# Function to check for stuck jobs
check_stuck_jobs() {
    print_status "Checking for stuck jobs..."
    
    # Get job stats
    local stats=$(docker exec scientistcloud_fastapi python /app/monitor_jobs.py stats 2>/dev/null | grep "Old queued jobs" | awk '{print $NF}')
    
    if [ "$stats" -gt 0 ]; then
        print_warning "Found $stats old queued jobs that may be stuck"
        return 1
    else
        print_success "No stuck jobs found"
        return 0
    fi
}

# Function to restart services if needed
restart_if_needed() {
    if ! check_services; then
        print_status "Restarting services..."
        DOCKER_DIR=$(get_docker_dir)
        cd "$DOCKER_DIR"
        ./start.sh down
        ./start.sh up --env-file docker.env
        print_success "Services restarted"
    fi
}

# Function to show help
show_help() {
    echo "ScientistCloud Maintenance Script"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  stats                    - Show job queue statistics"
    echo "  list [limit]             - List queued jobs (default: 10)"
    echo "  clean [hours]            - Clean old queued jobs (default: 1 hour)"
    echo "  check                    - Check for stuck jobs and restart if needed"
    echo "  restart                  - Restart Docker services"
    echo "  monitor                  - Continuous monitoring (every 30 seconds)"
    echo "  help                     - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 stats                 - Show current job statistics"
    echo "  $0 clean 2               - Clean jobs older than 2 hours"
    echo "  $0 check                 - Check for stuck jobs and auto-fix"
    echo "  $0 monitor               - Start continuous monitoring"
}

# Function for continuous monitoring
monitor() {
    print_status "Starting continuous monitoring (press Ctrl+C to stop)..."
    
    while true; do
        echo ""
        echo "=== $(date) ==="
        
        if check_stuck_jobs; then
            print_success "System is healthy"
        else
            print_warning "Stuck jobs detected, cleaning..."
            clean_old_jobs 1
        fi
        
        sleep 30
    done
}

# Main script logic
main() {
    case "${1:-help}" in
        "stats")
            check_services || exit 1
            show_stats
            ;;
        "list")
            check_services || exit 1
            list_queued "$2"
            ;;
        "clean")
            check_services || exit 1
            clean_old_jobs "$2"
            ;;
        "check")
            check_services || exit 1
            if ! check_stuck_jobs; then
                print_status "Cleaning stuck jobs..."
                clean_old_jobs 1
                print_status "Restarting services to clear any stuck state..."
                restart_if_needed
            fi
            ;;
        "restart")
            print_status "Restarting services..."
            DOCKER_DIR=$(get_docker_dir)
            cd "$DOCKER_DIR"
            ./start.sh down
            ./start.sh up --env-file docker.env
            print_success "Services restarted"
            ;;
        "monitor")
            check_services || exit 1
            monitor
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# Run main function with all arguments
main "$@"
