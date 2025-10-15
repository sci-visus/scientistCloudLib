# ScientistCloud Upload Methods Documentation

## Overview

The ScientistCloud upload system provides multiple methods for uploading files, each optimized for different use cases and file sizes.

## API Versions and Upload Methods

The ScientistCloud system provides three API versions, each with different upload method support:

| API Version | Content-Based | Path-Based | Chunked | Recommended Use |
|-------------|---------------|------------|---------|-----------------|
| **Unified API** | ✅ | ✅ | ✅ | **Production** - Automatic handling |
| **FastAPI** | ✅ | ✅ | ❌ | Legacy/Simple use cases |
| **LargeFiles API** | ❌ | ❌ | ✅ | Large files only |

**Recommendation**: Use the **Unified API** for all new development as it automatically handles all file sizes and upload methods.

## Upload Methods

### 1. Content-Based Upload (Default - Recommended)

**Endpoint**: `POST /api/upload/upload`

**Method**: `client.upload_file()`

**How it works**:
- Client reads file content and sends it via HTTP multipart form
- Server saves content to temporary location (`/tmp`)
- Server creates upload job with temporary file path
- Background processor copies file from `/tmp` to final destination
- Temporary file is cleaned up after processing

**Pros**:
- ✅ Works across all environments (local, Docker, cloud)
- ✅ Secure - no host file system access required
- ✅ Handles network uploads properly
- ✅ Works with any file source (local, remote, cloud)
- ✅ Proper file validation and isolation

**Cons**:
- ❌ Requires copying file to `/tmp` (uses disk space)
- ❌ Slower for very large files due to double I/O

**Best for**:
- Files < 1GB
- Production environments
- Network-based uploads
- Multi-user systems

### 2. Path-Based Upload (Development Only)

**Endpoint**: `POST /api/upload/upload-path`

**Method**: `client.upload_file_by_path()`

**Available in**: Unified API and FastAPI (not available in LargeFiles API)

**Note**: Directory uploads (`client.upload_directory()`) use content-based upload by default for reliability.

**How it works**:
- Client sends file path instead of file content
- Server validates file exists at the specified path
- Server creates upload job with original file path
- Background processor works directly with original file

**Pros**:
- ✅ No `/tmp` copying (saves disk space)
- ✅ Faster for large files
- ✅ Direct file access

**Cons**:
- ❌ Requires file to be accessible from server
- ❌ Security risk (exposes host file system)
- ❌ Doesn't work across different machines
- ❌ Requires specific Docker volume mounts
- ❌ Not suitable for production

**Best for**:
- Local development only
- Single-user environments
- Files already on the server

### 3. Chunked Upload (Large Files)

**Endpoint**: `POST /api/upload/large/initiate`, `POST /api/upload/large/chunk/{upload_id}/{chunk_index}`, `POST /api/upload/large/complete/{upload_id}`

**Method**: `client.upload_large_file()`

**How it works**:
- Client splits large file into chunks
- Chunks are uploaded sequentially
- Server assembles chunks in `/tmp`
- Final file is processed when all chunks are received

**Best for**:
- Files > 1GB
- Unreliable network connections
- Resumable uploads

## File Size Recommendations

| File Size | Recommended Method | Reason |
|-----------|-------------------|---------|
| < 100MB | Content-based upload | Fast, reliable, secure |
| 100MB - 1GB | Content-based upload | Still efficient, works everywhere |
| > 1GB | Chunked upload | Better for large files, resumable |
| Development | Path-based upload | Faster iteration, no copying |

## Implementation Details

### Content-Based Upload Flow

```
Client → HTTP Upload → Server (/tmp) → Background Processor → Final Destination
```

1. Client reads file and sends via HTTP multipart
2. Server saves to temporary location
3. Background job processes file from temp location
4. File copied to final destination
5. Temporary file cleaned up

### Path-Based Upload Flow

```
Client → File Path → Server Validation → Background Processor → Final Destination
```

1. Client sends file path
2. Server validates file exists
3. Background job processes file directly from original location
4. No copying required

### Chunked Upload Flow

```
Client → Chunk 1 → Server (/tmp)
Client → Chunk 2 → Server (/tmp)
Client → Chunk N → Server (/tmp)
Client → Complete → Server Assembly → Background Processor → Final Destination
```

## Configuration

### Docker Volume Mounts (for Path-Based Uploads)

If using path-based uploads in development, add volume mounts to `docker-compose.yml`:

```yaml
volumes:
  - /path/to/your/data:/mnt/data  # Mount data directory
```

### Environment Variables

```bash
# Temporary directory for uploads
TEMP_DIR=/tmp/scientistcloud_uploads

# Maximum file size
MAX_FILE_SIZE=1099511627776  # 1TB

# Chunk size for large files
CHUNK_SIZE=104857600  # 100MB
```

## API Examples

### Content-Based Upload (Recommended)

```python
from SCLib_UploadClient_Unified import ScientistCloudUploadClient

client = ScientistCloudUploadClient('http://localhost:5001')

# Upload file content
result = client.upload_file(
    file_path='/path/to/file.tif',
    user_email='user@example.com',
    dataset_name='My Dataset',
    sensor='TIFF RGB',
    convert=True,
    is_public=False
)
```

### Path-Based Upload (Development Only)

```python
# Upload by file path (requires file to be accessible from server)
result = client.upload_file_by_path(
    file_path='/mnt/data/file.tif',  # Must be accessible from server
    user_email='user@example.com',
    dataset_name='My Dataset',
    sensor='TIFF RGB',
    convert=True,
    is_public=False
)
```

### Chunked Upload (Large Files)

```python
# Upload large file in chunks
result = client.upload_large_file(
    file_path='/path/to/large_file.tif',
    user_email='user@example.com',
    dataset_name='Large Dataset',
    sensor='TIFF RGB',
    convert=True,
    is_public=False
)
```

## Best Practices

### For Production

1. **Use content-based uploads** - most reliable and secure
2. **Monitor `/tmp` disk usage** - ensure adequate space
3. **Implement cleanup** - remove temporary files after processing
4. **Use chunked uploads** for files > 1GB

### For Development

1. **Use path-based uploads** for faster iteration
2. **Mount data directories** in Docker for testing
3. **Test with both methods** to ensure compatibility

### For Large Files

1. **Use chunked uploads** for files > 1GB
2. **Implement progress tracking** for user feedback
3. **Handle network interruptions** gracefully
4. **Consider resumable uploads** for very large files

## Troubleshooting

### Common Issues

**"File not found" error with path-based uploads**:
- Ensure file path is accessible from server
- Check Docker volume mounts
- Verify file permissions

**"Disk space" errors**:
- Monitor `/tmp` directory usage
- Implement automatic cleanup
- Consider using chunked uploads for large files

**"Timeout" errors**:
- Increase timeout settings for large files
- Use chunked uploads for better reliability
- Check network stability

## Future Improvements

1. **Streaming uploads** - process files as they arrive
2. **Direct-to-storage** - bypass `/tmp` for supported storage backends
3. **Compression** - compress files during upload
4. **Parallel uploads** - upload multiple files simultaneously
5. **Cloud integration** - direct upload to cloud storage

## Conclusion

The content-based upload method is the recommended approach for production use due to its reliability, security, and cross-platform compatibility. Path-based uploads are useful for development but should not be used in production environments.

Choose the upload method based on your specific requirements:
- **Content-based**: General purpose, production-ready
- **Path-based**: Development only, local files
- **Chunked**: Large files, unreliable networks
