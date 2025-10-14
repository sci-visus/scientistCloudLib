# ScientistCloud Job Processing System

This directory contains the enhanced job processing system for ScientistCloud 2.0, designed to replace the existing background service with a more robust, scalable, and maintainable solution.

## 🚀 FastAPI Migration Complete

**Built with FastAPI for modern performance and features!** This provides:
- **Better Performance**: Async support and automatic validation
- **Modern API**: Auto-generated OpenAPI documentation
- **Type Safety**: Pydantic models with automatic validation
- **TB-Scale Support**: Chunked uploads for enormous datasets (up to 10TB)
- **Resumable Uploads**: Handle network interruptions gracefully
- **Parallel Processing**: Multiple concurrent upload streams
- **Automatic Handling**: No need to choose between standard and large file APIs!

### 🎯 Unified API - No More Choices!

**Use the Unified API** - it automatically handles both regular and TB-scale uploads:

1. **Unified FastAPI** (`SCLib_UploadAPI_Unified.py`) - **RECOMMENDED** - Automatically handles all file sizes
2. **Standard FastAPI** (`SCLib_UploadAPI_FastAPI.py`) - For regular uploads only
3. **Large Files FastAPI** (`SCLib_UploadAPI_LargeFiles.py`) - For TB-scale datasets only

### 🧠 Smart File Handling

The Unified API automatically determines the best upload method:
- **Files ≤ 100MB**: Standard upload (fast and efficient)
- **Files > 100MB**: Chunked upload (reliable for large files)
- **TB-Scale Files**: Full chunked upload with resumable transfers

**No configuration needed - it just works!**

## Prerequisites and Setup

### Required Services

Before using the upload client, you need to set up several services:

1. **MongoDB Database**
   - MongoDB instance running and accessible
   - Database with proper collections and indexes
   - Connection credentials configured

2. **Upload API Server**
   - FastAPI server running on a specific port
   - Upload processor service running
   - Proper file system permissions

3. **External Tools** (for upload functionality)
   - `rclone` - for Google Drive and cloud storage
   - `aws` CLI - for S3 uploads
   - `wget` or `curl` - for URL downloads
   - `rsync` - for file transfers

### Environment Configuration

The system requires extensive environment configuration. Create an environment file with these variables:

```bash
# Database Configuration
MONGO_URL=mongodb://localhost:27017
DB_NAME=scientistcloud
DB_HOST=localhost
DB_PASS=your_password

# SCLib Directory Structure
SCLIB_HOME=/path/to/scientistCloudLib/SCLib_JobProcessing  # Source code directory
SCLIB_MYTEST=/path/to/SCLib_TryTest                        # Test environment directory

# Server Configuration
DEPLOY_SERVER=your-server.com
DOMAIN_NAME=scientistcloud.com
VISUS_DATASETS=/path/to/datasets
VISUS_TEMP=/tmp/visus

# Authentication (Auth0)
AUTH0_DOMAIN=your-domain.auth0.com
AUTHO_CLIENT_ID=your_client_id
AUTHO_CLIENT_SECRET=your_client_secret
AUTH0_MANAGEMENT_CLIENT_ID=your_mgmt_client_id
AUTH0_MANAGEMENT_CLIENT_SECRET=your_mgmt_client_secret

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
AUTH_GOOGLE_CLIENT_ID=your_auth_google_client_id
AUTH_GOOGLE_CLIENT_SECRET=your_auth_google_client_secret

# Security
SECRET_KEY=your_secret_key
SECRET_IV=your_secret_iv
SSL_EMAIL=your_ssl_email

# Git Configuration
GIT_BRANCH_VISSTORE=main
GIT_BRANCH_JS=main
GIT_TOKEN=your_git_token

# Job Processing Directories
JOB_IN_DATA_DIR=${VISUS_DATASETS}/upload
JOB_OUT_DATA_DIR=${VISUS_DATASETS}/converted
JOB_SYNC_DATA_DIR=${VISUS_DATASETS}/sync
JOB_AUTH_DATA_DIR=${VISUS_DATASETS}/auth
```

### Directory Structure

The SCLib system uses two main environment variables for organization:

- **`SCLIB_HOME`**: Contains all source code files (APIs, clients, processors, etc.)
- **`SCLIB_MYTEST`**: Contains your test environment (env.local, test scripts, data loading scripts)

This separation allows you to:
- Keep source code clean and organized
- Have multiple test environments
- Easily switch between different configurations
- Maintain test scripts and data loading utilities separately

### Setup Steps

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   - Create environment file with variables above
   - Place in `${SCLIB_MYTEST}/env.local`
   - Or set environment variables directly

3. **Start MongoDB**:
   ```bash
   # Start MongoDB service
   sudo systemctl start mongod
   # Or using Docker
   docker run -d -p 27017:27017 --name mongodb mongo:latest
   ```

4. **Start FastAPI Server**:
   ```bash
   # Load environment variables
   source ${SCLIB_MYTEST}/env.local
   
   # Start the server
   cd ${SCLIB_HOME}
   python start_fastapi_server.py --port 8000
   ```

5. **Verify Setup**:
   ```bash
   # Load environment and change to source directory
   source ${SCLIB_MYTEST}/env.local
   cd ${SCLIB_HOME}
   
   # Test configuration
   python -c "from SCLib_Config import get_config; print('Config loaded:', get_config())"
   
   # Test MongoDB connection
   python -c "from SCLib_MongoConnection import get_mongo_connection; print('MongoDB connected:', get_mongo_connection())"
   
   # Test API server
   curl -s http://localhost:8000/api/upload/supported-sources
   ```

### File System Permissions

Ensure proper permissions for data directories:

**For Production/Server:**
```bash
sudo mkdir -p /mnt/visus_datasets/{upload,converted,sync,auth,tmp}
sudo chown -R $USER:$USER /mnt/visus_datasets
sudo chmod -R 755 /mnt/visus_datasets
```

**For Localhost Development:**
```bash
mkdir -p ${VISUS_DATASETS}/{upload,converted,sync,auth,tmp}
chmod -R 755 ${VISUS_DATASETS}
```

**Note:** For localhost development, set `VISUS_DATASETS` to a local directory (e.g., `/Users/username/GIT/VisStoreDataTemp`) and the system will automatically use your local paths instead of `/mnt/visus_datasets`.

### Server Configuration for Large Files

For TB-scale uploads, additional server configuration is required:

#### 1. Reverse Proxy Configuration (Nginx)

```nginx
# /etc/nginx/sites-available/scientistcloud
server {
    listen 80;
    server_name your-domain.com;
    
    # Large file upload settings
    client_max_body_size 10T;  # 10TB max file size
    client_body_timeout 300s;
    client_header_timeout 300s;
    
    # Proxy settings for large files
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    proxy_buffering off;
    proxy_request_buffering off;
    
    location / {
        proxy_pass http://localhost:5001;  # Large file API
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 2. Uvicorn Configuration

```bash
# Run the large file API with optimized settings
uvicorn SCLib_UploadAPI_LargeFiles:app \
    --host 0.0.0.0 \
    --port 5001 \
    --workers 1 \
    --timeout-keep-alive 300 \
    --limit-max-requests 100 \
    --log-level info
```

#### 3. System Limits

```bash
# Increase system limits for large files
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf
echo "fs.file-max = 2097152" >> /etc/sysctl.conf
sysctl -p
```

#### 4. Directory Organization

```bash
# All files use UUID-based organization
# Files are stored in: ${VISUS_DATASETS}/upload/{uuid}/
# No separate directories needed - UUID handles organization
# Large and small files use the same structure
```

## 🗂️ TB-Scale File Handling

For enormous datasets (TB-scale), we provide specialized APIs and clients:

### File Size Limits

| API Version | Max File Size | Chunk Size | Use Case |
|-------------|---------------|------------|----------|
| Standard FastAPI | 1GB | N/A | Regular uploads |
| Large Files FastAPI | **10TB** | 100MB | TB-scale datasets |
| Unified FastAPI | **10TB** | Auto | **RECOMMENDED** - All files |

### Large File Features

- **Chunked Uploads**: Files are split into 100MB chunks for reliable transfer
- **Resumable Transfers**: Resume interrupted uploads from where they left off
- **Parallel Processing**: Upload multiple chunks simultaneously for speed
- **Progress Tracking**: Real-time progress monitoring
- **Hash Validation**: SHA-256 verification for data integrity
- **Cloud Integration**: Direct S3/Google Drive support for large files

### Quick Start - Unified API (Recommended)

```python
from SCLib_UploadClient_Unified import ScientistCloudUploadClient

# Initialize unified client - handles all file sizes automatically!
client = ScientistCloudUploadClient("http://localhost:8000")

# Upload any file - automatically chooses best method
result = client.upload_file(
    file_path="/path/to/your/file.dat",  # Can be 1MB or 10TB!
    user_email="scientist@example.com",
    dataset_name="My Dataset",
    sensor="IDX",
    progress_callback=lambda p: print(f"Progress: {p*100:.1f}%")
)

print(f"Upload type: {result.upload_type}")  # "standard" or "chunked"
print(f"Job ID: {result.job_id}")

# Wait for completion
final_status = client.wait_for_completion(result.job_id)
print(f"Upload complete: {final_status.status}")
```

### Advanced: Manual API Selection (Not Recommended)

If you need specific control, you can still use the separate APIs:

```python
# For large files only
from SCLib_UploadClient_LargeFiles import LargeFileUploadClient
client = LargeFileUploadClient("http://localhost:5001")

# For standard files only  
from SCLib_UploadClient_FastAPI import ScientistCloudUploadClient
client = ScientistCloudUploadClient("http://localhost:8000")
```

## Current Status

✅ **FastAPI Server**: Successfully running on localhost:8000  
✅ **API Endpoints**: All upload endpoints working  
✅ **Environment Setup**: Localhost directories configured  
⚠️ **Known Issues**: Some basic endpoints (/, /health) have validation errors but core API works  
✅ **Documentation**: Available at http://localhost:8000/docs  

### Troubleshooting

**Issue**: `/health` and `/` endpoints return 500 errors  
**Solution**: This is a known issue with response validation. The core API endpoints work fine. Use `/api/upload/supported-sources` to test connectivity.

**Issue**: Environment variables not loading  
**Solution**: Make sure to use `AUTHO_CLIENT_ID` and `AUTHO_CLIENT_SECRET` (not `AUTH0_CLIENT_ID`). Load environment with `source env.local` before starting server.

**Issue**: Port 5000 already in use  
**Solution**: Use `--port 8000` or disable macOS AirPlay Receiver in System Preferences.  

## Quick Start

> **⚠️ Important**: Before using the examples below, make sure you have completed all the setup steps in the "Prerequisites and Setup" section above. The upload client requires MongoDB, the API server, and proper environment configuration to be running.

### Upload API Client (Recommended)

The easiest way to use the library is through the upload client:

```python
from SCLib_JobProcessing import ScientistCloudUploadClient

# Initialize client
client = ScientistCloudUploadClient("http://localhost:8000")

# Upload a local file
result = client.upload_local_file(
    file_path="/path/to/dataset.zip",
    user_email="user@example.com",
    dataset_name="My Dataset",
    sensor="TIFF",
    convert=True,
    is_public=False
)

print(f"Upload job started: {result['job_id']}")

# Monitor progress
final_status = client.wait_for_completion(result['job_id'])
print(f"Upload completed: {final_status['status']}")
```

### Other Upload Sources

```python
# Google Drive import
result = client.initiate_google_drive_upload(
    file_id="1ABC123DEF456",
    service_account_file="/path/to/service.json",
    user_email="user@example.com",
    dataset_name="Google Drive Dataset",
    sensor="NETCDF"
)

# S3 import
result = client.initiate_s3_upload(
    bucket_name="my-bucket",
    object_key="data/dataset.zip",
    access_key_id="AKIA...",
    secret_access_key="secret...",
    user_email="user@example.com",
    dataset_name="S3 Dataset",
    sensor="HDF5"
)

# URL download
result = client.initiate_url_upload(
    url="https://example.com/dataset.zip",
    user_email="user@example.com",
    dataset_name="URL Dataset",
    sensor="OTHER"
)
```

### Complete Example

See `example_usage_new_api.py` for a complete example showing all the main features of the library.

### More Usage Examples

**Simple Upload:**
```python
from SCLib_JobProcessing import ScientistCloudUploadClient

client = ScientistCloudUploadClient()
result = client.upload_local_file(
    file_path="/path/to/dataset.zip",
    user_email="user@example.com",
    dataset_name="My Dataset",
    sensor="TIFF"
)
```

**Google Drive Import:**
```python
result = client.initiate_google_drive_upload(
    file_id="1ABC123DEF456",
    service_account_file="/path/to/service.json",
    user_email="user@example.com",
    dataset_name="Google Drive Dataset",
    sensor="NETCDF"
)
```

**Monitor Progress:**
```python
status = client.wait_for_completion(result['job_id'])
print(f"Upload completed: {status['status']}")
```

## Overview

The SCLib_JobProcessing system provides:

- **Robust Job Queue Management**: MongoDB-based job queue with retry logic and error handling
- **Enhanced Background Service**: Improved reliability with PID monitoring and automatic recovery
- **Asynchronous Upload System**: Complete upload solution supporting local files, Google Drive, S3, and URL sources
- **Comprehensive Monitoring**: Real-time job monitoring, statistics, and health checks
- **Migration Tools**: Utilities to migrate from the old system to the new job queue
- **Type Safety**: Well-defined job types and status transitions
- **Configuration Management**: Centralized environment variable and collection name management

## Architecture

### Core Components

1. **SCLib_JobQueueManager**: Manages job creation, retrieval, and status updates
2. **SCLib_BackgroundService**: Enhanced background service with job processing capabilities
3. **SCLib_JobTypes**: Defines all job types, statuses, and transitions
4. **SCLib_JobMonitor**: Provides monitoring, statistics, and administrative functions
5. **SCLib_JobMigration**: Handles migration from the old system
6. **SCLib_Config**: Centralized configuration management for environment variables and collection names
7. **SCLib_MongoConnection**: Enhanced MongoDB connection manager with pooling and health monitoring
8. **SCLib_UploadJobTypes**: Defines upload job types, sensor types, and configurations
9. **SCLib_UploadProcessor**: Processes asynchronous upload jobs using rclone, rsync, and other tools
10. **SCLib_UploadAPI**: RESTful API for upload operations with immediate response and background processing

### Job Types

#### Traditional Job Types
- `google_sync`: Synchronize data from Google Drive
- `dataset_conversion`: Convert dataset to streamable format
- `file_upload`: Upload files to storage
- `file_extraction`: Extract files from archives
- `data_compression`: Compress data for storage
- `rsync_transfer`: Transfer data via rsync
- `backup_creation`: Create data backups
- `data_validation`: Validate dataset integrity

#### Upload Job Types
- `upload`: Asynchronous upload jobs supporting multiple sources
  - **Local files**: Direct file upload with progress tracking
  - **Google Drive**: Import from Google Drive using service accounts
  - **S3/Cloud Storage**: Import from Amazon S3 and other cloud providers
  - **URL**: Download files from URLs with resume support

#### Sensor Types
- `IDX`: IDX format datasets
- `TIFF`: TIFF image datasets
- `TIFF RGB`: RGB TIFF datasets
- `NETCDF`: NetCDF scientific data
- `HDF5`: HDF5 hierarchical data
- `4D_NEXUS`: 4D Nexus format
- `RGB`: RGB image data
- `MAPIR`: MAPIR sensor data
- `OTHER`: Other data formats

### Dataset Statuses

The system maintains backward compatibility with existing statuses:

- `submitted` → `sync queued` → `syncing` → `conversion queued` → `converting` → `done`
- `submitted` → `upload queued` → `uploading` → `done`
- `submitted` → `unzipping` → `conversion queued` → `converting` → `done`
- Error states: `sync error`, `conversion error`, `upload error`, etc.

## Asynchronous Upload System

The SCLib_JobProcessing system includes a comprehensive asynchronous upload solution that replaces synchronous upload tools like Uppy with a robust, scalable job-based approach.

### Key Features

- **Immediate Response**: Users get instant feedback and can navigate away from the upload page
- **Background Processing**: Uploads continue processing in the background
- **Multiple Sources**: Support for local files, Google Drive, S3, and URL downloads
- **Progress Tracking**: Real-time progress monitoring with detailed statistics
- **Resume Support**: Automatic resume for interrupted uploads
- **Error Recovery**: Automatic retry with exponential backoff
- **Tool Flexibility**: Uses the best tool for each source type (rclone, rsync, AWS CLI, wget, curl)

### Upload Sources

#### 1. Local File Upload
```python
# Upload a local file
POST /api/upload/local/upload
Content-Type: multipart/form-data

file: [binary data]
user_email: "user@example.com"
dataset_name: "My Dataset"
sensor: "TIFF"
convert: "true"
is_public: "false"
folder: "research_data"  # optional
team_uuid: "team_123"    # optional
```

#### 2. Google Drive Import
```python
# Import from Google Drive
POST /api/upload/initiate
{
    "source_type": "google_drive",
    "source_config": {
        "file_id": "1ABC123DEF456",
        "service_account_file": "/path/to/service.json"
    },
    "user_email": "user@example.com",
    "dataset_name": "Google Drive Dataset",
    "sensor": "NETCDF",
    "convert": true,
    "is_public": false,
    "folder": "cloud_data",
    "team_uuid": "team_456"
}
```

#### 3. S3 Import
```python
# Import from S3
POST /api/upload/initiate
{
    "source_type": "s3",
    "source_config": {
        "bucket_name": "my-bucket",
        "object_key": "data/dataset.zip",
        "access_key_id": "AKIA...",
        "secret_access_key": "secret..."
    },
    "user_email": "user@example.com",
    "dataset_name": "S3 Dataset",
    "sensor": "HDF5",
    "convert": true,
    "is_public": false,
    "folder": "s3_imports"
}
```

#### 4. URL Download
```python
# Download from URL
POST /api/upload/initiate
{
    "source_type": "url",
    "source_config": {
        "url": "https://example.com/dataset.zip"
    },
    "user_email": "user@example.com",
    "dataset_name": "URL Dataset",
    "sensor": "OTHER",
    "convert": true,
    "is_public": false
}
```

### Required Parameters

All upload jobs require these parameters:

- **`user_email`**: User email address
- **`dataset_name`**: Name of the dataset
- **`sensor`**: Sensor type (IDX, TIFF, TIFF RGB, NETCDF, HDF5, 4D_NEXUS, RGB, MAPIR, OTHER)
- **`convert`**: Whether to convert the data (true/false)
- **`is_public`**: Whether dataset is public (true/false)

### Optional Parameters

- **`folder`**: Optional folder name
- **`team_uuid`**: Optional team UUID

### Progress Monitoring

```python
# Check upload progress
GET /api/upload/status/{job_id}

# Response
{
    "job_id": "upload_12345",
    "status": "uploading",
    "progress_percentage": 45.2,
    "bytes_uploaded": 1024000,
    "bytes_total": 2264000,
    "speed_mbps": 12.5,
    "eta_seconds": 120,
    "current_file": "dataset.zip"
}
```

### Job Management

```python
# Cancel upload
POST /api/upload/cancel/{job_id}

# List user's upload jobs
GET /api/upload/jobs?user_id=user@example.com&status=completed

# Get supported sources and parameters
GET /api/upload/supported-sources
```

### Tool Requirements

The upload system uses various tools for optimal performance:

- **rclone**: Primary tool for most operations (Google Drive, S3, local)
- **rsync**: Fallback for local-to-local transfers
- **AWS CLI**: For S3 operations with multipart upload
- **wget/curl**: For URL downloads with resume support

Install required tools:
```bash
# Install rclone
curl https://rclone.org/install.sh | sudo bash

# Install AWS CLI
pip install awscli

# wget and curl are usually pre-installed
```

## Installation

### Prerequisites

- Python 3.8+
- MongoDB
- Required Python packages (see requirements.txt)
- Upload tools: rclone, AWS CLI, wget, curl (for upload functionality)

### Setup

1. **Environment Variables**:
   The system automatically detects and loads environment files from:
   - `/Users/amygooch/GIT/VisusDataPortalPrivate/config/env.scientistcloud.com`
   - `/Users/amygooch/GIT/VisusDataPortalPrivate/config/env.all`
   
   Or set manually:
   ```bash
   export MONGO_URL="mongodb://localhost:27017"
   export DB_NAME="scientistcloud"
   export DEPLOY_SERVER="https://scientistcloud.com"
   export DOMAIN_NAME="scientistcloud.com"
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Upload Tools** (for upload functionality):
   ```bash
   # Install rclone
   curl https://rclone.org/install.sh | sudo bash
   
   # Install AWS CLI
   pip install awscli
   
   # wget and curl are usually pre-installed
   ```

4. **Database Setup**:
   The system will automatically create necessary indexes on first run.

5. **Configuration Validation**:
   ```bash
   python SCLib_Config.py  # Test configuration loading
   cd ${SCLIB_HOME}
   python example_usage.py  # Test MongoDB connection
   ```

## Usage

### Starting the FastAPI Server

```bash
# Load environment and start server
source ${SCLIB_MYTEST}/env.local
cd ${SCLIB_HOME}
python start_fastapi_server.py --port 8000

# The server will start on http://localhost:8000
# Automatically handles both small and large files
```

### Using the Upload System

#### Python Client (Recommended)

The `ScientistCloudUploadClient` provides a clean, easy-to-use interface:

```python
from SCLib_JobProcessing import ScientistCloudUploadClient

client = ScientistCloudUploadClient("http://localhost:8000")

# Upload a local file
result = client.upload_local_file(
    file_path="/path/to/dataset.zip",
    user_email="user@example.com", 
    dataset_name="My Dataset",
    sensor="TIFF"
)

# Monitor progress
status = client.wait_for_completion(result['job_id'])
```

#### Direct API Example

```python
from SCLib_JobProcessing import ScientistCloudUploadClient

# Initialize client
client = ScientistCloudUploadClient("http://localhost:8000")

# Upload a local file
result = client.upload_local_file(
    file_path="/path/to/dataset.zip",
    user_email="user@example.com",
    dataset_name="My Dataset",
    sensor="TIFF",
    convert=True,
    is_public=False,
    folder="research_data",
    team_uuid="team_123"
)

job_id = result['job_id']
print(f"Upload started: {job_id}")

# Monitor progress
final_status = client.wait_for_completion(job_id, timeout=1800)
print(f"Upload completed: {final_status['status']}")
```

#### Frontend Integration

```javascript
// Replace Uppy with API calls
const formData = new FormData();
formData.append('file', file);
formData.append('user_email', 'user@example.com');
formData.append('dataset_name', 'My Dataset');
formData.append('sensor', 'TIFF');
formData.append('convert', 'true');
formData.append('is_public', 'false');
formData.append('folder', 'research_data');
formData.append('team_uuid', 'team_123');

const response = await fetch('/api/upload/local/upload', {
    method: 'POST',
    body: formData
});

const result = await response.json();
const jobId = result.job_id;

// User gets immediate response and can navigate away
showSuccess(`Upload started! Job ID: ${jobId}`);

// Optional: Poll for progress
const pollProgress = async () => {
    const status = await fetch(`/api/upload/status/${jobId}`);
    const progress = await status.json();
    
    if (progress.status === 'completed') {
        showSuccess('Upload completed!');
    } else if (progress.status === 'failed') {
        showError(progress.error_message);
    } else {
        updateProgressBar(progress.progress_percentage);
        setTimeout(pollProgress, 2000);
    }
};

// Only poll if user wants to see progress
if (userWantsProgress) {
    pollProgress();
}
```

### Starting the Background Service

```bash
# Create settings file
cat > settings.json << EOF
{
  "db_name": "scientistcloud",
  "in_data_dir": "${VISUS_DATASETS}/upload",
  "out_data_dir": "${VISUS_DATASETS}/converted",
  "sync_data_dir": "${VISUS_DATASETS}/sync",
  "auth_dir": "${VISUS_DATASETS}/auth"
}
EOF

# Start the service
python SCLib_BackgroundService.py settings.json
```

### Creating Jobs Programmatically

```python
from SCLib_JobQueueManager import SCLib_JobQueueManager
from pymongo import MongoClient

# Initialize
mongo_client = MongoClient("mongodb://localhost:27017")
job_queue = SCLib_JobQueueManager(mongo_client, "scientistcloud")

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
from SCLib_JobMonitor import SCLib_JobMonitor

# Initialize monitor
monitor = SCLib_JobMonitor(mongo_client, "scientistcloud")

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
python SCLib_JobMigration.py migrate --dry-run
```

### 2. Perform Migration

```bash
# Migrate all datasets (dry run first)
python SCLib_JobMigration.py migrate --dry-run
python SCLib_JobMigration.py migrate

# Or migrate specific dataset
python SCLib_JobMigration.py migrate --dataset-uuid=550e8400-e29b-41d4-a716-446655440000
```

### 3. Validate Migration

```bash
# Validate migration was successful
python SCLib_JobMigration.py validate
```

### 4. Rollback if Needed

```bash
# Rollback all migrations
python SCLib_JobMigration.py rollback

# Or rollback specific dataset
python SCLib_JobMigration.py rollback --dataset-uuid=550e8400-e29b-41d4-a716-446655440000
```

## Configuration

### Job Type Configuration

Each job type has configurable parameters in `SCLib_JobTypes.py`:

```python
SC_JOB_TYPE_CONFIGS = {
    SCLib_JobType.DATASET_CONVERSION: {
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
   python -c "from SCLib_JobMonitor import SCLib_JobMonitor; print(SCLib_JobMonitor(mongo_client, 'db').get_stale_jobs())"
   ```

2. **High Failure Rate**:
   ```bash
   # Get error summary
   python -c "from SCLib_JobMonitor import SCLib_JobMonitor; print(SCLib_JobMonitor(mongo_client, 'db').get_failed_jobs(24))"
   ```

3. **Performance Issues**:
   ```bash
   # Get performance report
   python SCLib_JobMonitor.py --performance-report --days=7
   ```

### Logs

The system logs to:
- Job-specific logs in `/tmp/sc_job_*.log`
- System logs in MongoDB `jobs` collection
- Background service logs to stdout

## Development

### Adding New Job Types

1. **Define Job Type** in `SCLib_JobTypes.py`:
   ```python
   class SCLib_JobType(Enum):
       NEW_JOB_TYPE = "new_job_type"
   ```

2. **Add Configuration**:
   ```python
   SC_JOB_TYPE_CONFIGS[SCLib_JobType.NEW_JOB_TYPE] = {
       'description': 'New job type description',
       'timeout_minutes': 30,
       'max_attempts': 3,
       'requires_internet': False,
       'priority': 2
   }
   ```

3. **Implement Handler** in `SCLib_BackgroundService.py`:
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
python -c "from SCLib_JobQueueManager import SCLib_JobQueueManager; # test code"

# Test migration
python SCLib_JobMigration.py migrate --dry-run
```

## Contributing

1. Follow the SC_ prefix naming convention
2. Add comprehensive error handling
3. Include logging for debugging
4. Update documentation for new features
5. Add tests for new functionality

## License

This code is part of the ScientistCloud project and follows the same licensing terms.
