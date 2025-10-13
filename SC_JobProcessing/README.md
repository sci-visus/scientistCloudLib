# ScientistCloud Job Processing System

This directory contains the enhanced job processing system for ScientistCloud 2.0, designed to replace the existing background service with a more robust, scalable, and maintainable solution.

## Overview

The SC_JobProcessing system provides:

- **Robust Job Queue Management**: MongoDB-based job queue with retry logic and error handling
- **Enhanced Background Service**: Improved reliability with PID monitoring and automatic recovery
- **Comprehensive Monitoring**: Real-time job monitoring, statistics, and health checks
- **Migration Tools**: Utilities to migrate from the old system to the new job queue
- **Type Safety**: Well-defined job types and status transitions

## Architecture

### Core Components

1. **SC_JobQueueManager**: Manages job creation, retrieval, and status updates
2. **SC_BackgroundService**: Enhanced background service with job processing capabilities
3. **SC_JobTypes**: Defines all job types, statuses, and transitions
4. **SC_JobMonitor**: Provides monitoring, statistics, and administrative functions
5. **SC_JobMigration**: Handles migration from the old system

### Job Types

- `google_sync`: Synchronize data from Google Drive
- `dataset_conversion`: Convert dataset to streamable format
- `file_upload`: Upload files to storage
- `file_extraction`: Extract files from archives
- `data_compression`: Compress data for storage
- `rsync_transfer`: Transfer data via rsync
- `backup_creation`: Create data backups
- `data_validation`: Validate dataset integrity

### Dataset Statuses

The system maintains backward compatibility with existing statuses:

- `submitted` → `sync queued` → `syncing` → `conversion queued` → `converting` → `done`
- `submitted` → `upload queued` → `uploading` → `done`
- `submitted` → `unzipping` → `conversion queued` → `converting` → `done`
- Error states: `sync error`, `conversion error`, `upload error`, etc.

## Installation

### Prerequisites

- Python 3.8+
- MongoDB
- Required Python packages (see requirements.txt)

### Setup

1. **Environment Variables**:
   ```bash
   export MONGO_URL="mongodb://localhost:27017"
   export DB_NAME="scientistcloud"
   ```

2. **Install Dependencies**:
   ```bash
   pip install pymongo psutil
   ```

3. **Database Setup**:
   The system will automatically create necessary indexes on first run.

## Usage

### Starting the Background Service

```bash
# Create settings file
cat > settings.json << EOF
{
  "db_name": "scientistcloud",
  "in_data_dir": "/mnt/visus_datasets/upload",
  "out_data_dir": "/mnt/visus_datasets/converted",
  "sync_data_dir": "/mnt/visus_datasets/sync",
  "auth_dir": "/mnt/visus_datasets/auth"
}
EOF

# Start the service
python SC_BackgroundService.py settings.json
```

### Creating Jobs Programmatically

```python
from SC_JobQueueManager import SC_JobQueueManager
from pymongo import MongoClient

# Initialize
mongo_client = MongoClient("mongodb://localhost:27017")
job_queue = SC_JobQueueManager(mongo_client, "scientistcloud")

# Create a dataset conversion job
job_id = job_queue.create_job(
    dataset_uuid="550e8400-e29b-41d4-a716-446655440000",
    job_type="dataset_conversion",
    parameters={
        "input_path": "/path/to/input",
        "output_path": "/path/to/output",
        "sensor_type": "4D_Probe",
        "conversion_params": {
            "Xs_dataset": "path/to/Xs",
            "Ys_dataset": "path/to/Ys"
        }
    },
    priority=1  # High priority
)

print(f"Created job: {job_id}")
```

### Monitoring Jobs

```python
from SC_JobMonitor import SC_JobMonitor

# Initialize monitor
monitor = SC_JobMonitor(mongo_client, "scientistcloud")

# Get queue overview
overview = monitor.get_queue_overview()
print(f"Queue status: {overview['health_status']['overall']}")

# Get job details
job_details = monitor.get_job_details("job_12345")
print(f"Job status: {job_details['status']}")

# Get performance report
report = monitor.get_performance_report(days=7)
print(f"Success rate: {report['summary']['success_rate']:.1%}")
```

## Migration from Old System

### 1. Analyze Current State

```bash
# Check what datasets need migration
python SC_JobMigration.py migrate --dry-run
```

### 2. Perform Migration

```bash
# Migrate all datasets (dry run first)
python SC_JobMigration.py migrate --dry-run
python SC_JobMigration.py migrate

# Or migrate specific dataset
python SC_JobMigration.py migrate --dataset-uuid=550e8400-e29b-41d4-a716-446655440000
```

### 3. Validate Migration

```bash
# Validate migration was successful
python SC_JobMigration.py validate
```

### 4. Rollback if Needed

```bash
# Rollback all migrations
python SC_JobMigration.py rollback

# Or rollback specific dataset
python SC_JobMigration.py rollback --dataset-uuid=550e8400-e29b-41d4-a716-446655440000
```

## Configuration

### Job Type Configuration

Each job type has configurable parameters in `SC_JobTypes.py`:

```python
SC_JOB_TYPE_CONFIGS = {
    SC_JobType.DATASET_CONVERSION: {
        'description': 'Convert dataset to streamable format',
        'timeout_minutes': 120,
        'max_attempts': 2,
        'requires_internet': False,
        'priority': 1,
        'estimated_duration': '10-60 minutes'
    }
}
```

### Priority Levels

- **1 (High)**: Critical operations like dataset conversion
- **2 (Normal)**: Standard operations like file uploads
- **3 (Low)**: Background tasks like compression

## Monitoring and Maintenance

### Health Checks

The system provides comprehensive health monitoring:

```python
# Get system health
health = monitor.get_queue_overview()['health_status']
if health['overall'] == 'critical':
    print("System needs attention!")
```

### Performance Monitoring

```python
# Get performance metrics
metrics = monitor.get_performance_metrics()
print(f"Average conversion time: {metrics['avg_duration_by_type']['dataset_conversion']:.1f}s")
```

### Cleanup

```python
# Clean up old completed jobs (older than 30 days)
deleted_count = monitor.cleanup_old_data(days=30)
print(f"Cleaned up {deleted_count} old jobs")
```

## Error Handling

### Automatic Retry

Jobs automatically retry on failure with exponential backoff:

```python
# Job will retry up to max_attempts times
job_config = {
    'max_attempts': 3,
    'timeout_minutes': 60
}
```

### Manual Intervention

```python
# Retry a failed job
success = monitor.retry_failed_job("job_12345")

# Cancel a running job
success = monitor.cancel_job("job_12345")
```

## API Integration

The job system integrates with the ScientistCloud API:

```python
# Submit job via API
POST /api/v1/jobs
{
    "dataset_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "job_type": "dataset_conversion",
    "parameters": {
        "input_path": "/path/to/input",
        "output_path": "/path/to/output",
        "sensor_type": "4D_Probe"
    },
    "priority": 1
}

# Check job status
GET /api/v1/jobs/{job_id}

# Get queue statistics
GET /api/v1/jobs/queue/stats
```

## Troubleshooting

### Common Issues

1. **Jobs Stuck in Running State**:
   ```bash
   # Check for stale jobs
   python -c "from SC_JobMonitor import SC_JobMonitor; print(SC_JobMonitor(mongo_client, 'db').get_stale_jobs())"
   ```

2. **High Failure Rate**:
   ```bash
   # Get error summary
   python -c "from SC_JobMonitor import SC_JobMonitor; print(SC_JobMonitor(mongo_client, 'db').get_failed_jobs(24))"
   ```

3. **Performance Issues**:
   ```bash
   # Get performance report
   python SC_JobMonitor.py --performance-report --days=7
   ```

### Logs

The system logs to:
- Job-specific logs in `/tmp/sc_job_*.log`
- System logs in MongoDB `jobs` collection
- Background service logs to stdout

## Development

### Adding New Job Types

1. **Define Job Type** in `SC_JobTypes.py`:
   ```python
   class SC_JobType(Enum):
       NEW_JOB_TYPE = "new_job_type"
   ```

2. **Add Configuration**:
   ```python
   SC_JOB_TYPE_CONFIGS[SC_JobType.NEW_JOB_TYPE] = {
       'description': 'New job type description',
       'timeout_minutes': 30,
       'max_attempts': 3,
       'requires_internet': False,
       'priority': 2
   }
   ```

3. **Implement Handler** in `SC_BackgroundService.py`:
   ```python
   def _handle_new_job_type(self, job):
       # Implementation here
       pass
   ```

4. **Add to Handler Registry**:
   ```python
   self.job_handlers = {
       # ... existing handlers
       'new_job_type': self._handle_new_job_type
   }
   ```

### Testing

```bash
# Run unit tests
python -m pytest tests/

# Test job creation
python -c "from SC_JobQueueManager import SC_JobQueueManager; # test code"

# Test migration
python SC_JobMigration.py migrate --dry-run
```

## Contributing

1. Follow the SC_ prefix naming convention
2. Add comprehensive error handling
3. Include logging for debugging
4. Update documentation for new features
5. Add tests for new functionality

## License

This code is part of the ScientistCloud project and follows the same licensing terms.
