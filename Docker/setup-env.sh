#!/bin/bash

# Environment Setup Script for ScientistCloud Docker
# This script helps you set up environment files for different deployments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

show_usage() {
    echo "Environment Setup Script for ScientistCloud Docker"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  copy SOURCE TARGET    Copy environment file from source to target"
    echo "  list                 List available environment files"
    echo "  create TARGET        Create a new environment file based on template"
    echo "  validate FILE        Validate an environment file"
    echo ""
    echo "Examples:"
    echo "  $0 copy ../SCLib_TryTest/env.local env.local"
    echo "  $0 copy ../SCLib_TryTest/env.production env.production"
    echo "  $0 list"
    echo "  $0 create env.development"
    echo "  $0 validate env.local"
}

# Function to list available environment files
list_env_files() {
    print_info "Available environment files:"
    echo ""
    
    # Check current directory
    echo "Current directory:"
    ls -la *.env 2>/dev/null || echo "  No .env files found"
    echo ""
    
    # Check SCLib_TryTest directory
    if [ -d "../SCLib_TryTest" ]; then
        echo "SCLib_TryTest directory:"
        ls -la ../SCLib_TryTest/env.* 2>/dev/null || echo "  No env.* files found"
        echo ""
    fi
    
    # Check other common locations
    if [ -d "../../SCLib_TryTest" ]; then
        echo "Alternative SCLib_TryTest directory:"
        ls -la ../../SCLib_TryTest/env.* 2>/dev/null || echo "  No env.* files found"
        echo ""
    fi
}

# Function to copy environment file
copy_env_file() {
    local source="$1"
    local target="$2"
    
    if [ -z "$source" ] || [ -z "$target" ]; then
        print_error "Both source and target must be specified"
        return 1
    fi
    
    # Check if source exists
    if [ ! -f "$source" ]; then
        print_error "Source file not found: $source"
        return 1
    fi
    
    # Create backup if target exists
    if [ -f "$target" ]; then
        print_warning "Target file exists. Creating backup..."
        cp "$target" "${target}.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Copy the file
    cp "$source" "$target"
    
    # Modify for Docker if needed
    if grep -q "mongodb+srv://" "$target"; then
        print_info "Converting MongoDB URL for Docker..."
        sed -i.bak 's|mongodb+srv://[^@]*@[^/]*/|mongodb://admin:your_db_password@mongodb:27017/|g' "$target"
        sed -i.bak 's|?retryWrites=true.*||g' "$target"
        sed -i.bak 's|mongodb://admin:your_db_password@mongodb:27017/|mongodb://admin:your_db_password@mongodb:27017/|g' "$target"
        echo "?authSource=admin" >> "$target"
        rm -f "${target}.bak"
    fi
    
    print_success "Environment file copied: $source -> $target"
}

# Function to create new environment file
create_env_file() {
    local target="$1"
    
    if [ -z "$target" ]; then
        print_error "Target file name must be specified"
        return 1
    fi
    
    # Use docker.env as template
    if [ -f "docker.env" ]; then
        cp "docker.env" "$target"
        print_success "Created new environment file: $target"
        print_info "Please edit the file to customize for your environment"
    else
        print_error "Template file docker.env not found"
        return 1
    fi
}

# Function to validate environment file
validate_env_file() {
    local file="$1"
    
    if [ -z "$file" ]; then
        print_error "File name must be specified"
        return 1
    fi
    
    if [ ! -f "$file" ]; then
        print_error "File not found: $file"
        return 1
    fi
    
    print_info "Validating environment file: $file"
    
    # Check for required variables
    required_vars=(
        "MONGO_URL"
        "DB_NAME"
        "AUTH0_DOMAIN"
        "AUTHO_CLIENT_ID"
        "AUTHO_CLIENT_SECRET"
        "SECRET_KEY"
    )
    
    missing_vars=()
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "$file"; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -eq 0 ]; then
        print_success "All required variables are present"
    else
        print_warning "Missing required variables: ${missing_vars[*]}"
    fi
    
    # Check for Docker-specific settings
    if grep -q "mongodb://.*:27017" "$file"; then
        print_success "MongoDB URL appears to be configured for Docker"
    else
        print_warning "MongoDB URL may not be configured for Docker"
    fi
}

# Parse command line arguments
case "${1:-}" in
    copy)
        copy_env_file "$2" "$3"
        ;;
    list)
        list_env_files
        ;;
    create)
        create_env_file "$2"
        ;;
    validate)
        validate_env_file "$2"
        ;;
    --help|help)
        show_usage
        ;;
    *)
        print_error "Unknown command: ${1:-}"
        show_usage
        exit 1
        ;;
esac
