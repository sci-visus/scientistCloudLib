# Update Dataset Sizes Script

**Location:** `scientistCloudLib/SCLib_Maintenance/`

This script computes the size of upload and convert directories for each dataset and updates the `data_size` field in the MongoDB `visstoredatas` collection.

## Features

- Calculates total size by summing upload and convert directories
- Stores size in GB (as float) for consistency
- Supports dry-run mode for testing
- Can update all datasets or filter by UUID
- Comprehensive logging
- Error handling and recovery
- Designed for cron job execution

## Requirements

- Python 3.6+
- pymongo library: `pip install pymongo`
- MongoDB connection (via MONGO_URL environment variable)
- Access to dataset directories on the filesystem

## Environment Variables

Required:
- `MONGO_URL`: MongoDB connection string
- `DB_NAME`: Database name

Optional:
- `UPLOAD_BASE_DIR`: Base directory for uploads (default: `/mnt/visus_datasets/upload`)
- `CONVERT_BASE_DIR`: Base directory for converted data (default: `/mnt/visus_datasets/converted`)

## Usage

### Basic Usage

```bash
# Set environment variables
export MONGO_URL="mongodb://user:pass@host:port/db"
export DB_NAME="your_database_name"

# Run the script
python update_dataset_sizes.py
```

### Dry Run (Test Without Updating Database)

```bash
python update_dataset_sizes.py --dry-run
```

### Update Specific Dataset

```bash
python update_dataset_sizes.py --uuid abc-123-def-456
```

### Custom Directories

```bash
UPLOAD_BASE_DIR=/custom/upload CONVERT_BASE_DIR=/custom/convert python update_dataset_sizes.py
```

### Verbose Logging

```bash
python update_dataset_sizes.py --log-level DEBUG
```

## Cron Job Setup

### Example Crontab Entry

Run daily at 2 AM:

```cron
0 2 * * * cd /path/to/scientistCloudLib/SCLib_Maintenance && /usr/bin/python3 update_dataset_sizes.py >> /var/log/update_dataset_sizes.log 2>&1
```

Run every 6 hours:

```cron
0 */6 * * * cd /path/to/scientistCloudLib/SCLib_Maintenance && /usr/bin/python3 update_dataset_sizes.py >> /var/log/update_dataset_sizes.log 2>&1
```

### Recommended Cron Setup

1. Create a wrapper script that sets environment variables:

```bash
#!/bin/bash
# /path/to/scientistCloudLib/SCLib_Maintenance/run_update_sizes.sh

export MONGO_URL="mongodb://user:pass@host:port/db"
export DB_NAME="your_database_name"
export UPLOAD_BASE_DIR="/mnt/visus_datasets/upload"
export CONVERT_BASE_DIR="/mnt/visus_datasets/converted"

cd /path/to/scientistCloudLib/SCLib_Maintenance
/usr/bin/python3 update_dataset_sizes.py >> /var/log/update_dataset_sizes.log 2>&1
```

2. Make it executable:

```bash
chmod +x /path/to/scientistCloudLib/SCLib_Maintenance/run_update_sizes.sh
```

3. Add to crontab:

```cron
0 2 * * * /path/to/scientistCloudLib/SCLib_Maintenance/run_update_sizes.sh
```

## Running in Docker Container

The script is available in the FastAPI container at:
- Container path: `/app/scientistCloudLib/SCLib_Maintenance/update_dataset_sizes.py`

To run inside the container:

```bash
# Execute in running container
docker exec -it sclib_fastapi python3 /app/scientistCloudLib/SCLib_Maintenance/update_dataset_sizes.py --dry-run

# Or with environment variables
docker exec -it sclib_fastapi bash -c "export MONGO_URL='...' && export DB_NAME='...' && python3 /app/scientistCloudLib/SCLib_Maintenance/update_dataset_sizes.py"
```

For cron jobs in the container, you can:
1. Add a cron job inside the container (not recommended - lost on restart)
2. Use host cron to execute `docker exec` commands (recommended)
3. Create a separate maintenance container that runs the script

## Output

The script logs to both:
- Console (stdout)
- Log file: `update_dataset_sizes.log` (in the script directory)

### Log Format

```
2025-01-15 10:30:00 - INFO - Connected to MongoDB: your_database
2025-01-15 10:30:01 - INFO - Found 150 dataset(s) to process
2025-01-15 10:30:05 - INFO - Updated abc-123: None -> 1.234567 GB
2025-01-15 10:30:10 - INFO - Summary
2025-01-15 10:30:10 - INFO - Total datasets processed: 150
2025-01-15 10:30:10 - INFO - Updated: 145
2025-01-15 10:30:10 - INFO - Skipped: 5
2025-01-15 10:30:10 - INFO - Errors: 0
2025-01-15 10:30:10 - INFO - Total size: 250.45 GB
```

## Database Schema

The script updates the following fields in `visstoredatas` collection:

- `data_size`: **Float/numeric value in GB** (NOT a string)
  - Example: `1.234567` (not `"1.23 GB"`)
  - This makes it easy to parse and convert to other units (KB, MB, TB) in the UI
  - Stored as MongoDB Number type for easy querying and aggregation
- `data_size_updated_at`: Timestamp of last update (UTC)

## Performance Considerations

- The script processes datasets sequentially to avoid overwhelming the filesystem
- Large directories may take time to calculate
- Consider running during off-peak hours
- For very large datasets, consider running with `--log-level WARNING` to reduce log verbosity

## Troubleshooting

### Connection Errors

If you see MongoDB connection errors:
- Verify `MONGO_URL` is correct
- Check network connectivity
- Ensure MongoDB is running and accessible

### Permission Errors

If you see permission errors accessing directories:
- Ensure the script user has read access to dataset directories
- Check filesystem permissions

### Missing Directories

If directories don't exist:
- The script will log warnings but continue
- Datasets with missing directories will have size 0 GB

### Large Execution Time

If the script takes too long:
- Consider running for specific UUIDs during testing
- Use `--log-level WARNING` to reduce overhead
- Check if directories are on slow storage (NFS, etc.)

## Example Output

```
============================================================
Dataset Size Update Script
============================================================
MongoDB: scientistcloud
Upload directory: /mnt/visus_datasets/upload
Convert directory: /mnt/visus_datasets/converted
Dry run: False
UUID filter: None (all datasets)
============================================================
2025-01-15 10:30:00 - INFO - Connected to MongoDB: scientistcloud
2025-01-15 10:30:01 - INFO - Found 150 dataset(s) to process
2025-01-15 10:30:05 - INFO - Updated abc-123-def: None -> 1.234567 GB
2025-01-15 10:30:06 - INFO - Updated xyz-789-ghi: 0.5 -> 0.987654 GB
...
============================================================
Summary
============================================================
Total datasets processed: 150
Updated: 145
Skipped: 5
Errors: 0
Total size: 250.45 GB
============================================================
```

