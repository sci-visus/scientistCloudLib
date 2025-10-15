# 🚀 ScientistCloud Upload API - Curl Commands

This guide provides curl commands for interacting with the ScientistCloud Upload API directly from the command line.

## 📋 **Prerequisites**

1. **FastAPI Server Running**: Make sure the server is started
   ```bash
   # Using Docker (recommended)
   cd /path/to/scientistCloudLib/Docker
   ./start.sh up --env-file ../../SCLib_TryTest/env.local
   
   # Or directly with Python
   source ${SCLIB_MYTEST}/env.local
   cd ${SCLIB_HOME}
   python start_fastapi_server.py --port 5001 --api-type unified
   ```

2. **Server URL**: All examples use `http://localhost:5001` (Docker) or `http://localhost:8000` (direct) - adjust if different

## 🔍 **API Discovery & Status**

### Check Server Health
```bash
curl -s http://localhost:5001/health
```

### Get Supported Sources
```bash
curl -s http://localhost:5001/api/upload/supported-sources
```

### Get Upload Limits
```bash
curl -s http://localhost:5001/api/upload/limits
```

## 📁 **File Upload Methods**

### 1. Local File Upload (Standard)

Upload a file directly from your local filesystem:

```bash
curl -X POST "http://localhost:5001/api/upload/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/file.tiff" \
  -F "user_email=user@example.com" \
  -F "dataset_name=My Dataset" \
  -F "sensor=TIFF" \
  -F "convert=true" \
  -F "is_public=false" \
  -F "folder=my_folder" \
  -F "team_uuid=optional-team-uuid"
```

#### 🆕 Adding Files to Existing Datasets

You can add files to existing datasets using flexible identifiers:

```bash
# Using UUID
curl -X POST "http://localhost:5001/api/upload/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/file.tiff" \
  -F "user_email=user@example.com" \
  -F "dataset_name=Additional File" \
  -F "sensor=TIFF" \
  -F "dataset_identifier=550e8400-e29b-41d4-a716-446655440000" \
  -F "add_to_existing=true"

# Using dataset name
curl -X POST "http://localhost:5001/api/upload/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/file.tiff" \
  -F "user_email=user@example.com" \
  -F "dataset_name=Additional File" \
  -F "sensor=TIFF" \
  -F "dataset_identifier=My Dataset" \
  -F "add_to_existing=true"

# Using slug
curl -X POST "http://localhost:5001/api/upload/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/file.tiff" \
  -F "user_email=user@example.com" \
  -F "dataset_name=Additional File" \
  -F "sensor=TIFF" \
  -F "dataset_identifier=my-dataset-2024" \
  -F "add_to_existing=true"

# Using numeric ID
curl -X POST "http://localhost:5001/api/upload/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/file.tiff" \
  -F "user_email=user@example.com" \
  -F "dataset_name=Additional File" \
  -F "sensor=TIFF" \
  -F "dataset_identifier=12345" \
  -F "add_to_existing=true"
```

**Response Example:**
```json
{
  "job_id": "uuid-here",
  "status": "processing",
  "message": "Upload initiated successfully",
  "estimated_duration": 300,
  "upload_type": "standard"
}
```

### 2. Directory Upload (Multiple Files)

Upload all files in a directory to a single dataset:

```bash
# Note: Directory uploads are handled by the client, but you can upload individual files
# with the same dataset_identifier to achieve the same result

# First file - creates new dataset
curl -X POST "http://localhost:5001/api/upload/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/directory/file1.tiff" \
  -F "user_email=user@example.com" \
  -F "dataset_name=Directory Dataset" \
  -F "sensor=TIFF" \
  -F "dataset_identifier=unique-uuid-for-directory" \
  -F "add_to_existing=false"

# Subsequent files - add to existing dataset
curl -X POST "http://localhost:5001/api/upload/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/directory/file2.tiff" \
  -F "user_email=user@example.com" \
  -F "dataset_name=Directory Dataset" \
  -F "sensor=TIFF" \
  -F "dataset_identifier=unique-uuid-for-directory" \
  -F "add_to_existing=true" \
  -F "folder=subdirectory_name"
```

### 3. URL Upload (Download from URL)

Download and process a file from a URL:

```bash
curl -X POST "http://localhost:5001/api/upload/initiate" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "url",
    "source_config": {
      "url": "https://example.com/data.tiff"
    },
    "user_email": "user@example.com",
    "dataset_name": "URL Dataset",
    "sensor": "TIFF",
    "convert": true,
    "is_public": false,
    "folder": "url_uploads",
    "team_uuid": "optional-team-uuid"
  }'
```

### 4. Google Drive Upload

Upload from Google Drive using file ID and service account:

```bash
curl -X POST "http://localhost:5001/api/upload/initiate" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "google_drive",
    "source_config": {
      "file_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
      "service_account_file": "/path/to/service-account.json"
    },
    "user_email": "user@example.com",
    "dataset_name": "Google Drive Dataset",
    "sensor": "TIFF",
    "convert": true,
    "is_public": false,
    "folder": "google_drive",
    "team_uuid": "optional-team-uuid"
  }'
```

### 5. S3 Upload

Upload from Amazon S3:

```bash
curl -X POST "http://localhost:5001/api/upload/initiate" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "s3",
    "source_config": {
      "bucket_name": "my-bucket",
      "object_key": "path/to/file.tiff",
      "access_key_id": "AKIAIOSFODNN7EXAMPLE",
      "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    },
    "user_email": "user@example.com",
    "dataset_name": "S3 Dataset",
    "sensor": "TIFF",
    "convert": true,
    "is_public": false,
    "folder": "s3_uploads",
    "team_uuid": "optional-team-uuid"
  }'
```

## 📊 **Job Management**

### Check Upload Status

```bash
# Replace JOB_ID with actual job ID from upload response
curl -s "http://localhost:5001/api/upload/status/JOB_ID"
```

**Response Example:**
```json
{
  "job_id": "uuid-here",
  "status": "processing",
  "progress_percentage": 45.2,
  "bytes_uploaded": 1048576,
  "bytes_total": 2097152,
  "message": "Processing file...",
  "error": null,
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:05:00Z"
}
```

### Cancel Upload

```bash
curl -X POST "http://localhost:5001/api/upload/cancel/JOB_ID"
```

## 🔍 **Dataset Management**

### Get Dataset Information

Retrieve dataset information using flexible identifiers:

```bash
# Using UUID
curl -s "http://localhost:5001/api/v1/datasets/550e8400-e29b-41d4-a716-446655440000"

# Using dataset name
curl -s "http://localhost:5001/api/v1/datasets/My%20Dataset"

# Using slug
curl -s "http://localhost:5001/api/v1/datasets/my-dataset-2024"

# Using numeric ID
curl -s "http://localhost:5001/api/v1/datasets/12345"
```

**Response Example:**
```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My Dataset",
  "slug": "my-dataset-2024",
  "id": 12345,
  "user_email": "user@example.com",
  "sensor": "TIFF",
  "convert": true,
  "is_public": false,
  "folder": "my_folder",
  "team_uuid": "optional-team-uuid",
  "status": "completed",
  "files": [
    {
      "filename": "file1.tiff",
      "size": 1048576,
      "uploaded_at": "2024-01-01T12:00:00Z"
    },
    {
      "filename": "file2.tiff",
      "size": 2097152,
      "uploaded_at": "2024-01-01T12:05:00Z"
    }
  ],
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:05:00Z"
}
```

## 🔄 **Large File Upload (Chunked)**

For files larger than 100MB, the API automatically uses chunked uploads:

### Step 1: Initiate Chunked Upload

```bash
curl -X POST "http://localhost:5001/api/upload/initiate-chunked" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "large_file.tiff",
    "file_size": 1073741824,
    "file_hash": "sha256-hash-of-complete-file",
    "user_email": "user@example.com",
    "dataset_name": "Large Dataset",
    "sensor": "TIFF",
    "convert": true,
    "is_public": false,
    "folder": "large_files"
  }'
```

**Response:**
```json
{
  "upload_id": "upload-session-uuid",
  "chunk_size": 104857600,
  "total_chunks": 11,
  "message": "Chunked upload initiated"
}
```

### Step 2: Upload Chunks

```bash
# Upload each chunk (repeat for each chunk)
curl -X POST "http://localhost:5001/api/upload/chunk" \
  -H "Content-Type: multipart/form-data" \
  -F "upload_id=UPLOAD_ID_FROM_STEP_1" \
  -F "chunk_number=1" \
  -F "chunk=@chunk_1.bin"
```

### Step 3: Complete Upload

```bash
curl -X POST "http://localhost:5001/api/upload/complete-chunked" \
  -H "Content-Type: application/json" \
  -d '{
    "upload_id": "UPLOAD_ID_FROM_STEP_1"
  }'
```

## 🎯 **Complete Workflow Example**

Here's a complete example that uploads a file and monitors its progress:

```bash
#!/bin/bash

# Upload a file and capture the job ID
echo "Uploading file..."
RESPONSE=$(curl -s -X POST "http://localhost:5001/api/upload/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/file.tiff" \
  -F "user_email=user@example.com" \
  -F "dataset_name=My Dataset" \
  -F "sensor=TIFF" \
  -F "convert=true" \
  -F "is_public=false")

# Extract job ID from response
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# Monitor progress
while true; do
  STATUS_RESPONSE=$(curl -s "http://localhost:5001/api/upload/status/$JOB_ID")
  STATUS=$(echo $STATUS_RESPONSE | jq -r '.status')
  PROGRESS=$(echo $STATUS_RESPONSE | jq -r '.progress_percentage')
  
  echo "Status: $STATUS, Progress: $PROGRESS%"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  
  sleep 5
done

echo "Final status: $STATUS_RESPONSE"
```

## 📝 **Available Parameters**

### Sensor Types
- `IDX` - IDX format
- `TIFF` - TIFF format
- `TIFF RGB` - TIFF RGB format
- `NETCDF` - NetCDF format
- `HDF5` - HDF5 format
- `4D_NEXUS` - 4D Nexus format
- `RGB` - RGB format
- `MAPIR` - MAPIR format
- `OTHER` - Other formats

### Source Types
- `local` - Local file upload
- `url` - URL download
- `google_drive` - Google Drive
- `s3` - Amazon S3
- `dropbox` - Dropbox
- `onedrive` - OneDrive

### Optional Parameters
- `folder` - Organize files in folders (UI organization only, not file system structure)
- `team_uuid` - Associate with team
- `convert` - Whether to convert data (default: true)
- `is_public` - Make dataset public (default: false)
- `dataset_identifier` - UUID, name, slug, or numeric ID for existing datasets
- `add_to_existing` - Whether to add to existing dataset (requires dataset_identifier)

## 🔧 **Troubleshooting**

### Common Issues

1. **Connection Refused**
   ```bash
   # Check if server is running
   curl -s http://localhost:5001/health
   ```

2. **File Not Found**
   ```bash
   # Make sure file path is correct and accessible
   ls -la /path/to/your/file.tiff
   ```

3. **Invalid JSON**
   ```bash
   # Validate JSON before sending
   echo '{"test": "data"}' | jq .
   ```

4. **Large File Timeout**
   ```bash
   # Use chunked upload for files > 100MB
   # Check file size first
   ls -lh /path/to/large/file.tiff
   ```

### Debug Mode

Add `-v` flag to curl for verbose output:

```bash
curl -v -X POST "http://localhost:5001/api/upload/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/file.tiff" \
  -F "user_email=user@example.com" \
  -F "dataset_name=My Dataset" \
  -F "sensor=TIFF"
```

## 📚 **Additional Resources**

- **Main README**: See `README.md` for Python client examples
- **API Documentation**: Visit `http://localhost:5001/docs` for interactive API docs
- **ReDoc Documentation**: Visit `http://localhost:5001/redoc` for detailed API reference
- **Upload Methods Guide**: See `README_upload_methods.md` for detailed upload strategies

## 🚀 **Quick Start**

1. Start the server:
   ```bash
   # Using Docker (recommended)
   cd /path/to/scientistCloudLib/Docker
   ./start.sh up --env-file ../../SCLib_TryTest/env.local
   
   # Or directly with Python
   source ${SCLIB_MYTEST}/env.local
   cd ${SCLIB_HOME}
   python start_fastapi_server.py --port 5001 --api-type unified
   ```

2. Test the API:
   ```bash
   curl -s http://localhost:5001/api/upload/supported-sources
   ```

3. Upload a file:
   ```bash
   curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@/path/to/your/file.tiff" \
     -F "user_email=user@example.com" \
     -F "dataset_name=Test Dataset" \
     -F "sensor=TIFF"
   ```

4. Add files to existing dataset:
   ```bash
   curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@/path/to/your/file2.tiff" \
     -F "user_email=user@example.com" \
     -F "dataset_name=Additional File" \
     -F "sensor=TIFF" \
     -F "dataset_identifier=Test Dataset" \
     -F "add_to_existing=true"
   ```

## 🆕 **New Features**

### Flexible Dataset Identification
The API now supports multiple ways to identify datasets:
- **UUID**: `550e8400-e29b-41d4-a716-446655440000`
- **Name**: `My Dataset`
- **Slug**: `my-dataset-2024` (human-readable, URL-friendly)
- **Numeric ID**: `12345` (short, auto-generated)

### Directory Uploads
Upload multiple files to a single dataset while preserving directory structure:
- All files in a directory upload share the same UUID
- Directory structure is preserved within the UUID directory
- Use `dataset_identifier` and `add_to_existing=true` for subsequent files

### Enhanced Dataset Management
- View dataset information using any identifier type
- Track multiple files within a single dataset
- Monitor upload progress and status
- Automatic cleanup of old jobs

### Docker Support
- Full Docker Compose setup with environment management
- Automatic service orchestration
- Volume mounting for data persistence
- Health checks and monitoring

Happy uploading! 🎉

