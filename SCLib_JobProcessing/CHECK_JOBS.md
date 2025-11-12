# How to Check and Manage Conversion Jobs

## Quick Check Commands

### 1. Check Job Queue Statistics

```bash
# From the FastAPI container
docker exec -it sclib_fastapi python3 /app/SCLib_JobProcessing/monitor_jobs.py stats
```

This shows:
- Total jobs in queue
- Jobs by status (queued, processing, completed, failed)
- Recent jobs (last 24 hours)
- Old queued jobs (>1 hour)

### 2. List Queued Conversion Jobs

```bash
# List all queued jobs (default: 10 most recent)
docker exec -it sclib_fastapi python3 /app/SCLib_JobProcessing/monitor_jobs.py list

# List more jobs
docker exec -it sclib_fastapi python3 /app/SCLib_JobProcessing/monitor_jobs.py list 50
```

### 3. Check Specific Job Status

```bash
# Check a specific job
docker exec -it sclib_fastapi python3 /app/SCLib_JobProcessing/monitor_jobs.py status <job_id>
```

### 4. Check if Background Service is Running

```bash
# Check if background service process is running
docker exec sclib_fastapi ps aux | grep BackgroundService

# Or check Docker logs
docker logs sclib_fastapi | grep -i "background\|conversion\|job"
```

## Understanding Job Status

Jobs can be in these states:
- **queued**: Job is waiting to be processed
- **processing**: Job is currently being executed
- **completed**: Job finished successfully
- **failed**: Job encountered an error
- **cancelled**: Job was cancelled

## Why Jobs Might Be Queued But Not Converting

### 1. Background Service Not Running

The background service (`SCLib_BackgroundService.py`) must be running to process conversion jobs.

**Check if it's running:**
```bash
docker exec sclib_fastapi ps aux | grep BackgroundService
```

**If not running, you need to start it.** The background service should be started automatically, but if it's not:

```bash
# Check how it's started in your Docker setup
# Usually it's started via start_fastapi_server.py or a separate service
```

### 2. Check Docker Container Status

```bash
# Check if FastAPI container is running
docker ps | grep sclib_fastapi

# Check container logs for errors
docker logs sclib_fastapi --tail 100
```

### 3. Check MongoDB Connection

Jobs are stored in MongoDB. If MongoDB is not accessible, jobs won't be processed.

```bash
# Check MongoDB connection from FastAPI container
docker exec sclib_fastapi python3 -c "
from SCLib_MongoConnection import get_mongo_connection
try:
    client = get_mongo_connection()
    client.admin.command('ping')
    print('✅ MongoDB connection OK')
except Exception as e:
    print(f'❌ MongoDB connection failed: {e}')
"
```

### 4. Check for Stuck Jobs

```bash
# Clean old queued jobs (older than 1 hour)
docker exec -it sclib_fastapi python3 /app/SCLib_JobProcessing/monitor_jobs.py clean 1
```

## Using Python API to Check Jobs

You can also check jobs programmatically:

```python
from SCLib_JobMonitor import SCLib_JobMonitor
from SCLib_MongoConnection import get_mongo_connection
from SCLib_Config import get_database_name

# Initialize monitor
mongo_client = get_mongo_connection()
db_name = get_database_name()
monitor = SCLib_JobMonitor(mongo_client, db_name)

# Get queue overview
overview = monitor.get_queue_overview()
print(f"Queue health: {overview['health_status']}")

# Get specific job details
job_details = monitor.get_job_details("job_id_here")
print(f"Job status: {job_details['status']}")

# Get all jobs for a dataset
dataset_jobs = monitor.get_dataset_jobs("dataset_uuid_here")
for job in dataset_jobs:
    print(f"Job {job['job_id']}: {job['status']}")
```

## FastAPI Endpoints for Job Status

You can also check jobs via the FastAPI API:

```bash
# List upload jobs (includes conversion jobs)
curl http://localhost:5001/api/upload/jobs?user_id=user@example.com

# Get specific job status
curl http://localhost:5001/api/upload/status/<job_id>

# Get dataset status (shows conversion status)
curl http://localhost:5001/api/v1/datasets/<dataset_uuid>/status?user_email=user@example.com
```

## Troubleshooting Steps

1. **Check if background service is running:**
   ```bash
   docker exec sclib_fastapi ps aux | grep BackgroundService
   ```

2. **Check job queue:**
   ```bash
   docker exec -it sclib_fastapi python3 /app/SCLib_JobProcessing/monitor_jobs.py stats
   ```

3. **List queued jobs:**
   ```bash
   docker exec -it sclib_fastapi python3 /app/SCLib_JobProcessing/monitor_jobs.py list
   ```

4. **Check container logs:**
   ```bash
   docker logs sclib_fastapi --tail 100 | grep -i "conversion\|job\|error"
   ```

5. **Check MongoDB:**
   ```bash
   docker exec sclib_fastapi python3 -c "from SCLib_MongoConnection import get_mongo_connection; get_mongo_connection().admin.command('ping'); print('OK')"
   ```

## Starting Background Service Manually

If the background service is not running automatically, you can start it manually:

```bash
# Inside the FastAPI container
docker exec -it sclib_fastapi bash

# Create settings.json
cat > /tmp/settings.json << EOF
{
  "db_name": "scientistcloud",
  "in_data_dir": "/mnt/visus_datasets/upload",
  "out_data_dir": "/mnt/visus_datasets/converted",
  "sync_data_dir": "/mnt/visus_datasets/sync",
  "auth_dir": "/mnt/visus_datasets/auth"
}
EOF

# Start background service
cd /app/SCLib_JobProcessing
python3 SCLib_BackgroundService.py /tmp/settings.json
```

## Common Issues

### Jobs Stuck in "queued" Status

- **Background service not running**: Start the background service
- **MongoDB connection issues**: Check MongoDB connectivity
- **Resource constraints**: Check CPU/memory usage
- **Conversion script errors**: Check logs for conversion script failures

### Jobs Failing Immediately

- **Missing conversion script**: Check if `run_conversion.py` exists
- **Permission issues**: Check file permissions on input/output directories
- **Missing dependencies**: Check if conversion tools are installed

### Jobs Processing But Not Completing

- **Large files taking time**: Check conversion script logs
- **Resource exhaustion**: Monitor CPU/memory/disk
- **Network issues**: If syncing to remote storage

