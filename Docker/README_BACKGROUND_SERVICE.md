# SCLib Background Service Docker Container

## Overview

The background service container processes datasets with `status: 'conversion queued'` directly from the `visstoredatas` MongoDB collection. It queries for datasets that need conversion and processes them automatically.

## Architecture

- **No jobs collection needed** - Dataset status in `visstoredatas` is the source of truth
- **Status-based processing** - Queries `visstoredatas.find({'status': 'conversion queued'})`
- **UUID-based** - All processing uses `dataset_uuid`, not user email
- **Direct updates** - Updates dataset status: `conversion queued` → `converting` → `done`

## Base Image

The background service uses a **two-stage build** with a base image:

1. **`Dockerfile.background-service-base`** - Base image containing:
   - System dependencies (build tools, libraries)
   - Python dependencies (from requirements files)
   - **OpenVisus** (large package, cached in base image)

2. **`Dockerfile.background-service`** - Final image that:
   - Uses the base image
   - Adds startup script
   - Adds application-specific configuration

### Why a Base Image?

- **Faster builds**: OpenVisus and heavy dependencies are cached in the base image
- **Consistency**: Same base across all builds
- **Efficiency**: Only rebuild base image when dependencies change

## Building

### Build Base Image First

```bash
cd /path/to/ScientistCloud2.0/scientistCloudLib/Docker

# Build base image (this takes a while - OpenVisus is large)
docker-compose --profile base-images build background-service-base

# Then build the main service
docker-compose build background-service
```

### Build Everything

```bash
# The start.sh script handles base image building automatically
./start.sh build
```

Or manually:

```bash
# Build base image
docker-compose --profile base-images build background-service-base

# Build and start all services
docker-compose build background-service
docker-compose up -d background-service
```

## Running

### Start the Container

```bash
docker-compose up -d background-service
```

### Check Status

```bash
# Check if container is running
docker ps | grep background-service

# Check logs
docker logs sclib_background_service

# Follow logs in real-time
docker logs -f sclib_background_service
```

### Stop the Container

```bash
docker-compose stop background-service
```

## Configuration

The container uses environment variables from `.env` file (loaded automatically by docker-compose):

- `MONGO_URL` - MongoDB connection string
- `DB_NAME` - Database name (default: `scientistcloud`)
- `VISUS_DATASETS` - Path to datasets directory (mounted as volume)
- `JOB_IN_DATA_DIR` - Input directory for conversions (default: `/mnt/visus_datasets/upload`)
- `JOB_OUT_DATA_DIR` - Output directory for conversions (default: `/mnt/visus_datasets/converted`)

## Volumes

- `/app/scientistCloudLib` - SCLib code (mounted from host)
- `/mnt/visus_datasets` - Datasets directory (shared with FastAPI container)
- `/app/logs` - Service logs (Docker volume)

## Health Check

The container includes a health check that verifies the background service process is running:

```bash
# Check health status
docker inspect sclib_background_service | grep -A 10 Health
```

## Troubleshooting

### Container won't start

1. Check logs:
   ```bash
   docker logs sclib_background_service
   ```

2. Verify MongoDB connection:
   ```bash
   docker exec sclib_background_service python3 -c "from SCLib_MongoConnection import get_mongo_connection; print(get_mongo_connection())"
   ```

3. Check environment variables:
   ```bash
   docker exec sclib_background_service env | grep MONGO
   ```

### No datasets being processed

1. Check if there are datasets with `status: 'conversion queued'`:
   ```bash
   # In MongoDB shell or via Python
   db.visstoredatas.find({status: "conversion queued"})
   ```

2. Check service logs for errors:
   ```bash
   docker logs sclib_background_service | grep -i error
   ```

3. Verify paths are accessible:
   ```bash
   docker exec sclib_background_service ls -la /mnt/visus_datasets/upload
   docker exec sclib_background_service ls -la /mnt/visus_datasets/converted
   ```

### Service keeps restarting

1. Check logs for fatal errors:
   ```bash
   docker logs sclib_background_service --tail 100
   ```

2. Verify MongoDB is accessible:
   ```bash
   docker exec sclib_background_service python3 -c "import pymongo; client = pymongo.MongoClient('$MONGO_URL'); print(client.server_info())"
   ```

### OpenVisus not found

If you see `ModuleNotFoundError: No module named 'OpenVisus'`:

1. Rebuild the base image:
   ```bash
   docker-compose --profile base-images build --no-cache background-service-base
   ```

2. Then rebuild the main service:
   ```bash
   docker-compose build --no-cache background-service
   ```

## Integration with Docker Compose

The background service is automatically started when you run:

```bash
docker-compose up -d
```

It depends on the `fastapi` service, so FastAPI will start first.

## Monitoring

### View Real-time Logs

```bash
docker logs -f sclib_background_service
```

### Check Processing Activity

Look for these log messages:
- `Processing conversion for dataset <uuid>...`
- `✅ Dataset <uuid> conversion completed successfully`
- `❌ Dataset <uuid> conversion failed: <error>`

### Check Dataset Status Changes

Query MongoDB to see status transitions:
```javascript
// In MongoDB shell
db.visstoredatas.find({status: {$in: ["conversion queued", "converting"]}})
```

## Comparison with Old Background Service

The new background service is simpler than the old one:

| Feature | Old Service | New Service |
|---------|------------|-------------|
| Job Collection | Uses `jobs` collection | No jobs collection needed |
| Processing | Processes jobs from queue | Queries datasets by status |
| Architecture | Job-based | Status-based |
| Complexity | Higher (job creation, tracking) | Lower (direct status updates) |
| Base Image | Yes (visstore-ag-explorer-bg-service-base) | Yes (sclib_background_service_base) |

## Files

- `Dockerfile.background-service-base` - Base image definition (OpenVisus, dependencies)
- `Dockerfile.background-service` - Final service image (uses base image)
- `start_background_service.sh` - Startup script
- `docker-compose.yml` - Service configuration
