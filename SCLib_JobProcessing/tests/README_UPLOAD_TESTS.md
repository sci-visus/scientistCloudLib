# Automated Upload Test Suite for ScientistCloud2.0

This directory contains an automated test suite for file upload functionality using the ScientistCloud2.0 SCLib upload system.

## Overview

The test suite validates:
- **Local file uploads**: 4D Nexus, TIFF RGB, IDX files via FastAPI upload endpoint
- **Remote linked uploads**: mod_visus URLs via initiate endpoint
- **Job status tracking**: Monitors upload progress through job status API
- **Completion verification**: Validates final job state

## Architecture

This test suite uses:
- **SCLib_UploadClient_Unified**: Client library for upload operations
- **FastAPI Upload API**: `/api/upload/upload` and `/api/upload/initiate` endpoints
- **Job-based tracking**: Uses job IDs to monitor upload progress
- **Status polling**: `get_upload_status()` and `wait_for_completion()` methods

## Quick Start

### Prerequisites

1. **Upload API Running**: The ScientistCloud upload API should be running
   ```bash
   # Default URL: http://localhost:5000
   # Can be configured via UPLOAD_API_URL environment variable
   ```

2. **Python Dependencies**:
   ```bash
   pip install pytest requests
   ```

3. **Test Files**: Update paths in `test_upload_config.py` to point to your test files

### Running Tests

#### Option 1: Using the Shell Script (Recommended)
```bash
cd scientistCloudLib/SCLib_JobProcessing/tests
./run_upload_tests.sh                    # All tests
./run_upload_tests.sh --local-only       # Only local uploads
./run_upload_tests.sh --remote-only      # Only remote uploads
./run_upload_tests.sh --verbose          # Verbose output
./run_upload_tests.sh --api-url http://localhost:5001  # Custom API URL
```

#### Option 2: Using pytest directly
```bash
cd scientistCloudLib/SCLib_JobProcessing/tests
pytest test_upload_automated.py -v
pytest test_upload_automated.py::TestLocalUploads -v
pytest test_upload_automated.py::TestRemoteUploads -v
```

#### Option 3: Using Python directly
```bash
cd scientistCloudLib/SCLib_JobProcessing/tests
python test_upload_automated.py
```

## Configuration

Edit `test_upload_config.py` to customize:

```python
class TestConfig:
    # Local test files
    NEXUS_4D_FILE = "/path/to/your/4d_nexus_file.nxs"
    TIFF_RGB_FILE = "/path/to/your/tiff_rgb_file.tif"
    IDX_FILE = "/path/to/your/idx_file.zip"
    
    # Remote test links
    REMOTE_IDX_URL = "http://atlantis.sci.utah.edu/mod_visus?dataset=BlueMarble&compression=zip"
    
    # Test settings
    USER_EMAIL = "test@example.com"
    UPLOAD_API_URL = "http://localhost:5000"  # Can be overridden by env var
    MAX_WAIT_TIME = 300  # 5 minutes
    STATUS_CHECK_INTERVAL = 5  # Check every 5 seconds
```

## Test Structure

### Test Classes

1. **TestLocalUploads**: Tests for local file uploads
   - `test_local_upload_4d_nexus()`: Tests 4D Nexus file upload
   - `test_local_upload_tiff_rgb()`: Tests TIFF RGB file upload
   - `test_local_upload_idx()`: Tests IDX file upload

2. **TestRemoteUploads**: Tests for remote linked uploads
   - `test_remote_link_idx()`: Tests remote mod_visus URL upload

### Test Flow

Each test follows this flow:
1. **Setup**: Validates test file exists
2. **Upload**: Uses `ScientistCloudUploadClient.upload_file()` or `initiate_url_upload()`
3. **Job Tracking**: Gets job_id from upload response
4. **Status Monitoring**: Polls job status using `get_upload_status()`
5. **Completion**: Waits for status to reach 'completed'
6. **Verification**: Validates final state (status, progress_percentage, etc.)

## Test Output

Tests provide detailed output showing:
- Test name and file/URL being tested
- Job ID from upload
- Status transitions with progress percentage
- Final results (✅ success or ❌ failure)

Example output:
```
============================================================
Test: 4D Nexus Upload
File: /path/to/file.nxs
============================================================
Uploading file...
✅ Upload initiated successfully!
   Job ID: upload_abc123
   Status: queued
   Upload Type: standard
Waiting for upload and conversion to complete...
  Status: None -> queued (0.0%)
  Status: queued -> uploading (25.5%)
  Status: uploading -> processing (100.0%)
  Status: processing -> completed (100.0%)
✅ 4D Nexus upload completed successfully!
   Dataset: AUTO_TEST_4D_NEXUS_20240101_120000
   Final Status: completed
   Progress: 100.0%
```

## Troubleshooting

### Upload API not accessible
- Verify the upload API is running: `curl http://localhost:5000/health`
- Check `UPLOAD_API_URL` environment variable or config
- Ensure network connectivity

### Test files not found
- Update paths in `test_upload_config.py`
- Tests will automatically skip missing files

### Job status stuck
- Check upload API logs
- Verify background job processor is running
- Check MongoDB connection for job queue
- Increase `MAX_WAIT_TIME` if conversions are slow

### Timeout errors
- Increase `MAX_WAIT_TIME` in `test_upload_config.py`
- Check conversion scripts are working
- Verify system resources (CPU, memory, disk)

## Adding New Tests

To add a new test:

1. **Add test file path** to `test_upload_config.py`:
   ```python
   NEW_FILE_TYPE = "/path/to/test/file"
   ```

2. **Create test method** in appropriate test class:
   ```python
   def test_local_upload_new_type(self, test_helper, upload_client):
       # Validate file exists
       test_helper.validate_file_exists(TestConfig.NEW_FILE_TYPE)
       
       # Create dataset name
       dataset_name = f"{TestConfig.TEST_DATASET_PREFIX}NEW_TYPE_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
       
       try:
           # Upload file
           result = upload_client.upload_file(
               file_path=TestConfig.NEW_FILE_TYPE,
               user_email=TestConfig.USER_EMAIL,
               dataset_name=dataset_name,
               sensor="NEW_SENSOR",
               convert=True,
               is_public=False
           )
           
           # Wait for completion
           status = test_helper.verify_job_completion(result.job_id)
           
           print(f"✅ Upload completed successfully!")
       except Exception as e:
           print(f"❌ Test failed: {e}")
           raise
   ```

## Integration with CI/CD

The test suite can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Upload Tests
  env:
    UPLOAD_API_URL: http://localhost:5000
  run: |
    cd scientistCloudLib/SCLib_JobProcessing/tests
    ./run_upload_tests.sh --verbose
```

## Best Practices

1. **Use test database**: Tests create datasets with `AUTO_TEST_` prefix
2. **Monitor job status**: Tests automatically wait for completion
3. **Check logs**: Review upload API logs if tests fail
4. **Test isolation**: Each test uses unique dataset names with timestamps
5. **Realistic files**: Use actual test files, not mock data

## Related Files

- `test_upload_automated.py`: Main test suite
- `test_upload_config.py`: Configuration file
- `run_upload_tests.sh`: Test runner script
- `SCLib_UploadClient_Unified.py`: Upload client library
- `SCLib_UploadAPI_Unified.py`: Upload API endpoints

## Differences from VisusDataPortalPrivate Tests

This test suite differs from the VisusDataPortalPrivate version:

1. **Uses FastAPI endpoints** instead of direct MongoDB/background service
2. **Job-based tracking** via job IDs instead of UUID status polling
3. **Client library** (`ScientistCloudUploadClient`) instead of direct database operations
4. **Status API** (`/api/upload/status/{job_id}`) instead of MongoDB queries
5. **No direct file copying** - files are uploaded via HTTP

## Support

For issues or questions:
1. Check upload API logs
2. Verify job status via API: `GET /api/upload/status/{job_id}`
3. Check MongoDB job queue if jobs are stuck
4. Review `SCLib_UploadProcessor` logs

