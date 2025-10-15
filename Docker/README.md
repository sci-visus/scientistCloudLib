# ScientistCloud Docker Setup

This directory contains Docker Compose configuration for running ScientistCloud services in containers. The setup is designed to be flexible and support different environments (development, staging, production) through different environment files.

## Services

The Docker Compose setup includes:

- **MongoDB** - Database service (port 27017)
- **FastAPI** - Python API service (port 5000)
- **Nginx** - Reverse proxy (ports 80, 443) - Optional
- **Redis** - Background task queue (port 6379) - Optional

## Quick Start

### 1. Set up your environment file

```bash
# Copy your existing environment file
./setup-env.sh copy ../SCLib_TryTest/env.local env.local

# Or create a new one
./setup-env.sh create env.development
```

### 2. Start the services

```bash
# Start with your environment file (copies to .env automatically)
./start.sh up --env-file env.local

# Or use your existing env.local directly
./start.sh up --env-file ../SCLib_TryTest/env.local

# Docker Compose automatically uses the .env file created by the script
```

### 3. Access the services

- **FastAPI API**: http://localhost:5001
- **API Documentation**: http://localhost:5001/docs
- **MongoDB**: localhost:27017
- **Redis**: localhost:6379
- **Nginx** (if enabled): http://localhost

## Environment Files

The system supports multiple environment files for different deployments:

- `env.local` - Local development
- `env.development` - Development server
- `env.staging` - Staging server
- `env.production` - Production server
- `docker.env` - Default Docker configuration

### How It Works

The Docker setup uses Docker Compose's automatic `.env` file loading mechanism:

1. **You specify your environment file**: `./start.sh up --env-file env.local`
2. **Script copies it to `.env`**: The start script copies your chosen environment file to `.env` in the Docker directory
3. **Docker Compose loads `.env`**: Docker Compose automatically loads the `.env` file without needing explicit `--env-file` flags
4. **Automatic cleanup**: When you stop services, the `.env` file is automatically removed

This approach is cleaner and follows Docker Compose best practices while still allowing flexible environment file management.

### Environment File Management

```bash
# List available environment files
./setup-env.sh list

# Copy environment file from SCLib_TryTest
./setup-env.sh copy ../SCLib_TryTest/env.local env.local

# Create new environment file
./setup-env.sh create env.production

# Validate environment file
./setup-env.sh validate env.local
```

## Usage Examples

### Development

```bash
# Start with local environment (copies env.local to .env automatically)
./start.sh up --env-file env.local

# Use your existing env.local directly
./start.sh up --env-file ../SCLib_TryTest/env.local

# Start only specific services
./start.sh up --env-file env.local --services mongodb,fastapi

# View logs
./start.sh logs --env-file env.local
```

### Production

```bash
# Start with production environment
./start.sh up --env-file env.production

# Check status
./start.sh status --env-file env.production
```

### Management Commands

```bash
# Stop services
./start.sh down --env-file env.local

# Restart services
./start.sh restart --env-file env.local

# Build FastAPI service
./start.sh build --env-file env.local

# Clean up (removes containers and volumes)
./start.sh clean --env-file env.local
```

## Environment Variables

Key environment variables that should be configured in your environment files:

### Database
- `MONGO_URL` - MongoDB connection string
- `DB_NAME` - Database name
- `DB_USER` - Database username
- `DB_PASS` - Database password

### Authentication
- `AUTH0_DOMAIN` - Auth0 domain
- `AUTHO_CLIENT_ID` - Auth0 client ID
- `AUTHO_CLIENT_SECRET` - Auth0 client secret
- `SECRET_KEY` - Application secret key

### File Processing
- `VISUS_DATASETS` - Path to dataset storage
- `JOB_CHUNK_SIZE` - File chunk size for uploads
- `MAX_FILE_SIZE` - Maximum file size allowed

### API Configuration
- `FASTAPI_HOST` - FastAPI host (default: 0.0.0.0)
- `FASTAPI_PORT` - FastAPI port (default: 5000)
- `FASTAPI_WORKERS` - Number of workers (default: 1)

## Docker Compose Override

You can create a `docker-compose.override.yml` file to customize the configuration for your specific environment:

```yaml
version: '3.8'
services:
  fastapi:
    environment:
      - FASTAPI_LOG_LEVEL=debug
    volumes:
      - ./custom-config:/app/config
```

## Troubleshooting

### Common Issues

1. **Port conflicts**: Make sure ports 27017, 5000, 80, 443, and 6379 are not in use
2. **Permission issues**: Ensure Docker has permission to access your data directories
3. **Environment variables**: Validate your environment file with `./setup-env.sh validate`

### Logs

```bash
# View all logs
./start.sh logs --env-file env.local

# View specific service logs
docker-compose --env-file env.local logs fastapi
docker-compose --env-file env.local logs mongodb
```

### Health Checks

The services include health checks. You can check the status:

```bash
# Check service status
./start.sh status --env-file env.local

# Check health directly
curl http://localhost:5000/health
```

## Development

### Building the FastAPI Service

```bash
# Build the service
./start.sh build --env-file env.local

# Rebuild with no cache
docker-compose --env-file env.local build --no-cache fastapi
```

### Adding New Services

To add new services, edit `docker-compose.yml` and add your service definition. Make sure to:

1. Add the service to the `scientistcloud_network`
2. Configure appropriate environment variables
3. Add health checks if needed
4. Update the startup script if necessary

## Security Notes

- Never commit environment files with sensitive data to version control
- Use Docker secrets for production deployments
- Regularly rotate API keys and passwords
- Keep Docker images updated

## Support

For issues or questions:

1. Check the logs: `./start.sh logs --env-file env.local`
2. Validate your environment: `./setup-env.sh validate env.local`
3. Check service status: `./start.sh status --env-file env.local`
4. Review the main ScientistCloud documentation in `../SCLib_JobProcessing/README.md`
