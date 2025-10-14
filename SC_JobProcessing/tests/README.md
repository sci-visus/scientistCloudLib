# SC_JobProcessing Test Suite

This directory contains comprehensive test cases for the SC_JobProcessing system, covering all components and their interactions.

## Test Structure

### Unit Tests

- **`test_SC_JobQueueManager.py`** - Tests job queue management functionality
- **`test_SC_BackgroundService.py`** - Tests background service job processing
- **`test_SC_JobTypes.py`** - Tests job type definitions and status transitions
- **`test_SC_JobMonitor.py`** - Tests monitoring and administrative functions
- **`test_SC_JobMigration.py`** - Tests migration utilities and rollback operations
- **`test_SC_UploadJobTypes.py`** - Tests upload job type definitions, sensor types, and configurations
- **`test_SC_UploadProcessor.py`** - Tests upload job processing functionality
- **`test_SC_UploadAPI.py`** - Tests RESTful API endpoints for upload operations

### Integration Tests

- **`test_integration.py`** - Tests end-to-end workflows and component interactions

### Test Runner

- **`run_tests.py`** - Comprehensive test runner with detailed reporting

## Running Tests

### Run All Tests

```bash
# From the SC_JobProcessing directory
python tests/run_tests.py

# Or from the tests directory
python run_tests.py
```

### Run Specific Test Suites

```bash
# Run only job types tests
python run_tests.py types

# Run only job queue tests
python run_tests.py queue

# Run only background service tests
python run_tests.py service

# Run only monitor tests
python run_tests.py monitor

# Run only migration tests
python run_tests.py migration

# Run only upload tests
python run_tests.py upload_types upload_processor upload_api

# Run only integration tests
python run_tests.py integration

# Run multiple suites
python run_tests.py types queue service upload_types
```

### Run Individual Test Files

```bash
# Run specific test file
python -m unittest tests.test_SC_JobQueueManager

# Run specific test class
python -m unittest tests.test_SC_JobQueueManager.TestSC_JobQueueManager

# Run specific test method
python -m unittest tests.test_SC_JobQueueManager.TestSC_JobQueueManager.test_create_job_success
```

## Test Coverage

### SC_JobQueueManager Tests

- ✅ Job creation and validation
- ✅ Job retrieval and status updates
- ✅ Retry logic and error handling
- ✅ Queue statistics and monitoring
- ✅ Database operations and error handling
- ✅ Index creation and management

### SC_BackgroundService Tests

- ✅ Service initialization and configuration
- ✅ Job processing workflows
- ✅ Job type handlers (Google sync, conversion, upload, etc.)
- ✅ Error handling and recovery
- ✅ Process management and cleanup
- ✅ Stale job detection and restart

### SC_JobTypes Tests

- ✅ Job type enum definitions
- ✅ Dataset status enum definitions
- ✅ Job type configurations
- ✅ Status transition logic
- ✅ Legacy status compatibility
- ✅ Helper function validation

### SC_JobMonitor Tests

- ✅ Queue overview and statistics
- ✅ Job details and monitoring
- ✅ Worker management
- ✅ Failed job handling
- ✅ Performance reporting
- ✅ Health status monitoring
- ✅ Cleanup operations

### SC_JobMigration Tests

- ✅ Dataset migration workflows
- ✅ Job creation for different statuses
- ✅ Migration validation
- ✅ Rollback operations
- ✅ Error handling and recovery
- ✅ File system operations

### SC_UploadJobTypes Tests

- ✅ Upload source type enum definitions
- ✅ Upload status enum definitions
- ✅ Sensor type enum definitions
- ✅ Upload job configuration creation
- ✅ Upload progress tracking
- ✅ Upload job manager functionality
- ✅ Tool configuration for different sources
- ✅ Upload job creation helper functions

### SC_UploadProcessor Tests

- ✅ Processor initialization and configuration
- ✅ Job submission and management
- ✅ Local file upload processing
- ✅ Google Drive upload processing
- ✅ S3 upload processing
- ✅ URL download processing
- ✅ Tool availability checking
- ✅ Progress tracking and status updates
- ✅ Error handling and recovery
- ✅ Database operations

### SC_UploadAPI Tests

- ✅ Health check endpoint
- ✅ Supported sources endpoint
- ✅ Upload initiation for all source types
- ✅ Local file upload endpoint
- ✅ Job status monitoring
- ✅ Job cancellation
- ✅ Job listing
- ✅ Upload time estimation
- ✅ Error handling and validation
- ✅ Parameter validation

### Integration Tests

- ✅ End-to-end job processing
- ✅ Component interactions
- ✅ Error handling and recovery
- ✅ Performance monitoring
- ✅ Health monitoring
- ✅ Worker management
- ✅ Job cancellation workflows

## Test Data and Mocking

### Mock Objects

All tests use comprehensive mocking to isolate components:

- **MongoDB Client** - Mocked for database operations
- **File System** - Mocked for file operations
- **Subprocess** - Mocked for external command execution
- **Time/Date** - Mocked for consistent testing

### Test Fixtures

- **Temporary Directories** - Created and cleaned up automatically
- **Mock Datasets** - Realistic test data for all scenarios
- **Mock Jobs** - Various job states and configurations
- **Error Scenarios** - Database errors, file system errors, etc.

## Test Scenarios

### Success Scenarios

- Job creation and processing
- Status transitions
- Worker management
- Monitoring and statistics
- Migration operations

### Error Scenarios

- Database connection failures
- File system errors
- Process failures
- Network timeouts
- Invalid configurations

### Edge Cases

- Empty job queues
- Missing files
- Invalid status transitions
- Stale processes
- Resource exhaustion

## Performance Testing

### Load Testing

- Multiple concurrent jobs
- Large job queues
- High failure rates
- Resource monitoring

### Stress Testing

- Database connection limits
- File system limits
- Memory usage
- CPU utilization

## Continuous Integration

### GitHub Actions

```yaml
name: SC_JobProcessing Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python tests/run_tests.py
```

### Local Development

```bash
# Install test dependencies
pip install -r requirements.txt

# Run tests before committing
python tests/run_tests.py

# Run specific tests during development
python run_tests.py types queue
```

## Test Results

### Expected Output

```
SC_JobProcessing System Test Suite
============================================================

============================================================
Running SC_JobTypes Tests
============================================================
test_job_type_enum_values ... ok
test_job_status_enum_values ... ok
test_dataset_status_enum_values ... ok
...

SC_JobTypes Tests Summary:
  Tests run: 25
  Failures: 0
  Errors: 0
  Skipped: 0
  Time: 0.15 seconds

============================================================
OVERALL TEST SUMMARY
============================================================
Total Tests: 150
Total Failures: 0
Total Errors: 0
Success Rate: 100.0%

🎉 All tests passed!
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure you're in the correct directory
   cd /path/to/SC_JobProcessing
   python tests/run_tests.py
   ```

2. **Missing Dependencies**
   ```bash
   # Install required packages
   pip install -r requirements.txt
   ```

3. **Mock Issues**
   ```bash
   # Check mock configurations
   # Ensure all external dependencies are properly mocked
   ```

### Debug Mode

```bash
# Run tests with verbose output
python -m unittest tests.test_SC_JobQueueManager -v

# Run specific test with debug output
python -c "
import unittest
from tests.test_SC_JobQueueManager import TestSC_JobQueueManager
suite = unittest.TestLoader().loadTestsFromTestCase(TestSC_JobQueueManager)
runner = unittest.TextTestRunner(verbosity=2)
runner.run(suite)
"
```

## Contributing

### Adding New Tests

1. **Follow naming conventions**
   - Test files: `test_<module_name>.py`
   - Test classes: `Test<ClassName>`
   - Test methods: `test_<functionality>_<scenario>`

2. **Use descriptive test names**
   ```python
   def test_create_job_success(self):
       """Test successful job creation."""
   
   def test_create_job_database_error(self):
       """Test job creation with database error."""
   ```

3. **Include comprehensive assertions**
   ```python
   # Verify all important aspects
   self.assertEqual(result['status'], 'success')
   self.assertIn('job_id', result)
   self.assertIsNotNone(result['created_at'])
   ```

4. **Mock external dependencies**
   ```python
   with patch('module.external_function') as mock_func:
       mock_func.return_value = expected_value
       # Test code here
   ```

5. **Clean up resources**
   ```python
   def tearDown(self):
       """Clean up test fixtures."""
       # Remove temporary files, reset mocks, etc.
   ```

### Test Coverage

- Aim for 100% code coverage
- Test all error paths
- Include edge cases
- Test integration scenarios
- Verify performance characteristics

### Documentation

- Document test purpose and scenarios
- Include setup and teardown instructions
- Explain mock configurations
- Provide troubleshooting guidance
