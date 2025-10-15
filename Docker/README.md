# ScientistCloud Docker Setup

This directory contains Docker configuration for the ScientistCloud services.

## Quick Start

1. **Copy the environment template:**
   ```bash
   cp docker.env.template docker.env
   ```

2. **Edit docker.env with your actual values:**
   - Replace all `your_*_here` placeholders with your actual credentials
   - Update database passwords, API keys, and other secrets

3. **Start the services:**
   ```bash
   ./start.sh up --env-file docker.env
   ```

## Environment Files

- `docker.env.template` - Template with placeholder values (safe to commit)
- `docker.env` - Your actual environment file with secrets (DO NOT COMMIT)

## Security Notes

- **Never commit `docker.env`** - it contains sensitive information
- The `.gitignore` file is configured to exclude environment files
- Use the template file to create your local environment configuration
- Rotate any exposed secrets immediately

## Available Commands

```bash
# Start services
./start.sh up --env-file docker.env

# Stop services  
./start.sh down

# View logs
./start.sh logs

# Check status
./start.sh status

# Build FastAPI service
./start.sh build
```

## Services

- **FastAPI**: http://localhost:5001
- **API Docs**: http://localhost:5001/docs
- **Redis**: localhost:6379
- **MongoDB**: Uses cloud connection (configured in docker.env)

## Troubleshooting

If you encounter permission issues with file uploads, ensure the `VISUS_DATASETS` directory exists and has proper permissions:

```bash
sudo mkdir -p /Users/amygooch/GIT/VisStoreDataTemp
sudo chown -R $USER:$USER /Users/amygooch/GIT/VisStoreDataTemp
```