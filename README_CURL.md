# 🚀 ScientistCloud Library - Complete Curl Guide

This comprehensive guide provides curl commands for all ScientistCloud Library operations with JWT authentication.

## 📋 **Prerequisites**

### 1. Start Services

```bash
# Navigate to Docker directory
cd /Users/amygooch/GIT/ScientistCloud_2.0/scientistCloudLib/Docker

# Start all services
./start.sh up

# Verify services are running
curl http://localhost:8001/health  # Authentication service
curl http://localhost:5001/health  # Upload service
```

### 2. Service URLs

- **Authentication Service**: `http://localhost:8001` (Port 8001)
- **Upload Service**: `http://localhost:5001` (Port 5001)
- **API Documentation**: 
  - Auth: `http://localhost:8001/docs`
  - Upload: `http://localhost:5001/docs`

## 🔐 **Authentication**

### 1. Login to Get JWT Token

```bash
# Login and get JWT token
curl -X POST "http://localhost:8001/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}'

# Response:
# {
#   "success": true,
#   "data": {
#     "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
#     "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
#     "expires_in": 86400,
#     "token_type": "Bearer",
#     "user": {
#       "user_id": "user_123",
#       "email": "user@example.com",
#       "name": "User Name"
#     }
#   }
# }
```

### 2. Extract Token for Use

```bash
# Extract token for use in subsequent requests
TOKEN=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}' | \
     jq -r '.data.access_token')

echo "Token: $TOKEN"
```

### 3. Check Authentication Status

```bash
# Check if authentication is valid
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/auth/status"

# Response:
# {
#   "authenticated": true,
#   "user": {
#     "email": "user@example.com",
#     "name": "User Name"
#   }
# }
```

### 4. Refresh Token (if expired)

```bash
# Get refresh token from login response
REFRESH_TOKEN=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}' | \
     jq -r '.data.refresh_token')

# Refresh access token
curl -X POST "http://localhost:8001/api/auth/refresh" \
     -H "Content-Type: application/json" \
     -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"

# Extract new access token
NEW_TOKEN=$(curl -s -X POST "http://localhost:8001/api/auth/refresh" \
     -H "Content-Type: application/json" \
     -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}" | \
     jq -r '.data.access_token')
```

### 5. Get Current User Info

```bash
# Get current user information
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8001/api/auth/me"

# Response:
# {
#   "user_id": "user_123",
#   "email": "user@example.com",
#   "name": "User Name",
#   "email_verified": true
# }
```

### 6. Logout

```bash
# Logout and revoke tokens
curl -X POST "http://localhost:8001/api/auth/logout" \
     -H "Authorization: Bearer $TOKEN"

# Response:
# {
#   "success": true,
#   "message": "Logout successful"
# }
```

## 📤 **File Upload Operations**

> **⚠️ Important for UI Development:** All upload operations require the complete set of fields shown below. The UI must collect all these fields from users to ensure proper dataset organization, team access control, and searchability.

### **Required Fields for UI:**
- `dataset_name` - Human-readable dataset name
- `sensor` - Data type (TIFF, IDX, HDF5, RAW, CSV, JSON)
- `convert` - Whether to convert to IDX format (true/false)
- `is_public` - Public/private access control (true/false)
- `folder` - UI organization folder (required for proper organization)
- `team_uuid` - Team association for sharing (required for team access)
- `tags` - Comma-separated searchable tags (required for discovery)
- `description` - Detailed dataset description (required for understanding)

### 1. Upload Single File

```bash
# Upload file with authentication (all fields required for UI)
curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@/path/to/your/file.tiff" \
     -F "dataset_name=My Dataset" \
     -F "sensor=TIFF" \
     -F "convert=true" \
     -F "is_public=false" \
     -F "folder=my_folder" \
     -F "team_uuid=DevTestTeam" \
     -F "tags=research,test,2024" \
     -F "description=My dataset description"

# Response:
# {
#   "job_id": "job_123456",
#   "status": "queued",
#   "upload_type": "standard",
#   "estimated_duration": 120
# }
```

### 2. Upload Large File (Chunked)

```bash
# Large files are automatically handled with chunked upload
curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@/path/to/large/file.tiff" \
     -F "dataset_name=Large Dataset" \
     -F "sensor=TIFF" \
     -F "convert=true" \
     -F "is_public=false" \
     -F "folder=LargeFiles" \
     -F "team_uuid=DevTestTeam" \
     -F "tags=large,research,data" \
     -F "description=Large dataset for research"

# Response:
# {
#   "job_id": "job_789012",
#   "status": "queued",
#   "upload_type": "chunked",
#   "estimated_duration": 3600
# }
```

### 3. Upload from URL

```bash
# Upload from URL (stored as direct link)
curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "url=http://example.com/data.tiff" \
     -F "dataset_name=URL Dataset" \
     -F "sensor=TIFF" \
     -F "convert=false" \
     -F "is_public=false" \
     -F "folder=External" \
     -F "team_uuid=DevTestTeam" \
     -F "tags=url,external,reference" \
     -F "description=External dataset from URL"
```

### 4. Add Files to Existing Dataset

```bash
# Add file to existing dataset using dataset identifier
curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@/path/to/additional/file.tiff" \
     -F "dataset_identifier=My Dataset" \
     -F "add_to_existing=true" \
     -F "sensor=TIFF" \
     -F "convert=true"
```

## 📊 **Status Monitoring**

### 1. Check Upload Status

```bash
# Check status of specific job
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/upload/status/JOB_ID"

# Response:
# {
#   "job_id": "job_123456",
#   "status": "running",
#   "progress_percentage": 45,
#   "estimated_time_remaining": 120,
#   "error": null
# }
```

### 2. List User's Jobs

```bash
# List all jobs for authenticated user
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/upload/jobs"

# With pagination
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/upload/jobs?limit=10&offset=0"

# Response:
# {
#   "jobs": [
#     {
#       "job_id": "job_123456",
#       "status": "completed",
#       "dataset_name": "My Dataset",
#       "created_at": "2024-01-01T12:00:00Z",
#       "updated_at": "2024-01-01T12:05:00Z"
#     }
#   ],
#   "total": 1,
#   "limit": 10,
#   "offset": 0
# }
```

### 3. Cancel Upload

```bash
# Cancel running upload
curl -X POST "http://localhost:5001/api/upload/cancel" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"job_id": "JOB_ID"}'
```

## 🔍 **System Information**

### 1. Check Service Health

```bash
# Authentication service health
curl http://localhost:8001/health

# Upload service health
curl http://localhost:5001/health

# Response:
# {
#   "status": "healthy",
#   "timestamp": "2024-01-01T12:00:00Z"
# }
```

### 2. Get Supported Sources

```bash
# Get list of supported upload sources
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/upload/supported-sources"

# Response:
# {
#   "sources": [
#     "local_file",
#     "local_directory", 
#     "url",
#     "google_drive",
#     "s3"
#   ]
# }
```

### 3. Get Upload Limits

```bash
# Get upload size limits and constraints
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/upload/limits"

# Response:
# {
#   "max_file_size": "10TB",
#   "max_concurrent_uploads": 3,
#   "chunk_size": "10MB",
#   "supported_formats": ["TIFF", "IDX", "HDF5"]
# }
```

## 🌐 **Advanced Operations**

### 1. Google Drive Upload

```bash
# Upload from Google Drive (requires service account)
curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "source_type=google_drive" \
     -F "file_id=GOOGLE_DRIVE_FILE_ID" \
     -F "service_account_file=@/path/to/service-account.json" \
     -F "dataset_name=Google Drive Dataset" \
     -F "sensor=TIFF" \
     -F "convert=true" \
     -F "is_public=false" \
     -F "folder=GoogleDrive" \
     -F "team_uuid=DevTestTeam" \
     -F "tags=google,drive,cloud" \
     -F "description=Dataset from Google Drive"
```

### 2. S3 Upload

```bash
# Upload from S3 (requires AWS credentials)
curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "source_type=s3" \
     -F "bucket_name=my-bucket" \
     -F "object_key=path/to/file.tiff" \
     -F "access_key_id=AWS_ACCESS_KEY" \
     -F "secret_access_key=AWS_SECRET_KEY" \
     -F "dataset_name=S3 Dataset" \
     -F "sensor=TIFF" \
     -F "convert=true" \
     -F "is_public=false" \
     -F "folder=S3" \
     -F "team_uuid=DevTestTeam" \
     -F "tags=s3,aws,cloud" \
     -F "description=Dataset from S3 bucket"
```

### 3. Batch Operations

```bash
# Upload multiple files in sequence
for file in /path/to/files/*.tiff; do
    echo "Uploading $file..."
    curl -X POST "http://localhost:5001/api/upload/upload" \
         -H "Authorization: Bearer $TOKEN" \
         -F "file=@$file" \
         -F "dataset_name=Batch Upload" \
         -F "sensor=TIFF" \
         -F "convert=true" \
         -F "is_public=false" \
         -F "folder=Batch" \
         -F "team_uuid=DevTestTeam" \
         -F "tags=batch,multiple,files" \
         -F "description=Batch upload of multiple files"
    echo "Uploaded $file"
done
```

## 🛠️ **Error Handling**

### 1. Handle Authentication Errors

```bash
# Check if token is valid
if ! curl -s -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/auth/status" | grep -q "authenticated"; then
    echo "Token expired, refreshing..."
    # Refresh token logic here
fi
```

### 2. Handle Upload Errors

```bash
# Upload with error handling
RESPONSE=$(curl -s -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@/path/to/file.tiff" \
     -F "dataset_name=My Dataset" \
     -F "sensor=TIFF" \
     -F "convert=true" \
     -F "is_public=false" \
     -F "folder=Test" \
     -F "team_uuid=DevTestTeam" \
     -F "tags=test,error,handling" \
     -F "description=Test upload with error handling")

# Check for errors
if echo "$RESPONSE" | grep -q "error"; then
    echo "Upload failed: $RESPONSE"
else
    echo "Upload successful: $RESPONSE"
fi
```

### 3. Retry Logic

```bash
# Retry upload on failure
MAX_RETRIES=3
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    RESPONSE=$(curl -s -X POST "http://localhost:5001/api/upload/upload" \
         -H "Authorization: Bearer $TOKEN" \
         -F "file=@/path/to/file.tiff" \
         -F "dataset_name=My Dataset" \
         -F "sensor=TIFF" \
         -F "convert=true" \
         -F "is_public=false" \
         -F "folder=Test" \
         -F "team_uuid=DevTestTeam" \
         -F "tags=test,retry,logic" \
         -F "description=Test upload with retry logic")
    
    if echo "$RESPONSE" | grep -q "job_id"; then
        echo "Upload successful: $RESPONSE"
        break
    else
        echo "Upload failed, retrying... ($((RETRY_COUNT + 1))/$MAX_RETRIES)"
        RETRY_COUNT=$((RETRY_COUNT + 1))
        sleep 5
    fi
done
```

## 📝 **Complete Workflow Example**

```bash
#!/bin/bash
# Complete ScientistCloud workflow with authentication

# 1. Login
echo "🔐 Logging in..."
TOKEN=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}' | \
     jq -r '.data.access_token')

if [ "$TOKEN" = "null" ]; then
    echo "❌ Login failed"
    exit 1
fi

echo "✅ Login successful"

# 2. Check authentication
echo "🔍 Checking authentication..."
if curl -s -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/auth/status" | grep -q "authenticated"; then
    echo "✅ Authentication valid"
else
    echo "❌ Authentication failed"
    exit 1
fi

# 3. Upload file
echo "📤 Uploading file..."
UPLOAD_RESPONSE=$(curl -s -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@/path/to/your/file.tiff" \
     -F "dataset_name=My Dataset" \
     -F "sensor=TIFF" \
     -F "convert=true" \
     -F "is_public=false" \
     -F "folder=Workflow" \
     -F "team_uuid=DevTestTeam" \
     -F "tags=workflow,complete,example" \
     -F "description=Complete workflow example")

JOB_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.job_id')

if [ "$JOB_ID" = "null" ]; then
    echo "❌ Upload failed: $UPLOAD_RESPONSE"
    exit 1
fi

echo "✅ Upload initiated, Job ID: $JOB_ID"

# 4. Monitor progress
echo "📊 Monitoring progress..."
while true; do
    STATUS_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
         "http://localhost:5001/api/upload/status/$JOB_ID")
    
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
    PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.progress_percentage')
    
    echo "Status: $STATUS ($PROGRESS%)"
    
    if [ "$STATUS" = "completed" ]; then
        echo "✅ Upload completed successfully!"
        break
    elif [ "$STATUS" = "failed" ]; then
        echo "❌ Upload failed"
        break
    fi
    
    sleep 5
done

# 5. Logout
echo "🚪 Logging out..."
curl -s -X POST "http://localhost:8001/api/auth/logout" \
     -H "Authorization: Bearer $TOKEN" > /dev/null

echo "✅ Workflow completed!"
```

## 🎯 **Best Practices**

### 1. Token Management

- Always check token validity before operations
- Implement token refresh logic for long-running processes
- Store tokens securely (environment variables, not hardcoded)
- Logout when done to clean up sessions

### 2. Error Handling

- Check HTTP status codes and response content
- Implement retry logic for transient failures
- Handle authentication errors gracefully
- Monitor upload progress and handle timeouts

### 3. Performance

- Use chunked uploads for large files
- Monitor upload progress to provide user feedback
- Implement concurrent upload limits
- Use appropriate timeouts for different operations

### 4. Security

- Never hardcode tokens in scripts
- Use HTTPS in production environments
- Validate all input parameters
- Implement proper error messages without exposing sensitive information

## 📞 **Support**

For issues and questions:

1. Check service health: `curl http://localhost:8001/health`
2. Verify authentication: Test login endpoint
3. Check upload service: `curl http://localhost:5001/health`
4. Review logs: `./start.sh logs`
5. Check configuration: `docker-compose config`

The ScientistCloud Library is now ready for production use with comprehensive curl support and JWT authentication!
