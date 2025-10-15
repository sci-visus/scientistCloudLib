# 🚀 ScientistCloud Upload API - Curl Commands

This guide provides curl commands for interacting with the ScientistCloud Upload API directly from the command line.

## 📋 **Prerequisites**

1. **FastAPI Server Running**: Make sure the server is started
   ```bash
   source ${SCLIB_MYTEST}/env.local
   cd ${SCLIB_HOME}
   python start_fastapi_server.py --port 8000
   ```

2. **Server URL**: All examples use `http://localhost:8000` - adjust if different

## 🔍 **API Discovery & Status**

### Check Server Health
```bash
curl -s http://localhost:8000/health
```

### Get Supported Sources
```bash
curl -s http://localhost:8000/api/upload/supported-sources
```

### Get Upload Limits
```bash
curl -s http://localhost:8000/api/upload/limits
```

## 📁 **File Upload Methods**

### 1. Local File Upload (Standard)

Upload a file directly from your local filesystem:

```bash
curl -X POST "http://localhost:8000/api/upload/upload" \
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

### 2. URL Upload (Download from URL)

Download and process a file from a URL:

```bash
curl -X POST "http://localhost:8000/api/upload/initiate" \
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

### 3. Google Drive Upload

Upload from Google Drive using file ID and service account:

```bash
curl -X POST "http://localhost:8000/api/upload/initiate" \
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

### 4. S3 Upload

Upload from Amazon S3:

```bash
curl -X POST "http://localhost:8000/api/upload/initiate" \
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
curl -s "http://localhost:8000/api/upload/status/JOB_ID"
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
curl -X POST "http://localhost:8000/api/upload/cancel/JOB_ID"
```

## 🔄 **Large File Upload (Chunked)**

For files larger than 100MB, the API automatically uses chunked uploads:

### Step 1: Initiate Chunked Upload

```bash
curl -X POST "http://localhost:8000/api/upload/initiate-chunked" \
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
curl -X POST "http://localhost:8000/api/upload/chunk" \
  -H "Content-Type: multipart/form-data" \
  -F "upload_id=UPLOAD_ID_FROM_STEP_1" \
  -F "chunk_number=1" \
  -F "chunk=@chunk_1.bin"
```

### Step 3: Complete Upload

```bash
curl -X POST "http://localhost:8000/api/upload/complete-chunked" \
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
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/upload/upload" \
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
  STATUS_RESPONSE=$(curl -s "http://localhost:8000/api/upload/status/$JOB_ID")
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
- `folder` - Organize files in folders
- `team_uuid` - Associate with team
- `convert` - Whether to convert data (default: true)
- `is_public` - Make dataset public (default: false)

## 🔧 **Troubleshooting**

### Common Issues

1. **Connection Refused**
   ```bash
   # Check if server is running
   curl -s http://localhost:8000/health
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
curl -v -X POST "http://localhost:8000/api/upload/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/file.tiff" \
  -F "user_email=user@example.com" \
  -F "dataset_name=My Dataset" \
  -F "sensor=TIFF"
```

## 📚 **Additional Resources**

- **Main README**: See `README.md` for Python client examples
- **API Documentation**: Visit `http://localhost:8000/docs` for interactive API docs
- **ReDoc Documentation**: Visit `http://localhost:8000/redoc` for detailed API reference

## 🚀 **Quick Start**

1. Start the server:
   ```bash
   source ${SCLIB_MYTEST}/env.local
   cd ${SCLIB_HOME}
   python start_fastapi_server.py --port 8000
   ```

2. Test the API:
   ```bash
   curl -s http://localhost:8000/api/upload/supported-sources
   ```

3. Upload a file:
   ```bash
   curl -X POST "http://localhost:8000/api/upload/upload" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@/path/to/your/file.tiff" \
     -F "user_email=user@example.com" \
     -F "dataset_name=Test Dataset" \
     -F "sensor=TIFF"
   ```

Happy uploading! 🎉

