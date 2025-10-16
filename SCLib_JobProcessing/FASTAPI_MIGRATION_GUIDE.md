# FastAPI Migration Guide - ScientistCloud Upload API

## 🎯 Migration Overview

We have **completely migrated** from Flask to FastAPI, providing a modern, high-performance API for ScientistCloud uploads with **TB-scale file support**.

## 🚀 What's New

### Performance Improvements
- **Async Support**: Non-blocking I/O for better concurrency
- **Automatic Validation**: Pydantic models with type safety
- **Auto Documentation**: OpenAPI/Swagger docs generated automatically
- **Better Error Handling**: Structured error responses

### TB-Scale File Support
- **10TB File Limit**: Up from 100MB with Flask
- **Chunked Uploads**: 100MB chunks for reliable transfer
- **Resumable Transfers**: Resume interrupted uploads
- **Parallel Processing**: Multiple concurrent upload streams
- **Progress Tracking**: Real-time upload progress
- **Hash Validation**: SHA-256 integrity checking

## 📁 New Files Created

### API Servers
1. **`SCLib_UploadAPI_FastAPI.py`** - Standard FastAPI server (up to 1GB files)
2. **`SCLib_UploadAPI_LargeFiles.py`** - Large files API (up to 10TB files)
3. **`start_fastapi_server.py`** - Server startup script

### Clients
1. **`SCLib_UploadClient_FastAPI.py`** - Standard FastAPI client
2. **`SCLib_UploadClient_LargeFiles.py`** - Large files client with chunked uploads
3. **`example_large_file_upload.py`** - Comprehensive examples

### Configuration
1. **`requirements_fastapi.txt`** - FastAPI dependencies
2. **`FASTAPI_MIGRATION_GUIDE.md`** - This guide

## 🔧 Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements_fastapi.txt
```

### 2. Environment Configuration
Set these environment variables:
```bash
export MONGO_URL="mongodb://localhost:27017"
export DB_NAME="scientistcloud"
export AUTH0_DOMAIN="your-domain.auth0.com"
export AUTH0_CLIENT_ID="your-client-id"
export AUTH0_CLIENT_SECRET="your-client-secret"
# No separate temp directory needed - UUID handles organization
```

### 3. Start the Server

**Option A: Using Docker (Recommended)**:
```bash
cd /path/to/scientistCloudLib/Docker
./start.sh up --env-file ../../SCLib_TryTest/env.local
# Server will be available at http://localhost:5001
```

**Option B: Direct Python execution**:
```bash
# First install dependencies
cd ${SCLIB_HOME}
pip install -r requirements_fastapi.txt

# For unified API (handles both small and large files automatically)
python start_fastapi_server.py --api-type unified --port 5001

# For large files only (TB-scale)
python start_fastapi_server.py --api-type large-files --port 5001

# For standard files only (up to 1GB)
python start_fastapi_server.py --api-type standard --port 5000
```

## 📊 API Comparison

| Feature | Flask (Old) | FastAPI Standard | FastAPI Large Files |
|---------|-------------|------------------|-------------------|
| Max File Size | 100MB | 1GB | **10TB** |
| Async Support | ❌ | ✅ | ✅ |
| Auto Documentation | ❌ | ✅ | ✅ |
| Type Validation | ❌ | ✅ | ✅ |
| Chunked Uploads | ❌ | ❌ | ✅ |
| Resumable Uploads | ❌ | ❌ | ✅ |
| Parallel Uploads | ❌ | ❌ | ✅ |
| Progress Tracking | ❌ | ❌ | ✅ |
| Hash Validation | ❌ | ❌ | ✅ |

## 🗂️ TB-Scale File Handling

### File Size Limits
- **Standard API**: Up to 1GB files
- **Large Files API**: Up to 10TB files
- **Chunk Size**: 100MB (configurable)
- **Parallel Workers**: 4-8 concurrent uploads

### Key Features for Large Files

#### 1. Chunked Uploads
Files are automatically split into 100MB chunks:
```python
# Each chunk is uploaded separately
chunk_1: bytes 0-100MB
chunk_2: bytes 100MB-200MB
chunk_3: bytes 200MB-300MB
...
```

#### 2. Resumable Transfers
If upload is interrupted, resume from where it left off:
```python
# Check what chunks are missing
resume_info = client.get_resume_info(upload_id)
missing_chunks = resume_info.missing_chunks  # [5, 7, 12, ...]

# Resume upload
client.upload_file_chunked(..., resume_upload_id=upload_id)
```

#### 3. Parallel Processing
Upload multiple chunks simultaneously:
```python
client = LargeFileUploadClient(max_workers=8)  # 8 parallel uploads
```

#### 4. Progress Tracking
Real-time progress monitoring:
```python
def progress_callback(progress):
    print(f"Upload progress: {progress * 100:.1f}%")

client.upload_file_parallel(..., progress_callback=progress_callback)
```

## 💻 Usage Examples

### Standard File Upload (< 1GB)
```python
from SCLib_UploadClient_FastAPI import ScientistCloudUploadClient

client = ScientistCloudUploadClient("http://localhost:5000")

# Upload local file
result = client.upload_local_file(
    file_path="/path/to/file.dat",
    user_email="scientist@example.com",
    dataset_name="My Dataset",
    sensor="IDX"
)

print(f"Upload ID: {result.job_id}")
```

### Large File Upload (TB-scale)
```python
from SCLib_UploadClient_LargeFiles import LargeFileUploadClient

client = LargeFileUploadClient(
    base_url="http://localhost:5001",
    chunk_size=100 * 1024 * 1024,  # 100MB chunks
    max_workers=4                   # 4 parallel uploads
)

# Upload TB-scale file
upload_id = client.upload_file_parallel(
    file_path="/path/to/5TB/dataset.idx",
    user_email="scientist@example.com",
    dataset_name="Massive Dataset",
    sensor="IDX",
    progress_callback=lambda p: print(f"Progress: {p*100:.1f}%")
)

# Wait for completion
final_status = client.wait_for_completion(upload_id)
```

### Async Upload (Maximum Performance)
```python
from SCLib_UploadClient_LargeFiles import AsyncLargeFileUploadClient
import asyncio

async def upload_large_file():
    client = AsyncLargeFileUploadClient(
        base_url="http://localhost:5001",
        max_concurrent=8  # 8 concurrent uploads
    )
    
    upload_id = await client.upload_file_async(
        file_path="/path/to/10TB/dataset.idx",
        user_email="scientist@example.com",
        dataset_name="Huge Dataset",
        sensor="IDX"
    )
    
    return upload_id

# Run async upload
upload_id = asyncio.run(upload_large_file())
```

## 🔧 Server Configuration

### Nginx Configuration for Large Files
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # Large file settings
    client_max_body_size 10T;  # 10TB max
    client_body_timeout 300s;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    proxy_buffering off;
    
    location / {
        proxy_pass http://localhost:5001;
    }
}
```

### System Limits
```bash
# Increase file limits
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf
echo "fs.file-max = 2097152" >> /etc/sysctl.conf
sysctl -p
```

## 🚨 Migration Notes

### Breaking Changes
1. **Port Change**: Large files API runs on port 5001 (standard on 5000)
2. **Client API**: New client classes with different method signatures
3. **Response Format**: Some response fields have changed
4. **Error Handling**: Structured error responses with HTTP status codes

### Backward Compatibility
- **Legacy Flask API**: Still available but deprecated
- **Old Clients**: Will continue to work with Flask API
- **Database**: No changes to database schema
- **Configuration**: Same environment variables

### Migration Steps
1. **Install FastAPI dependencies**: `pip install -r requirements_fastapi.txt`
2. **Update client code**: Use new FastAPI clients
3. **Configure server**: Set up Nginx and system limits
4. **Test with small files**: Verify functionality
5. **Migrate large files**: Use new chunked upload system

## 📈 Performance Benefits

### Upload Speed
- **Parallel Uploads**: 4-8x faster for large files
- **Chunked Transfer**: More reliable than single large upload
- **Async Processing**: Better server resource utilization

### Reliability
- **Resumable Uploads**: Handle network interruptions
- **Hash Validation**: Ensure data integrity
- **Progress Tracking**: Monitor long-running uploads

### Scalability
- **Async I/O**: Handle more concurrent users
- **Chunked Processing**: Better memory management
- **Cloud Integration**: Direct S3/Google Drive support

## 🔍 Monitoring & Debugging

### API Documentation
- **Swagger UI**: `http://localhost:5001/docs`
- **ReDoc**: `http://localhost:5001/redoc`
- **OpenAPI Spec**: `http://localhost:5001/openapi.json`

### Health Checks
```python
# Check API health
health = client.health_check()
print(f"Status: {health['status']}")
print(f"Active uploads: {health['active_uploads']}")

# Check upload limits
limits = client.get_upload_limits()
print(f"Max file size: {limits['max_file_size_tb']} TB")
```

### Logging
```python
import logging
logging.basicConfig(level=logging.INFO)

# Server logs all upload activities
# Client logs progress and errors
```

## 🎯 Next Steps

1. **Test the new APIs** with your existing data
2. **Update client applications** to use FastAPI clients
3. **Configure production servers** with proper limits
4. **Monitor performance** and adjust settings as needed
5. **Plan migration timeline** for existing users

## 📞 Support

For questions or issues:
1. Check the API documentation at `/docs`
2. Review the example files
3. Check server logs for errors
4. Verify environment configuration

---

**🎉 Congratulations!** You now have a modern, high-performance API that can handle TB-scale datasets with reliability and speed.
