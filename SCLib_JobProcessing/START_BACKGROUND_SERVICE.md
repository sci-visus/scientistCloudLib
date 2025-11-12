# How to Start the Background Service

The background service processes datasets with `status: 'conversion queued'` directly from the `visstoredatas` collection.

## Check if Background Service is Running

```bash
# Check if the service is running in the FastAPI container
docker exec sclib_fastapi ps aux | grep BackgroundService

# Or check Docker logs
docker logs sclib_fastapi | grep -i "background\|conversion\|processing"
```

## Start the Background Service

### Option 1: Use Docker Container (Recommended)

A dedicated Docker container is available for the background service. It's already configured in `docker-compose.yml`.

**Start the container:**
```bash
cd /path/to/ScientistCloud2.0/scientistCloudLib/Docker
docker-compose up -d background-service
```

**Check if it's running:**
```bash
docker ps | grep background-service
docker logs sclib_background_service
```

**Rebuild if needed:**
```bash
docker-compose build background-service
docker-compose up -d background-service
```

### Option 2: Run in FastAPI Container (Temporary/Testing)

```bash
# Get into the container
docker exec -it sclib_fastapi /bin/bash

# Create a minimal settings file
cat > /tmp/bg_service_settings.json <<EOF
{
  "db_name": "scientistcloud"
}
EOF

# Start the background service
cd /app/scientistCloudLib/SCLib_JobProcessing
python3 SCLib_BackgroundService.py /tmp/bg_service_settings.json
```

## Verify It's Working

1. **Check logs** - You should see:
   ```
   Starting SC_BackgroundService worker sc_worker_...
   Processing conversion for dataset <uuid>...
   ```

2. **Check dataset status** - The status should change:
   - `conversion queued` → `converting` → `done`

3. **Check converted directory** - After processing, files should appear in:
   ```
   /mnt/visus_datasets/converted/<dataset_uuid>/
   ```

## Troubleshooting

### No datasets being processed

1. Check if there are datasets with `status: 'conversion queued'`:
   ```bash
   # In MongoDB
   db.visstoredatas.find({status: "conversion queued"})
   ```

2. Check background service logs for errors

3. Verify paths are correct:
   - Input: `/mnt/visus_datasets/upload/<dataset_uuid>/`
   - Output: `/mnt/visus_datasets/converted/<dataset_uuid>/`

### Background service not starting

1. Check MongoDB connection:
   ```bash
   docker exec sclib_fastapi python3 -c "from SCLib_MongoConnection import get_mongo_connection; print(get_mongo_connection())"
   ```

2. Check environment variables:
   ```bash
   docker exec sclib_fastapi env | grep MONGO
   ```

## Architecture Notes

- **No jobs collection needed** - The service queries `visstoredatas` directly by status
- **Status-based processing** - Finds datasets with `status: 'conversion queued'`
- **UUID-based** - All processing uses `dataset_uuid`, not user email
- **Direct updates** - Updates dataset status in place: `conversion queued` → `converting` → `done`

