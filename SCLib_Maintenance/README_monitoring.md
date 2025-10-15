# ScientistCloud Job Queue Monitoring

This directory contains tools to monitor and maintain the ScientistCloud job queue, preventing old spinning jobs from becoming a problem.

**Location**: `/Users/amygooch/GIT/ScientistCloud_2.0/scientistCloudLib/SCLib_Maintenance/`

## Tools Available

### 1. `monitor_jobs.py` - Python Job Monitor
A Python script that provides detailed job queue statistics and management.

**Usage:**

**From Docker container:**
```bash
# Show job statistics
docker exec scientistcloud_fastapi python /app/monitor_jobs.py stats

# List queued jobs (limit: 10)
docker exec scientistcloud_fastapi python /app/monitor_jobs.py list

# Clean old queued jobs (older than 1 hour)
docker exec scientistcloud_fastapi python /app/monitor_jobs.py clean
```

**From host system:**
```bash
# Navigate to the maintenance directory
cd /Users/amygooch/GIT/ScientistCloud_2.0/scientistCloudLib/SCLib_Maintenance

# Option 1: Use the setup script (recommended)
./setup_host_env.sh stats
./setup_host_env.sh list
./setup_host_env.sh clean

# Option 2: Run directly (requires environment variables to be set)
python monitor_jobs.py stats
python monitor_jobs.py list
python monitor_jobs.py clean
```

### 2. `setup_host_env.sh` - Host Environment Setup
A script to set up the environment for running maintenance tools on the host system.

**Usage:**
```bash
# Navigate to the maintenance directory
cd /Users/amygooch/GIT/ScientistCloud_2.0/scientistCloudLib/SCLib_Maintenance

# Run any maintenance command with proper environment
./setup_host_env.sh stats
./setup_host_env.sh list
./setup_host_env.sh clean
```

### 3. `maintenance.sh` - Shell Maintenance Script
A comprehensive shell script for monitoring and maintaining the system.

**Usage:**
```bash
# Navigate to the maintenance directory
cd /Users/amygooch/GIT/ScientistCloud_2.0/scientistCloudLib/SCLib_Maintenance

# Show job statistics
./maintenance.sh stats

# List queued jobs
./maintenance.sh list

# Clean old jobs
./maintenance.sh clean

# Check for stuck jobs and auto-fix
./maintenance.sh check

# Restart services
./maintenance.sh restart

# Start continuous monitoring (every 30 seconds)
./maintenance.sh monitor

# Show help
./maintenance.sh help
```

## Prevention Measures

### 1. Automatic Cleanup in Upload Processor
The upload processor now includes automatic cleanup that runs every 5 minutes:
- Removes queued jobs older than 1 hour
- Cleans up both database and in-memory job references
- Logs cleanup activities

### 2. Regular Monitoring
Use the maintenance script to set up regular monitoring:
```bash
# Start continuous monitoring
./maintenance.sh monitor
```

### 3. Manual Cleanup
If you notice stuck jobs, you can manually clean them:
```bash
# Clean jobs older than 1 hour
./maintenance.sh clean

# Or clean jobs older than 2 hours
./maintenance.sh clean 2
```

## Common Issues and Solutions

### Issue: Empty UUID directories being created
**Cause:** Old stuck jobs in the database that the processor can't find configurations for.

**Solution:**
```bash
# Check for stuck jobs
./maintenance.sh check

# This will automatically clean old jobs and restart services if needed
```

### Issue: Processor stuck in error loop
**Cause:** Old job references causing continuous "Job config not found" errors.

**Solution:**
```bash
# Clean old jobs and restart
./maintenance.sh clean
./maintenance.sh restart
```

### Issue: High number of queued jobs
**Cause:** Jobs getting stuck in queued state.

**Solution:**
```bash
# Check what's queued
./maintenance.sh list

# Clean old queued jobs
./maintenance.sh clean
```

## Monitoring Best Practices

1. **Regular Health Checks**: Run `./maintenance.sh stats` daily to check job queue health
2. **Automated Monitoring**: Use `./maintenance.sh monitor` for continuous monitoring
3. **Proactive Cleanup**: Set up a cron job to run cleanup daily:
   ```bash
   # Add to crontab (runs daily at 2 AM)
   0 2 * * * cd /path/to/ScientistCloud_2.0/scientistCloudLib/Docker && ./maintenance.sh clean
   ```
4. **Alert on Stuck Jobs**: Monitor logs for "Job config not found" errors

## Job Status Meanings

- **queued**: Job is waiting to be processed
- **processing**: Job is currently being processed
- **completed**: Job finished successfully
- **failed**: Job failed with an error
- **cancelled**: Job was cancelled by user or system

## Database Schema

Jobs are stored in MongoDB with the following structure:
```json
{
  "job_id": "upload_1234567890_abcdef12",
  "job_type": "upload",
  "status": "queued",
  "created_at": "2025-10-15T15:30:00Z",
  "user_email": "user@example.com",
  "dataset_uuid": "uuid-string",
  "parameters": {...}
}
```

## Troubleshooting

### Cannot connect to MongoDB
- Check if Docker services are running: `docker ps`
- Verify MongoDB connection in logs: `docker logs scientistcloud_fastapi`

### Permission denied errors
- Ensure the script has execute permissions: `chmod +x maintenance.sh`
- Check Docker volume permissions

### Script not found errors
- Ensure you're in the correct directory: `/Users/amygooch/GIT/ScientistCloud_2.0/scientistCloudLib/Docker`
- Check if the script exists: `ls -la maintenance.sh`
